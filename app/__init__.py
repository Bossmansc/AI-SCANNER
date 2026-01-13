"""
CodeCraft AI - High-Concurrency Architectural Engine
Root Package Initialization

This module marks the 'app' directory as a Python package and handles
top-level package metadata and resolution strategies.

Purpose:
    - Initialize package namespace.
    - Define semantic versioning.
    - Expose package-level constants.
"""

import os
import sys
import logging

# -----------------------------------------------------------------------------
# Package Metadata
# -----------------------------------------------------------------------------

__version__ = "1.0.0-alpha"
__author__ = "CodeCraft AI"
__license__ = "Proprietary"
__app_name__ = "High-Concurrency Architectural Engine"

# -----------------------------------------------------------------------------
# Environment & Path Configuration
# -----------------------------------------------------------------------------

# Ensure the current directory is in the python path to resolve sibling modules
# correctly in complex deployment environments (e.g., Docker, Lambda).
current_path = os.path.dirname(os.path.abspath(__file__))
if current_path not in sys.path:
    sys.path.append(current_path)

# -----------------------------------------------------------------------------
# Logging Initialization (Bootstrap)
# -----------------------------------------------------------------------------

# Set a default null handler to prevent "No handler found" warnings
# if the consuming application does not configure logging.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# -----------------------------------------------------------------------------
# Export Control
# -----------------------------------------------------------------------------

# Explicitly define what is available when doing `from app import *`
# Currently empty to encourage explicit sub-module imports for clarity
# and to avoid circular dependency issues during initialization.
__all__ = [
    "__version__",
    "__app_name__",
]
