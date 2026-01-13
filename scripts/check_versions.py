#!/usr/bin/env python3
"""
Version Compatibility Checker for Python Packages

This module provides comprehensive version checking for Python packages,
including compatibility validation, dependency resolution analysis, and
environment verification. It supports multiple package sources (PyPI, conda,
local) and generates detailed compatibility reports.

Features:
- Multi-source package version checking
- Semantic version compatibility analysis
- Dependency conflict detection
- Environment snapshot and comparison
- Support for version specifiers (==, >=, <=, ~=, !=)
- Cross-platform compatibility
- Detailed reporting in multiple formats (JSON, YAML, Markdown)
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import warnings
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from packaging import version
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
import yaml
try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PackageSource(Enum):
    """Enumeration of package sources."""
    PYPI = "pypi"
    CONDA = "conda"
    LOCAL = "local"
    GIT = "git"
    UNKNOWN = "unknown"


class CompatibilityStatus(Enum):
    """Enumeration of compatibility statuses."""
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"
    WARNING = "warning"


@dataclass
class PackageInfo:
    """Data class representing package information."""
    name: str
    version: str
    source: PackageSource
    required_version: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    location: Optional[str] = None
    summary: Optional[str] = None
    
    def __post_init__(self):
        """Validate and normalize package info."""
        self.name = self.name.lower().strip()
        if self.version:
            self.version = self.version.strip()
        if self.required_version:
            self.required_version = self.required_version.strip()
    
    @property
    def parsed_version(self) -> version.Version:
        """Get parsed version object."""
        try:
            return version.parse(self.version) if self.version else version.parse("0.0.0")
        except version.InvalidVersion:
            return version.parse("0.0.0")
    
    @property
    def is_installed(self) -> bool:
        """Check if package is installed."""
        return self.version != "0.0.0" and self.source != PackageSource.UNKNOWN


@dataclass
class CompatibilityResult:
    """Data class representing compatibility check result."""
    package: PackageInfo
    status: CompatibilityStatus
    message: str
    required_specifier: Optional[str] = None
    installed_version: Optional[str] = None
    available_versions: List[str] = field(default_factory=list)
    conflicts: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['package'] = asdict(self.package)
        result['status'] = self.status.value
        result['package']['source'] = self.package.source.value
        return result


class VersionChecker:
    """Main version checker class."""
    
    def __init__(self, python_path: Optional[str] = None):
        """
        Initialize version checker.
        
        Args:
            python_path: Path to Python interpreter (default: sys.executable)
        """
        self.python_path = python_path or sys.executable
        self.packages: Dict[str, PackageInfo] = {}
        self.results: List[CompatibilityResult] = []
        self.environment_info: Dict[str, Any] = {}
        
    def load_environment(self) -> Dict[str, PackageInfo]:
        """
        Load all installed packages from current environment.
        
        Returns:
            Dictionary of package name to PackageInfo
        """
        logger.info("Loading environment packages...")
        
        try:
            # Use pip list to get installed packages
            result = subprocess.run(
                [self.python_path, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True
            )
            
            packages_data = json.loads(result.stdout)
            
            for pkg in packages_data:
                package_info = PackageInfo(
                    name=pkg['name'],
                    version=pkg['version'],
                    source=PackageSource.PYPI,
                    location=self._get_package_location(pkg['name'])
                )
                self.packages[pkg['name'].lower()] = package_info
                
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load packages via pip: {e}")
            # Fallback to pkg_resources
            self._load_packages_fallback()
        
        # Load conda packages if in conda environment
        self._load_conda_packages()
        
        logger.info(f"Loaded {len(self.packages)} packages from environment")
        return self.packages
    
    def _load_packages_fallback(self) -> None:
        """Fallback method to load packages using pkg_resources."""
        try:
            import pkg_resources
            
            for dist in pkg_resources.working_set:
                package_info = PackageInfo(
                    name=dist.project_name,
                    version=dist.version,
                    source=PackageSource.PYPI,
                    location=dist.location
                )
                self.packages[dist.project_name.lower()] = package_info
                
        except ImportError:
            logger.error("Cannot load packages: pkg_resources not available")
    
    def _load_conda_packages(self) -> None:
        """Load conda packages if in conda environment."""
        conda_env = os.environ.get('CONDA_DEFAULT_ENV')
        if not conda_env:
            return
            
        try:
            result = subprocess.run(
                ['conda', 'list', '--json'],
                capture_output=True,
                text=True,
                check=True
            )
            
            conda_packages = json.loads(result.stdout)
            
            for pkg in conda_packages:
                package_info = PackageInfo(
                    name=pkg['name'],
                    version=pkg['version'],
                    source=PackageSource.CONDA,
                    location=None
                )
                self.packages[pkg['name'].lower()] = package_info
                
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
            pass  # Not a conda environment or conda not available
    
    def _get_package_location(self, package_name: str) -> Optional[str]:
        """Get installation location of a package."""
        try:
            result = subprocess.run(
                [self.python_path, "-m", "pip", "show", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.split('\n'):
                if line.startswith('Location:'):
                    return line.split(':', 1)[1].strip()
                    
        except subprocess.CalledProcessError:
            pass
            
        return None
    
    def load_requirements(self, requirements_file: str) -> Dict[str, str]:
        """
        Load requirements from a file.
        
        Args:
            requirements_file: Path to requirements file
            
        Returns:
            Dictionary of package name to version specifier
        """
        requirements = {}
        file_path = Path(requirements_file)
        
        if not file_path.exists():
            logger.error(f"Requirements file not found: {requirements_file}")
            return requirements
        
        logger.info(f"Loading requirements from {requirements_file}")
        
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                try:
                    req = Requirement(line)
                    requirements[req.name.lower()] = str(req.specifier) if req.specifier else ""
                except Exception as e:
                    logger.warning(f"Line {line_num}: Could not parse requirement '{line}': {e}")
        
        logger.info(f"Loaded {len(requirements)} requirements")
        return requirements
    
    def load_pyproject(self, pyproject_file: str) -> Dict[str, str]:
        """
        Load dependencies from pyproject.toml.
        
        Args:
            pyproject_file: Path to pyproject.toml
            
        Returns:
            Dictionary of package name to version specifier
        """
        requirements = {}
        file_path = Path(pyproject_file)
        
        if not file_path.exists():
            logger.error(f"pyproject.toml not found: {pyproject_file}")
            return requirements
        
        logger.info(f"Loading dependencies from {pyproject_file}")
        
        try:
            with open(file_path, 'rb') as f:
                data = tomllib.load(f)
            
            # Check for dependencies in various sections
            project_deps = data.get('project', {}).get('dependencies', [])
            tool_poetry_deps = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
            
            deps_to_process = []
            
            if project_deps:
                deps_to_process.extend(project_deps)
            
            if tool_poetry_deps:
                for dep, spec in tool_poetry_deps.items():
                    if dep.lower() != 'python':
                        if isinstance(spec, dict):
                            spec_str = spec.get('version', '')
                        else:
                            spec_str = str(spec)
                        deps_to_process.append(f"{dep}{spec_str}")
            
            for dep in deps_to_process:
                try:
                    req = Requirement(dep)
                    requirements[req.name.lower()] = str(req.specifier) if req.specifier else ""
                except Exception as e:
                    logger.warning(f"Could not parse dependency '{dep}': {e}")
                    
        except Exception as e:
            logger.error(f"Failed to parse pyproject.toml: {e}")
        
        logger.info(f"Loaded {len(requirements)} dependencies from pyproject.toml")
        return requirements
    
    def check_compatibility(self, 
                           requirements: Dict[str, str],
                           check_dependencies: bool = False) -> List[CompatibilityResult]:
        """
        Check compatibility between installed packages and requirements.
        
        Args:
            requirements: Dictionary of package name to version specifier
            check_dependencies: Whether to check transitive dependencies
            
        Returns:
            List of compatibility results
        """
        logger.info(f"Checking compatibility for {len(requirements)} packages")
        self.results = []
        
        # Ensure environment is loaded
        if not self.packages:
            self.load_environment()
        
        # Check direct requirements
        for pkg_name, specifier_str in requirements.items():
            result = self._check_single_package(pkg_name, specifier_str)
            self.results.append(result)
        
        # Check dependency conflicts if requested
        if check_dependencies:
            self._check_dependency_conflicts()
        
        return self.results
    
    def _check_single_package(self, 
                             pkg_name: str, 
                             specifier_str: str) -> CompatibilityResult:
        """
        Check compatibility for a single package.
        
        Args:
            pkg_name: Package name
            specifier_str: Version specifier string
            
        Returns:
            CompatibilityResult object
        """
        installed_pkg = self.packages.get(pkg_name.lower())
        
        if not installed_pkg:
            # Package not installed
            return CompatibilityResult(
                package=PackageInfo(
                    name=pkg_name,
                    version="0.0.0",
                    source=PackageSource.UNKNOWN
                ),
                status=CompatibilityStatus.INCOMPATIBLE,
                message=f"Package '{pkg_name}' is not installed",
                required_specifier=specifier_str,
                installed_version=None,
                available_versions=self._get_available_versions(pkg_name)
            )
        
        if not specifier_str:
            # No version requirement specified
            return CompatibilityResult(
                package=installed_pkg,
                status=CompatibilityStatus.COMPATIBLE,
                message=f"Package '{pkg_name}' is installed (no version requirement)",
                required_specifier=None,
                installed_version=installed_pkg.version
            )
        
        try:
            specifier = SpecifierSet(specifier_str)
            
            if specifier.contains(installed_pkg.version):
                # Version is compatible
                return CompatibilityResult(
                    package=installed_pkg,
                    status=CompatibilityStatus.COMPATIBLE,
                    message=f"Package '{pkg_name}' version {installed_pkg.version} satisfies requirement '{specifier_str}'",
                    required_specifier=specifier_str,
                    installed_version=installed_pkg.version
                )
            else:
                # Version is incompatible
                return CompatibilityResult(
                    package=installed_pkg,
                    status=CompatibilityStatus.INCOMPATIBLE,
                    message=f"Package '{pkg_name}' version {installed_pkg.version} does not satisfy requirement '{specifier_str}'",
                    required_specifier=specifier_str,
                    installed_version=installed_pkg.version,
                    available_versions=self._get_available_versions(pkg_name)
                )
                
        except Exception as e:
            # Error parsing specifier
            return CompatibilityResult(
                package=installed_pkg,
                status=CompatibilityStatus.UNKNOWN,
                message=f"Error checking compatibility for '{pkg_name}': {e}",
                required_specifier=specifier_str,
                installed_version=installed_pkg.version
            )
    
    def _get_available_versions(self, pkg_name: str) -> List[str]:
        """
        Get available versions from PyPI.
        
        Args:
            pkg_name: Package name
            
        Returns:
            List of available version strings
        """
        try:
            import requests
            
            response = requests.get(
                f"https://pypi.org/pypi/{pkg_name}/json",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return list(data.get('releases', {}).keys())
                
        except Exception as e:
            logger.debug(f"Could not fetch versions for {pkg_name}: {e}")
        
        return []
    
    def _check_dependency_conflicts(self) -> None:
        """Check for dependency conflicts between installed packages."""
        logger.info("Checking for dependency conflicts...")
        
        # Build dependency graph
        dependency_graph = defaultdict(set)
        
        for pkg_name, pkg_info in self.packages.items():
            try:
                # Get package dependencies
                result = subprocess.run(
                    [self.python_path, "-m", "pip", "show", pkg_name],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                for line in result.stdout.split('\n'):
                    if line.startswith('Requires:'):
                        deps = line.split(':', 1)[1].strip()
                        if deps:
                            for dep in deps.split(','):
                                dep_name = dep.strip().lower()
                                if dep_name:
                                    dependency_graph[pkg_name].add(dep_name)
                                    
            except subprocess.CalledProcessError:
                continue
        
        # Check for conflicts
        for result in self.results:
            if result.status == CompatibilityStatus.COMPATIBLE:
                conflicts = self._find_conflicts_for_package(
                    result.package.name,
                    dependency_graph
                )
                if conflicts:
                    result.status = CompatibilityStatus.CONFLICT
                    result.message = f"Package '{result.package.name}' has dependency conflicts"
                    result.conflicts = conflicts
    
    def _find_conflicts_for_package(self, 
                                   pkg_name: str,
                                   dependency_graph: Dict[str, Set[str]]) -> List[Dict[str, str]]:
        """
        Find dependency conflicts for a package.
        
        Args:
            pkg_name: Package name
            dependency_graph: Dependency graph
            
        Returns:
            List of conflict descriptions
        """
        conflicts = []
        visited = set()
        
        def dfs(current_pkg, path):
            if current_pkg in visited:
                return
            
            visited.add(current_pkg)
            
            for dep in dependency_graph.get(current_pkg, []):
                if dep in path:
                    # Circular dependency detected
                    conflicts.append({
                        'type': 'circular',
                        'path': ' -> '.join(path + [dep]),
                        'package': pkg_name
                    })
                else:
                    dfs(dep, path + [dep])
        
        dfs(pkg_name, [pkg_name])
        return conflicts
    
    def generate_report(self, 
                       format: str = "text",
                       output_file: Optional[str] = None) -> str:
        """
        Generate compatibility report.
        
        Args:
            format: Output format (text, json, yaml, markdown)
            output_file: Optional file to write report to
            
        Returns:
            Report as string
        """
        if format == "json":
            report = self._generate_json_report()
        elif format == "yaml":
            report = self._generate_yaml_report()
        elif format == "markdown":
            report = self._generate_markdown_report()
        else:
            report = self._generate_text_report()
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            logger.info(f"Report written to {output_file}")
        
        return report
    
    def _generate_text_report(self) -> str:
        """Generate text format report."""
        lines = []
        lines.append("=" * 80)
        lines.append("PYTHON PACKAGE COMPATIBILITY REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append(f"Python: {sys.version}")
        lines.append(f"Platform: {sys.platform}")
        lines.append("")
        
        # Summary
        total = len(self.results)
        compatible = sum(1 for r in self.results if r.status == CompatibilityStatus.COMPATIBLE)
        incompatible = sum(1 for r in self.results if r.status == CompatibilityStatus.INCOMPATIBLE)
        conflicts = sum(1 for r in self.results if r.status == CompatibilityStatus.CONFLICT)
        unknown = sum(1 for r in self.results if