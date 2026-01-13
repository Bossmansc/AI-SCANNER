"""
Authentication Security Fixes Module

This module addresses critical security vulnerabilities in the authentication system:
1. Timing attacks on password verification
2. Weak session management
3. Insufficient rate limiting
4. JWT security issues
5. Password policy enforcement

All fixes are production-ready and designed for high-concurrency environments.
"""

import os
import time
import secrets
import hashlib
import hmac
import base64
import json
from typing import Optional, Tuple, Dict, Any, Callable
from datetime import datetime, timedelta
from functools import wraps
import asyncio
from contextlib import asynccontextmanager

# Third-party imports
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import constant_time
import redis.asyncio as redis
from pydantic import BaseModel, Field, validator
import bcrypt

# Local imports
from ..config import settings
from ..logging import security_logger
from ..exceptions import SecurityException, AuthenticationException

# Constants
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 900  # 15 minutes in seconds
TOKEN_REFRESH_THRESHOLD = 300  # 5 minutes before expiry
PASSWORD_MIN_LENGTH = 12
SESSION_TIMEOUT = 3600  # 1 hour
CSRF_TOKEN_BYTES = 32
REFRESH_TOKEN_BYTES = 64


class SecurityConfig(BaseModel):
    """Security configuration model"""
    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 30
    refresh_token_expiry_days: int = 7
    bcrypt_rounds: int = 12
    rate_limit_per_minute: int = 60
    require_2fa: bool = False
    session_encryption_key: Optional[str] = None
    cors_origins: list = []
    secure_cookies: bool = True
    http_only_cookies: bool = True
    same_site_cookies: str = "Lax"
    
    @validator("jwt_secret")
    def validate_jwt_secret(cls, v):
        if len(v) < 32:
            raise ValueError("JWT secret must be at least 32 characters")
        return v
    
    @validator("session_encryption_key")
    def validate_encryption_key(cls, v):
        if v and len(v) < 32:
            raise ValueError("Encryption key must be at least 32 characters")
        return v


class PasswordPolicy(BaseModel):
    """Password policy configuration"""
    min_length: int = PASSWORD_MIN_LENGTH
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True
    require_special: bool = True
    max_age_days: int = 90
    prevent_reuse: int = 5  # Number of previous passwords to remember
    block_common_passwords: bool = True
    
    def validate_password(self, password: str) -> Tuple[bool, Optional[str]]:
        """Validate password against policy"""
        if len(password) < self.min_length:
            return False, f"Password must be at least {self.min_length} characters"
        
        if self.require_uppercase and not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if self.require_lowercase and not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if self.require_digits and not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"
        
        if self.require_special and not any(not c.isalnum() for c in password):
            return False, "Password must contain at least one special character"
        
        if self.block_common_passwords and self._is_common_password(password):
            return False, "Password is too common. Please choose a stronger password."
        
        return True, None
    
    def _is_common_password(self, password: str) -> bool:
        """Check if password is in common passwords list"""
        common_passwords = {
            "password", "123456", "qwerty", "admin", "welcome",
            "password123", "12345678", "123456789", "1234567890"
        }
        return password.lower() in common_passwords


class TimingAttackSafeComparator:
    """Constant-time comparison to prevent timing attacks"""
    
    @staticmethod
    def compare_strings(a: str, b: str) -> bool:
        """Constant-time string comparison"""
        return constant_time.bytes_eq(a.encode(), b.encode())
    
    @staticmethod
    def compare_bytes(a: bytes, b: bytes) -> bool:
        """Constant-time byte comparison"""
        return constant_time.bytes_eq(a, b)
    
    @staticmethod
    def compare_hmac(a: str, b: str, key: bytes) -> bool:
        """Constant-time HMAC comparison"""
        hmac_a = hmac.new(key, a.encode(), hashlib.sha256).digest()
        hmac_b = hmac.new(key, b.encode(), hashlib.sha256).digest()
        return constant_time.bytes_eq(hmac_a, hmac_b)


class RateLimiter:
    """Distributed rate limiter using Redis"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def check_rate_limit(self, key: str, limit: int, window: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit
        
        Args:
            key: Rate limit key (e.g., "login:user@example.com")
            limit: Maximum requests per window
            window: Time window in seconds
        
        Returns:
            Tuple of (allowed, details)
        """
        current = int(time.time())
        window_start = current - window
        
        # Use Redis pipeline for atomic operations
        async with self.redis.pipeline() as pipe:
            try:
                # Remove old entries
                await pipe.zremrangebyscore(key, 0, window_start)
                
                # Count current requests
                await pipe.zcard(key)
                
                # Add current request
                await pipe.zadd(key, {str(current): current})
                
                # Set expiry
                await pipe.expire(key, window)
                
                results = await pipe.execute()
                count = results[1]
                
                if count >= limit:
                    # Calculate retry after
                    oldest = await self.redis.zrange(key, 0, 0, withscores=True)
                    if oldest:
                        retry_after = int(oldest[0][1]) + window - current
                    else:
                        retry_after = window
                    
                    return False, {
                        "limit": limit,
                        "remaining": 0,
                        "reset": current + retry_after,
                        "retry_after": retry_after
                    }
                
                return True, {
                    "limit": limit,
                    "remaining": limit - count - 1,
                    "reset": current + window,
                    "retry_after": 0
                }
                
            except Exception as e:
                security_logger.error(f"Rate limit check failed: {e}")
                # Fail open in case of Redis failure
                return True, {"error": str(e)}


class SessionManager:
    """Secure session management with encryption"""
    
    def __init__(self, redis_client: redis.Redis, encryption_key: Optional[str] = None):
        self.redis = redis_client
        self.fernet = None
        
        if encryption_key:
            # Ensure key is 32 bytes URL-safe base64 encoded
            if len(encryption_key) < 32:
                raise ValueError("Encryption key must be at least 32 characters")
            
            # Pad or truncate to 32 bytes and encode
            key_bytes = encryption_key.encode()[:32]
            if len(key_bytes) < 32:
                key_bytes = key_bytes.ljust(32, b'\0')
            
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            self.fernet = Fernet(fernet_key)
    
    async def create_session(self, user_id: str, user_data: Dict[str, Any], 
                           ttl: int = SESSION_TIMEOUT) -> str:
        """Create a new encrypted session"""
        session_id = secrets.token_urlsafe(32)
        session_data = {
            "user_id": user_id,
            "created_at": time.time(),
            "data": user_data,
            "csrf_token": secrets.token_urlsafe(CSRF_TOKEN_BYTES)
        }
        
        # Encrypt session data if Fernet is available
        if self.fernet:
            session_json = json.dumps(session_data).encode()
            encrypted_data = self.fernet.encrypt(session_json)
            stored_data = base64.b64encode(encrypted_data).decode()
        else:
            stored_data = json.dumps(session_data)
        
        # Store in Redis with TTL
        await self.redis.setex(
            f"session:{session_id}",
            ttl,
            stored_data
        )
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve and decrypt session data"""
        stored_data = await self.redis.get(f"session:{session_id}")
        
        if not stored_data:
            return None
        
        try:
            if self.fernet:
                encrypted_data = base64.b64decode(stored_data)
                decrypted_json = self.fernet.decrypt(encrypted_data)
                session_data = json.loads(decrypted_json.decode())
            else:
                session_data = json.loads(stored_data)
            
            # Verify session hasn't expired
            if time.time() - session_data["created_at"] > SESSION_TIMEOUT:
                await self.delete_session(session_id)
                return None
            
            # Refresh TTL on access
            await self.redis.expire(f"session:{session_id}", SESSION_TIMEOUT)
            
            return session_data
            
        except Exception as e:
            security_logger.error(f"Session decryption failed: {e}")
            await self.delete_session(session_id)
            return None
    
    async def delete_session(self, session_id: str):
        """Delete session from storage"""
        await self.redis.delete(f"session:{session_id}")
    
    async def validate_csrf(self, session_id: str, csrf_token: str) -> bool:
        """Validate CSRF token"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        return TimingAttackSafeComparator.compare_strings(
            session.get("csrf_token", ""),
            csrf_token
        )


class JWTHandler:
    """Secure JWT token handling"""
    
    def __init__(self, secret: str, algorithm: str = "HS256", expiry_minutes: int = 30):
        if len(secret) < 32:
            raise ValueError("JWT secret must be at least 32 characters")
        
        self.secret = secret
        self.algorithm = algorithm
        self.expiry_minutes = expiry_minutes
    
    def create_access_token(self, user_id: str, payload: Optional[Dict[str, Any]] = None) -> str:
        """Create a signed JWT access token"""
        now = datetime.utcnow()
        expiry = now + timedelta(minutes=self.expiry_minutes)
        
        token_payload = {
            "sub": user_id,
            "iat": now,
            "exp": expiry,
            "jti": secrets.token_urlsafe(16),  # Unique token ID
            "type": "access"
        }
        
        if payload:
            token_payload.update(payload)
        
        return jwt.encode(token_payload, self.secret, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create a secure refresh token"""
        token_id = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expiry = now + timedelta(days=settings.SECURITY.refresh_token_expiry_days)
        
        token_payload = {
            "sub": user_id,
            "iat": now,
            "exp": expiry,
            "jti": token_id,
            "type": "refresh"
        }
        
        return jwt.encode(token_payload, self.secret, algorithm=self.algorithm)
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"require": ["exp", "iat", "sub"]}
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                security_logger.warning(f"Invalid token type: {payload.get('type')}")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            security_logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            security_logger.warning(f"Invalid JWT token: {e}")
            return None
    
    def should_refresh(self, token: str) -> bool:
        """Check if token should be refreshed"""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm], 
                               options={"verify_exp": False})
            
            exp_timestamp = payload.get("exp")
            if not exp_timestamp:
                return True
            
            expiry_time = datetime.fromtimestamp(exp_timestamp)
            time_until_expiry = expiry_time - datetime.utcnow()
            
            return time_until_expiry.total_seconds() < TOKEN_REFRESH_THRESHOLD
            
        except jwt.InvalidTokenError:
            return True


class PasswordManager:
    """Secure password handling with bcrypt"""
    
    def __init__(self, rounds: int = 12):
        self.rounds = rounds
        self.comparator = TimingAttackSafeComparator()
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt with timing attack protection"""
        if not password or len(password) < PASSWORD_MIN_LENGTH:
            raise ValueError("Password is too short")
        
        # Add a random delay to prevent timing attacks
        time.sleep(secrets.randbelow(10) / 1000)  # 0-10ms random delay
        
        # Hash with bcrypt
        salt = bcrypt.gensalt(rounds=self.rounds)
        hashed = bcrypt.hashpw(password.encode(), salt)
        
        return hashed.decode()
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password with constant-time comparison"""
        try:
            # Add a random delay to prevent timing attacks
            time.sleep(secrets.randbelow(10) / 1000)  # 0-10ms random delay
            
            # Use bcrypt's constant-time comparison
            return bcrypt.checkpw(password.encode(), hashed_password.encode())
            
        except (ValueError, TypeError):
            # Still perform comparison to prevent timing leaks
            self.comparator.compare_strings("dummy", "dummy")
            return False
    
    def generate_secure_password(self) -> str:
        """Generate a cryptographically secure password"""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(16))
        
        # Ensure password meets policy
        policy = PasswordPolicy()
        valid, _ = policy.validate_password(password)
        
        if not valid:
            # Fallback: generate with all requirements
            uppercase = secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            lowercase = secrets.choice("abcdefghijklmnopqrstuvwxyz")
            digit = secrets.choice("0123456789")
            special = secrets.choice("!@#$%^&*")
            remaining = ''.join(secrets.choice(alphabet) for _ in range(12))
            
            # Shuffle the characters
            all_chars = list(uppercase + lowercase + digit + special + remaining)
            secrets.SystemRandom().shuffle(all_chars)
            password = ''.join(all_chars)
        
        return password


class LoginSecurity:
    """Enhanced login security with rate limiting and lockout"""
    
    def __init__(self, redis_client: redis.Redis, password_manager: PasswordManager):
        self.redis = redis_client
        self.password_manager = password_manager
        self.rate_limiter = RateLimiter(redis_client)
    
    async def check_login_attempts(self, username: str) -> Tuple[bool, Optional[int]]:
        """
        Check if user is locked out due to too many failed attempts
        
        Returns:
            Tuple of (allowed, remaining_lockout_seconds)
        """
        lockout_key = f"lockout:{username}"
        attempts_key = f"attempts:{username}"
        
        # Check if locked out
        lockout_until = await self.redis.get(lockout_key)
        if lockout_until:
            lockout_time = float(lockout_until)
            remaining = int(lockout_time - time.time())
            
            if remaining > 0:
                return False, remaining
        
        # Get current attempt count
        attempts = await self.redis.get(attempts_key)
        attempt_count = int(attempts) if attempts else 0
        
        return True, None
    
    async def record_failed_attempt(self, username: str):
        """Record a failed login attempt"""
        attempts_key = f"attempts:{username}"
        lockout_key = f"lockout:{username}"
        
        # Increment attempt count
        attempts = await self.redis.incr(attempts_key)
        
        # Set expiry on attempts key
        await self.redis.expire(attempts_key, LOCKOUT_DURATION * 2)
        
        # Check if lockout should be triggered
        if attempts >= MAX_LOGIN_ATTEMPTS:
            lockout_until = time.time() + LOCKOUT_DURATION
            await self.redis.setex(lockout_key, LOCKOUT_DURATION, lockout_until)
            
            security_logger.warning(f"Account locked out: {username}")
            
            # Reset attempt count
            await self.redis.delete(attempts_key)
    
    async def record_successful_login