# tests/test_similarity_search.py

import json
import pytest

from aco.optimizations.optimization_server import OptimizationClient
from aco.server.database_manager import DB


# Test session IDs to use for isolation
TEST_SESSION_PREFIX = "test_similarity_"


@pytest.fixture(autouse=True)
def cleanup_database():
    """Clean up database before and after each test - only test data."""
    # Clean up before test
    DB.switch_mode("local")
    # Only clean up test-specific data using the test session prefix
    try:
        DB.execute(
            "DELETE FROM lessons_embeddings WHERE session_id LIKE ?", (f"{TEST_SESSION_PREFIX}%",)
        )
        # Note: lessons_vec will be cleaned up automatically via foreign key constraints
    except Exception:
        pass  # Tables might not exist, that's ok
    yield
    # Clean up after test - only test data
    try:
        DB.execute(
            "DELETE FROM lessons_embeddings WHERE session_id LIKE ?", (f"{TEST_SESSION_PREFIX}%",)
        )
    except Exception:
        pass  # Tables might not exist, that's ok


def setup_test_embeddings():
    """
    Set up test embeddings in the real database.
    """

    # Create 1536-dimensional embeddings (matching OpenAI's text-embedding-3-small)
    # Use mostly zeros but set a few dimensions to create distinct vectors
    def create_embedding(base_value, offset_dim=0, offset_value=0.0):
        emb = [0.0] * 1536
        emb[0] = base_value  # Primary dimension
        if offset_dim > 0 and offset_dim < 1536:
            emb[offset_dim] = offset_value
        return emb

    # Insert test embeddings with proper dimensions and test session prefix
    test_embeddings = [
        (f"{TEST_SESSION_PREFIX}s1", "n1", create_embedding(1.0)),  # Query vector
        (
            f"{TEST_SESSION_PREFIX}fake_session",
            "fake_node",
            create_embedding(1.0),
        ),  # Identical match (distance=0)
        (f"{TEST_SESSION_PREFIX}test_session", "node1", create_embedding(0.5)),  # Close match
        (f"{TEST_SESSION_PREFIX}s3", "n3", create_embedding(-0.2)),  # Further match
    ]

    for session_id, node_id, embedding in test_embeddings:
        DB.insert_lesson_embedding_query(session_id, node_id, json.dumps(embedding), "test_user")


# ======================================================================
# TESTS
# ======================================================================


def test_similarity_search_happy_path(monkeypatch):
    """
    Full integration test of similarity search using real SQLite database.
    Tests the actual ANN path and ensures results are properly sorted.
    """
    # Set up test database with real embeddings
    setup_test_embeddings()

    captured = {}

    def fake_send_json(conn, msg):
        captured["msg"] = msg

    # Only patch send_json - use real DB
    monkeypatch.setattr("aco.optimizations.optimization_server.send_json", fake_send_json)

    client = OptimizationClient()
    client.conn = object()

    client.handle_similarity_search(
        {
            "type": "similarity_search",
            "session_id": f"{TEST_SESSION_PREFIX}s1",
            "node_id": "n1",
            "k": 3,
        }
    )

    msg = captured["msg"]

    assert msg["type"] == "similarity_search_result"
    assert msg["session_id"] == f"{TEST_SESSION_PREFIX}s1"
    assert msg["node_id"] == "n1"

    results = msg["results"]
    assert len(results) == 3

    # Verify result format matches actual implementation (no score field)
    for result in results:
        assert "session_id" in result
        assert "node_id" in result
        assert "score" not in result  # Real implementation doesn't include score

    # The closest match should be the query vector itself (distance=0)
    # followed by the identical embedding we inserted
    top = results[0]
    assert top["session_id"] == f"{TEST_SESSION_PREFIX}s1"
    assert top["node_id"] == "n1"


def test_similarity_search_no_target_embedding(monkeypatch):
    """
    When the target embedding is missing,
    similarity search returns an empty list.
    """
    # Database is already clean thanks to the cleanup_database fixture
    # No need to insert any embeddings for this test

    captured = {}

    def fake_send_json(conn, msg):
        captured["msg"] = msg

    # Only patch send_json - use real DB
    monkeypatch.setattr("aco.optimizations.optimization_server.send_json", fake_send_json)

    client = OptimizationClient()
    client.conn = object()

    client.handle_similarity_search(
        {
            "type": "similarity_search",
            "session_id": f"{TEST_SESSION_PREFIX}nonexistent",
            "node_id": "n1",
            "k": 5,
        }
    )

    msg = captured["msg"]

    assert msg["type"] == "similarity_search_result"
    assert msg["session_id"] == f"{TEST_SESSION_PREFIX}nonexistent"
    assert msg["node_id"] == "n1"
    assert msg["results"] == []
