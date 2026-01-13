"""
Dependency Checker Utility
==========================

A comprehensive runtime dependency validation system that checks package
availability, versions, and compatibility. Provides detailed diagnostics
and graceful fallback mechanisms for missing or incompatible dependencies.

Features:
- Version constraint parsing and validation
- Optional dependency support with fallback detection
- Environment-specific requirement checking
- Detailed diagnostic reporting
- Import-time and runtime validation modes
- Dependency graph analysis
"""

import importlib
import importlib.metadata
import importlib.util
import sys
import warnings
import re
import json
import pkgutil
from typing import (
    Any, Dict, List, Optional, Tuple, Union, Set, Callable,
    NamedTuple, TypeVar, Generic, Type, cast
)
from enum import Enum, auto
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
from contextlib import contextmanager
from functools import lru_cache

# Type variables
T = TypeVar('T')
VersionType = Union[str, Tuple[int, ...]]


class DependencyStatus(Enum):
    """Status of a dependency check."""
    AVAILABLE = auto()
    MISSING = auto()
    VERSION_MISMATCH = auto()
    INCOMPATIBLE = auto()
    OPTIONAL_MISSING = auto()
    OPTIONAL_AVAILABLE = auto()


class DependencySeverity(Enum):
    """Severity level for dependency issues."""
    CRITICAL = auto()   # Required dependency missing - will crash
    ERROR = auto()      # Required version mismatch - may crash
    WARNING = auto()    # Optional dependency missing - reduced functionality
    INFO = auto()       # Informational - compatibility notes
    DEBUG = auto()      # Debug information


@dataclass
class DependencyResult:
    """Result of a dependency check."""
    name: str
    status: DependencyStatus
    severity: DependencySeverity
    required_version: Optional[str] = None
    installed_version: Optional[str] = None
    message: str = ""
    extra_info: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_ok(self) -> bool:
        """Check if dependency is acceptable."""
        return self.status in (
            DependencyStatus.AVAILABLE,
            DependencyStatus.OPTIONAL_AVAILABLE,
            DependencyStatus.OPTIONAL_MISSING  # Optional missing is OK
        )
    
    @property
    def is_critical(self) -> bool:
        """Check if dependency issue is critical."""
        return self.severity == DependencySeverity.CRITICAL
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "name": self.name,
            "status": self.status.name,
            "severity": self.severity.name,
            "required_version": self.required_version,
            "installed_version": self.installed_version,
            "message": self.message,
            "is_ok": self.is_ok,
            "is_critical": self.is_critical,
            **self.extra_info
        }
    
    def __str__(self) -> str:
        """Human-readable representation."""
        status_icon = {
            DependencyStatus.AVAILABLE: "✓",
            DependencyStatus.MISSING: "✗",
            DependencyStatus.VERSION_MISMATCH: "⚠",
            DependencyStatus.INCOMPATIBLE: "⚡",
            DependencyStatus.OPTIONAL_MISSING: "○",
            DependencyStatus.OPTIONAL_AVAILABLE: "✓"
        }.get(self.status, "?")
        
        return (
            f"{status_icon} {self.name}"
            f"{f' ({self.required_version})' if self.required_version else ''}"
            f"{f' -> {self.installed_version}' if self.installed_version else ''}"
            f"{f': {self.message}' if self.message else ''}"
        )


@dataclass
class DependencyReport:
    """Collection of dependency check results."""
    results: List[DependencyResult] = field(default_factory=list)
    timestamp: float = field(default_factory=lambda: importlib.import_module('time').time())
    environment_info: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize environment info."""
        import platform
        import sys
        
        self.environment_info = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "python_implementation": platform.python_implementation(),
            "executable": sys.executable,
            "path": sys.path
        }
    
    @property
    def all_ok(self) -> bool:
        """Check if all critical dependencies are satisfied."""
        return all(result.is_ok for result in self.results)
    
    @property
    def critical_issues(self) -> List[DependencyResult]:
        """Get all critical issues."""
        return [r for r in self.results if r.is_critical and not r.is_ok]
    
    @property
    def warnings(self) -> List[DependencyResult]:
        """Get all warnings."""
        return [r for r in self.results if r.severity == DependencySeverity.WARNING]
    
    def add_result(self, result: DependencyResult) -> None:
        """Add a result to the report."""
        self.results.append(result)
    
    def merge(self, other: 'DependencyReport') -> 'DependencyReport':
        """Merge another report into this one."""
        self.results.extend(other.results)
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "timestamp": self.timestamp,
            "all_ok": self.all_ok,
            "environment_info": self.environment_info,
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "total": len(self.results),
                "ok": sum(1 for r in self.results if r.is_ok),
                "critical_issues": len(self.critical_issues),
                "warnings": len(self.warnings)
            }
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def print_summary(self, verbose: bool = False) -> None:
        """Print a summary of the dependency check."""
        print(f"\n{'='*60}")
        print("DEPENDENCY CHECK REPORT")
        print(f"{'='*60}")
        
        if self.all_ok:
            print("✅ All dependencies satisfied!")
        else:
            print("❌ Dependency issues found:")
        
        # Group by severity
        by_severity = defaultdict(list)
        for result in self.results:
            by_severity[result.severity].append(result)
        
        for severity in DependencySeverity:
            if severity in by_severity:
                print(f"\n{severity.name}:")
                for result in by_severity[severity]:
                    print(f"  {result}")
        
        if verbose:
            print(f"\nEnvironment:")
            for key, value in self.environment_info.items():
                if key != "path":  # Skip path in verbose for brevity
                    print(f"  {key}: {value}")
        
        print(f"{'='*60}")


class VersionConstraint:
    """Parse and validate version constraints."""
    
    # Regex patterns for version constraints
    PATTERNS = {
        'exact': r'^==\s*([\w\.\+\-]+)$',
        'compatible': r'^~=\s*([\w\.\+\-]+)$',
        'greater_equal': r'^>=\s*([\w\.\+\-]+)$',
        'greater': r'^>\s*([\w\.\+\-]+)$',
        'less_equal': r'^<=\s*([\w\.\+\-]+)$',
        'less': r'^<\s*([\w\.\+\-]+)$',
        'not_equal': r'^!=\s*([\w\.\+\-]+)$',
        'range': r'^>=\s*([\w\.\+\-]+)\s*,\s*<=\s*([\w\.\+\-]+)$',
        'range_exclusive': r'^>\s*([\w\.\+\-]+)\s*,\s*<\s*([\w\.\+\-]+)$',
        'wildcard': r'^==\s*([\w\.]+)\.\*$'
    }
    
    def __init__(self, constraint: str):
        """Initialize with a version constraint string."""
        self.original = constraint.strip()
        self.constraint_type = None
        self.version_spec = None
        self._parse_constraint()
    
    def _parse_constraint(self) -> None:
        """Parse the version constraint."""
        constraint = self.original
        
        # Try each pattern
        for const_type, pattern in self.PATTERNS.items():
            match = re.match(pattern, constraint)
            if match:
                self.constraint_type = const_type
                self.version_spec = match.groups()
                return
        
        # No match - assume exact version or invalid
        if re.match(r'^[\w\.\+\-]+$', constraint):
            self.constraint_type = 'exact'
            self.version_spec = (constraint,)
        else:
            raise ValueError(f"Invalid version constraint: {constraint}")
    
    def check(self, version: str) -> bool:
        """Check if a version satisfies the constraint."""
        if not self.constraint_type or not self.version_spec:
            return False
        
        try:
            return self._compare_versions(version, self.constraint_type, self.version_spec)
        except (ValueError, AttributeError):
            return False
    
    def _compare_versions(self, version: str, const_type: str, spec: Tuple[str, ...]) -> bool:
        """Compare versions based on constraint type."""
        from packaging import version as packaging_version
        
        v = packaging_version.parse(version)
        
        if const_type == 'exact':
            spec_v = packaging_version.parse(spec[0])
            return v == spec_v
        
        elif const_type == 'compatible':
            # ~= X.Y means >= X.Y, == X.Y.*
            spec_v = packaging_version.parse(spec[0])
            if len(spec_v.release) >= 2:
                # For X.Y.Z, compatible means >= X.Y.Z, < X.Y+1
                next_minor = (spec_v.release[0], spec_v.release[1] + 1)
                next_v = packaging_version.parse('.'.join(map(str, next_minor)))
                return v >= spec_v and v < next_v
            return v >= spec_v
        
        elif const_type == 'greater_equal':
            spec_v = packaging_version.parse(spec[0])
            return v >= spec_v
        
        elif const_type == 'greater':
            spec_v = packaging_version.parse(spec[0])
            return v > spec_v
        
        elif const_type == 'less_equal':
            spec_v = packaging_version.parse(spec[0])
            return v <= spec_v
        
        elif const_type == 'less':
            spec_v = packaging_version.parse(spec[0])
            return v < spec_v
        
        elif const_type == 'not_equal':
            spec_v = packaging_version.parse(spec[0])
            return v != spec_v
        
        elif const_type == 'range':
            min_v = packaging_version.parse(spec[0])
            max_v = packaging_version.parse(spec[1])
            return min_v <= v <= max_v
        
        elif const_type == 'range_exclusive':
            min_v = packaging_version.parse(spec[0])
            max_v = packaging_version.parse(spec[1])
            return min_v < v < max_v
        
        elif const_type == 'wildcard':
            # == X.Y.* means >= X.Y.0, < X.Y+1
            base = spec[0]
            base_v = packaging_version.parse(base)
            if len(base_v.release) >= 2:
                next_minor = (base_v.release[0], base_v.release[1] + 1)
                next_v = packaging_version.parse('.'.join(map(str, next_minor)))
                return v >= base_v and v < next_v
            return v >= base_v
        
        return False
    
    def __str__(self) -> str:
        return self.original


class DependencyChecker:
    """
    Main dependency checker class.
    
    Provides comprehensive dependency validation with caching,
    detailed reporting, and graceful fallback mechanisms.
    """
    
    def __init__(self, cache_results: bool = True):
        """Initialize the dependency checker."""
        self.cache_results = cache_results
        self._cache: Dict[str, DependencyResult] = {}
        self._import_cache: Dict[str, Any] = {}
        
        # Register default checkers
        self._checkers: Dict[str, Callable] = {
            'python': self._check_python_version,
            'package': self._check_package,
            'module': self._check_module,
            'file': self._check_file,
            'command': self._check_command,
        }
    
    @lru_cache(maxsize=128)
    def get_package_version(self, package_name: str) -> Optional[str]:
        """Get installed package version with caching."""
        try:
            # Try standard metadata first
            return importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            try:
                # Try importing the package and checking __version__
                module = importlib.import_module(package_name)
                return getattr(module, '__version__', None)
            except ImportError:
                return None
    
    def _check_python_version(self, spec: str) -> DependencyResult:
        """Check Python version."""
        import platform
        
        python_version = platform.python_version()
        constraint = VersionConstraint(spec)
        
        if constraint.check(python_version):
            return DependencyResult(
                name="python",
                status=DependencyStatus.AVAILABLE,
                severity=DependencySeverity.INFO,
                required_version=spec,
                installed_version=python_version,
                message=f"Python version {python_version} satisfies {spec}"
            )
        else:
            return DependencyResult(
                name="python",
                status=DependencyStatus.VERSION_MISMATCH,
                severity=DependencySeverity.CRITICAL,
                required_version=spec,
                installed_version=python_version,
                message=f"Python version {python_version} does not satisfy {spec}"
            )
    
    def _check_package(self, name: str, version: Optional[str] = None,
                      optional: bool = False) -> DependencyResult:
        """Check if a package is available and optionally validate version."""
        
        # Check cache first
        cache_key = f"package:{name}:{version}:{optional}"
        if self.cache_results and cache_key in self._cache:
            return self._cache[cache_key]
        
        installed_version = self.get_package_version(name)
        
        if installed_version is None:
            # Package not installed
            status = (DependencyStatus.OPTIONAL_MISSING if optional 
                     else DependencyStatus.MISSING)
            severity = (DependencySeverity.WARNING if optional 
                       else DependencySeverity.CRITICAL)
            
            result = DependencyResult(
                name=name,
                status=status,
                severity=severity,
                required_version=version,
                installed_version=None,
                message=f"Package '{name}' is not installed"
            )
        elif version is None:
            # Package installed, no version check
            status = (DependencyStatus.OPTIONAL_AVAILABLE if optional 
                     else DependencyStatus.AVAILABLE)
            severity = (DependencySeverity.INFO if optional 
                       else DependencySeverity.INFO)
            
            result = DependencyResult(
                name=name,
                status=status,
                severity=severity,
                required_version=None,
                installed_version=installed_version,
                message=f"Package '{name}' ({installed_version}) is available"
            )
        else:
            # Check version constraint
            constraint = VersionConstraint(version)
            if constraint.check(installed_version):
                status = (DependencyStatus.OPTIONAL_AVAILABLE if optional 
                         else DependencyStatus.AVAILABLE)
                severity = (DependencySeverity.INFO if optional 
                           else DependencySeverity.INFO)
                
                result = DependencyResult(
                    name=name,
                    status=status,
                    severity=severity,
                    required_version=version,
                    installed_version=installed_version,
                    message=f"Package '{name}' ({installed_version}) satisfies {version}"
                )
            else:
                status = (DependencyStatus.VERSION_MISMATCH if not optional 
                         else DependencyStatus.INCOMPATIBLE)
                severity = (DependencySeverity.ERROR if not optional 
                           else DependencySeverity.WARNING)
                
                result = DependencyResult(
                    name=name,
                    status=status,
                    severity=severity,
                    required_version=version,
                    installed_version=installed_version,
                    message=f"Package '{name}' ({installed_version}) does not satisfy {version}"
                )
        
        # Cache the result
        if self.cache_results:
            self._cache[cache_key] = result
        
        return result
    
    def _check_module(self, module_name: str, optional: bool = False) -> DependencyResult:
        """Check if a module can be imported."""
        cache_key = f"module:{module_name}:{optional}"
        if self.cache_results and cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, '__version__', None)
            
            status = (DependencyStatus.OPTIONAL_AVAILABLE if optional 
                     else DependencyStatus.AVAILABLE)
            severity = (DependencySeverity.INFO if optional 
                       else DependencySeverity.INFO)
            
            result = DependencyResult(
                name=module_name,
                status=status,
                severity=severity,
                installed_version=version,
                message=f"Module '{module_name}' can be imported"
            )
        except ImportError as e:
            status = (DependencyStatus.OPTIONAL_MISSING if optional 
                     else DependencyStatus.MISSING)
            severity = (DependencySeverity.WARNING if optional 
                       else DependencySeverity.CRITICAL)
            
            result = DependencyResult(
                name=module_name,
                status=status,
                severity=severity,
                message=f"Module '{module_name}' cannot be imported: {e}"
            )
        
        if self.cache_results:
            self._cache[cache_key] = result
        
        return result
    
    def _check_file(self, file_path: str, optional: bool = False) -> DependencyResult:
        """Check if a file