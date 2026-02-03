# log_utils.py
# Logging utilities for secure query logging
# Jeremiah Kroesche | Halfservers LLC
#
# SECURITY: Prevents sensitive data exposure in logs by hashing query content

import hashlib
from typing import Optional


def log_safe_query(query: str, max_length: int = 16) -> str:
    """
    Generate a safe representation of a query for logging.

    Instead of logging full query content (which may contain sensitive data),
    this function returns a hash prefix for correlation without exposure.

    Args:
        query: The query string to sanitize
        max_length: Length of hash prefix to return (default: 16)

    Returns:
        Hash prefix in format "hash:{prefix}"

    Example:
        >>> log_safe_query("SELECT * FROM users WHERE email='user@example.com'")
        'hash:a1b2c3d4e5f6g7h8'
    """
    if not query:
        return "hash:empty"

    query_hash = hashlib.sha256(query.encode()).hexdigest()[:max_length]
    return f"hash:{query_hash}"


def log_safe_text(text: str, preview_length: int = 30, hash_length: int = 8) -> str:
    """
    Generate a safe representation combining preview and hash.

    Provides a short preview of the text (for human readability) plus a hash
    (for uniqueness/correlation) without exposing the full content.

    Args:
        text: The text to sanitize
        preview_length: Number of characters to preview (default: 30)
        hash_length: Length of hash suffix (default: 8)

    Returns:
        Safe representation in format "preview... [hash:suffix]"

    Example:
        >>> log_safe_text("This is sensitive data")
        'This is sensitive data [hash:a1b2c3d4]'
    """
    if not text:
        return "[empty]"

    preview = text[:preview_length]
    if len(text) > preview_length:
        preview += "..."

    text_hash = hashlib.sha256(text.encode()).hexdigest()[:hash_length]
    return f"{preview} [hash:{text_hash}]"


def sanitize_log_data(data: dict, sensitive_keys: Optional[list] = None) -> dict:
    """
    Sanitize dictionary data for logging by hashing sensitive fields.

    Args:
        data: Dictionary containing log data
        sensitive_keys: List of keys to sanitize (default: ['query', 'content', 'text'])

    Returns:
        New dictionary with sensitive fields hashed

    Example:
        >>> sanitize_log_data({'query': 'secret', 'limit': 10})
        {'query': 'hash:a1b2c3d4', 'limit': 10}
    """
    if sensitive_keys is None:
        sensitive_keys = ['query', 'content', 'text', 'password', 'token', 'secret']

    sanitized = {}
    for key, value in data.items():
        if key.lower() in [k.lower() for k in sensitive_keys]:
            if isinstance(value, str):
                sanitized[key] = log_safe_query(value)
            else:
                sanitized[key] = log_safe_query(str(value))
        else:
            sanitized[key] = value

    return sanitized
