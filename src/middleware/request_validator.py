"""
Request Validation and Input Sanitization Middleware
Core security layer for all incoming HTTP requests.
Implements strict schema validation, type coercion, and malicious input filtering.
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, TypeVar, Type
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from email.utils import parseaddr
import ipaddress
import uuid
from functools import wraps

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError, Field, validator, create_model
from pydantic.error_wrappers import ErrorWrapper
import sqlparse
from html import escape

# Type variables for generic validation
T = TypeVar('T')
ValidationResult = Tuple[bool, Optional[Dict[str, Any]], Optional[str]]

# Configure logging
logger = logging.getLogger(__name__)

class ValidationConfig:
    """Configuration for validation behavior"""
    
    # Strictness levels
    STRICT = "strict"      # Reject any invalid data
    LENIENT = "lenient"    # Attempt to coerce types
    PERMISSIVE = "permissive"  # Only filter dangerous content
    
    # Sanitization modes
    SANITIZE_HTML = "html"          # Escape HTML entities
    SANITIZE_SQL = "sql"            # Detect SQL injection patterns
    SANITIZE_PATH = "path"          # Prevent path traversal
    SANITIZE_XSS = "xss"            # Cross-site scripting prevention
    SANITIZE_ALL = "all"            # Apply all sanitizations
    
    def __init__(
        self,
        strictness: str = STRICT,
        sanitize: List[str] = None,
        max_field_length: int = 10000,
        max_array_size: int = 1000,
        max_nesting_depth: int = 10,
        allow_unknown_fields: bool = False,
        coerce_types: bool = True,
        log_violations: bool = True,
        raise_on_violation: bool = True
    ):
        self.strictness = strictness
        self.sanitize = sanitize or [self.SANITIZE_ALL]
        self.max_field_length = max_field_length
        self.max_array_size = max_array_size
        self.max_nesting_depth = max_nesting_depth
        self.allow_unknown_fields = allow_unknown_fields
        self.coerce_types = coerce_types
        self.log_violations = log_violations
        self.raise_on_violation = raise_on_violation
        
        # Validate configuration
        if strictness not in [self.STRICT, self.LENIENT, self.PERMISSIVE]:
            raise ValueError(f"Invalid strictness: {strictness}")
        
        valid_sanitizations = [self.SANITIZE_HTML, self.SANITIZE_SQL, 
                              self.SANITIZE_PATH, self.SANITIZE_XSS, self.SANITIZE_ALL]
        for s in self.sanitize:
            if s not in valid_sanitizations:
                raise ValueError(f"Invalid sanitization: {s}")


class FieldValidator:
    """Validates individual fields based on type and constraints"""
    
    # Common regex patterns
    PATTERNS = {
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone': r'^\+?[1-9]\d{1,14}$',  # E.164 format
        'username': r'^[a-zA-Z0-9_]{3,30}$',
        'password': r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        'ipv4': r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$',
        'ipv6': r'^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$',
        'url': r'^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)$',
        'date_iso': r'^\d{4}-\d{2}-\d{2}$',
        'datetime_iso': r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$',
        'credit_card': r'^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})$',
        'ssn': r'^\d{3}-\d{2}-\d{4}$',
        'zip_code': r'^\d{5}(?:-\d{4})?$',
    }
    
    @staticmethod
    def validate_string(
        value: Any,
        min_length: int = 0,
        max_length: int = None,
        pattern: str = None,
        allowed_values: List[str] = None,
        config: ValidationConfig = None
    ) -> ValidationResult:
        """Validate string field"""
        config = config or ValidationConfig()
        
        # Type checking
        if not isinstance(value, str):
            if config.coerce_types and config.strictness != ValidationConfig.STRICT:
                try:
                    value = str(value)
                except (ValueError, TypeError):
                    return False, None, f"Could not coerce to string: {type(value)}"
            else:
                return False, None, f"Expected string, got {type(value)}"
        
        # Length validation
        if len(value) < min_length:
            return False, None, f"String too short: {len(value)} < {min_length}"
        
        if max_length and len(value) > max_length:
            if config.strictness == ValidationConfig.STRICT:
                return False, None, f"String too long: {len(value)} > {max_length}"
            else:
                value = value[:max_length]
        
        # Pattern matching
        if pattern:
            if pattern in FieldValidator.PATTERNS:
                regex = FieldValidator.PATTERNS[pattern]
            else:
                regex = pattern
            
            if not re.match(regex, value):
                return False, None, f"String does not match pattern: {pattern}"
        
        # Allowed values
        if allowed_values and value not in allowed_values:
            return False, None, f"Value not in allowed list: {allowed_values}"
        
        return True, value, None
    
    @staticmethod
    def validate_number(
        value: Any,
        min_value: Union[int, float] = None,
        max_value: Union[int, float] = None,
        is_int: bool = False,
        config: ValidationConfig = None
    ) -> ValidationResult:
        """Validate numeric field"""
        config = config or ValidationConfig()
        
        # Type checking and coercion
        if not isinstance(value, (int, float, Decimal)):
            if config.coerce_types and config.strictness != ValidationConfig.STRICT:
                try:
                    if is_int:
                        value = int(value)
                    else:
                        value = float(value)
                except (ValueError, TypeError):
                    return False, None, f"Could not coerce to number: {type(value)}"
            else:
                return False, None, f"Expected number, got {type(value)}"
        
        # Integer validation
        if is_int and not isinstance(value, int):
            if config.coerce_types and config.strictness != ValidationConfig.STRICT:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return False, None, f"Could not coerce to integer: {value}"
            else:
                return False, None, f"Expected integer, got {type(value)}"
        
        # Range validation
        if min_value is not None and value < min_value:
            if config.strictness == ValidationConfig.STRICT:
                return False, None, f"Value too small: {value} < {min_value}"
            else:
                value = min_value
        
        if max_value is not None and value > max_value:
            if config.strictness == ValidationConfig.STRICT:
                return False, None, f"Value too large: {value} > {max_value}"
            else:
                value = max_value
        
        return True, value, None
    
    @staticmethod
    def validate_boolean(value: Any, config: ValidationConfig = None) -> ValidationResult:
        """Validate boolean field"""
        config = config or ValidationConfig()
        
        if isinstance(value, bool):
            return True, value, None
        
        if config.coerce_types and config.strictness != ValidationConfig.STRICT:
            # Try to coerce common truthy/falsy values
            if isinstance(value, str):
                value_lower = value.lower()
                if value_lower in ('true', 't', 'yes', 'y', '1', 'on'):
                    return True, True, None
                elif value_lower in ('false', 'f', 'no', 'n', '0', 'off', ''):
                    return True, False, None
            
            # Try numeric coercion
            try:
                num = float(value)
                return True, bool(num), None
            except (ValueError, TypeError):
                pass
        
        return False, None, f"Expected boolean, got {type(value)}"
    
    @staticmethod
    def validate_datetime(value: Any, config: ValidationConfig = None) -> ValidationResult:
        """Validate datetime field"""
        config = config or ValidationConfig()
        
        if isinstance(value, datetime):
            return True, value, None
        
        if isinstance(value, date):
            return True, datetime.combine(value, datetime.min.time()), None
        
        if config.coerce_types and config.strictness != ValidationConfig.STRICT:
            if isinstance(value, str):
                try:
                    # Try ISO format
                    if 'T' in value:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(value, '%Y-%m-%d')
                    return True, dt, None
                except (ValueError, TypeError):
                    pass
            
            # Try timestamp
            try:
                dt = datetime.fromtimestamp(float(value))
                return True, dt, None
            except (ValueError, TypeError):
                pass
        
        return False, None, f"Could not parse datetime from {type(value)}"
    
    @staticmethod
    def validate_array(
        value: Any,
        item_type: Type[T] = None,
        min_items: int = 0,
        max_items: int = None,
        unique: bool = False,
        config: ValidationConfig = None
    ) -> ValidationResult:
        """Validate array field"""
        config = config or ValidationConfig()
        
        if not isinstance(value, list):
            if config.coerce_types and config.strictness != ValidationConfig.STRICT:
                try:
                    value = list(value)
                except (ValueError, TypeError):
                    return False, None, f"Could not coerce to list: {type(value)}"
            else:
                return False, None, f"Expected list, got {type(value)}"
        
        # Size validation
        if len(value) < min_items:
            return False, None, f"Array too small: {len(value)} < {min_items}"
        
        if max_items and len(value) > max_items:
            if config.strictness == ValidationConfig.STRICT:
                return False, None, f"Array too large: {len(value)} > {max_items}"
            else:
                value = value[:max_items]
        
        # Item type validation
        if item_type:
            validated_items = []
            for i, item in enumerate(value):
                if item_type == str:
                    valid, validated_item, error = FieldValidator.validate_string(item, config=config)
                elif item_type == int:
                    valid, validated_item, error = FieldValidator.validate_number(item, is_int=True, config=config)
                elif item_type == float:
                    valid, validated_item, error = FieldValidator.validate_number(item, config=config)
                elif item_type == bool:
                    valid, validated_item, error = FieldValidator.validate_boolean(item, config=config)
                elif item_type == datetime:
                    valid, validated_item, error = FieldValidator.validate_datetime(item, config=config)
                else:
                    # For custom types, assume they implement validation
                    if isinstance(item, item_type):
                        validated_item = item
                        valid = True
                    else:
                        valid = False
                        error = f"Item {i} is not of type {item_type.__name__}"
                
                if not valid:
                    return False, None, f"Array item {i} invalid: {error}"
                
                validated_items.append(validated_item)
            
            value = validated_items
        
        # Uniqueness validation
        if unique and len(value) != len(set(value)):
            if config.strictness == ValidationConfig.STRICT:
                return False, None, "Array contains duplicate values"
            else:
                value = list(dict.fromkeys(value))  # Preserve order
        
        return True, value, None
    
    @staticmethod
    def validate_object(
        value: Any,
        schema: Dict[str, Any] = None,
        config: ValidationConfig = None
    ) -> ValidationResult:
        """Validate object/dict field"""
        config = config or ValidationConfig()
        
        if not isinstance(value, dict):
            if config.coerce_types and config.strictness != ValidationConfig.STRICT:
                try:
                    value = dict(value)
                except (ValueError, TypeError):
                    return False, None, f"Could not coerce to dict: {type(value)}"
            else:
                return False, None, f"Expected dict, got {type(value)}"
        
        if not schema:
            return True, value, None
        
        # Validate against schema
        validated_dict = {}
        errors = []
        
        for field_name, field_schema in schema.items():
            if field_name in value:
                field_value = value[field_name]
                
                # Recursive validation
                if isinstance(field_schema, dict):
                    valid, validated_field, error = FieldValidator.validate_object(
                        field_value, field_schema, config
                    )
                elif isinstance(field_schema, list):
                    item_type = field_schema[0] if field_schema else Any
                    valid, validated_field, error = FieldValidator.validate_array(
                        field_value, item_type=item_type, config=config
                    )
                else:
                    # Type-based validation
                    if field_schema == str:
                        valid, validated_field, error = FieldValidator.validate_string(
                            field_value, config=config
                        )
                    elif field_schema == int:
                        valid, validated_field, error = FieldValidator.validate_number(
                            field_value, is_int=True, config=config
                        )
                    elif field_schema == float:
                        valid, validated_field, error = FieldValidator.validate_number(
                            field_value, config=config
                        )
                    elif field_schema == bool:
                        valid, validated_field, error = FieldValidator.validate_boolean(
                            field_value, config=config
                        )
                    elif field_schema == datetime:
                        valid, validated_field, error = FieldValidator.validate