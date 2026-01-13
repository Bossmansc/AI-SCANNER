#!/usr/bin/env python3
"""
Dependency Installation Manager with Fallback Versions

This script handles robust dependency installation for the CodeCraft AI system.
It provides:
1. Primary version installation with automatic fallback to compatible versions
2. Environment validation and dependency conflict resolution
3. Comprehensive logging and error reporting
4. Support for multiple package managers (pip, conda, poetry)
5. Dependency tree analysis and verification
"""

import sys
import os
import subprocess
import json
import logging
import argparse
import platform
import re
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import time
import warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dependency_install.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PackageManager(Enum):
    """Supported package managers"""
    PIP = "pip"
    CONDA = "conda"
    POETRY = "poetry"
    UV = "uv"


class InstallStatus(Enum):
    """Installation status codes"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    FALLBACK_USED = "fallback_used"
    CONFLICT_RESOLVED = "conflict_resolved"


@dataclass
class Dependency:
    """Represents a single dependency with version constraints"""
    name: str
    primary_version: str
    fallback_versions: List[str] = field(default_factory=list)
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    source: str = "pypi"  # pypi, conda, git, local
    optional: bool = False
    groups: List[str] = field(default_factory=list)  # dev, test, docs, etc.
    
    def __post_init__(self):
        """Validate dependency data"""
        if not self.name or not self.primary_version:
            raise ValueError("Dependency name and primary_version are required")
        
        # Ensure fallback versions are valid
        self.fallback_versions = [v for v in self.fallback_versions if v]
        
        # Validate version format (basic check)
        version_pattern = r'^[~>=<!^]*\d+\.\d+(\.\d+)*[a-zA-Z0-9]*$'
        for version in [self.primary_version] + self.fallback_versions:
            if version and not re.match(version_pattern, version):
                warnings.warn(f"Version '{version}' for '{self.name}' may not be valid")


@dataclass
class InstallResult:
    """Result of a dependency installation attempt"""
    dependency: Dependency
    status: InstallStatus
    installed_version: Optional[str] = None
    used_fallback: bool = False
    fallback_index: int = -1
    error_message: Optional[str] = None
    install_time: float = 0.0
    package_manager: Optional[PackageManager] = None


class DependencyManager:
    """Main dependency management class"""
    
    def __init__(
        self,
        package_manager: PackageManager = PackageManager.PIP,
        use_cache: bool = True,
        strict_mode: bool = False,
        timeout: int = 300,
        retry_count: int = 3
    ):
        """
        Initialize the dependency manager
        
        Args:
            package_manager: Preferred package manager
            use_cache: Whether to use pip/conda cache
            strict_mode: Fail on any conflict
            timeout: Timeout for installation commands (seconds)
            retry_count: Number of retry attempts for failed installs
        """
        self.package_manager = package_manager
        self.use_cache = use_cache
        self.strict_mode = strict_mode
        self.timeout = timeout
        self.retry_count = retry_count
        
        # Track installation results
        self.install_results: List[InstallResult] = []
        self.installed_packages: Dict[str, str] = {}
        
        # Environment information
        self.system_info = self._get_system_info()
        
        # Cache directory for downloaded packages
        self.cache_dir = Path.home() / ".cache" / "codecraft_deps"
        if use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized DependencyManager with {package_manager.value}")
        logger.info(f"System: {self.system_info['os']} {self.system_info['python_version']}")
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get detailed system information"""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }
    
    def _run_command(
        self,
        command: List[str],
        capture_output: bool = True,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Tuple[int, str, str]:
        """
        Run a shell command with timeout and error handling
        
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            logger.debug(f"Running command: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                timeout=self.timeout,
                cwd=cwd,
                env=env or os.environ.copy()
            )
            
            return (
                result.returncode,
                result.stdout.strip() if result.stdout else "",
                result.stderr.strip() if result.stderr else ""
            )
            
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {self.timeout} seconds: {' '.join(command)}")
            return (1, "", f"Command timed out after {self.timeout} seconds")
        except Exception as e:
            logger.error(f"Command failed with error: {str(e)}")
            return (1, "", str(e))
    
    def _check_package_installed(self, package_name: str) -> Optional[str]:
        """
        Check if a package is already installed and return its version
        
        Args:
            package_name: Name of the package to check
            
        Returns:
            Installed version or None if not installed
        """
        try:
            # Try pip first
            if self.package_manager in [PackageManager.PIP, PackageManager.POETRY, PackageManager.UV]:
                cmd = [sys.executable, "-m", "pip", "show", package_name]
                returncode, stdout, stderr = self._run_command(cmd)
                
                if returncode == 0:
                    # Parse version from pip show output
                    for line in stdout.split('\n'):
                        if line.startswith('Version:'):
                            return line.split(':', 1)[1].strip()
            
            # Try conda if available
            if self.package_manager == PackageManager.CONDA:
                cmd = ["conda", "list", package_name, "--json"]
                returncode, stdout, stderr = self._run_command(cmd)
                
                if returncode == 0:
                    try:
                        data = json.loads(stdout)
                        if data and len(data) > 0:
                            return data[0].get('version')
                    except json.JSONDecodeError:
                        pass
            
            return None
            
        except Exception as e:
            logger.debug(f"Error checking package {package_name}: {str(e)}")
            return None
    
    def _parse_version_specifier(self, version_spec: str) -> Tuple[str, str]:
        """
        Parse version specifier into operator and version
        
        Args:
            version_spec: Version string like ">=1.2.3", "~=2.0", "1.5.0"
            
        Returns:
            Tuple of (operator, version)
        """
        # Match operators at the beginning
        match = re.match(r'^([~>=<!^]+)?(.+)$', version_spec)
        if match:
            operator = match.group(1) or "=="
            version = match.group(2)
            return operator, version
        return "==", version_spec
    
    def _version_satisfies(self, installed_version: str, required_spec: str) -> bool:
        """
        Check if installed version satisfies the requirement
        
        Note: This is a simplified version checker.
        For production use, consider using packaging.version or similar.
        """
        try:
            # Simple equality check for now
            # In a real implementation, use packaging.version.parse
            if required_spec.startswith("=="):
                required_version = required_spec[2:].strip()
                return installed_version == required_version
            elif required_spec.startswith(">="):
                required_version = required_spec[2:].strip()
                # Simple string comparison (not accurate for all versions)
                return installed_version >= required_version
            else:
                # For complex operators, assume True and let pip handle it
                return True
        except Exception:
            # If we can't parse, assume it satisfies (pip will handle conflicts)
            return True
    
    def _get_install_command(
        self,
        dependency: Dependency,
        version_spec: str,
        extra_args: List[str] = None
    ) -> List[str]:
        """
        Generate the appropriate install command for the package manager
        """
        base_args = extra_args or []
        
        if self.package_manager == PackageManager.PIP:
            cmd = [sys.executable, "-m", "pip", "install"]
            if self.use_cache:
                cmd.extend(["--cache-dir", str(self.cache_dir)])
            cmd.extend(base_args)
            cmd.append(f"{dependency.name}{version_spec}")
            
        elif self.package_manager == PackageManager.CONDA:
            cmd = ["conda", "install", "-y"]
            cmd.extend(base_args)
            cmd.append(f"{dependency.name}{version_spec}")
            
        elif self.package_manager == PackageManager.POETRY:
            cmd = ["poetry", "add"]
            cmd.extend(base_args)
            cmd.append(f"{dependency.name}{version_spec}")
            
        elif self.package_manager == PackageManager.UV:
            cmd = ["uv", "pip", "install"]
            if self.use_cache:
                cmd.extend(["--cache-dir", str(self.cache_dir)])
            cmd.extend(base_args)
            cmd.append(f"{dependency.name}{version_spec}")
            
        else:
            raise ValueError(f"Unsupported package manager: {self.package_manager}")
        
        return cmd
    
    def _install_with_fallback(
        self,
        dependency: Dependency,
        extra_args: List[str] = None
    ) -> InstallResult:
        """
        Attempt to install a dependency with fallback versions
        
        Args:
            dependency: The dependency to install
            extra_args: Additional arguments for the package manager
            
        Returns:
            InstallResult with installation status
        """
        # Check if already installed with compatible version
        installed_version = self._check_package_installed(dependency.name)
        if installed_version:
            if self._version_satisfies(installed_version, dependency.primary_version):
                logger.info(f"✓ {dependency.name} {installed_version} already installed")
                return InstallResult(
                    dependency=dependency,
                    status=InstallStatus.SKIPPED,
                    installed_version=installed_version
                )
        
        # Try primary version first
        versions_to_try = [dependency.primary_version] + dependency.fallback_versions
        
        for i, version_spec in enumerate(versions_to_try):
            start_time = time.time()
            used_fallback = i > 0
            
            if used_fallback:
                logger.warning(f"Trying fallback version {i} for {dependency.name}: {version_spec}")
            
            # Format version specifier
            operator, version = self._parse_version_specifier(version_spec)
            if operator == "==":
                pip_spec = f"=={version}"
            else:
                pip_spec = version_spec
            
            # Generate install command
            cmd = self._get_install_command(dependency, pip_spec, extra_args)
            
            # Attempt installation with retries
            for attempt in range(self.retry_count):
                logger.info(f"Installing {dependency.name}{pip_spec} (attempt {attempt + 1}/{self.retry_count})")
                
                returncode, stdout, stderr = self._run_command(cmd)
                install_time = time.time() - start_time
                
                if returncode == 0:
                    # Verify installation
                    installed_version = self._check_package_installed(dependency.name)
                    
                    if installed_version:
                        status = InstallStatus.FALLBACK_USED if used_fallback else InstallStatus.SUCCESS
                        
                        logger.info(f"✓ Successfully installed {dependency.name} {installed_version}")
                        
                        return InstallResult(
                            dependency=dependency,
                            status=status,
                            installed_version=installed_version,
                            used_fallback=used_fallback,
                            fallback_index=i if used_fallback else -1,
                            install_time=install_time,
                            package_manager=self.package_manager
                        )
                    else:
                        error_msg = f"Installation succeeded but package not found"
                        logger.error(f"✗ {error_msg}")
                
                else:
                    error_msg = stderr or "Unknown error"
                    
                    if attempt < self.retry_count - 1:
                        logger.warning(f"Installation failed, retrying... ({error_msg[:100]})")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        logger.error(f"✗ Failed to install {dependency.name}{pip_spec}: {error_msg[:200]}")
        
        # All attempts failed
        return InstallResult(
            dependency=dependency,
            status=InstallStatus.FAILED,
            error_message=f"Failed to install {dependency.name} after trying {len(versions_to_try)} versions",
            install_time=time.time() - start_time,
            package_manager=self.package_manager
        )
    
    def _resolve_conflicts(
        self,
        dependencies: List[Dependency],
        installed: Dict[str, str]
    ) -> Tuple[List[Dependency], List[str]]:
        """
        Attempt to resolve dependency conflicts
        
        Returns:
            Tuple of (resolved_dependencies, conflict_messages)
        """
        if not self.strict_mode:
            return dependencies, []
        
        conflicts = []
        resolved = []
        
        # Simple conflict detection based on version ranges
        # In production, use a proper resolver like pip's resolver
        for dep in dependencies:
            if dep.name in installed:
                installed_version = installed[dep.name]
                
                # Check if installed version satisfies requirement
                if not self._version_satisfies(installed_version, dep.primary_version):
                    conflict_msg = (
                        f"Conflict: {dep.name} {installed_version} installed, "
                        f"but {dep.primary_version} required"
                    )
                    conflicts.append(conflict_msg)
                    
                    if dep.fallback_versions:
                        # Try to find a compatible fallback
                        for fallback in dep.fallback_versions:
                            if self._version_satisfies(installed_version, fallback):
                                # Create a new dependency with fallback as primary
                                resolved_dep = Dependency(
                                    name=dep.name,
                                    primary_version=fallback,
                                    fallback_versions=dep.fallback_versions[1:],
                                    min_version=dep.min_version,
                                    max_version=dep.max_version,
                                    source=dep.source,
                                    optional=dep.optional,
                                    groups=dep.groups
                                )
                                resolved.append(resolved_dep)
                                conflicts[-1] += f" - using fallback {fallback}"
                                break
                        else:
                            # No compatible fallback, keep original
                            resolved.append(dep)
                    else:
                        # No fallbacks, keep original
                        resolved.append(dep)
                else:
                    resolved.append(dep)
            else:
                resolved.append(dep)
        
        return resolved, conflicts
    
    def install_dependencies(
        self,
        dependencies: List[Dependency],
        extra_args: List[str] = None,
        install_optional: bool = False,
        groups: List[str] = None
    ) -> List[InstallResult]:
        """
        Install multiple dependencies with fallback support
        
        Args:
            dependencies: List of dependencies to install
            extra_args: Additional arguments for package manager
            install_optional: Whether to install optional dependencies
            groups: Specific dependency groups to install
            
        Returns:
            List of installation results
        """
        logger.info(f"Starting installation of {len(dependencies)} dependencies")
        
        # Filter dependencies
        filtered_deps = []
        for dep in dependencies:
            if not install_optional and dep.optional:
                continue
            
            if groups and not any(group in dep.groups for group in groups):
                continue
            
            filtered_deps.append(dep)
        
        logger.info(f"Installing {len(filtered_deps)} filtered dependencies")
        
        # Get currently installed packages
        self.installed_packages = {}
        for dep in filtered_deps:
            version = self._check_package_installed(dep.name)
            if version:
                self.installed_packages[dep.name] = version
        
        # Resolve conflicts
        resolved_deps, conflicts = self._resolve_conflicts(filtered_deps, self.installed_packages)
        
        if conflicts:
            logger.warning(f"Found {len(conflicts)} dependency conflicts:")
            for conflict in conflicts:
                logger.warning(f"  - {conflict}")
            
            if self.strict_mode:
                logger.error("Strict mode enabled - cannot proceed with conflicts")
                raise RuntimeError(f"Dependency conflicts detected: {conflicts}")
        
        # Install dependencies
        self.install_results = []
        for i, dep in enumerate(resolved_deps):
            logger.info(f"[{i+1}/{len(resolved_deps)}] Processing {dep.name}")
            
            result = self._install_with_fallback(dep, extra_args)
            self.install_results.append(result)
            
            if result.status == InstallStatus.SUCCESS or result.status == InstallStatus.FALLBACK_USED:
                if result.installed_version:
                    self.installed_packages[dep.name] = result.installed_version
        
        # Generate summary
        self._generate_summary()
        
        return self.install_results
    
    def _generate_summary(self):
       