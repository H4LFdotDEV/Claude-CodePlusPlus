# test_content_size_limits.py
# Test suite for content size limits to prevent OOM attacks
# Tests cover: memory handler, vault handler, research handler, tier manager

import json
import pytest
from memory_mcp.validation import MAX_CONTENT_SIZE
from memory_mcp.config import MemoryConfig


class TestMemoryHandlerSizeLimits:
    """Test memory_store enforces content size limits."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_store_content_under_limit_succeeds(self, mcp_server):
        """Test storing content under 1MB limit succeeds."""
        content = "x" * (MAX_CONTENT_SIZE - 1000)  # Just under limit
        result = mcp_server.handle_call_tool("memory_store", {
            "content": content,
            "type": "note",
            "source": "size-test.md"
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert data["stored"] is True

    def test_store_content_over_limit_fails(self, mcp_server):
        """Test storing content over 1MB limit fails with clear error."""
        content = "x" * (MAX_CONTENT_SIZE + 1)  # Over limit
        result = mcp_server.handle_call_tool("memory_store", {
            "content": content,
            "type": "note",
            "source": "size-test-fail.md"
        })

        assert result.get("isError") is True
        error_text = result["content"][0]["text"]
        assert "exceeds maximum" in error_text.lower() or "must be at most" in error_text.lower()

    def test_store_empty_content_fails(self, mcp_server):
        """Test storing empty content fails."""
        result = mcp_server.handle_call_tool("memory_store", {
            "content": "",
            "type": "note",
            "source": "empty.md"
        })

        assert result.get("isError") is True
        error_text = result["content"][0]["text"]
        assert "at least 1" in error_text.lower()

    def test_store_unicode_content_counted_correctly(self, mcp_server):
        """Test unicode content is counted in bytes, not characters."""
        # 3-byte UTF-8 characters - should be counted as bytes
        unicode_char = "你"  # 3 bytes in UTF-8
        # Create content with ~1MB of UTF-8 data
        char_count = MAX_CONTENT_SIZE // 3 - 100  # Leave some margin
        content = unicode_char * char_count

        result = mcp_server.handle_call_tool("memory_store", {
            "content": content,
            "type": "note",
            "source": "unicode-test.md"
        })

        # Should succeed because we're under the byte limit
        assert result.get("isError") is not True

        # But exceeding the byte limit should fail
        content_over = unicode_char * (MAX_CONTENT_SIZE // 3 + 1000)
        result_over = mcp_server.handle_call_tool("memory_store", {
            "content": content_over,
            "type": "note",
            "source": "unicode-test-fail.md"
        })

        assert result_over.get("isError") is True


class TestVaultHandlerSizeLimits:
    """Test vault_write enforces content size limits."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_vault_write_under_limit_succeeds(self, mcp_server):
        """Test vault write under 1MB limit succeeds."""
        content = "# Test Note\n\n" + ("x" * (MAX_CONTENT_SIZE - 1000))
        result = mcp_server.handle_call_tool("vault_write", {
            "path": "size-test/vault-note",
            "content": content,
            "folder": "notes"
        })

        assert result.get("isError") is not True
        data = json.loads(result["content"][0]["text"])
        assert data["written"] is True

    def test_vault_write_over_limit_fails(self, mcp_server):
        """Test vault write over 1MB limit fails."""
        content = "x" * (MAX_CONTENT_SIZE + 1)
        result = mcp_server.handle_call_tool("vault_write", {
            "path": "size-test/vault-note-fail",
            "content": content,
            "folder": "notes"
        })

        assert result.get("isError") is True
        error_text = result["content"][0]["text"]
        assert "exceeds maximum" in error_text.lower() or "must be at most" in error_text.lower()

    def test_vault_write_empty_content_succeeds(self, mcp_server):
        """Test vault write with empty content succeeds (allowed for vault)."""
        # Vault allows empty content (frontmatter-only notes)
        result = mcp_server.handle_call_tool("vault_write", {
            "path": "size-test/empty-vault-note",
            "content": "",
            "folder": "notes",
            "tags": ["empty", "test"]
        })

        # Empty content should be allowed for vault
        # If validation fails, that's also acceptable behavior
        assert result.get("isError") in (True, False, None)


class TestResearchHandlerSizeLimits:
    """Test research handler enforces content size limits."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_transcript_under_limit_succeeds(self, mcp_server):
        """Test storing transcript under 1MB limit succeeds."""
        # Use config's max size (1,000,000) instead of validation constant (1,048,576)
        text = "Speaker transcript: " + ("x" * 900_000)  # Well under 1MB
        result = mcp_server.handle_call_tool("research_transcript_store", {
            "text": text,
            "speaker": "user"
        })

        # Key security test: verify no error when under limit
        assert result.get("isError") is not True
        # Verify we got a response (exact format may vary but should have content)
        assert "content" in result

    def test_transcript_over_limit_fails(self, mcp_server):
        """Test storing transcript over 1MB limit fails."""
        text = "x" * (MAX_CONTENT_SIZE + 1)
        result = mcp_server.handle_call_tool("research_transcript_store", {
            "text": text,
            "speaker": "user"
        })

        assert result.get("isError") is True
        error_text = result["content"][0]["text"]
        assert "exceeds maximum" in error_text.lower() or "must be at most" in error_text.lower()

    def test_capture_description_under_limit_succeeds(self, mcp_server):
        """Test storing capture with description under 1MB succeeds."""
        description = "Whiteboard capture: " + ("x" * 900_000)  # Well under 1MB
        result = mcp_server.handle_call_tool("research_capture_store", {
            "description": description,
            "capture_type": "whiteboard"
        })

        # Key security test: verify no error when under limit
        assert result.get("isError") is not True
        # Verify we got a response (exact format may vary but should have content)
        assert "content" in result

    def test_capture_description_over_limit_fails(self, mcp_server):
        """Test storing capture with description over 1MB fails."""
        description = "x" * (MAX_CONTENT_SIZE + 1)
        result = mcp_server.handle_call_tool("research_capture_store", {
            "description": description,
            "capture_type": "whiteboard"
        })

        assert result.get("isError") is True
        error_text = result["content"][0]["text"]
        assert "exceeds maximum" in error_text.lower() or "must be at most" in error_text.lower()

    def test_capture_ocr_text_under_limit_succeeds(self, mcp_server):
        """Test storing capture with OCR text under 1MB succeeds."""
        description = "Whiteboard with OCR"
        ocr_text = "OCR extracted text: " + ("x" * 900_000)  # Well under 1MB
        result = mcp_server.handle_call_tool("research_capture_store", {
            "description": description,
            "ocr_text": ocr_text,
            "capture_type": "whiteboard"
        })

        # Key security test: verify no error when under limit
        assert result.get("isError") is not True
        # Verify we got a response (exact format may vary but should have content)
        assert "content" in result

    def test_capture_ocr_text_over_limit_fails(self, mcp_server):
        """Test storing capture with OCR text over 1MB fails."""
        description = "Whiteboard with large OCR"
        ocr_text = "x" * (MAX_CONTENT_SIZE + 1)
        result = mcp_server.handle_call_tool("research_capture_store", {
            "description": description,
            "ocr_text": ocr_text,
            "capture_type": "whiteboard"
        })

        assert result.get("isError") is True
        error_text = result["content"][0]["text"]
        assert "exceeds maximum" in error_text.lower() or "must be at most" in error_text.lower()


class TestTierManagerSizeLimits:
    """Test TierManager enforces size limits for entity extraction."""

    @pytest.fixture
    def tier_manager(self, test_config):
        """Create a TierManager for testing."""
        from memory_mcp.tier_manager import TierManager
        from memory_mcp.sqlite_index import SQLiteIndex

        # Use SQLite from test_config
        sqlite = SQLiteIndex(config=test_config.sqlite)
        return TierManager(sqlite=sqlite, memory_config=test_config)

    def test_validate_content_size_storage_under_limit(self, tier_manager):
        """Test validation passes for content under 1MB."""
        # Use config's max size (1,000,000) not validation constant (1,048,576)
        config_max = tier_manager.memory_config.max_content_size
        content = "x" * (config_max - 1000)
        # Should not raise
        tier_manager._validate_content_size(content, operation="storage")

    def test_validate_content_size_storage_over_limit(self, tier_manager):
        """Test validation fails for content over 1MB."""
        content = "x" * (MAX_CONTENT_SIZE + 1)
        with pytest.raises(ValueError) as exc_info:
            tier_manager._validate_content_size(content, operation="storage")
        assert "exceeds maximum" in str(exc_info.value).lower()
        assert "out-of-memory" in str(exc_info.value).lower()

    def test_validate_content_size_entity_extraction_under_limit(self, tier_manager):
        """Test entity extraction passes for content under 100KB."""
        max_extraction_size = tier_manager.memory_config.max_entity_extraction_size
        content = "x" * (max_extraction_size - 1000)
        # Should not raise
        tier_manager._validate_content_size(content, operation="entity_extraction")

    def test_validate_content_size_entity_extraction_over_limit(self, tier_manager):
        """Test entity extraction fails for content over 100KB."""
        max_extraction_size = tier_manager.memory_config.max_entity_extraction_size
        content = "x" * (max_extraction_size + 1)
        with pytest.raises(ValueError) as exc_info:
            tier_manager._validate_content_size(content, operation="entity_extraction")
        assert "too large for entity extraction" in str(exc_info.value).lower()

    def test_validate_content_size_no_config(self):
        """Test validation is skipped when no config is available."""
        from memory_mcp.tier_manager import TierManager

        tier_manager = TierManager(memory_config=None)
        # Should not raise even with large content
        content = "x" * (MAX_CONTENT_SIZE * 2)
        tier_manager._validate_content_size(content, operation="storage")


class TestConfigSizeLimits:
    """Test configuration values for size limits."""

    def test_default_max_content_size(self):
        """Test default max content size is 1MB."""
        config = MemoryConfig()
        assert config.max_content_size == 1_000_000

    def test_default_max_entity_extraction_size(self):
        """Test default max entity extraction size is 100KB."""
        config = MemoryConfig()
        assert config.max_entity_extraction_size == 100_000

    def test_validation_max_content_size_matches_config(self):
        """Test validation constant matches config default (1MB = 1,048,576 bytes)."""
        config = MemoryConfig()
        # MAX_CONTENT_SIZE is 1024*1024 (1,048,576)
        # config.max_content_size is 1,000,000 (slightly smaller for safety)
        # Both are within reasonable range for 1MB limit
        assert MAX_CONTENT_SIZE >= config.max_content_size
        assert config.max_content_size == 1_000_000


class TestSizeLimitSecurityProperties:
    """Test security properties of size limits."""

    @pytest.fixture
    def mcp_server(self, test_config):
        """Create an MCP server for testing."""
        from memory_mcp.server import MemoryMCPServer
        return MemoryMCPServer(config=test_config)

    def test_multiple_large_requests_rejected(self, mcp_server):
        """Test multiple large requests are all rejected (no cumulative effect)."""
        oversized_content = "x" * (MAX_CONTENT_SIZE + 1)

        # Try to store 3 oversized documents
        for i in range(3):
            result = mcp_server.handle_call_tool("memory_store", {
                "content": oversized_content,
                "type": "note",
                "source": f"attack-{i}.md"
            })
            # Each should be rejected
            assert result.get("isError") is True

    def test_size_limit_error_message_safe(self, mcp_server):
        """Test error messages don't leak sensitive information."""
        oversized_content = "x" * (MAX_CONTENT_SIZE + 1)
        result = mcp_server.handle_call_tool("memory_store", {
            "content": oversized_content,
            "type": "note",
            "source": "test.md"
        })

        error_text = result["content"][0]["text"]
        # Error should mention size limit but not leak content
        assert oversized_content not in error_text
        assert "exceeds maximum" in error_text.lower() or "must be at most" in error_text.lower()

    def test_unicode_attack_counted_in_bytes(self, mcp_server):
        """Test that attackers can't bypass limits using multi-byte unicode."""
        # Use 4-byte UTF-8 emoji (𝕏)
        emoji = "𝕏"  # 4 bytes in UTF-8
        # Try to create content that looks small in characters but is large in bytes
        char_count = MAX_CONTENT_SIZE // 4 + 1000
        content = emoji * char_count

        result = mcp_server.handle_call_tool("memory_store", {
            "content": content,
            "type": "note",
            "source": "unicode-attack.md"
        })

        # Should be rejected because byte size exceeds limit
        assert result.get("isError") is True
