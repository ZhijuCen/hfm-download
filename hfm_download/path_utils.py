"""
Path safety validation utilities.
Ensures all file operations stay within the current working directory.
"""

import os
from pathlib import Path
from .exceptions import PathTraversalError


def validate_safe_path(path: str, cwd: str) -> Path:
    """
    Validate that a path stays within the current working directory.
    
    For relative paths: joins with cwd first, then resolves.
    For absolute paths: resolves directly.
    
    Args:
        path: The path to validate (relative or absolute)
        cwd: The current working directory (absolute path)
    
    Returns:
        Absolute Path object
    
    Raises:
        PathTraversalError: If path would escape cwd
    """
    abs_cwd = Path(cwd).resolve()
    
    # Handle absolute vs relative paths
    path_obj = Path(path)
    if path_obj.is_absolute():
        # Absolute path - resolve directly
        abs_path = path_obj.resolve()
    else:
        # Relative path - join with cwd first, then resolve
        # This prevents .. traversal from escaping cwd
        abs_path = (abs_cwd / path_obj).resolve()
    
    # Check if the resolved path is under cwd
    try:
        abs_path.relative_to(abs_cwd)
    except ValueError:
        raise PathTraversalError(
            f"Path '{path}' escapes current working directory '{cwd}'. "
            f"Only paths within '{cwd}' are allowed."
        )
    
    return abs_path


def validate_subdir_exists(subdir: str, cwd: str) -> Path:
    """
    Validate that a subdirectory exists within cwd.
    
    Args:
        subdir: Subdirectory name/path. '.' means current directory itself.
        cwd: Current working directory
    
    Returns:
        Absolute Path to the subdirectory
    
    Raises:
        PathTraversalError: If subdir doesn't exist or escapes cwd
    """
    abs_cwd = Path(cwd).resolve()
    
    # Special case: '.' means current directory
    if subdir == '.':
        if not abs_cwd.is_dir():
            raise PathTraversalError(
                f"Current working directory '{cwd}' is not a valid directory."
            )
        return abs_cwd
    
    # Empty or whitespace-only key is invalid
    if not subdir or not subdir.strip():
        raise PathTraversalError(
            f"Subdirectory key cannot be empty."
        )
    
    # General case: join with cwd then resolve
    abs_subdir = (abs_cwd / subdir).resolve()
    
    # Check it's within cwd
    try:
        abs_subdir.relative_to(abs_cwd)
    except ValueError:
        raise PathTraversalError(
            f"Subdirectory '{subdir}' escapes current working directory '{cwd}'."
        )
    
    # Check ALL intermediate directories exist
    current = abs_cwd
    parts = Path(subdir).parts  # e.g. ('models', 'bert')
    for part in parts:
        current = current / part
        if not current.is_dir():
            raise PathTraversalError(
                f"Intermediate directory '{current.relative_to(abs_cwd)}' "
                f"(from subdir '{subdir}') does not exist. "
                f"Please create all intermediate directories first: "
                f"mkdir -p {subdir}"
            )
    
    return abs_subdir


def build_dest_path(subdir: Path, filename: str, cwd: str) -> Path:
    """
    Build and validate destination path for a downloaded file.
    
    Args:
        subdir: Validated subdirectory path
        filename: Name of the file to download
        cwd: Current working directory
    
    Returns:
        Absolute destination path
    """
    abs_cwd = Path(cwd).resolve()
    dest = subdir / filename
    return validate_safe_path(str(dest), cwd)
