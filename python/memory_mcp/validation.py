# validation.py
# Input validation module for Memory MCP Server
# Centralized validation logic for domain-specific inputs

import re
from typing import Any, List, Optional

# Allowed document types
ALLOWED_DOC_TYPES = frozenset(["code", "note", "reference", "conversation"])

# Max content size: 1MB
MAX_CONTENT_SIZE = 1048576

# Tag validation pattern: alphanumeric and hyphen only
TAG_PATTERN = re.compile(r'^[a-zA-Z0-9-]+$')

# Project name validation pattern: alphanumeric, hyphen, and underscore only
PROJECT_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def validate_string(value: Any, name: str, min_len: int = 0, max_len: int = 100000) -> str:
    """Validate and return a string value.

    Args:
        value: Value to validate
        name: Field name for error messages
        min_len: Minimum string length (default: 0)
        max_len: Maximum string length (default: 100000)

    Returns:
        Validated string

    Raises:
        ValueError: If value is None or outside length bounds
        TypeError: If value is not a string
    """
    if value is None:
        raise ValueError(f"{name} is required")
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, got {type(value).__name__}")
    if len(value) < min_len:
        raise ValueError(f"{name} must be at least {min_len} characters")
    if len(value) > max_len:
        raise ValueError(f"{name} must be at most {max_len} characters")
    return value


def validate_int(value: Any, name: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """Validate and return an integer value.

    Args:
        value: Value to validate
        name: Field name for error messages
        min_val: Minimum value (default: None for no limit)
        max_val: Maximum value (default: None for no limit)

    Returns:
        Validated integer

    Raises:
        ValueError: If value is None or outside bounds
        TypeError: If value is not numeric
    """
    if value is None:
        raise ValueError(f"{name} is required")
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    result = int(value)
    if min_val is not None and result < min_val:
        raise ValueError(f"{name} must be at least {min_val}")
    if max_val is not None and result > max_val:
        raise ValueError(f"{name} must be at most {max_val}")
    return result


def validate_list(value: Any, name: str, item_type: type = str) -> List:
    """Validate and return a list value.

    Args:
        value: Value to validate
        name: Field name for error messages
        item_type: Expected type of list items (default: str)

    Returns:
        Validated list (empty list if None)

    Raises:
        TypeError: If value is not a list or contains wrong item type
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list, got {type(value).__name__}")
    for i, item in enumerate(value):
        if not isinstance(item, item_type):
            raise TypeError(f"{name}[{i}] must be {item_type.__name__}")
    return value


def validate_doc_type(value: Any, name: str = "type") -> str:
    """Validate document type against allowed values.

    Args:
        value: Document type to validate
        name: Field name for error messages (default: "type")

    Returns:
        Validated document type

    Raises:
        ValueError: If type not in allowed types
        TypeError/ValueError: From validate_string
    """
    value = validate_string(value, name)
    if value not in ALLOWED_DOC_TYPES:
        raise ValueError(
            f"Invalid {name}: '{value}'. Must be one of: {', '.join(sorted(ALLOWED_DOC_TYPES))}"
        )
    return value


def validate_tags(value: Any, name: str = "tags") -> List[str]:
    """Validate and sanitize tags array (alphanumeric + hyphen only).

    Args:
        value: Tags list to validate
        name: Field name for error messages (default: "tags")

    Returns:
        Validated tags list (duplicates removed, empty tags filtered)

    Raises:
        ValueError: If tags contain invalid characters
        TypeError: From validate_list
    """
    tags = validate_list(value, name, str)
    sanitized = []
    for i, tag in enumerate(tags):
        if not tag:
            continue
        if not TAG_PATTERN.match(tag):
            raise ValueError(
                f"{name}[{i}] '{tag}' contains invalid characters. "
                "Tags must be alphanumeric with hyphens only."
            )
        sanitized.append(tag)
    return sanitized


def validate_project(value: Any, name: str = "project") -> Optional[str]:
    """Validate project name (no special characters except hyphen/underscore).

    Args:
        value: Project name to validate
        name: Field name for error messages (default: "project")

    Returns:
        Validated project name or None if value is None

    Raises:
        ValueError: If project name contains invalid characters
        TypeError/ValueError: From validate_string
    """
    if value is None:
        return None
    project = validate_string(value, name, max_len=100)
    if not PROJECT_PATTERN.match(project):
        raise ValueError(
            f"Invalid {name}: '{project}'. "
            "Project names must be alphanumeric with hyphens and underscores only."
        )
    return project


def validate_content(value: Any, name: str = "content") -> str:
    """Validate content with size limit (max 1MB).

    Args:
        value: Content to validate
        name: Field name for error messages (default: "content")

    Returns:
        Validated content

    Raises:
        ValueError: If content exceeds size limit or is empty
        TypeError: From validate_string
    """
    content = validate_string(value, name, min_len=1, max_len=MAX_CONTENT_SIZE)
    content_bytes = len(content.encode('utf-8'))
    if content_bytes > MAX_CONTENT_SIZE:
        raise ValueError(
            f"{name} exceeds maximum size of {MAX_CONTENT_SIZE} bytes "
            f"(got {content_bytes} bytes)"
        )
    return content


def validate_limit(value: Any, name: str = "limit", default: int = 10) -> int:
    """Validate limit parameter (1-1000 range).

    Args:
        value: Limit value to validate
        name: Field name for error messages (default: "limit")
        default: Default value if None (default: 10)

    Returns:
        Validated limit (between 1 and 1000)

    Raises:
        ValueError: If value outside range
        TypeError: From validate_int
    """
    if value is None:
        return default
    return validate_int(value, name, min_val=1, max_val=1000)
