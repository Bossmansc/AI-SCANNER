#!/usr/bin/env python3
"""
Robust Dependency Installation Script with Fallbacks

This script provides a production-grade dependency installation system with:
- Multiple package manager support (pip, pip3, uv, poetry)
- Fallback mechanisms for network failures
- Parallel installation for performance
- Dependency verification and validation
- Comprehensive logging and error handling
- Platform-specific optimizations
- Cache management
- Security validation
"""

import argparse
import concurrent.futures
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any, Union

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

class PackageManager(Enum):
    """Supported package managers"""
    PIP = "pip"
    PIP3 = "pip3"
    UV = "uv"
    POETRY = "poetry"
    CONDA = "conda"
    
    @classmethod
    def get_available(cls) -> List['PackageManager']:
        """Get available package managers on the system"""
        available = []
        for manager in cls:
            if shutil.which(manager.value):
                available.append(manager)
        return available

class InstallMode(Enum):
    """Installation modes"""
    NORMAL = "normal"
    DEV = "dev"
    ALL = "all"
    PRODUCTION = "production"

# Default configuration
DEFAULT_CONFIG = {
    "timeout": 300,  # 5 minutes
    "max_retries": 3,
    "parallel_workers": 4,
    "cache_ttl": 3600,  # 1 hour
    "verify_ssl": True,
    "use_mirrors": True,
    "mirrors": [
        "https://pypi.org/simple/",
        "https://mirrors.aliyun.com/pypi/simple/",
        "https://pypi.tuna.tsinghua.edu.cn/simple/"
    ],
    "platform_specific": {
        "windows": {
            "prefer": [PackageManager.PIP, PackageManager.CONDA],
            "env_vars": {"PYTHONUTF8": "1"}
        },
        "linux": {
            "prefer": [PackageManager.PIP3, PackageManager.UV],
            "env_vars": {}
        },
        "darwin": {
            "prefer": [PackageManager.PIP3, PackageManager.POETRY],
            "env_vars": {}
        }
    }
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """Configure logging system"""
    logger = logging.getLogger("install_deps")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_platform_info() -> Dict[str, Any]:
    """Get detailed platform information"""
    return {
        "system": platform.system().lower(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "cwd": os.getcwd(),
        "user": os.getenv("USER") or os.getenv("USERNAME"),
        "env_path": os.getenv("PATH", ""),
        "cpu_count": os.cpu_count() or 1
    }

def validate_python_version(min_version: Tuple[int, int] = (3, 8)) -> bool:
    """Validate Python version meets minimum requirements"""
    current = sys.version_info[:2]
    if current < min_version:
        print(f"ERROR: Python {min_version[0]}.{min_version[1]}+ required. "
              f"Found {current[0]}.{current[1]}")
        return False
    return True

def check_disk_space(min_gb: float = 1.0) -> bool:
    """Check if sufficient disk space is available"""
    try:
        stat = shutil.disk_usage(".")
        free_gb = stat.free / (1024 ** 3)
        return free_gb >= min_gb
    except Exception:
        return True  # If we can't check, assume it's OK

def create_temp_directory() -> str:
    """Create a temporary directory for downloads"""
    temp_dir = tempfile.mkdtemp(prefix="install_deps_")
    os.chmod(temp_dir, 0o755)
    return temp_dir

def cleanup_temp_directory(temp_dir: str) -> None:
    """Clean up temporary directory"""
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass

def calculate_hash(file_path: str, algorithm: str = "sha256") -> str:
    """Calculate file hash"""
    hash_func = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def parse_requirements_file(file_path: str) -> List[Dict[str, Any]]:
    """Parse requirements.txt or similar file"""
    requirements = []
    
    if not os.path.exists(file_path):
        return requirements
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse package specification
            requirement = {
                "original": line,
                "line_number": line_num,
                "package": None,
                "version_spec": None,
                "extras": None,
                "marker": None,
                "url": None,
                "editable": line.startswith('-e ') or line.startswith('--editable ')
            }
            
            # Handle editable installs
            if requirement["editable"]:
                line = line.replace('-e ', '').replace('--editable ', '').strip()
            
            # Parse URL installs
            if line.startswith(('http://', 'https://', 'git+', 'svn+', 'hg+')):
                requirement["url"] = line
                # Extract package name from URL if possible
                match = re.search(r'#egg=([^&]+)', line)
                if match:
                    requirement["package"] = match.group(1)
            else:
                # Parse standard package specification
                # Remove environment markers
                if ';' in line:
                    line, requirement["marker"] = line.split(';', 1)
                    requirement["marker"] = requirement["marker"].strip()
                
                # Extract extras
                if '[' in line and ']' in line:
                    match = re.match(r'^([^\[]+)\[([^\]]+)\](.*)$', line)
                    if match:
                        requirement["package"] = match.group(1).strip()
                        requirement["extras"] = match.group(2).strip()
                        version_part = match.group(3).strip()
                    else:
                        requirement["package"] = line.split('[')[0].strip()
                        requirement["extras"] = None
                        version_part = line
                else:
                    requirement["package"] = line.split()[0].strip()
                    version_part = line
                
                # Extract version specifiers
                if requirement["package"] and len(requirement["package"]) < len(version_part):
                    requirement["version_spec"] = version_part[len(requirement["package"]):].strip()
                else:
                    requirement["package"] = line
                    requirement["version_spec"] = None
            
            requirements.append(requirement)
    
    return requirements

def parse_pyproject_toml(file_path: str) -> Dict[str, Any]:
    """Parse pyproject.toml for dependencies"""
    try:
        import tomli
        with open(file_path, 'r', encoding='utf-8') as f:
            data = tomli.loads(f.read())
        
        dependencies = {
            "dependencies": [],
            "dev_dependencies": [],
            "optional_dependencies": {}
        }
        
        # Get project dependencies
        project = data.get("project", {})
        if "dependencies" in project:
            dependencies["dependencies"] = project["dependencies"]
        
        if "optional-dependencies" in project:
            dependencies["optional_dependencies"] = project["optional-dependencies"]
        
        # Get tool.poetry dependencies
        tool = data.get("tool", {})
        poetry = tool.get("poetry", {})
        if "dependencies" in poetry:
            deps = poetry["dependencies"]
            if isinstance(deps, list):
                dependencies["dependencies"] = deps
            elif isinstance(deps, dict):
                # Filter out python version specifier
                deps_list = []
                for name, spec in deps.items():
                    if name != "python":
                        if isinstance(spec, dict):
                            deps_list.append(f"{name}{spec.get('version', '')}")
                        else:
                            deps_list.append(f"{name}{spec}")
                dependencies["dependencies"] = deps_list
        
        return dependencies
    except ImportError:
        # tomli not available, try simple parsing
        return {"dependencies": [], "dev_dependencies": [], "optional_dependencies": {}}
    except Exception as e:
        print(f"Warning: Could not parse pyproject.toml: {e}")
        return {"dependencies": [], "dev_dependencies": [], "optional_dependencies": {}}

# ============================================================================
# PACKAGE MANAGER INTERFACE
# ============================================================================

class PackageManagerInterface:
    """Base class for package manager interfaces"""
    
    def __init__(self, manager: PackageManager, logger: logging.Logger):
        self.manager = manager
        self.logger = logger
        self.name = manager.value
        self.version = self._get_version()
    
    def _get_version(self) -> Optional[str]:
        """Get package manager version"""
        try:
            result = subprocess.run(
                [self.name, "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def is_available(self) -> bool:
        """Check if package manager is available"""
        return shutil.which(self.name) is not None
    
    def install_packages(
        self,
        packages: List[str],
        upgrade: bool = False,
        no_deps: bool = False,
        index_url: Optional[str] = None,
        extra_index_url: Optional[str] = None,
        timeout: int = 300
    ) -> Tuple[bool, str]:
        """Install packages using this manager"""
        raise NotImplementedError
    
    def install_from_file(
        self,
        file_path: str,
        upgrade: bool = False,
        no_deps: bool = False,
        index_url: Optional[str] = None,
        extra_index_url: Optional[str] = None,
        timeout: int = 300
    ) -> Tuple[bool, str]:
        """Install from requirements file"""
        raise NotImplementedError
    
    def uninstall_packages(
        self,
        packages: List[str],
        yes: bool = False
    ) -> Tuple[bool, str]:
        """Uninstall packages"""
        raise NotImplementedError
    
    def list_packages(self) -> List[Dict[str, str]]:
        """List installed packages"""
        raise NotImplementedError
    
    def check_package(self, package: str) -> bool:
        """Check if a package is installed"""
        raise NotImplementedError

class PipInterface(PackageManagerInterface):
    """Interface for pip package manager"""
    
    def install_packages(
        self,
        packages: List[str],
        upgrade: bool = False,
        no_deps: bool = False,
        index_url: Optional[str] = None,
        extra_index_url: Optional[str] = None,
        timeout: int = 300
    ) -> Tuple[bool, str]:
        """Install packages using pip"""
        cmd = [self.name, "install"]
        
        if upgrade:
            cmd.append("--upgrade")
        
        if no_deps:
            cmd.append("--no-deps")
        
        if index_url:
            cmd.extend(["--index-url", index_url])
        
        if extra_index_url:
            cmd.extend(["--extra-index-url", extra_index_url])
        
        # Add trusted-host for HTTP indexes
        if index_url and index_url.startswith("http://"):
            host = index_url.split("://")[1].split("/")[0]
            cmd.extend(["--trusted-host", host])
        
        cmd.extend(packages)
        
        self.logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, f"Installation timed out after {timeout} seconds"
        except Exception as e:
            return False, str(e)
    
    def install_from_file(
        self,
        file_path: str,
        upgrade: bool = False,
        no_deps: bool = False,
        index_url: Optional[str] = None,
        extra_index_url: Optional[str] = None,
        timeout: int = 300
    ) -> Tuple[bool, str]:
        """Install from requirements file using pip"""
        cmd = [self.name, "install", "-r", file_path]
        
        if upgrade:
            cmd.append("--upgrade")
        
        if no_deps:
            cmd.append("--no-deps")
        
        if index_url:
            cmd.extend(["--index-url", index_url])
        
        if extra_index_url:
            cmd.extend(["--extra-index-url", extra_index_url])
        
        self.logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, f"Installation timed out after {timeout} seconds"
        except Exception as e:
            return False, str(e)
    
    def uninstall_packages(
        self,
        packages: List[str],
        yes: bool = False
    ) -> Tuple[bool, str]:
        """Uninstall packages using pip"""
        cmd = [self.name, "uninstall"]
        
        if yes:
            cmd.append("-y")
        
        cmd.extend(packages)
        
        self.logger.info(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
        except Exception as e:
            return False, str(e)
    
    def list_packages(self) -> List[Dict[str, str]]:
        """List installed packages using pip"""
        try:
            result = subprocess.run(
                [self.name, "list", "--format=json"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                return packages
        except Exception:
            pass
        
        # Fallback to pip freeze
        try:
            result = subprocess.run(
                [self.name, "freeze"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                packages = []
                for line in result.stdout.strip().split('\n'):
                    if line and '==' in line:
                        name, version = line.split('==', 1)
                        packages.append({
                            "name": name.strip(),
                            "version": version.strip()
                        })
                return packages
        except Exception:
            pass
        
        return []
    
    def check_package(self, package: str) -> bool:
        """Check if a package is installed using pip"""
        try:
            # Try to import the package
            subprocess.run(
                [sys.executable, "-c", f"import {package}"],
                capture_output=True,
                check=False
            )
            return True
        except Exception:
            pass
        
        # Check in pip list
        packages = self.list_packages()
        for pkg in packages:
            if pkg["name"].lower() == package.lower():
                return True
        
        return False

class UvInterface(PipInterface):
    """Interface for uv package manager (compatible with pip interface)"""
    
    def install_packages(
        self,
        packages: List[str],
        upgrade: bool = False,
        no_deps: bool = False,
        index_url: Optional[str] = None,
        extra_index_url: Optional[str] = None,
        timeout: int = 300
    ) -> Tuple[bool, str]:
        """Install packages using uv"""
        cmd = [self.name, "pip", "install"]
        
        if upgrade:
            cmd.append("--upgrade")
        
        if no_deps:
            cmd.append("--no-deps")
        
        if index