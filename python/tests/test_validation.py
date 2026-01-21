# test_validation.py
# Comprehensive test suite for validation module
# Tests cover: string, int, list validation, domain-specific validators

import pytest
from memory_mcp.validation import (
    validate_string, validate_int, validate_list, validate_doc_type,
    validate_tags, validate_project, validate_content, validate_limit,
    ALLOWED_DOC_TYPES, MAX_CONTENT_SIZE, TAG_PATTERN, PROJECT_PATTERN
)


# ============================================================================
# CATEGORY 1: String Validation (8 tests)
# ============================================================================

class TestValidateString:
    """Test validate_string function."""

    def test_valid_string(self):
        """Test validation of valid string."""
        result = validate_string("test content", "field")
        assert result == "test content"

    def test_none_value_raises_error(self):
        """Test None value raises ValueError."""
        with pytest.raises(ValueError, match="required"):
            validate_string(None, "field")

    def test_non_string_raises_error(self):
        """Test non-string raises TypeError."""
        with pytest.raises(TypeError, match="must be a string"):
            validate_string(123, "field")

    def test_min_length_violation(self):
        """Test string below min length raises ValueError."""
        with pytest.raises(ValueError, match="at least 5"):
            validate_string("ab", "field", min_len=5)

    def test_max_length_violation(self):
        """Test string above max length raises ValueError."""
        with pytest.raises(ValueError, match="at most 5"):
            validate_string("toolong", "field", max_len=5)

    def test_empty_string_valid_by_default(self):
        """Test empty string is valid by default."""
        result = validate_string("", "field")
        assert result == ""

    def test_empty_string_fails_with_min_len(self):
        """Test empty string fails with min_len=1."""
        with pytest.raises(ValueError):
            validate_string("", "field", min_len=1)

    def test_max_length_default(self):
        """Test default max length is 100000."""
        long_string = "x" * 100000
        result = validate_string(long_string, "field")
        assert result == long_string


# ============================================================================
# CATEGORY 2: Integer Validation (6 tests)
# ============================================================================

class TestValidateInt:
    """Test validate_int function."""

    def test_valid_int(self):
        """Test validation of valid integer."""
        result = validate_int(42, "number")
        assert result == 42

    def test_float_converted_to_int(self):
        """Test float is converted to int."""
        result = validate_int(42.7, "number")
        assert result == 42

    def test_none_value_raises_error(self):
        """Test None value raises ValueError."""
        with pytest.raises(ValueError, match="required"):
            validate_int(None, "number")

    def test_non_numeric_raises_error(self):
        """Test non-numeric raises TypeError."""
        with pytest.raises(TypeError, match="must be a number"):
            validate_int("not a number", "number")

    def test_min_value_violation(self):
        """Test value below min raises ValueError."""
        with pytest.raises(ValueError, match="at least 10"):
            validate_int(5, "number", min_val=10)

    def test_max_value_violation(self):
        """Test value above max raises ValueError."""
        with pytest.raises(ValueError, match="at most 10"):
            validate_int(15, "number", max_val=10)


# ============================================================================
# CATEGORY 3: List Validation (5 tests)
# ============================================================================

class TestValidateList:
    """Test validate_list function."""

    def test_valid_list(self):
        """Test validation of valid list."""
        result = validate_list(["a", "b", "c"], "items", str)
        assert result == ["a", "b", "c"]

    def test_none_returns_empty_list(self):
        """Test None returns empty list."""
        result = validate_list(None, "items")
        assert result == []

    def test_non_list_raises_error(self):
        """Test non-list raises TypeError."""
        with pytest.raises(TypeError, match="must be a list"):
            validate_list("not a list", "items")

    def test_wrong_item_type_raises_error(self):
        """Test wrong item type raises TypeError."""
        with pytest.raises(TypeError, match="must be str"):
            validate_list([1, 2, 3], "items", str)

    def test_mixed_list_raises_error(self):
        """Test mixed item types raise TypeError."""
        with pytest.raises(TypeError):
            validate_list(["a", 1, "c"], "items", str)


# ============================================================================
# CATEGORY 4: Document Type Validation (4 tests)
# ============================================================================

class TestValidateDocType:
    """Test validate_doc_type function."""

    def test_valid_types(self):
        """Test all valid document types."""
        for doc_type in ALLOWED_DOC_TYPES:
            result = validate_doc_type(doc_type)
            assert result == doc_type

    def test_invalid_type_raises_error(self):
        """Test invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid"):
            validate_doc_type("invalid_type")

    def test_none_raises_error(self):
        """Test None raises error."""
        with pytest.raises(ValueError):
            validate_doc_type(None)

    def test_case_sensitive(self):
        """Test type validation is case-sensitive."""
        with pytest.raises(ValueError):
            validate_doc_type("CODE")  # uppercase


# ============================================================================
# CATEGORY 5: Tags Validation (8 tests)
# ============================================================================

class TestValidateTags:
    """Test validate_tags function."""

    def test_valid_tags(self):
        """Test valid tags are accepted."""
        result = validate_tags(["python", "test", "code-review"], "tags")
        assert result == ["python", "test", "code-review"]

    def test_empty_list_returns_empty(self):
        """Test empty list returns empty list."""
        result = validate_tags([], "tags")
        assert result == []

    def test_none_returns_empty(self):
        """Test None returns empty list."""
        result = validate_tags(None, "tags")
        assert result == []

    def test_filters_empty_strings(self):
        """Test empty strings in tags are filtered."""
        result = validate_tags(["python", "", "test"], "tags")
        assert result == ["python", "test"]

    def test_invalid_characters_raise_error(self):
        """Test tags with invalid characters raise ValueError."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_tags(["python", "test@invalid"], "tags")

    def test_special_chars_rejected(self):
        """Test special characters are rejected."""
        with pytest.raises(ValueError):
            validate_tags(["test-tag!", "another"], "tags")

    def test_spaces_rejected(self):
        """Test spaces are rejected in tags."""
        with pytest.raises(ValueError):
            validate_tags(["test tag"], "tags")

    def test_numbers_and_hyphens_allowed(self):
        """Test numbers and hyphens are allowed."""
        result = validate_tags(["python3", "test-2-tag", "v1-beta"], "tags")
        assert result == ["python3", "test-2-tag", "v1-beta"]


# ============================================================================
# CATEGORY 6: Project Validation (7 tests)
# ============================================================================

class TestValidateProject:
    """Test validate_project function."""

    def test_valid_project(self):
        """Test valid project name."""
        result = validate_project("my-project", "project")
        assert result == "my-project"

    def test_none_returns_none(self):
        """Test None returns None."""
        result = validate_project(None, "project")
        assert result is None

    def test_alphanumeric_valid(self):
        """Test alphanumeric project names."""
        result = validate_project("MyProject123", "project")
        assert result == "MyProject123"

    def test_hyphen_underscore_valid(self):
        """Test hyphens and underscores in project names."""
        result = validate_project("my_project-2", "project")
        assert result == "my_project-2"

    def test_invalid_characters_raise_error(self):
        """Test invalid characters raise ValueError."""
        with pytest.raises(ValueError, match="Invalid"):
            validate_project("my@project", "project")

    def test_max_length_100(self):
        """Test max length is 100 characters."""
        valid = "a" * 100
        result = validate_project(valid, "project")
        assert result == valid

    def test_exceeds_max_length(self):
        """Test exceeding max length raises ValueError."""
        invalid = "a" * 101
        with pytest.raises(ValueError):
            validate_project(invalid, "project")


# ============================================================================
# CATEGORY 7: Content Validation (6 tests)
# ============================================================================

class TestValidateContent:
    """Test validate_content function."""

    def test_valid_content(self):
        """Test valid content."""
        result = validate_content("This is content", "content")
        assert result == "This is content"

    def test_empty_content_raises_error(self):
        """Test empty content raises ValueError."""
        with pytest.raises(ValueError, match="at least 1"):
            validate_content("", "content")

    def test_none_raises_error(self):
        """Test None raises ValueError."""
        with pytest.raises(ValueError):
            validate_content(None, "content")

    def test_max_size_1mb(self):
        """Test content cannot exceed 1MB."""
        # Create content just under limit
        content_under_limit = "x" * (MAX_CONTENT_SIZE - 10)
        result = validate_content(content_under_limit, "content")
        assert result == content_under_limit

    def test_exceeds_1mb_limit(self):
        """Test content exceeding 1MB raises ValueError."""
        content_over_limit = "x" * (MAX_CONTENT_SIZE + 1)
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_content(content_over_limit, "content")

    def test_unicode_content_valid(self):
        """Test unicode content is valid and counted correctly."""
        # 3-byte UTF-8 characters
        unicode_content = "你好世界" * 100  # Each char is 3 bytes
        result = validate_content(unicode_content, "content")
        assert result == unicode_content


# ============================================================================
# CATEGORY 8: Limit Validation (5 tests)
# ============================================================================

class TestValidateLimit:
    """Test validate_limit function."""

    def test_none_returns_default(self):
        """Test None returns default value."""
        result = validate_limit(None, "limit", default=10)
        assert result == 10

    def test_custom_default(self):
        """Test custom default value."""
        result = validate_limit(None, "limit", default=20)
        assert result == 20

    def test_valid_limit(self):
        """Test valid limit."""
        result = validate_limit(50, "limit")
        assert result == 50

    def test_limit_range_1_1000(self):
        """Test limit is bounded 1-1000."""
        assert validate_limit(1, "limit") == 1
        assert validate_limit(1000, "limit") == 1000

    def test_limit_outside_range_raises_error(self):
        """Test limit outside 1-1000 raises ValueError."""
        with pytest.raises(ValueError, match="at least 1"):
            validate_limit(0, "limit")
        with pytest.raises(ValueError, match="at most 1000"):
            validate_limit(1001, "limit")


# ============================================================================
# CATEGORY 9: Constants Validation (3 tests)
# ============================================================================

class TestConstants:
    """Test validation constants."""

    def test_allowed_doc_types(self):
        """Test ALLOWED_DOC_TYPES constant."""
        assert "code" in ALLOWED_DOC_TYPES
        assert "note" in ALLOWED_DOC_TYPES
        assert "reference" in ALLOWED_DOC_TYPES
        assert "conversation" in ALLOWED_DOC_TYPES
        assert len(ALLOWED_DOC_TYPES) == 4

    def test_max_content_size(self):
        """Test MAX_CONTENT_SIZE is 1MB."""
        assert MAX_CONTENT_SIZE == 1048576  # 1024 * 1024

    def test_patterns(self):
        """Test regex patterns."""
        # TAG_PATTERN
        assert TAG_PATTERN.match("valid-tag")
        assert TAG_PATTERN.match("tag123")
        assert not TAG_PATTERN.match("tag!")

        # PROJECT_PATTERN
        assert PROJECT_PATTERN.match("valid_project")
        assert PROJECT_PATTERN.match("project-123")
        assert not PROJECT_PATTERN.match("project!")


# ============================================================================
# CATEGORY 10: Integration Tests (5 tests)
# ============================================================================

class TestValidationIntegration:
    """Integration tests for validation functions."""

    def test_memory_store_validation_workflow(self):
        """Test validation workflow for memory store operation."""
        content = validate_content("Code snippet", "content")
        doc_type = validate_doc_type("code")
        source = validate_string("github", "source")
        tags = validate_tags(["python", "test"], "tags")
        project = validate_project("my-project", "project")

        assert content == "Code snippet"
        assert doc_type == "code"
        assert source == "github"
        assert tags == ["python", "test"]
        assert project == "my-project"

    def test_search_validation_workflow(self):
        """Test validation workflow for search operation."""
        query = validate_string("search term", "query")
        limit = validate_limit(20, "limit")

        assert query == "search term"
        assert limit == 20

    def test_invalid_workflow_stops_at_first_error(self):
        """Test validation stops at first error."""
        with pytest.raises(ValueError):
            validate_doc_type("invalid")
            validate_string("should not reach", "field")

    def test_full_validation_chain_success(self):
        """Test full validation chain succeeds with valid data."""
        data = {
            "content": "def test(): pass",
            "type": "code",
            "source": "github",
            "tags": ["python", "test"],
            "project": "claude-code",
            "limit": 50
        }

        content = validate_content(data["content"])
        doc_type = validate_doc_type(data["type"])
        source = validate_string(data["source"], "source")
        tags = validate_tags(data["tags"])
        project = validate_project(data["project"])
        limit = validate_limit(data["limit"])

        assert all([content, doc_type, source, tags, project, limit])

    def test_full_validation_chain_fails_on_bad_input(self):
        """Test full validation chain fails on invalid data."""
        invalid_data = {
            "content": "test",
            "type": "invalid_type",
            "source": "github",
        }

        # Should fail on invalid type
        with pytest.raises(ValueError):
            validate_doc_type(invalid_data["type"])
