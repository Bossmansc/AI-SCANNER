#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Setup configuration for the CodeCraft AI Synthesis Engine package.
This file defines package metadata, dependencies, and installation instructions.
"""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info

# Read the README file for long description
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()

# Read version from package
version_path = Path(__file__).parent / "codecraft_ai" / "version.py"
version_info = {}
if version_path.exists():
    with open(version_path, "r", encoding="utf-8") as f:
        exec(f.read(), version_info)
    __version__ = version_info.get("__version__", "0.1.0")
else:
    __version__ = "0.1.0"

# Custom installation commands for post-install setup
class PostInstallCommand(install):
    """Custom installation command to run post-install tasks."""
    def run(self):
        install.run(self)
        self._post_install()
    
    def _post_install(self):
        """Execute post-installation tasks."""
        print("\n" + "="*60)
        print("CodeCraft AI Synthesis Engine Installation Complete")
        print("="*60)
        print("\nPost-installation tasks:")
        
        # Create necessary directories
        data_dir = Path.home() / ".codecraft_ai"
        cache_dir = data_dir / "cache"
        logs_dir = data_dir / "logs"
        
        for directory in [data_dir, cache_dir, logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Created directory: {directory}")
        
        # Set permissions
        try:
            import stat
            for directory in [cache_dir, logs_dir]:
                os.chmod(directory, stat.S_IRWXU)
        except:
            pass
        
        # Create default configuration if not exists
        config_file = data_dir / "config.yaml"
        if not config_file.exists():
            default_config = """# CodeCraft AI Configuration
# Auto-generated configuration file

engine:
  # Concurrency settings
  max_workers: 10
  queue_size: 100
  timeout_seconds: 30
  
  # Synthesis settings
  token_limit: 8192
  enable_validation: true
  strict_mode: true
  
  # Cache settings
  cache_enabled: true
  cache_ttl_hours: 24
  
  # Logging settings
  log_level: "INFO"
  log_format: "detailed"
  
  # Security settings
  validate_imports: true
  sanitize_output: true
  
# Module registry
modules:
  core:
    - "manifest_parser"
    - "synthesis_engine"
    - "validation_layer"
    - "concurrency_manager"
  
  utilities:
    - "file_handler"
    - "cache_manager"
    - "logger"
    - "security"
  
  interfaces:
    - "cli"
    - "api"
    - "web"

# Path configurations
paths:
  cache_dir: "~/.codecraft_ai/cache"
  logs_dir: "~/.codecraft_ai/logs"
  templates_dir: "~/.codecraft_ai/templates"
  
# Feature flags
features:
  enable_parallel_processing: true
  enable_real_time_validation: true
  enable_performance_monitoring: true
  enable_error_recovery: true
"""
            with open(config_file, "w", encoding="utf-8") as f:
                f.write(default_config)
            print(f"  ✓ Created default configuration: {config_file}")
        
        print("\n" + "-"*60)
        print("Quick Start:")
        print("  1. Run: codecraft-ai --help")
        print("  2. Check: codecraft-ai version")
        print("  3. View config: cat ~/.codecraft_ai/config.yaml")
        print("-"*60)
        print("\nFor documentation, visit: https://github.com/codecraft-ai/docs")
        print("="*60 + "\n")

class PostDevelopCommand(develop):
    """Custom develop command for development installation."""
    def run(self):
        develop.run(self)
        print("\nDevelopment mode activated.")
        print("Package installed in editable mode.")
        print("Use 'pip install -e .' to update installation.\n")

class CustomEggInfoCommand(egg_info):
    """Custom egg_info command to include additional metadata."""
    def run(self):
        # Add custom metadata
        self.distribution.metadata.version = __version__
        self.distribution.metadata.description = "High-concurrency architectural engine for AI-powered code synthesis"
        egg_info.run(self)

# Package dependencies
install_requires = [
    # Core dependencies
    "setuptools>=68.0.0",
    "wheel>=0.40.0",
    
    # Concurrency and async
    "asyncio>=3.4.3; python_version < '3.7'",
    "aiohttp>=3.9.0",
    "aiofiles>=23.2.0",
    "concurrent-futures>=3.0.0",
    
    # Data processing and validation
    "pydantic>=2.5.0",
    "pyyaml>=6.0",
    "jsonschema>=4.20.0",
    "marshmallow>=3.20.0",
    
    # CLI and interface
    "click>=8.1.0",
    "rich>=13.7.0",
    "prompt-toolkit>=3.0.0",
    "typer>=0.9.0",
    
    # Utilities
    "python-dotenv>=1.0.0",
    "pathlib2>=2.3.0; python_version < '3.4'",
    "tqdm>=4.66.0",
    "colorama>=0.4.6",
    
    # Security
    "cryptography>=41.0.0",
    "bcrypt>=4.0.0",
    
    # Monitoring and logging
    "structlog>=23.2.0",
    "loguru>=0.7.0",
    
    # Testing (optional but recommended)
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    
    # Performance
    "uvloop>=0.19.0; sys_platform != 'win32'",
    "orjson>=3.9.0",
    
    # File handling
    "watchdog>=3.0.0",
    "filelock>=3.13.0",
]

# Development dependencies
extras_require = {
    "dev": [
        "black>=23.0.0",
        "flake8>=6.0.0",
        "mypy>=1.7.0",
        "isort>=5.12.0",
        "pre-commit>=3.5.0",
        "pytest>=7.4.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.1.0",
        "pytest-xdist>=3.5.0",
        "hypothesis>=6.88.0",
        "tox>=4.11.0",
        "coverage>=7.3.0",
        "sphinx>=7.2.0",
        "sphinx-rtd-theme>=1.3.0",
    ],
    "docs": [
        "sphinx>=7.2.0",
        "sphinx-rtd-theme>=1.3.0",
        "sphinx-autodoc-typehints>=2.0.0",
        "myst-parser>=2.0.0",
        "sphinx-copybutton>=0.5.0",
    ],
    "performance": [
        "uvloop>=0.19.0; sys_platform != 'win32'",
        "orjson>=3.9.0",
        "ujson>=5.8.0",
        "psutil>=5.9.0",
        "py-spy>=0.3.0",
    ],
    "security": [
        "bandit>=1.7.0",
        "safety>=2.3.0",
        "semgrep>=1.0.0",
    ],
    "all": [
        "black>=23.0.0",
        "flake8>=6.0.0",
        "mypy>=1.7.0",
        "sphinx>=7.2.0",
        "uvloop>=0.19.0; sys_platform != 'win32'",
        "orjson>=3.9.0",
        "bandit>=1.7.0",
    ],
}

# Entry points for CLI
entry_points = {
    "console_scripts": [
        "codecraft-ai = codecraft_ai.cli.main:cli",
        "ccai = codecraft_ai.cli.main:cli",  # Short alias
        "codecraft-synthesize = codecraft_ai.cli.synthesize:main",
        "codecraft-validate = codecraft_ai.cli.validate:main",
        "codecraft-manifest = codecraft_ai.cli.manifest:main",
    ],
}

# Package classifiers
classifiers = [
    # Development Status
    "Development Status :: 4 - Beta",
    
    # Intended Audience
    "Intended Audience :: Developers",
    "Intended Audience :: Science/Research",
    "Intended Audience :: Information Technology",
    
    # Topics
    "Topic :: Software Development",
    "Topic :: Software Development :: Build Tools",
    "Topic :: Software Development :: Code Generators",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    
    # License
    "License :: OSI Approved :: MIT License",
    
    # Programming Languages
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: Implementation :: CPython",
    "Programming Language :: Python :: Implementation :: PyPy",
    
    # Operating Systems
    "Operating System :: OS Independent",
    "Operating System :: POSIX",
    "Operating System :: Unix",
    "Operating System :: MacOS",
    "Operating System :: Microsoft :: Windows",
    
    # Framework
    "Framework :: AsyncIO",
    
    # Additional metadata
    "Natural Language :: English",
    "Environment :: Console",
    "Environment :: Web Environment",
]

# Setup configuration
setup(
    # Basic information
    name="codecraft-ai",
    version=__version__,
    author="CodeCraft AI Team",
    author_email="team@codecraft.ai",
    maintainer="CodeCraft AI Maintainers",
    maintainer_email="maintainers@codecraft.ai",
    
    # Description
    description="High-concurrency architectural engine for AI-powered code synthesis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    
    # URLs
    url="https://github.com/codecraft-ai/codecraft-engine",
    project_urls={
        "Homepage": "https://codecraft.ai",
        "Documentation": "https://docs.codecraft.ai",
        "Repository": "https://github.com/codecraft-ai/codecraft-engine",
        "Changelog": "https://github.com/codecraft-ai/codecraft-engine/releases",
        "Issue Tracker": "https://github.com/codecraft-ai/codecraft-engine/issues",
        "Discussion": "https://github.com/codecraft-ai/codecraft-engine/discussions",
    },
    
    # License
    license="MIT",
    license_files=["LICENSE"],
    
    # Package discovery
    packages=find_packages(
        include=["codecraft_ai", "codecraft_ai.*"],
        exclude=["tests", "tests.*", "docs", "docs.*", "examples", "examples.*"],
    ),
    
    # Include package data
    include_package_data=True,
    package_data={
        "codecraft_ai": [
            "py.typed",
            "templates/*.j2",
            "templates/*.yaml",
            "templates/*.json",
            "schemas/*.json",
            "schemas/*.yaml",
            "data/*.json",
            "data/*.yaml",
        ],
    },
    
    # Dependencies
    install_requires=install_requires,
    extras_require=extras_require,
    python_requires=">=3.8",
    
    # Entry points
    entry_points=entry_points,
    
    # Classifiers
    classifiers=classifiers,
    
    # Keywords
    keywords=[
        "ai",
        "code-generation",
        "synthesis",
        "architecture",
        "concurrency",
        "development",
        "automation",
        "productivity",
        "engine",
        "manifest",
        "blueprint",
    ],
    
    # Custom commands
    cmdclass={
        "install": PostInstallCommand,
        "develop": PostDevelopCommand,
        "egg_info": CustomEggInfoCommand,
    },
    
    # Additional metadata
    platforms=["any"],
    zip_safe=False,
    
    # Security considerations
    provides=["codecraft_ai"],
    
    # Download URL
    download_url=f"https://github.com/codecraft-ai/codecraft-engine/archive/v{__version__}.tar.gz",
    
    # Options
    options={
        "bdist_wheel": {
            "universal": False,
        },
        "egg_info": {
            "tag_build": "",
            "tag_date": False,
        },
    },
    
    # Test suite
    test_suite="tests",
    
    # Data files
    data_files=[
        ("share/doc/codecraft-ai", ["README.md", "CHANGELOG.md", "CONTRIBUTING.md"]),
        ("share/licenses/codecraft-ai", ["LICENSE"]),
        ("share/codecraft-ai/examples", ["examples/basic_manifest.json", "examples/advanced_manifest.yaml"]),
    ],
)

# Post-setup validation
if __name__ == "__main__":
    # Validate Python version
    if sys.version_info < (3, 8):
        print("ERROR: CodeCraft AI requires Python 3.8 or higher")
        print(f"Current Python version: {sys.version}")
        sys.exit(1)
    
    # Check for required system dependencies
    try:
        import ssl
        import hashlib
        import json
    except ImportError as e:
        print(f"ERROR: Missing required system module: {e}")
        sys.exit(1)
    
    print(f"CodeCraft AI {__version__} setup configuration validated successfully.")
