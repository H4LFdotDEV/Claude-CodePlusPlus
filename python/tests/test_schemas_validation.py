# test_schemas_validation.py
# Comprehensive test suite for schemas.py validation models
# Tests all Pydantic models and validators with edge cases, injection attempts, and boundary conditions

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from memory_mcp.schemas import (
    # Validators
    validate_session_id,
    validate_iso_timestamp,
    validate_path,
    validate_embedding_vector,
    # Models
    SessionStateModel,
    MemoryItemModel,
    EmbeddingCacheModel,
    ContextWindowModel,
    ToolCallModel,
    TemplateCacheModel,
    QueryCacheModel,
    ContextWindowMessageModel,
    # Validation helpers
    validate_redis_data,
    validate_session_state,
    validate_memory_item,
    validate_embedding_cache,
    validate_context_window,
    validate_tool_call,
    validate_template_cache,
    validate_query_cache,
)


# ============================================================================
# FIXTURES: Test Data and Helpers
# ============================================================================

@pytest.fixture
def valid_iso_timestamp():
    """Create a valid ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def valid_embedding_vector():
    """Create a valid embedding vector."""
    return [0.1 + i * 0.001 for i in range(768)]


@pytest.fixture
def valid_session_state_dict(valid_iso_timestamp):
    """Create valid session state data."""
    return {
        "session_id": "sess-001",
        "project_path": "project/path",
        "active_files": ["file1.py", "file2.py"],
        "recent_queries": ["query1", "query2"],
        "context_window": [
            {
                "role": "user",
                "content": "Hello assistant",
                "timestamp": valid_iso_timestamp
            }
        ],
        "created_at": valid_iso_timestamp,
        "updated_at": valid_iso_timestamp,
    }


@pytest.fixture
def valid_memory_item_dict(valid_iso_timestamp):
    """Create valid memory item data."""
    return {
        "id": "mem-001",
        "type": "note",
        "content": "This is a test memory item with content",
        "tags": ["test", "sample"],
        "created_at": valid_iso_timestamp,
        "importance": 5,
    }


@pytest.fixture
def valid_embedding_cache_dict(valid_iso_timestamp, valid_embedding_vector):
    """Create valid embedding cache data."""
    return {
        "query": "test query",
        "embedding": valid_embedding_vector,
        "model": "text-embedding-3-small",
        "created_at": valid_iso_timestamp,
    }


@pytest.fixture
def valid_context_window_dict(valid_iso_timestamp):
    """Create valid context window data."""
    return {
        "id": "ctx-001",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ],
        "tokens_used": 100,
        "created_at": valid_iso_timestamp,
    }


@pytest.fixture
def valid_tool_call_dict(valid_iso_timestamp):
    """Create valid tool call data."""
    return {
        "tool_name": "search_memory",
        "parameters": {"query": "test", "limit": 10},
        "result": "Found 5 results",
        "timestamp": valid_iso_timestamp,
        "duration_ms": 250,
    }


@pytest.fixture
def valid_template_cache_dict(valid_iso_timestamp):
    """Create valid template cache data."""
    return {
        "content": "Template content with placeholders",
        "metadata": {"version": 1, "language": "python"},
        "cached_at": valid_iso_timestamp,
    }


@pytest.fixture
def valid_query_cache_dict(valid_iso_timestamp):
    """Create valid query cache data."""
    return {
        "query": "SELECT * FROM memories",
        "result": "Query result data",
        "created_at": valid_iso_timestamp,
        "hits": 10,
    }


# ============================================================================
# TEST CATEGORY 1: SessionStateModel Validation (8 tests)
# ============================================================================

class TestSessionStateModelValidation:
    """Tests for SessionStateModel validation."""

    def test_valid_session_state(self, valid_session_state_dict):
        """Test valid session state passes validation."""
        model = SessionStateModel(**valid_session_state_dict)

        assert model.session_id == "sess-001"
        assert model.project_path == "project/path"
        assert len(model.active_files) == 2

    def test_session_id_required(self, valid_session_state_dict):
        """Test session_id is required."""
        del valid_session_state_dict["session_id"]

        with pytest.raises(ValidationError):
            SessionStateModel(**valid_session_state_dict)

    def test_session_id_alphanumeric_hyphen_underscore(self, valid_session_state_dict):
        """Test session_id allows alphanumeric, hyphens, underscores."""
        valid_session_state_dict["session_id"] = "sess-001_test"

        model = SessionStateModel(**valid_session_state_dict)
        assert model.session_id == "sess-001_test"

    def test_session_id_rejects_special_characters(self, valid_session_state_dict):
        """Test session_id rejects special characters."""
        valid_session_state_dict["session_id"] = "sess@001"

        with pytest.raises(ValidationError):
            SessionStateModel(**valid_session_state_dict)

    def test_session_id_max_length(self, valid_session_state_dict):
        """Test session_id respects max length."""
        valid_session_state_dict["session_id"] = "a" * 256

        model = SessionStateModel(**valid_session_state_dict)
        assert len(model.session_id) == 256

    def test_session_id_too_long(self, valid_session_state_dict):
        """Test session_id rejects values over max length."""
        valid_session_state_dict["session_id"] = "a" * 257

        with pytest.raises(ValidationError):
            SessionStateModel(**valid_session_state_dict)

    def test_project_path_prevents_traversal(self, valid_session_state_dict):
        """Test project_path prevents path traversal."""
        valid_session_state_dict["project_path"] = "../../../etc/passwd"

        with pytest.raises(ValidationError):
            SessionStateModel(**valid_session_state_dict)

    def test_context_window_validates_nested_messages(self, valid_session_state_dict):
        """Test context_window validates nested ContextWindowMessageModel."""
        model = SessionStateModel(**valid_session_state_dict)

        assert len(model.context_window) == 1
        assert model.context_window[0].role == "user"


# ============================================================================
# TEST CATEGORY 2: MemoryItemModel Validation (7 tests)
# ============================================================================

class TestMemoryItemModelValidation:
    """Tests for MemoryItemModel validation."""

    def test_valid_memory_item(self, valid_memory_item_dict):
        """Test valid memory item passes validation."""
        model = MemoryItemModel(**valid_memory_item_dict)

        assert model.id == "mem-001"
        assert model.type == "note"
        assert model.importance == 5

    def test_memory_item_type_whitelist(self, valid_memory_item_dict):
        """Test memory item type must be in whitelist."""
        valid_types = ["note", "code", "conversation", "reference"]

        for t in valid_types:
            valid_memory_item_dict["type"] = t
            model = MemoryItemModel(**valid_memory_item_dict)
            assert model.type == t

    def test_memory_item_type_rejects_invalid(self, valid_memory_item_dict):
        """Test memory item type rejects invalid values."""
        valid_memory_item_dict["type"] = "invalid_type"

        with pytest.raises(ValidationError):
            MemoryItemModel(**valid_memory_item_dict)

    def test_memory_item_tags_validation(self, valid_memory_item_dict):
        """Test memory item tags are validated."""
        valid_memory_item_dict["tags"] = ["tag-1", "tag_2", "tag/sub"]

        model = MemoryItemModel(**valid_memory_item_dict)
        assert len(model.tags) == 3

    def test_memory_item_tags_reject_invalid_chars(self, valid_memory_item_dict):
        """Test memory item tags reject invalid characters."""
        valid_memory_item_dict["tags"] = ["tag@invalid"]

        with pytest.raises(ValidationError):
            MemoryItemModel(**valid_memory_item_dict)

    def test_memory_item_importance_bounds(self, valid_memory_item_dict):
        """Test memory item importance respects bounds."""
        for importance in [1, 5, 10]:
            valid_memory_item_dict["importance"] = importance
            model = MemoryItemModel(**valid_memory_item_dict)
            assert model.importance == importance

    def test_memory_item_importance_out_of_bounds(self, valid_memory_item_dict):
        """Test memory item importance rejects out of bounds."""
        for importance in [0, 11]:
            valid_memory_item_dict["importance"] = importance
            with pytest.raises(ValidationError):
                MemoryItemModel(**valid_memory_item_dict)


# ============================================================================
# TEST CATEGORY 3: EmbeddingCacheModel Validation (6 tests)
# ============================================================================

class TestEmbeddingCacheModelValidation:
    """Tests for EmbeddingCacheModel validation."""

    def test_valid_embedding_cache(self, valid_embedding_cache_dict):
        """Test valid embedding cache passes validation."""
        model = EmbeddingCacheModel(**valid_embedding_cache_dict)

        assert model.query == "test query"
        assert len(model.embedding) == 768

    def test_embedding_vector_dimension_min(self, valid_embedding_cache_dict):
        """Test embedding vector respects minimum dimension."""
        valid_embedding_cache_dict["embedding"] = [0.1] * 256

        model = EmbeddingCacheModel(**valid_embedding_cache_dict)
        assert len(model.embedding) == 256

    def test_embedding_vector_dimension_max(self, valid_embedding_cache_dict):
        """Test embedding vector respects maximum dimension."""
        valid_embedding_cache_dict["embedding"] = [0.1] * 4096

        model = EmbeddingCacheModel(**valid_embedding_cache_dict)
        assert len(model.embedding) == 4096

    def test_embedding_vector_dimension_too_small(self, valid_embedding_cache_dict):
        """Test embedding vector rejects undersized vectors."""
        valid_embedding_cache_dict["embedding"] = [0.1] * 255

        with pytest.raises(ValidationError):
            EmbeddingCacheModel(**valid_embedding_cache_dict)

    def test_embedding_vector_rejects_nan(self, valid_embedding_cache_dict):
        """Test embedding vector rejects NaN values."""
        valid_embedding_cache_dict["embedding"] = [0.1] * 767 + [float('nan')]

        with pytest.raises(ValidationError):
            EmbeddingCacheModel(**valid_embedding_cache_dict)

    def test_embedding_vector_rejects_infinity(self, valid_embedding_cache_dict):
        """Test embedding vector rejects infinite values."""
        valid_embedding_cache_dict["embedding"] = [0.1] * 767 + [float('inf')]

        with pytest.raises(ValidationError):
            EmbeddingCacheModel(**valid_embedding_cache_dict)


# ============================================================================
# TEST CATEGORY 4: ContextWindowModel Validation (6 tests)
# ============================================================================

class TestContextWindowModelValidation:
    """Tests for ContextWindowModel validation."""

    def test_valid_context_window(self, valid_context_window_dict):
        """Test valid context window passes validation."""
        model = ContextWindowModel(**valid_context_window_dict)

        assert model.id == "ctx-001"
        assert len(model.messages) == 2

    def test_context_window_messages_role_validation(self, valid_context_window_dict):
        """Test context window messages validate roles."""
        valid_roles = ["user", "assistant", "system"]

        for role in valid_roles:
            valid_context_window_dict["messages"] = [
                {"role": role, "content": "Test content"}
            ]
            model = ContextWindowModel(**valid_context_window_dict)
            assert model.messages[0]["role"] == role

    def test_context_window_messages_reject_invalid_role(self, valid_context_window_dict):
        """Test context window messages reject invalid roles."""
        valid_context_window_dict["messages"] = [
            {"role": "invalid_role", "content": "Test"}
        ]

        with pytest.raises(ValidationError):
            ContextWindowModel(**valid_context_window_dict)

    def test_context_window_tokens_used_bounds(self, valid_context_window_dict):
        """Test context window tokens_used respects bounds."""
        for tokens in [0, 500000, 1_000_000]:
            valid_context_window_dict["tokens_used"] = tokens
            model = ContextWindowModel(**valid_context_window_dict)
            assert model.tokens_used == tokens

    def test_context_window_tokens_used_exceeds_max(self, valid_context_window_dict):
        """Test context window tokens_used exceeds maximum."""
        valid_context_window_dict["tokens_used"] = 1_000_001

        with pytest.raises(ValidationError):
            ContextWindowModel(**valid_context_window_dict)

    def test_context_window_message_content_max_length(self, valid_context_window_dict):
        """Test context window message content respects max length."""
        valid_context_window_dict["messages"] = [
            {"role": "user", "content": "x" * 100_000}
        ]

        model = ContextWindowModel(**valid_context_window_dict)
        assert len(model.messages[0]["content"]) == 100_000


# ============================================================================
# TEST CATEGORY 5: ToolCallModel Validation (5 tests)
# ============================================================================

class TestToolCallModelValidation:
    """Tests for ToolCallModel validation."""

    def test_valid_tool_call(self, valid_tool_call_dict):
        """Test valid tool call passes validation."""
        model = ToolCallModel(**valid_tool_call_dict)

        assert model.tool_name == "search_memory"
        assert model.duration_ms == 250

    def test_tool_name_validation(self, valid_tool_call_dict):
        """Test tool name must start with letter and contain alphanumeric/underscore."""
        valid_tool_call_dict["tool_name"] = "valid_tool_123"

        model = ToolCallModel(**valid_tool_call_dict)
        assert model.tool_name == "valid_tool_123"

    def test_tool_name_rejects_invalid_start(self, valid_tool_call_dict):
        """Test tool name rejects starting with number or special char."""
        for name in ["123_tool", "_tool", "tool@invalid"]:
            valid_tool_call_dict["tool_name"] = name
            with pytest.raises(ValidationError):
                ToolCallModel(**valid_tool_call_dict)

    def test_tool_call_duration_bounds(self, valid_tool_call_dict):
        """Test tool call duration respects bounds."""
        for duration in [0, 1_800_000, 3_600_000]:
            valid_tool_call_dict["duration_ms"] = duration
            model = ToolCallModel(**valid_tool_call_dict)
            assert model.duration_ms == duration

    def test_tool_call_duration_exceeds_max(self, valid_tool_call_dict):
        """Test tool call duration exceeds maximum."""
        valid_tool_call_dict["duration_ms"] = 3_600_001

        with pytest.raises(ValidationError):
            ToolCallModel(**valid_tool_call_dict)


# ============================================================================
# TEST CATEGORY 6: TemplateCacheModel Validation (5 tests)
# ============================================================================

class TestTemplateCacheModelValidation:
    """Tests for TemplateCacheModel validation."""

    def test_valid_template_cache(self, valid_template_cache_dict):
        """Test valid template cache passes validation."""
        model = TemplateCacheModel(**valid_template_cache_dict)

        assert "Template content" in model.content
        assert model.metadata["version"] == 1

    def test_template_content_max_length(self, valid_template_cache_dict):
        """Test template content respects max length."""
        valid_template_cache_dict["content"] = "x" * 100_000

        model = TemplateCacheModel(**valid_template_cache_dict)
        assert len(model.content) == 100_000

    def test_template_content_exceeds_max(self, valid_template_cache_dict):
        """Test template content exceeds maximum."""
        valid_template_cache_dict["content"] = "x" * 100_001

        with pytest.raises(ValidationError):
            TemplateCacheModel(**valid_template_cache_dict)

    def test_template_metadata_validation(self, valid_template_cache_dict):
        """Test template metadata is validated."""
        valid_template_cache_dict["metadata"] = {
            "version": 1,
            "language": "python",
            "nested": {"key": "value"}
        }

        model = TemplateCacheModel(**valid_template_cache_dict)
        assert model.metadata["nested"]["key"] == "value"

    def test_template_metadata_size_limit(self, valid_template_cache_dict):
        """Test template metadata size is limited."""
        valid_template_cache_dict["metadata"] = {
            "data": "x" * 49_000
        }

        model = TemplateCacheModel(**valid_template_cache_dict)
        assert len(str(model.metadata)) < 50_000


# ============================================================================
# TEST CATEGORY 7: QueryCacheModel Validation (5 tests)
# ============================================================================

class TestQueryCacheModelValidation:
    """Tests for QueryCacheModel validation."""

    def test_valid_query_cache(self, valid_query_cache_dict):
        """Test valid query cache passes validation."""
        model = QueryCacheModel(**valid_query_cache_dict)

        assert model.query == "SELECT * FROM memories"
        assert model.hits == 10

    def test_query_max_length(self, valid_query_cache_dict):
        """Test query respects max length."""
        valid_query_cache_dict["query"] = "q" * 10_000

        model = QueryCacheModel(**valid_query_cache_dict)
        assert len(model.query) == 10_000

    def test_query_empty_rejected(self, valid_query_cache_dict):
        """Test query cannot be empty."""
        valid_query_cache_dict["query"] = ""

        with pytest.raises(ValidationError):
            QueryCacheModel(**valid_query_cache_dict)

    def test_result_max_length(self, valid_query_cache_dict):
        """Test result respects max length."""
        valid_query_cache_dict["result"] = "r" * 500_000

        model = QueryCacheModel(**valid_query_cache_dict)
        assert len(model.result) == 500_000

    def test_hits_bounds(self, valid_query_cache_dict):
        """Test hits respects bounds."""
        for hits in [0, 500_000, 1_000_000]:
            valid_query_cache_dict["hits"] = hits
            model = QueryCacheModel(**valid_query_cache_dict)
            assert model.hits == hits


# ============================================================================
# TEST CATEGORY 8: ContextWindowMessageModel Validation (4 tests)
# ============================================================================

class TestContextWindowMessageModelValidation:
    """Tests for ContextWindowMessageModel validation."""

    def test_valid_context_window_message(self, valid_iso_timestamp):
        """Test valid context window message passes validation."""
        data = {
            "role": "user",
            "content": "Hello assistant",
            "timestamp": valid_iso_timestamp
        }

        model = ContextWindowMessageModel(**data)

        assert model.role == "user"
        assert model.content == "Hello assistant"

    def test_message_role_validation(self, valid_iso_timestamp):
        """Test message role validation."""
        for role in ["user", "assistant", "system"]:
            data = {
                "role": role,
                "content": "Test",
                "timestamp": valid_iso_timestamp
            }
            model = ContextWindowMessageModel(**data)
            assert model.role == role

    def test_message_role_rejects_invalid(self, valid_iso_timestamp):
        """Test message role rejects invalid values."""
        data = {
            "role": "invalid",
            "content": "Test",
            "timestamp": valid_iso_timestamp
        }

        with pytest.raises(ValidationError):
            ContextWindowMessageModel(**data)

    def test_message_content_max_length(self, valid_iso_timestamp):
        """Test message content respects max length."""
        data = {
            "role": "user",
            "content": "x" * 100_000,
            "timestamp": valid_iso_timestamp
        }

        model = ContextWindowMessageModel(**data)
        assert len(model.content) == 100_000


# ============================================================================
# TEST CATEGORY 9: Cross-Model Integration (4 tests)
# ============================================================================

class TestCrossModelIntegration:
    """Tests for interactions between models."""

    def test_session_state_with_nested_messages(self, valid_session_state_dict, valid_iso_timestamp):
        """Test SessionStateModel properly validates nested ContextWindowMessageModel."""
        valid_session_state_dict["context_window"] = [
            {
                "role": "user",
                "content": "First message",
                "timestamp": valid_iso_timestamp
            },
            {
                "role": "assistant",
                "content": "Response",
                "timestamp": valid_iso_timestamp
            }
        ]

        model = SessionStateModel(**valid_session_state_dict)

        assert len(model.context_window) == 2
        assert model.context_window[0].role == "user"
        assert model.context_window[1].role == "assistant"

    def test_memory_item_content_injection_prevention(self, valid_memory_item_dict):
        """Test memory item prevents injection attacks in content."""
        injection_attempts = [
            "'; DROP TABLE memories; --",
            "<script>alert('xss')</script>",
            "${SHELL}",
            "\\x00\\x00\\x00",
        ]

        for attempt in injection_attempts:
            valid_memory_item_dict["content"] = attempt
            model = MemoryItemModel(**valid_memory_item_dict)
            assert model.content == attempt  # Should be stored as-is, not executed

    def test_tool_call_parameters_large_data_handling(self, valid_tool_call_dict):
        """Test tool call handles large parameters."""
        valid_tool_call_dict["parameters"] = {
            "query": "x" * 50_000,
            "filters": {"key": "y" * 25_000}
        }

        model = ToolCallModel(**valid_tool_call_dict)
        assert len(str(model.parameters)) < 100_000

    def test_extra_fields_rejected(self, valid_memory_item_dict):
        """Test extra fields are rejected (strict schema)."""
        valid_memory_item_dict["extra_field"] = "should be rejected"

        with pytest.raises(ValidationError):
            MemoryItemModel(**valid_memory_item_dict)


# ============================================================================
# TEST CATEGORY: Timestamp Validation (Helper Function Tests)
# ============================================================================

class TestTimestampValidation:
    """Tests for ISO 8601 timestamp validation."""

    def test_valid_iso_timestamps(self):
        """Test various valid ISO 8601 formats."""
        valid_timestamps = [
            "2024-01-01T12:00:00+00:00",
            "2024-01-01T12:00:00Z",
            "2024-01-01T12:00:00",
            datetime.now(timezone.utc).isoformat(),
        ]

        for ts in valid_timestamps:
            result = validate_iso_timestamp(ts)
            assert isinstance(result, str)

    def test_invalid_timestamps(self):
        """Test invalid timestamp formats."""
        invalid_timestamps = [
            "2024-13-01",  # Invalid month
            "invalid-date",
            12345,  # Non-string
        ]

        for ts in invalid_timestamps:
            with pytest.raises(ValueError):
                validate_iso_timestamp(ts)

    def test_datetime_object_converted(self):
        """Test datetime objects are converted to ISO format."""
        dt = datetime.now(timezone.utc)
        result = validate_iso_timestamp(dt)

        assert isinstance(result, str)
        assert "T" in result


# ============================================================================
# TEST CATEGORY: Path Validation (Helper Function Tests)
# ============================================================================

class TestPathValidation:
    """Tests for path validation."""

    def test_valid_paths(self):
        """Test valid relative paths."""
        valid_paths = [
            "file.py",
            "path/to/file.py",
            "relative/path/file.txt",
            "file-with-dash.txt",
            "file_with_underscore.py",
        ]

        for path in valid_paths:
            result = validate_path(path)
            assert result == path

    def test_absolute_paths_rejected(self):
        """Test absolute paths are rejected."""
        with pytest.raises(ValueError):
            validate_path("/etc/passwd")

    def test_path_traversal_rejected(self):
        """Test path traversal attempts are rejected."""
        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "file/../../../etc/passwd",
        ]

        for attempt in traversal_attempts:
            with pytest.raises(ValueError):
                validate_path(attempt)

    def test_null_bytes_rejected(self):
        """Test null bytes in paths are rejected."""
        with pytest.raises(ValueError):
            validate_path("file\x00.py")

    def test_empty_path_rejected(self):
        """Test empty paths are rejected."""
        with pytest.raises(ValueError):
            validate_path("")


# ============================================================================
# TEST CATEGORY: Session ID Validation (Helper Function Tests)
# ============================================================================

class TestSessionIDValidation:
    """Tests for session ID validation."""

    def test_valid_session_ids(self):
        """Test valid session IDs."""
        valid_ids = [
            "sess-001",
            "session_123",
            "abc123def456",
            "TEST-SESSION",
        ]

        for sid in valid_ids:
            result = validate_session_id(sid)
            assert result == sid

    def test_session_id_rejects_special_chars(self):
        """Test session ID rejects special characters."""
        invalid_ids = [
            "sess@001",
            "sess.001",
            "sess/001",
            "sess#001",
            "sess:001",
        ]

        for sid in invalid_ids:
            with pytest.raises(ValueError):
                validate_session_id(sid)

    def test_session_id_empty_rejected(self):
        """Test empty session ID is rejected."""
        with pytest.raises(ValueError):
            validate_session_id("")

    def test_session_id_max_length_enforced(self):
        """Test session ID max length is enforced."""
        valid = validate_session_id("a" * 256)
        assert len(valid) == 256

        with pytest.raises(ValueError):
            validate_session_id("a" * 257)


# ============================================================================
# TEST CATEGORY: Embedding Vector Validation (Helper Function Tests)
# ============================================================================

class TestEmbeddingVectorValidation:
    """Tests for embedding vector validation."""

    def test_valid_embedding_vectors(self):
        """Test valid embedding vectors."""
        for dim in [256, 768, 1536, 4096]:
            vector = [0.1] * dim
            result = validate_embedding_vector(vector)
            assert len(result) == dim

    def test_vector_too_small_rejected(self):
        """Test vectors smaller than 256 are rejected."""
        vector = [0.1] * 255

        with pytest.raises(ValueError):
            validate_embedding_vector(vector)

    def test_vector_too_large_rejected(self):
        """Test vectors larger than 4096 are rejected."""
        vector = [0.1] * 4097

        with pytest.raises(ValueError):
            validate_embedding_vector(vector)

    def test_nan_values_rejected(self):
        """Test NaN values are rejected."""
        vector = [0.1] * 767 + [float('nan')]

        with pytest.raises(ValueError):
            validate_embedding_vector(vector)

    def test_infinity_values_rejected(self):
        """Test infinite values are rejected."""
        vector = [0.1] * 767 + [float('inf')]

        with pytest.raises(ValueError):
            validate_embedding_vector(vector)

    def test_non_numeric_values_rejected(self):
        """Test non-numeric values are rejected."""
        vector = [0.1] * 767 + ["not_a_number"]

        with pytest.raises(ValueError):
            validate_embedding_vector(vector)

    def test_empty_vector_rejected(self):
        """Test empty vector is rejected."""
        with pytest.raises(ValueError):
            validate_embedding_vector([])


# ============================================================================
# TEST CATEGORY: Validation Helper Functions
# ============================================================================

class TestValidationHelpers:
    """Tests for validation helper functions."""

    def test_validate_session_state_success(self, valid_session_state_dict):
        """Test validate_session_state helper function."""
        model = validate_session_state(valid_session_state_dict)

        assert isinstance(model, SessionStateModel)
        assert model.session_id == valid_session_state_dict["session_id"]

    def test_validate_memory_item_success(self, valid_memory_item_dict):
        """Test validate_memory_item helper function."""
        model = validate_memory_item(valid_memory_item_dict)

        assert isinstance(model, MemoryItemModel)
        assert model.id == valid_memory_item_dict["id"]

    def test_validate_embedding_cache_success(self, valid_embedding_cache_dict):
        """Test validate_embedding_cache helper function."""
        model = validate_embedding_cache(valid_embedding_cache_dict)

        assert isinstance(model, EmbeddingCacheModel)
        assert model.query == valid_embedding_cache_dict["query"]

    def test_validate_context_window_success(self, valid_context_window_dict):
        """Test validate_context_window helper function."""
        model = validate_context_window(valid_context_window_dict)

        assert isinstance(model, ContextWindowModel)
        assert model.id == valid_context_window_dict["id"]

    def test_validate_tool_call_success(self, valid_tool_call_dict):
        """Test validate_tool_call helper function."""
        model = validate_tool_call(valid_tool_call_dict)

        assert isinstance(model, ToolCallModel)
        assert model.tool_name == valid_tool_call_dict["tool_name"]

    def test_validate_template_cache_success(self, valid_template_cache_dict):
        """Test validate_template_cache helper function."""
        model = validate_template_cache(valid_template_cache_dict)

        assert isinstance(model, TemplateCacheModel)
        assert "Template" in model.content

    def test_validate_query_cache_success(self, valid_query_cache_dict):
        """Test validate_query_cache helper function."""
        model = validate_query_cache(valid_query_cache_dict)

        assert isinstance(model, QueryCacheModel)
        assert model.query == valid_query_cache_dict["query"]

    def test_validation_error_raised_on_invalid_data(self, valid_memory_item_dict):
        """Test ValidationError is raised on invalid data."""
        valid_memory_item_dict["importance"] = 99  # Out of bounds

        with pytest.raises(ValueError):
            validate_memory_item(valid_memory_item_dict)


# ============================================================================
# TEST CATEGORY: Security and Injection Prevention
# ============================================================================

class TestSecurityAndInjectionPrevention:
    """Tests for security and injection prevention."""

    def test_sql_injection_prevention_in_content(self, valid_memory_item_dict):
        """Test SQL injection attempts are stored as content, not executed."""
        valid_memory_item_dict["content"] = "'; DROP TABLE memories; --"

        model = MemoryItemModel(**valid_memory_item_dict)
        # Content should be stored as-is (validation stores strings safely)
        assert "DROP TABLE" in model.content

    def test_xss_prevention_in_content(self, valid_memory_item_dict):
        """Test XSS attempts are stored as content, not executed."""
        valid_memory_item_dict["content"] = "<script>alert('xss')</script>"

        model = MemoryItemModel(**valid_memory_item_dict)
        assert "<script>" in model.content

    def test_path_traversal_prevention(self, valid_session_state_dict):
        """Test path traversal is prevented."""
        valid_session_state_dict["project_path"] = "../../../../etc/passwd"

        with pytest.raises(ValidationError):
            SessionStateModel(**valid_session_state_dict)

    def test_null_byte_injection_prevention(self, valid_session_state_dict):
        """Test null byte injection is prevented."""
        valid_session_state_dict["session_id"] = "sess\x00admin"

        with pytest.raises(ValidationError):
            SessionStateModel(**valid_session_state_dict)

    def test_large_payload_rejection(self, valid_memory_item_dict):
        """Test very large payloads are rejected."""
        valid_memory_item_dict["content"] = "x" * 1_000_001  # Exceeds max

        with pytest.raises(ValidationError):
            MemoryItemModel(**valid_memory_item_dict)
