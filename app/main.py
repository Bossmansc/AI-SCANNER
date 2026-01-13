#!/usr/bin/env python3
"""
Main application entry point with enhanced dependency validation.
Validates all required dependencies, configurations, and system resources
before starting the application.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import importlib
import importlib.util
import platform
import subprocess
import json
from dataclasses import dataclass
from enum import Enum
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app_startup.log')
    ]
)
logger = logging.getLogger(__name__)


class DependencyStatus(Enum):
    """Status of a dependency check."""
    OK = "OK"
    MISSING = "MISSING"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    FAILED = "FAILED"
    WARNING = "WARNING"


class ResourceStatus(Enum):
    """Status of a system resource check."""
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT = "INSUFFICIENT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class DependencyCheck:
    """Result of a dependency check."""
    name: str
    required_version: Optional[str] = None
    installed_version: Optional[str] = None
    status: DependencyStatus = DependencyStatus.OK
    message: str = ""
    is_critical: bool = True


@dataclass
class ResourceCheck:
    """Result of a system resource check."""
    resource_type: str
    required: Optional[float] = None
    available: Optional[float] = None
    status: ResourceStatus = ResourceStatus.AVAILABLE
    message: str = ""


class StartupValidator:
    """Validates all dependencies and system resources before application startup."""
    
    def __init__(self):
        self.dependency_checks: List[DependencyCheck] = []
        self.resource_checks: List[ResourceCheck] = []
        self.config_checks: List[Tuple[str, bool, str]] = []
        self.startup_time = datetime.now()
        
    def add_dependency(self, name: str, required_version: Optional[str] = None, 
                      is_critical: bool = True) -> None:
        """Add a dependency to check."""
        self.dependency_checks.append(
            DependencyCheck(
                name=name,
                required_version=required_version,
                is_critical=is_critical
            )
        )
    
    def add_resource_check(self, resource_type: str, required: Optional[float] = None) -> None:
        """Add a system resource to check."""
        self.resource_checks.append(
            ResourceCheck(
                resource_type=resource_type,
                required=required
            )
        )
    
    def add_config_check(self, config_key: str, validation_func) -> None:
        """Add a configuration validation check."""
        self.config_checks.append((config_key, validation_func))
    
    def check_python_version(self) -> DependencyCheck:
        """Check Python version compatibility."""
        import platform
        python_version = platform.python_version()
        required_major = 3
        required_minor = 8
        
        major, minor, _ = map(int, python_version.split('.'))
        
        check = DependencyCheck(
            name="Python",
            required_version=f">={required_major}.{required_minor}",
            installed_version=python_version,
            is_critical=True
        )
        
        if major < required_major or (major == required_major and minor < required_minor):
            check.status = DependencyStatus.VERSION_MISMATCH
            check.message = f"Python {required_major}.{required_minor}+ required, found {python_version}"
        else:
            check.status = DependencyStatus.OK
            check.message = f"Python {python_version} meets requirements"
        
        return check
    
    def check_package(self, package_name: str, version_spec: Optional[str] = None) -> DependencyCheck:
        """Check if a Python package is installed with optional version check."""
        try:
            # Try to import the package
            module = importlib.import_module(package_name)
            
            # Get version if available
            installed_version = None
            if hasattr(module, '__version__'):
                installed_version = module.__version__
            elif hasattr(module, 'version'):
                installed_version = module.version
            
            check = DependencyCheck(
                name=package_name,
                required_version=version_spec,
                installed_version=installed_version,
                is_critical=True
            )
            
            # Check version if spec provided
            if version_spec and installed_version:
                from packaging import version
                from packaging.specifiers import SpecifierSet
                
                try:
                    spec = SpecifierSet(version_spec)
                    if version.parse(installed_version) in spec:
                        check.status = DependencyStatus.OK
                        check.message = f"Version {installed_version} meets requirement {version_spec}"
                    else:
                        check.status = DependencyStatus.VERSION_MISMATCH
                        check.message = f"Version {installed_version} does not meet requirement {version_spec}"
                except Exception as e:
                    check.status = DependencyStatus.WARNING
                    check.message = f"Version check failed: {str(e)}"
            else:
                check.status = DependencyStatus.OK
                check.message = f"Package '{package_name}' is available"
                if installed_version:
                    check.message += f" (version {installed_version})"
            
            return check
            
        except ImportError:
            return DependencyCheck(
                name=package_name,
                required_version=version_spec,
                status=DependencyStatus.MISSING,
                message=f"Package '{package_name}' is not installed",
                is_critical=True
            )
        except Exception as e:
            return DependencyCheck(
                name=package_name,
                required_version=version_spec,
                status=DependencyStatus.FAILED,
                message=f"Failed to check package '{package_name}': {str(e)}",
                is_critical=True
            )
    
    def check_system_memory(self, required_gb: float = 1.0) -> ResourceCheck:
        """Check available system memory."""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024 ** 3)
            
            check = ResourceCheck(
                resource_type="System Memory",
                required=required_gb,
                available=available_gb
            )
            
            if available_gb >= required_gb:
                check.status = ResourceStatus.AVAILABLE
                check.message = f"{available_gb:.2f} GB available, {required_gb} GB required"
            else:
                check.status = ResourceStatus.INSUFFICIENT
                check.message = f"Insufficient memory: {available_gb:.2f} GB available, {required_gb} GB required"
            
            return check
            
        except ImportError:
            return ResourceCheck(
                resource_type="System Memory",
                required=required_gb,
                status=ResourceStatus.UNAVAILABLE,
                message="psutil not installed, cannot check memory"
            )
        except Exception as e:
            return ResourceCheck(
                resource_type="System Memory",
                required=required_gb,
                status=ResourceStatus.UNAVAILABLE,
                message=f"Failed to check memory: {str(e)}"
            )
    
    def check_disk_space(self, path: str = ".", required_gb: float = 5.0) -> ResourceCheck:
        """Check available disk space."""
        try:
            import psutil
            
            disk = psutil.disk_usage(path)
            available_gb = disk.free / (1024 ** 3)
            
            check = ResourceCheck(
                resource_type="Disk Space",
                required=required_gb,
                available=available_gb
            )
            
            if available_gb >= required_gb:
                check.status = ResourceStatus.AVAILABLE
                check.message = f"{available_gb:.2f} GB available at '{path}', {required_gb} GB required"
            else:
                check.status = ResourceStatus.INSUFFICIENT
                check.message = f"Insufficient disk space: {available_gb:.2f} GB available, {required_gb} GB required"
            
            return check
            
        except ImportError:
            return ResourceCheck(
                resource_type="Disk Space",
                required=required_gb,
                status=ResourceStatus.UNAVAILABLE,
                message="psutil not installed, cannot check disk space"
            )
        except Exception as e:
            return ResourceCheck(
                resource_type="Disk Space",
                required=required_gb,
                status=ResourceStatus.UNAVAILABLE,
                message=f"Failed to check disk space: {str(e)}"
            )
    
    def check_network_connectivity(self, host: str = "8.8.8.8", port: int = 53, 
                                  timeout: int = 3) -> ResourceCheck:
        """Check network connectivity."""
        import socket
        
        check = ResourceCheck(resource_type="Network Connectivity")
        
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            check.status = ResourceStatus.AVAILABLE
            check.message = f"Network connectivity to {host}:{port} is available"
        except socket.error as e:
            check.status = ResourceStatus.UNAVAILABLE
            check.message = f"No network connectivity to {host}:{port}: {str(e)}"
        
        return check
    
    def check_environment_variables(self, required_vars: List[str]) -> List[Tuple[str, bool, str]]:
        """Check required environment variables."""
        results = []
        for var in required_vars:
            value = os.getenv(var)
            if value:
                results.append((var, True, f"Environment variable '{var}' is set"))
            else:
                results.append((var, False, f"Environment variable '{var}' is not set"))
        return results
    
    def check_config_file(self, config_path: str) -> Tuple[bool, str]:
        """Check if configuration file exists and is valid JSON."""
        path = Path(config_path)
        
        if not path.exists():
            return False, f"Config file '{config_path}' does not exist"
        
        if not path.is_file():
            return False, f"'{config_path}' is not a file"
        
        try:
            with open(config_path, 'r') as f:
                json.load(f)
            return True, f"Config file '{config_path}' is valid JSON"
        except json.JSONDecodeError as e:
            return False, f"Config file '{config_path}' contains invalid JSON: {str(e)}"
        except Exception as e:
            return False, f"Failed to read config file '{config_path}': {str(e)}"
    
    def validate_all(self) -> Tuple[bool, Dict[str, List]]:
        """Run all validation checks."""
        logger.info("Starting comprehensive startup validation...")
        
        results = {
            "dependencies": [],
            "resources": [],
            "environment": [],
            "config": []
        }
        
        # Check Python version
        python_check = self.check_python_version()
        results["dependencies"].append(python_check)
        
        # Check all registered dependencies
        for dep in self.dependency_checks:
            if dep.name != "Python":  # Already checked
                check_result = self.check_package(dep.name, dep.required_version)
                check_result.is_critical = dep.is_critical
                results["dependencies"].append(check_result)
        
        # Check system resources
        for resource in self.resource_checks:
            if resource.resource_type == "System Memory":
                check_result = self.check_system_memory(resource.required or 1.0)
            elif resource.resource_type == "Disk Space":
                check_result = self.check_disk_space(".", resource.required or 5.0)
            elif resource.resource_type == "Network Connectivity":
                check_result = self.check_network_connectivity()
            else:
                check_result = ResourceCheck(
                    resource_type=resource.resource_type,
                    status=ResourceStatus.UNAVAILABLE,
                    message=f"Unknown resource type: {resource.resource_type}"
                )
            results["resources"].append(check_result)
        
        # Check environment variables
        required_env_vars = ["APP_ENV", "LOG_LEVEL"]
        env_results = self.check_environment_variables(required_env_vars)
        results["environment"].extend(env_results)
        
        # Check config files
        config_files = ["config/app.json", "config/database.json"]
        for config_file in config_files:
            valid, message = self.check_config_file(config_file)
            results["config"].append((config_file, valid, message))
        
        # Determine overall status
        all_passed = True
        critical_failures = []
        
        # Check dependencies
        for dep in results["dependencies"]:
            if dep.status != DependencyStatus.OK:
                if dep.is_critical:
                    all_passed = False
                    critical_failures.append(f"Critical dependency '{dep.name}': {dep.message}")
                else:
                    logger.warning(f"Non-critical dependency issue: {dep.name} - {dep.message}")
        
        # Check resources
        for resource in results["resources"]:
            if resource.status != ResourceStatus.AVAILABLE:
                logger.warning(f"Resource issue: {resource.resource_type} - {resource.message}")
                # Only fail on insufficient resources, not unavailable checks
                if resource.status == ResourceStatus.INSUFFICIENT:
                    all_passed = False
                    critical_failures.append(f"Insufficient {resource.resource_type}: {resource.message}")
        
        # Check environment variables
        for var, is_set, message in results["environment"]:
            if not is_set:
                logger.warning(f"Environment variable not set: {var}")
                # Environment variables might not be critical depending on the app
        
        # Check config files
        for config_file, is_valid, message in results["config"]:
            if not is_valid:
                all_passed = False
                critical_failures.append(f"Config file error: {message}")
        
        return all_passed, results
    
    def print_validation_report(self, results: Dict[str, List]) -> None:
        """Print a detailed validation report."""
        print("\n" + "="*80)
        print("STARTUP VALIDATION REPORT")
        print("="*80)
        
        print(f"\nValidation timestamp: {self.startup_time}")
        print(f"System: {platform.system()} {platform.release()}")
        print(f"Python: {platform.python_version()}")
        print(f"Working directory: {os.getcwd()}")
        
        # Dependencies
        print("\n" + "-"*40)
        print("DEPENDENCIES")
        print("-"*40)
        for dep in results["dependencies"]:
            status_icon = "✓" if dep.status == DependencyStatus.OK else "✗"
            if dep.status == DependencyStatus.WARNING:
                status_icon = "⚠"
            print(f"{status_icon} {dep.name}: {dep.message}")
        
        # Resources
        print("\n" + "-"*40)
        print("SYSTEM RESOURCES")
        print("-"*40)
        for resource in results["resources"]:
            status_icon = "✓" if resource.status == ResourceStatus.AVAILABLE else "✗"
            if resource.status == ResourceStatus.INSUFFICIENT:
                status_icon = "⚠"
            print(f"{status_icon} {resource.resource_type}: {resource.message}")
        
        # Environment
        print("\n" + "-"*40)
        print("ENVIRONMENT VARIABLES")
        print("-"*40)
        for var, is_set, message in results["environment"]:
            status_icon = "✓" if is_set else "⚠"
            print(f"{status_icon} {message}")
        
        # Config files
        print("\n" + "-"*40)
        print("CONFIGURATION FILES")
        print("-"*40)
        for config_file, is_valid, message in results["config"]:
            status_icon = "✓" if is_valid else "✗"
            print(f"{status_icon} {message}")
        
        print("\n" + "="*80)
        
        # Summary
        critical_issues = []
        for dep in results["dependencies"]:
            if dep.status != DependencyStatus.OK and dep.is_critical:
                critical_issues.append(f"Critical dependency: {dep.name} - {dep.message}")
        
        for resource in results["resources"]:
            if resource.status == ResourceStatus.INSUFFICIENT:
                critical_issues.append(f"Insufficient resource: {resource.resource_type} - {resource.message}")
        
        for config_file, is_valid, message in results["config"]:
            if not is_valid:
                critical_issues.append(f"Invalid config: {config_file} - {message}")
        
        if critical_issues:
            print("\n❌ CRITICAL ISSUES FOUND:")
            for issue in critical_issues:
                print(f"  • {issue}")
            print(f"\nTotal critical issues: {len(critical_issues)}")
        else:
            print("\n✅ All critical checks passed!")
        
        print("="*80 + "\n")


async def initialize_application() -> bool:
    """
    Initialize the application with comprehensive startup validation.
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    logger.info("Initializing application...")
    
    # Create validator
    validator = StartupValidator()
    
    # Register core dependencies
    validator.add_dependency("fastapi", ">=0.68.0")
    validator.add_dependency("uvicorn", ">=0.15.0")
    validator.add_dependency("sqlalchemy", ">=1.4.0")
    validator.add_dependency("pydantic", ">=1.8.0")
    validator.add_dependency("aiosqlite", ">=0.17.0")
    validator.add_dependency("aiohttp", ">=3.8.0")
    validator.add_dependency("redis", ">=4.0.0")
    validator.add_dependency("psutil", ">=5.8.0", is_critical=False)
    validator.add_dependency("python-jose", ">=3.3.0")
    validator.add_dependency("passlib", ">=1.7.4")
    
    # Register system resources to check
    validator.add_resource_check("System Memory", required=2.0) 