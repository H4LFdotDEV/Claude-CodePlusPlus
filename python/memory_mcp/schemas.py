# schemas.py
# Pydantic Data Validation Models for Redis Deserialization Security
# Prevents injection attacks and data corruption from untrusted Redis data

import re
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ValidationError

logger = logging.getLogger("memory_mcp.schemas")

# Validators
def validate_session_id(value: str) -> str:
    """Validate session ID - prevents injection attacks."""
    if not isinstance(value, str) or not value:
        raise ValueError("Session ID must be non-empty string")
    if len(value) > 256:
        raise ValueError("Session ID too long")
    if not re.match(r"^[a-zA-Z0-9\-_]+$", value):
        raise ValueError(f"Session ID invalid format: {value}")
    return value

def validate_iso_timestamp(value: Union[str, datetime]) -> str:
    """Validate ISO 8601 timestamps."""
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError("Timestamp must be string or datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.isoformat()
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid ISO 8601 timestamp: {value}") from e

def validate_path(value: str) -> str:
    """Validate paths - prevent traversal attacks."""
    if not isinstance(value, str) or not value:
        raise ValueError("Path must be non-empty string")
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        raise ValueError("Absolute paths not allowed")
    if ".." in value:
        raise ValueError("Path traversal detected")
    if "\x00" in value:
        raise ValueError("Null bytes in path")
    return value

def validate_embedding_vector(vector: List[float]) -> List[float]:
    """Validate embedding vectors."""
    if not isinstance(vector, list) or not vector:
        raise ValueError("Vector must be non-empty list")
    if len(vector) < 256 or len(vector) > 4096:
        raise ValueError(f"Invalid vector dimension ({len(vector)})")
    for i, val in enumerate(vector):
        if not isinstance(val, (int, float)):
            raise ValueError(f"Vector[{i}] is not numeric")
        if isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf')):
            raise ValueError(f"Vector[{i}] contains NaN or Inf")
    return vector

# Models
class SessionStateModel(BaseModel):
    """Validated session state from Redis."""
    session_id: str = Field(...)
    project_path: str = Field(...)
    active_files: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(...)
    updated_at: str = Field(...)

    @field_validator("session_id")
    @classmethod
    def check_session_id(cls, v: str) -> str:
        return validate_session_id(v)

    @field_validator("project_path")
    @classmethod
    def check_project_path(cls, v: str) -> str:
        return validate_path(v)

    @field_validator("active_files")
    @classmethod
    def check_active_files(cls, v: List[str]) -> List[str]:
        if not isinstance(v, list):
            raise ValueError("active_files must be list")
        for f in v:
            validate_path(f)
        return v

    @field_validator("created_at", "updated_at")
    @classmethod
    def check_timestamps(cls, v: str) -> str:
        return validate_iso_timestamp(v)

    class Config:
        extra = "forbid"

class MemoryItemModel(BaseModel):
    """Validated memory item from Redis."""
    id: str = Field(...)
    type: str = Field(...)
    content: str = Field(...)
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(...)
    importance: int = Field(default=5, ge=1, le=10)

    @field_validator("id")
    @classmethod
    def check_id(cls, v: str) -> str:
        if not isinstance(v, str) or not v or len(v) > 256:
            raise ValueError("Invalid ID")
        return v

    @field_validator("type")
    @classmethod
    def check_type(cls, v: str) -> str:
        if v not in {"note", "code", "conversation", "reference"}:
            raise ValueError(f"Invalid type: {v}")
        return v

    @field_validator("content")
    @classmethod
    def check_content(cls, v: str) -> str:
        if not isinstance(v, str) or not v or len(v) > 1_000_000:
            raise ValueError("Invalid content")
        return v

    @field_validator("tags")
    @classmethod
    def check_tags(cls, v: List[str]) -> List[str]:
        if not isinstance(v, list) or len(v) > 100:
            raise ValueError("Invalid tags")
        for tag in v:
            if not re.match(r"^[a-zA-Z0-9\-_/]+$", tag):
                raise ValueError(f"Invalid tag: {tag}")
        return v

    @field_validator("created_at")
    @classmethod
    def check_created_at(cls, v: str) -> str:
        return validate_iso_timestamp(v)

    class Config:
        extra = "forbid"

class EmbeddingCacheModel(BaseModel):
    """Validated embedding cache from Redis."""
    query: str = Field(..., max_length=10000)
    embedding: List[float] = Field(...)
    model: str = Field(...)
    created_at: str = Field(...)

    @field_validator("query")
    @classmethod
    def check_query(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Query cannot be empty")
        return v

    @field_validator("embedding")
    @classmethod
    def check_embedding(cls, v: List[float]) -> List[float]:
        return validate_embedding_vector(v)

    @field_validator("created_at")
    @classmethod
    def check_created_at(cls, v: str) -> str:
        return validate_iso_timestamp(v)

    class Config:
        extra = "forbid"

class ContextWindowModel(BaseModel):
    """Validated context window from Redis."""
    id: str = Field(...)
    messages: List[Dict[str, str]] = Field(default_factory=list)
    tokens_used: int = Field(default=0, ge=0, le=1_000_000)
    created_at: str = Field(...)

    @field_validator("id")
    @classmethod
    def check_id(cls, v: str) -> str:
        if not isinstance(v, str) or not v or len(v) > 256:
            raise ValueError("Invalid ID")
        return v

    @field_validator("messages")
    @classmethod
    def check_messages(cls, v: List[Dict[str, str]]) -> List[Dict[str, str]]:
        if not isinstance(v, list) or len(v) > 1000:
            raise ValueError("Invalid messages")
        for msg in v:
            if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                raise ValueError("Invalid message format")
            if msg["role"] not in {"user", "assistant", "system"}:
                raise ValueError(f"Invalid role: {msg['role']}")
            if not isinstance(msg["content"], str) or len(msg["content"]) > 100_000:
                raise ValueError("Invalid message content")
        return v

    @field_validator("created_at")
    @classmethod
    def check_created_at(cls, v: str) -> str:
        return validate_iso_timestamp(v)

    class Config:
        extra = "forbid"

class ToolCallModel(BaseModel):
    """Validated tool call from Redis."""
    tool_name: str = Field(...)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = Field(None)
    timestamp: str = Field(...)
    duration_ms: int = Field(default=0, ge=0, le=3_600_000)

    @field_validator("tool_name")
    @classmethod
    def check_tool_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", v):
            raise ValueError(f"Invalid tool name: {v}")
        return v

    @field_validator("parameters")
    @classmethod
    def check_parameters(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if len(str(v)) > 100_000:
            raise ValueError("Parameters too large")
        return v

    @field_validator("result")
    @classmethod
    def check_result(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 1_000_000:
            raise ValueError("Result too large")
        return v

    @field_validator("timestamp")
    @classmethod
    def check_timestamp(cls, v: str) -> str:
        return validate_iso_timestamp(v)

    class Config:
        extra = "forbid"

# Validation Helpers
def validate_redis_data(data: Dict[str, Any], model_class) -> Any:
    """Safely validate Redis data against a Pydantic model."""
    try:
        return model_class(**data)
    except ValidationError as e:
        logger.error(f"Validation failed for {model_class.__name__}: {e}")
        raise ValueError(f"Invalid {model_class.__name__}: {str(e)}") from e

def validate_session_state(data: Dict[str, Any]) -> SessionStateModel:
    """Validate session state from Redis."""
    return validate_redis_data(data, SessionStateModel)

def validate_memory_item(data: Dict[str, Any]) -> MemoryItemModel:
    """Validate memory item from Redis."""
    return validate_redis_data(data, MemoryItemModel)

def validate_embedding_cache(data: Dict[str, Any]) -> EmbeddingCacheModel:
    """Validate embedding cache from Redis."""
    return validate_redis_data(data, EmbeddingCacheModel)

def validate_context_window(data: Dict[str, Any]) -> ContextWindowModel:
    """Validate context window from Redis."""
    return validate_redis_data(data, ContextWindowModel)

def validate_tool_call(data: Dict[str, Any]) -> ToolCallModel:
    """Validate tool call from Redis."""
    return validate_redis_data(data, ToolCallModel)
