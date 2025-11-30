# tests/test_similarity_search.py

import json
import pytest

from aco.optimizations.optimization_server import OptimizationClient


class DummyDB:
    """
    Fake DB that mimics the real DB API the optimization server uses:
      - get_lesson_embedding_query
      - query_all (ANN stub)
      - query_one  (rowid -> session/node)
    """

    def __init__(self):
        # embeddings stored like real DB (JSON strings)
        self._store = {
            ("s1", "n1"): json.dumps([1.0, 0.0, 0.0]),
            ("fake_session", "fake_node"): json.dumps([1.0, 0.0, 0.0]),  # best match
            ("test_session", "node1"): json.dumps([0.5, 0.0, 0.0]),
            ("s3", "n3"): json.dumps([-0.2, 0.0, 0.0]),
        }

    # -------- PRIMARY QUERY USED BY OPT SERVER -------- #

    def get_lesson_embedding_query(self, session_id, node_id):
        key = (session_id, node_id)
        if key not in self._store:
            return None
        return {
            "session_id": session_id,
            "node_id": node_id,
            "embedding": self._store[key],
        }

    # ANN-like implementation for tests
    def query_all(self, sql, params=()):
        """
        Simulates ANN search. Returns rows with:
            { "session_id": ..., "node_id": ..., "distance": ... }
        SQL contents are ignored – only params[0] (vector JSON) and params[1] (k) matter.
        """
        import numpy as np

        target_vec = np.array(json.loads(params[0]), dtype=float)
        k = params[1]

        rows = []
        for (sid, nid), emb_json in self._store.items():
            # Skip the query vector itself
            if (sid, nid) == ("s1", "n1"):
                continue
            v = np.array(json.loads(emb_json), dtype=float)
            dist = float(np.linalg.norm(target_vec - v))

            rows.append(
                {
                    "session_id": sid,
                    "node_id": nid,
                    "distance": dist,
                }
            )

        rows.sort(key=lambda r: r["distance"])
        return rows[:k]

    # Used by production code to map rowid → (session_id, node_id)
    def query_one(self, sql, params=()):
        sid, nid = params[0]
        return {"session_id": sid, "node_id": nid}


# ======================================================================
# TESTS
# ======================================================================


def test_similarity_search_happy_path(monkeypatch):
    """
    Full simulation of similarity search using dummy embeddings.
    ANN path must work and return sorted results.
    """

    captured = {}

    def fake_send_json(conn, msg):
        captured["msg"] = msg

    # patch in the dummy DB + send_json
    monkeypatch.setattr("aco.optimizations.optimization_server.DB", DummyDB())
    monkeypatch.setattr("aco.optimizations.optimization_server.send_json", fake_send_json)

    client = OptimizationClient()
    client.conn = object()

    client.handle_similarity_search(
        {
            "type": "similarity_search",
            "session_id": "s1",
            "node_id": "n1",
            "k": 3,
        }
    )

    msg = captured["msg"]

    assert msg["type"] == "similarity_search_result"
    assert msg["session_id"] == "s1"
    assert msg["node_id"] == "n1"
    assert msg["k"] == 3

    results = msg["results"]
    assert len(results) == 3

    # must be sorted by similarity
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)

    # best match must be the identical embedding
    top = results[0]
    assert top["session_id"] == "fake_session"
    assert top["node_id"] == "fake_node"


def test_similarity_search_no_target_embedding(monkeypatch):
    """
    When the target embedding is missing,
    similarity search returns an empty list.
    """

    class EmptyDB(DummyDB):
        def get_lesson_embedding_query(self, s, n):
            return None

    captured = {}

    def fake_send_json(conn, msg):
        captured["msg"] = msg

    monkeypatch.setattr("aco.optimizations.optimization_server.DB", EmptyDB())
    monkeypatch.setattr("aco.optimizations.optimization_server.send_json", fake_send_json)

    client = OptimizationClient()
    client.conn = object()

    client.handle_similarity_search(
        {
            "type": "similarity_search",
            "session_id": "s1",
            "node_id": "n1",
            "k": 5,
        }
    )

    msg = captured["msg"]

    assert msg["type"] == "similarity_search_result"
    assert msg["session_id"] == "s1"
    assert msg["node_id"] == "n1"
    assert msg["results"] == []
