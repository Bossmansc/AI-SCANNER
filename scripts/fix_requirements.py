#!/usr/bin/env python3
"""
Requirements.txt Fixer and Validator

This script cleans, validates, and optimizes Python requirements.txt files.
It performs the following operations:
1. Removes duplicate packages
2. Sorts packages alphabetically (with optional comments preserved)
3. Validates package names and versions via PyPI API
4. Pins versions to latest compatible releases
5. Removes unused/obsolete packages by analyzing imports
6. Outputs a clean, production-ready requirements.txt

Usage:
    python scripts/fix_requirements.py [input_file] [options]

Examples:
    python scripts/fix_requirements.py requirements.txt
    python scripts/fix_requirements.py requirements.txt --output requirements_clean.txt
    python scripts/fix_requirements.py requirements.txt --validate-only
    python scripts/fix_requirements.py requirements.txt --analyze-imports /path/to/project
"""

import argparse
import re
import sys
import os
import subprocess
import json
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass
from enum import Enum
import urllib.request
import urllib.error
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RequirementType(Enum):
    """Types of requirements lines."""
    PACKAGE = "package"
    COMMENT = "comment"
    EMPTY = "empty"
    INDEX_URL = "index_url"
    EXTRA_INDEX = "extra_index"
    TRUSTED_HOST = "trusted_host"
    OPTION = "option"
    CONSTRAINT = "constraint"
    EDITABLE = "editable"


@dataclass
class Requirement:
    """Represents a parsed requirement line."""
    original: str
    cleaned: str
    line_type: RequirementType
    package_name: Optional[str] = None
    version_spec: Optional[str] = None
    extras: Optional[List[str]] = None
    markers: Optional[str] = None
    hash_options: Optional[List[str]] = None
    index_url: Optional[str] = None
    trusted_host: Optional[str] = None
    comment: Optional[str] = None
    line_number: int = 0


class RequirementsFixer:
    """Main class for fixing and validating requirements.txt files."""
    
    # Regex patterns for parsing requirements
    PACKAGE_PATTERN = re.compile(
        r'^(?P<editable>-e\s+)?'
        r'(?P<package>[a-zA-Z0-9][a-zA-Z0-9._-]*)'
        r'(?P<extras>\[[^\]]+\])?'
        r'(?P<version_spec>\s*(?:[=<>!~]=?|===)\s*[^;\s]+)?'
        r'(?P<markers>\s*;\s*[^#]+)?'
        r'(?P<hash_options>\s*--hash=[^#\s]+(?:\s+--hash=[^#\s]+)*)?'
        r'(?P<comment>\s*#.*)?$'
    )
    
    INDEX_URL_PATTERN = re.compile(r'^-i\s+|^--index-url\s+', re.IGNORECASE)
    EXTRA_INDEX_PATTERN = re.compile(r'^--extra-index-url\s+', re.IGNORECASE)
    TRUSTED_HOST_PATTERN = re.compile(r'^--trusted-host\s+', re.IGNORECASE)
    OPTION_PATTERN = re.compile(r'^--(?!hash|index-url|extra-index-url|trusted-host)')
    CONSTRAINT_PATTERN = re.compile(r'^-c\s+|^--constraint\s+', re.IGNORECASE)
    
    # PyPI API endpoints
    PYPI_API_URL = "https://pypi.org/pypi/{package}/json"
    PYPI_SEARCH_URL = "https://pypi.org/search/?q={query}"
    
    def __init__(self, input_file: str, output_file: Optional[str] = None):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file) if output_file else self.input_file
        self.requirements: List[Requirement] = []
        self.package_versions: Dict[str, str] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def parse_file(self) -> bool:
        """Parse the requirements.txt file."""
        if not self.input_file.exists():
            self.errors.append(f"Input file not found: {self.input_file}")
            return False
            
        logger.info(f"Parsing {self.input_file}")
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines, 1):
            requirement = self._parse_line(line.strip(), i)
            self.requirements.append(requirement)
            
        logger.info(f"Parsed {len(self.requirements)} lines")
        return True
        
    def _parse_line(self, line: str, line_number: int) -> Requirement:
        """Parse a single line from requirements.txt."""
        original = line
        
        # Check for empty lines
        if not line or line.isspace():
            return Requirement(original, line, RequirementType.EMPTY, line_number=line_number)
            
        # Check for comments
        if line.startswith('#'):
            return Requirement(original, line, RequirementType.COMMENT, comment=line, line_number=line_number)
            
        # Check for index URLs
        if self.INDEX_URL_PATTERN.match(line):
            url = self.INDEX_URL_PATTERN.sub('', line).strip()
            return Requirement(original, line, RequirementType.INDEX_URL, index_url=url, line_number=line_number)
            
        # Check for extra index URLs
        if self.EXTRA_INDEX_PATTERN.match(line):
            url = self.EXTRA_INDEX_PATTERN.sub('', line).strip()
            return Requirement(original, line, RequirementType.EXTRA_INDEX, index_url=url, line_number=line_number)
            
        # Check for trusted hosts
        if self.TRUSTED_HOST_PATTERN.match(line):
            host = self.TRUSTED_HOST_PATTERN.sub('', line).strip()
            return Requirement(original, line, RequirementType.TRUSTED_HOST, trusted_host=host, line_number=line_number)
            
        # Check for constraints
        if self.CONSTRAINT_PATTERN.match(line):
            constraint = self.CONSTRAINT_PATTERN.sub('', line).strip()
            return Requirement(original, line, RequirementType.CONSTRAINT, comment=constraint, line_number=line_number)
            
        # Check for other options
        if self.OPTION_PATTERN.match(line):
            return Requirement(original, line, RequirementType.OPTION, line_number=line_number)
            
        # Try to parse as a package
        match = self.PACKAGE_PATTERN.match(line)
        if match:
            groups = match.groupdict()
            package_name = groups['package']
            
            # Handle editable packages
            if groups['editable']:
                line_type = RequirementType.EDITABLE
                # Extract package name from path for editable installs
                if '/' in package_name or '\\' in package_name:
                    # Try to get package name from setup.py or pyproject.toml
                    package_name = self._extract_package_name_from_path(package_name)
            else:
                line_type = RequirementType.PACKAGE
                
            # Parse extras
            extras = None
            if groups['extras']:
                extras_text = groups['extras'][1:-1]  # Remove brackets
                extras = [extra.strip() for extra in extras_text.split(',')]
                
            # Parse markers
            markers = groups['markers'].strip() if groups['markers'] else None
            
            # Parse hash options
            hash_options = None
            if groups['hash_options']:
                hash_options = [h.strip() for h in groups['hash_options'].split() if h.startswith('--hash=')]
                
            # Parse comment
            comment = groups['comment'].strip() if groups['comment'] else None
            
            # Clean version (remove extra spaces)
            version_spec = groups['version_spec'].strip() if groups['version_spec'] else None
            if version_spec:
                version_spec = re.sub(r'\s+', ' ', version_spec)
                
            # Create cleaned version
            cleaned_parts = []
            if groups['editable']:
                cleaned_parts.append('-e')
            cleaned_parts.append(package_name)
            if extras:
                cleaned_parts.append(f"[{','.join(extras)}]")
            if version_spec:
                cleaned_parts.append(version_spec)
            if markers:
                cleaned_parts.append(f";{markers}")
            if hash_options:
                cleaned_parts.extend(hash_options)
            if comment:
                cleaned_parts.append(comment)
                
            cleaned = ' '.join(cleaned_parts)
            
            return Requirement(
                original=original,
                cleaned=cleaned,
                line_type=line_type,
                package_name=package_name,
                version_spec=version_spec,
                extras=extras,
                markers=markers,
                hash_options=hash_options,
                comment=comment,
                line_number=line_number
            )
            
        # If we get here, it's an unparseable line - treat as comment
        self.warnings.append(f"Line {line_number}: Could not parse line, treating as comment: {line}")
        return Requirement(original, f"# {line}", RequirementType.COMMENT, comment=line, line_number=line_number)
        
    def _extract_package_name_from_path(self, path: str) -> str:
        """Extract package name from a local path for editable installs."""
        path_obj = Path(path)
        
        # Check for setup.py
        setup_py = path_obj / "setup.py"
        if setup_py.exists():
            try:
                with open(setup_py, 'r') as f:
                    content = f.read()
                    # Simple regex to find name in setup()
                    name_match = re.search(r'name\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                    if name_match:
                        return name_match.group(1)
            except Exception:
                pass
                
        # Check for pyproject.toml
        pyproject_toml = path_obj / "pyproject.toml"
        if pyproject_toml.exists():
            try:
                with open(pyproject_toml, 'r') as f:
                    content = f.read()
                    # Simple regex to find project.name
                    name_match = re.search(r'name\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                    if name_match:
                        return name_match.group(1)
            except Exception:
                pass
                
        # Fallback to directory name
        return path_obj.name
        
    def validate_packages(self, max_workers: int = 10) -> bool:
        """Validate packages against PyPI API."""
        packages = [req for req in self.requirements if req.line_type == RequirementType.PACKAGE]
        
        if not packages:
            logger.info("No packages to validate")
            return True
            
        logger.info(f"Validating {len(packages)} packages against PyPI...")
        
        # Use ThreadPoolExecutor for concurrent validation
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._validate_package, req.package_name): req 
                for req in packages if req.package_name
            }
            
            for future in as_completed(futures):
                req = futures[future]
                try:
                    result = future.result()
                    if result:
                        latest_version, is_valid = result
                        if is_valid:
                            self.package_versions[req.package_name] = latest_version
                        else:
                            self.errors.append(f"Package not found on PyPI: {req.package_name}")
                    else:
                        self.warnings.append(f"Could not validate package: {req.package_name}")
                except Exception as e:
                    self.warnings.append(f"Error validating {req.package_name}: {str(e)}")
                    
        return len(self.errors) == 0
        
    def _validate_package(self, package_name: str) -> Optional[Tuple[str, bool]]:
        """Validate a single package against PyPI."""
        try:
            url = self.PYPI_API_URL.format(package=package_name.lower())
            request = urllib.request.Request(url, headers={'User-Agent': 'RequirementsFixer/1.0'})
            
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            if 'info' in data and 'version' in data['info']:
                latest_version = data['info']['version']
                return (latest_version, True)
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return (None, False)
            else:
                logger.warning(f"HTTP error for {package_name}: {e.code}")
        except Exception as e:
            logger.warning(f"Error validating {package_name}: {str(e)}")
            
        return None
        
    def remove_duplicates(self) -> None:
        """Remove duplicate package entries."""
        seen_packages: Set[str] = set()
        unique_requirements: List[Requirement] = []
        
        for req in self.requirements:
            if req.line_type == RequirementType.PACKAGE and req.package_name:
                if req.package_name.lower() in seen_packages:
                    self.warnings.append(f"Removed duplicate package: {req.package_name}")
                    continue
                seen_packages.add(req.package_name.lower())
            unique_requirements.append(req)
            
        removed_count = len(self.requirements) - len(unique_requirements)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate packages")
            self.requirements = unique_requirements
            
    def sort_packages(self) -> None:
        """Sort package entries alphabetically while preserving structure."""
        # Separate packages from other lines
        packages: List[Requirement] = []
        other_lines: List[Requirement] = []
        
        for req in self.requirements:
            if req.line_type == RequirementType.PACKAGE:
                packages.append(req)
            else:
                other_lines.append(req)
                
        # Sort packages by package name (case-insensitive)
        packages.sort(key=lambda x: (x.package_name or '').lower())
        
        # Reconstruct requirements list
        self.requirements = other_lines + packages
        
    def pin_versions(self, update_to_latest: bool = False) -> None:
        """Pin package versions to latest compatible releases."""
        if not self.package_versions:
            logger.warning("No package version data available. Run validation first.")
            return
            
        for req in self.requirements:
            if req.line_type == RequirementType.PACKAGE and req.package_name:
                package_lower = req.package_name.lower()
                if package_lower in self.package_versions:
                    latest_version = self.package_versions[package_lower]
                    
                    if update_to_latest:
                        # Update to latest version
                        new_version_spec = f"=={latest_version}"
                    else:
                        # Keep existing spec but ensure it's pinned if not already
                        if not req.version_spec or '==' not in req.version_spec:
                            new_version_spec = f"=={latest_version}"
                        else:
                            # Keep existing version spec
                            continue
                            
                    # Update the requirement
                    req.version_spec = new_version_spec
                    
                    # Reconstruct cleaned line
                    cleaned_parts = [req.package_name]
                    if req.extras:
                        cleaned_parts.append(f"[{','.join(req.extras)}]")
                    cleaned_parts.append(new_version_spec)
                    if req.markers:
                        cleaned_parts.append(f";{req.markers}")
                    if req.hash_options:
                        cleaned_parts.extend(req.hash_options)
                    if req.comment:
                        cleaned_parts.append(req.comment)
                        
                    req.cleaned = ' '.join(cleaned_parts)
                    
    def analyze_imports(self, project_path: str) -> Dict[str, Set[str]]:
        """Analyze Python files to find used imports."""
        project_dir = Path(project_path)
        if not project_dir.exists():
            self.errors.append(f"Project path not found: {project_path}")
            return {}
            
        logger.info(f"Analyzing imports in {project_path}")
        
        # Find all Python files
        python_files = list(project_dir.rglob("*.py"))
        
        if not python_files:
            self.warnings.append(f"No Python files found in {project_path}")
            return {}
            
        import_patterns = [
            re.compile(r'^\s*import\s+([a-zA-Z0-9_]+(?:\s*,\s*[a-zA-Z0-9_]+)*)'),
            re.compile(r'^\s*from\s+([a-zA-Z0-9_.]+)\s+import'),
        ]
        
        used_packages: Set[str] = set()
        module_to_package: Dict[str, str] = {}
        
        # First, build a mapping of module names to package names
        for req in self.requirements:
            if req.line_type == RequirementType.PACKAGE and req.package_name:
                # For common packages, module name often equals package name
                module_to_package[req.package_name.lower()] = req.package_name
                # Also add common variations
                module_to_package[req.package_name.replace('-', '_').lower()] = req.package_name
                
        # Common module to package mappings
        common_mappings = {
            'yaml': 'pyyaml',
            'dateutil': 'python-dateutil',
            'pil': 'pillow',
            'sklearn': 'scikit-learn',
            'bs4': 'beautifulsoup4',
            'cv2': 'opencv-python',
        }
        module_to_package.update(common_mappings)
        
        # Analyze each Python file
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8