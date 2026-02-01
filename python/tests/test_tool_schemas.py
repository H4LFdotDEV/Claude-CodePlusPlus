# test_tool_schemas.py
# Comprehensive test suite for tool schemas
# Tests cover: schema structure, completeness, field validation

import pytest
from memory_mcp.tool_schemas import (
    get_tool_schemas,
    TOOL_MEMORY_STORE,
    TOOL_MEMORY_SEARCH,
    TOOL_MEMORY_RECALL,
    TOOL_MEMORY_DELETE,
    TOOL_MEMORY_LIST,
    TOOL_SESSION_SAVE,
    TOOL_SESSION_RESTORE,
    TOOL_VAULT_WRITE,
    TOOL_VAULT_READ,
    TOOL_MEMORY_STATS,
    ALL_TOOL_NAMES
)


# ============================================================================
# CATEGORY 1: Schema Structure Validation (4 tests)
# ============================================================================

class TestSchemaStructure:
    """Test basic schema structure and required fields."""

    def test_schemas_returned_as_list(self):
        """Test that get_tool_schemas returns a list."""
        schemas = get_tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0

    def test_all_schemas_have_required_fields(self):
        """Test that all schemas have name, description, and inputSchema."""
        schemas = get_tool_schemas()
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "inputSchema" in schema
            assert isinstance(schema["name"], str)
            assert isinstance(schema["description"], str)
            assert isinstance(schema["inputSchema"], dict)

    def test_all_input_schemas_have_type_and_properties(self):
        """Test that all inputSchemas have type and properties."""
        schemas = get_tool_schemas()
        for schema in schemas:
            input_schema = schema["inputSchema"]
            assert "type" in input_schema
            assert input_schema["type"] == "object"
            assert "properties" in input_schema
            assert isinstance(input_schema["properties"], dict)

    def test_schema_names_are_unique(self):
        """Test that all schema names are unique."""
        schemas = get_tool_schemas()
        names = [s["name"] for s in schemas]
        assert len(names) == len(set(names))


# ============================================================================
# CATEGORY 2: Tool Count and Coverage (2 tests)
# ============================================================================

class TestToolCoverage:
    """Test that all expected tools are defined."""

    def test_exactly_20_tools_defined(self):
        """Test that exactly 20 tools are defined (10 core + 5 research + 5 tier)."""
        schemas = get_tool_schemas()
        assert len(schemas) == 20

    def test_all_expected_tools_present(self):
        """Test that all expected tools are in schemas."""
        schemas = get_tool_schemas()
        tool_names = [s["name"] for s in schemas]
        expected_tools = [
            TOOL_MEMORY_STORE,
            TOOL_MEMORY_SEARCH,
            TOOL_MEMORY_RECALL,
            TOOL_MEMORY_DELETE,
            TOOL_MEMORY_LIST,
            TOOL_SESSION_SAVE,
            TOOL_SESSION_RESTORE,
            TOOL_VAULT_WRITE,
            TOOL_VAULT_READ,
            TOOL_MEMORY_STATS
        ]
        for tool in expected_tools:
            assert tool in tool_names


# ============================================================================
# CATEGORY 3: Individual Tool Schema Tests (4 tests)
# ============================================================================

class TestMemoryStoreSchema:
    """Test memory_store tool schema."""

    def test_memory_store_has_correct_structure(self):
        """Test memory_store schema structure."""
        schemas = get_tool_schemas()
        store_schema = next(s for s in schemas if s["name"] == TOOL_MEMORY_STORE)

        assert "content" in store_schema["inputSchema"]["properties"]
        assert "type" in store_schema["inputSchema"]["properties"]
        assert "source" in store_schema["inputSchema"]["properties"]
        assert "tags" in store_schema["inputSchema"]["properties"]
        assert "project" in store_schema["inputSchema"]["properties"]

    def test_memory_store_has_required_fields(self):
        """Test memory_store required fields."""
        schemas = get_tool_schemas()
        store_schema = next(s for s in schemas if s["name"] == TOOL_MEMORY_STORE)

        required = store_schema["inputSchema"].get("required", [])
        assert "content" in required
        assert "type" in required
        assert "source" in required

    def test_memory_store_type_enum(self):
        """Test memory_store type field has correct enum."""
        schemas = get_tool_schemas()
        store_schema = next(s for s in schemas if s["name"] == TOOL_MEMORY_STORE)

        type_enum = store_schema["inputSchema"]["properties"]["type"]["enum"]
        assert "code" in type_enum
        assert "note" in type_enum
        assert "conversation" in type_enum
        assert "reference" in type_enum


class TestMemorySearchSchema:
    """Test memory_search tool schema."""

    def test_memory_search_has_correct_structure(self):
        """Test memory_search schema structure."""
        schemas = get_tool_schemas()
        search_schema = next(s for s in schemas if s["name"] == TOOL_MEMORY_SEARCH)

        assert "query" in search_schema["inputSchema"]["properties"]
        assert "type" in search_schema["inputSchema"]["properties"]
        assert "limit" in search_schema["inputSchema"]["properties"]
        assert "filters" in search_schema["inputSchema"]["properties"]

    def test_memory_search_type_enum(self):
        """Test memory_search type field enum values."""
        schemas = get_tool_schemas()
        search_schema = next(s for s in schemas if s["name"] == TOOL_MEMORY_SEARCH)

        type_enum = search_schema["inputSchema"]["properties"]["type"]["enum"]
        assert "text" in type_enum
        assert "semantic" in type_enum
        assert "hybrid" in type_enum


class TestSessionSaveSchema:
    """Test session_save tool schema."""

    def test_session_save_has_correct_structure(self):
        """Test session_save schema structure."""
        schemas = get_tool_schemas()
        save_schema = next(s for s in schemas if s["name"] == TOOL_SESSION_SAVE)

        assert "project_path" in save_schema["inputSchema"]["properties"]
        assert "active_files" in save_schema["inputSchema"]["properties"]
        assert "context" in save_schema["inputSchema"]["properties"]

    def test_session_save_has_required_fields(self):
        """Test session_save required fields."""
        schemas = get_tool_schemas()
        save_schema = next(s for s in schemas if s["name"] == TOOL_SESSION_SAVE)

        required = save_schema["inputSchema"].get("required", [])
        assert "project_path" in required


class TestVaultWriteSchema:
    """Test vault_write tool schema."""

    def test_vault_write_has_correct_structure(self):
        """Test vault_write schema structure."""
        schemas = get_tool_schemas()
        vault_schema = next(s for s in schemas if s["name"] == TOOL_VAULT_WRITE)

        assert "path" in vault_schema["inputSchema"]["properties"]
        assert "content" in vault_schema["inputSchema"]["properties"]
        assert "folder" in vault_schema["inputSchema"]["properties"]
        assert "tags" in vault_schema["inputSchema"]["properties"]

    def test_vault_write_folder_enum(self):
        """Test vault_write folder enum values."""
        schemas = get_tool_schemas()
        vault_schema = next(s for s in schemas if s["name"] == TOOL_VAULT_WRITE)

        folder_enum = vault_schema["inputSchema"]["properties"]["folder"]["enum"]
        assert "code" in folder_enum
        assert "notes" in folder_enum
        assert "conversations" in folder_enum
        assert "references" in folder_enum
        assert "daily" in folder_enum


# ============================================================================
# CATEGORY 4: Tool Constants (3 tests)
# ============================================================================

class TestToolConstants:
    """Test tool name constants."""

    def test_constants_defined(self):
        """Test that all constants are defined."""
        assert TOOL_MEMORY_STORE == "memory_store"
        assert TOOL_MEMORY_SEARCH == "memory_search"
        assert TOOL_MEMORY_RECALL == "memory_recall"
        assert TOOL_MEMORY_DELETE == "memory_delete"
        assert TOOL_MEMORY_LIST == "memory_list"
        assert TOOL_SESSION_SAVE == "session_save"
        assert TOOL_SESSION_RESTORE == "session_restore"
        assert TOOL_VAULT_WRITE == "vault_write"
        assert TOOL_VAULT_READ == "vault_read"
        assert TOOL_MEMORY_STATS == "memory_stats"

    def test_all_tool_names_constant(self):
        """Test ALL_TOOL_NAMES constant."""
        assert len(ALL_TOOL_NAMES) == 20  # 10 core + 5 research + 5 tier
        assert TOOL_MEMORY_STORE in ALL_TOOL_NAMES
        assert TOOL_MEMORY_SEARCH in ALL_TOOL_NAMES
        assert TOOL_SESSION_SAVE in ALL_TOOL_NAMES
        assert TOOL_VAULT_WRITE in ALL_TOOL_NAMES

    def test_tool_names_match_schemas(self):
        """Test that tool constants match schema names."""
        schemas = get_tool_schemas()
        schema_names = [s["name"] for s in schemas]
        for tool_name in ALL_TOOL_NAMES:
            assert tool_name in schema_names


# ============================================================================
# CATEGORY 5: Simple Tool Schemas (5 tests)
# ============================================================================

class TestSimpleToolSchemas:
    """Test schemas for simple tools with minimal fields."""

    def test_memory_recall_schema(self):
        """Test memory_recall schema."""
        schemas = get_tool_schemas()
        recall_schema = next(s for s in schemas if s["name"] == TOOL_MEMORY_RECALL)

        assert "id" in recall_schema["inputSchema"]["properties"]
        required = recall_schema["inputSchema"].get("required", [])
        assert "id" in required

    def test_memory_delete_schema(self):
        """Test memory_delete schema."""
        schemas = get_tool_schemas()
        delete_schema = next(s for s in schemas if s["name"] == TOOL_MEMORY_DELETE)

        assert "id" in delete_schema["inputSchema"]["properties"]
        required = delete_schema["inputSchema"].get("required", [])
        assert "id" in required

    def test_vault_read_schema(self):
        """Test vault_read schema."""
        schemas = get_tool_schemas()
        read_schema = next(s for s in schemas if s["name"] == TOOL_VAULT_READ)

        assert "path" in read_schema["inputSchema"]["properties"]
        required = read_schema["inputSchema"].get("required", [])
        assert "path" in required

    def test_session_restore_schema(self):
        """Test session_restore schema."""
        schemas = get_tool_schemas()
        restore_schema = next(s for s in schemas if s["name"] == TOOL_SESSION_RESTORE)

        assert "session_id" in restore_schema["inputSchema"]["properties"]

    def test_memory_stats_schema(self):
        """Test memory_stats schema."""
        schemas = get_tool_schemas()
        stats_schema = next(s for s in schemas if s["name"] == TOOL_MEMORY_STATS)

        # memory_stats takes no arguments
        props = stats_schema["inputSchema"]["properties"]
        assert len(props) == 0


# ============================================================================
# CATEGORY 6: Description Validation (2 tests)
# ============================================================================

class TestDescriptions:
    """Test that all tools have meaningful descriptions."""

    def test_all_descriptions_present(self):
        """Test that all tools have descriptions."""
        schemas = get_tool_schemas()
        for schema in schemas:
            assert "description" in schema
            assert len(schema["description"]) > 0
            assert isinstance(schema["description"], str)

    def test_all_descriptions_meaningful(self):
        """Test that descriptions are meaningful (not just placeholder text)."""
        schemas = get_tool_schemas()
        for schema in schemas:
            desc = schema["description"]
            # Should not be generic placeholder text
            assert desc != ""
            assert desc != "Tool"
            assert len(desc) > 5  # At least some content


# ============================================================================
# CATEGORY 7: Array Type Validation (2 tests)
# ============================================================================

class TestArrayTypes:
    """Test schemas with array properties."""

    def test_tags_arrays_have_string_items(self):
        """Test that tags arrays specify string items."""
        schemas = get_tool_schemas()
        for schema in schemas:
            props = schema["inputSchema"]["properties"]
            if "tags" in props:
                assert props["tags"]["type"] == "array"
                assert "items" in props["tags"]
                assert props["tags"]["items"]["type"] == "string"

    def test_active_files_array_has_string_items(self):
        """Test that active_files array specifies string items."""
        schemas = get_tool_schemas()
        save_schema = next(s for s in schemas if s["name"] == TOOL_SESSION_SAVE)

        active_files = save_schema["inputSchema"]["properties"]["active_files"]
        assert active_files["type"] == "array"
        assert active_files["items"]["type"] == "string"


# ============================================================================
# CATEGORY 8: Integration Tests (2 tests)
# ============================================================================

class TestSchemaIntegration:
    """Integration tests for tool schemas."""

    def test_get_schemas_returns_consistent_results(self):
        """Test that get_tool_schemas returns consistent results."""
        schemas1 = get_tool_schemas()
        schemas2 = get_tool_schemas()

        # Same number of schemas
        assert len(schemas1) == len(schemas2)

        # Same tool names in same order
        names1 = [s["name"] for s in schemas1]
        names2 = [s["name"] for s in schemas2]
        assert names1 == names2

    def test_all_tools_in_all_tool_names(self):
        """Test that all defined tools are in ALL_TOOL_NAMES."""
        schemas = get_tool_schemas()
        schema_names = {s["name"] for s in schemas}
        all_names = set(ALL_TOOL_NAMES)

        assert schema_names == all_names
