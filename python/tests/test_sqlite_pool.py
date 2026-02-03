# test_sqlite_pool.py
# Tests for SQLite connection pooling

import pytest
import threading
import time
from memory_mcp.sqlite_index import SQLiteConnectionPool, SQLiteIndex, MemoryDocument


class TestSQLiteConnectionPool:
    """Tests for SQLiteConnectionPool."""

    def test_pool_creation(self, temp_dir):
        """Test pool is created with correct size."""
        import os
        db_path = os.path.join(temp_dir, "pool_test.db")
        pool = SQLiteConnectionPool(db_path, pool_size=3)
        assert pool.pool_size == 3
        pool.close_all()

    def test_get_connection(self, temp_dir):
        """Test getting connection from pool."""
        import os
        db_path = os.path.join(temp_dir, "pool_test.db")
        pool = SQLiteConnectionPool(db_path, pool_size=2)

        with pool.get_connection() as conn:
            assert conn is not None
            # Verify PRAGMA settings
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode == "wal"

        pool.close_all()

    def test_connection_reuse(self, temp_dir):
        """Test connections are reused from pool."""
        import os
        db_path = os.path.join(temp_dir, "pool_test.db")
        pool = SQLiteConnectionPool(db_path, pool_size=1)  # Pool size of 1

        # Get and return connection
        with pool.get_connection() as conn1:
            conn1_id = id(conn1)

        # With pool size of 1, should get same connection back
        with pool.get_connection() as conn2:
            conn2_id = id(conn2)

        # Same connection object should be reused
        assert conn1_id == conn2_id

        pool.close_all()

    def test_concurrent_access(self, temp_dir):
        """Test pool handles concurrent access."""
        import os
        db_path = os.path.join(temp_dir, "pool_test.db")
        pool = SQLiteConnectionPool(db_path, pool_size=3)
        results = []

        def worker(worker_id):
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()[0]
                results.append((worker_id, result))
                time.sleep(0.01)  # Simulate work

        # Create threads
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # All workers should succeed
        assert len(results) == 5
        assert all(result == 1 for _, result in results)

        pool.close_all()

    def test_pool_overflow(self, temp_dir):
        """Test pool creates temporary connections when exhausted."""
        import os
        db_path = os.path.join(temp_dir, "pool_test.db")
        pool = SQLiteConnectionPool(db_path, pool_size=2)

        # Hold 2 connections from pool
        with pool.get_connection() as conn1:
            with pool.get_connection() as conn2:
                # Pool is now exhausted
                # This should create a temporary connection
                with pool.get_connection() as conn3:
                    assert conn3 is not None

        pool.close_all()

    def test_close_all(self, temp_dir):
        """Test close_all properly closes connections."""
        import os
        db_path = os.path.join(temp_dir, "pool_test.db")
        pool = SQLiteConnectionPool(db_path, pool_size=2)

        # Close all connections
        pool.close_all()

        # Pool should be empty
        assert pool._pool.empty()


class TestSQLiteIndexPooling:
    """Test SQLiteIndex with connection pooling."""

    def test_index_uses_pool(self, temp_dir):
        """Test SQLiteIndex uses connection pool."""
        import os
        db_path = os.path.join(temp_dir, "index_pool_test.db")
        index = SQLiteIndex(path=db_path)

        # Verify pool exists
        assert hasattr(index, '_pool')
        assert isinstance(index._pool, SQLiteConnectionPool)

        index.close()

    def test_multiple_operations_reuse_connections(self, temp_dir):
        """Test multiple operations reuse pooled connections."""
        import os
        db_path = os.path.join(temp_dir, "index_pool_test.db")
        index = SQLiteIndex(path=db_path)

        # Perform multiple operations
        for i in range(10):
            doc = MemoryDocument(
                id=f"pool-test-{i}",
                content=f"Test document {i}",
                doc_type="note",
                source="test.py",
            )
            index.insert(doc)
            retrieved = index.get(doc.id)
            assert retrieved.id == doc.id
            index.delete(doc.id)

        index.close()

    def test_concurrent_index_operations(self, temp_dir):
        """Test concurrent operations on SQLiteIndex."""
        import os
        db_path = os.path.join(temp_dir, "index_pool_test.db")
        index = SQLiteIndex(path=db_path)

        def worker(worker_id):
            doc = MemoryDocument(
                id=f"concurrent-{worker_id}",
                content=f"Concurrent document {worker_id}",
                doc_type="note",
                source="test.py",
            )
            index.insert(doc)
            retrieved = index.get(doc.id)
            assert retrieved.id == doc.id

        # Create threads
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify all documents were inserted
        assert index.count() == 5

        index.close()
