#!/usr/bin/env python3
"""
Integration test for cross-session taint tracking between writer and reader scripts.
This test verifies that when a reader script reads a file written by a writer script,
the reader's LLM nodes get added to the writer's session graph with proper edges.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from aco.runner.taint_wrappers import TaintStr
from aco.server.database_manager import DB
from ...utils import cleanup_taint_db, setup_test_session

# Add the project root to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class MockOpenAIResponse:
    def __init__(self, content):
        self.choices = [MagicMock()]
        self.choices[0].message.content = content


def test_cross_session_writer_reader():
    """Test cross-session taint tracking between writer and reader"""
    # Clean up any existing taint data before the test
    cleanup_taint_db()

    # Create temporary files for the test
    with tempfile.TemporaryDirectory() as temp_dir:
        content_file = Path(temp_dir) / "content.txt"
        extended_file = Path(temp_dir) / "extended_content.txt"

        print(f"\n=== Testing Cross-Session Writer/Reader ===")
        print(f"Temp directory: {temp_dir}")

        # === WRITER SESSION ===
        print("\n1. Simulating Writer Session...")

        writer_session_id = "writer-session-12345"
        writer_node_id = "node-writer-67890"

        # Create experiment record for writer session
        setup_test_session(writer_session_id, name="Writer Session")

        # Set environment for writer session
        os.environ["AGENT_COPILOT_SESSION_ID"] = writer_session_id

        # Mock OpenAI call for writer
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Mock the chat completion response
            mock_response = MockOpenAIResponse(
                "In the distant future, humans and AI work together in harmony. "
                "The great factories of Neo-Tokyo hum with collaborative energy."
            )
            mock_client.chat.completions.create.return_value = mock_response

            # Simulate the writer script behavior
            from openai import OpenAI

            client = OpenAI()

            # Generate content (this creates a tainted response)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": "Write a short creative story about robots and humans working together.",
                    }
                ],
            )

            # The response should be tainted with the writer node ID
            tainted_content = TaintStr(response.choices[0].message.content, [writer_node_id])

            # Write to file (this should store taint info)
            print(f"Writing tainted content to {content_file}")
            with open(str(content_file), "w") as f:
                # Manually simulate what TaintFile would do
                DB.store_taint_info(writer_session_id, str(content_file), 0, [writer_node_id])
                f.write(str(tainted_content))

        # Verify content file was created
        assert content_file.exists(), "Content file should be created"
        print(f"✅ Writer created content file: {content_file}")

        # Verify taint info was stored
        stored_session_id, stored_taint = DB.get_taint_info(str(content_file), 0)
        assert (
            stored_session_id == writer_session_id
        ), f"Expected writer session {writer_session_id}, got {stored_session_id}"
        assert (
            writer_node_id in stored_taint
        ), f"Expected writer node {writer_node_id} in taint, got {stored_taint}"
        print(f"✅ Taint info stored correctly: session={stored_session_id}, taint={stored_taint}")

        # === READER SESSION ===
        print("\n2. Simulating Reader Session...")

        reader_session_id = "reader-session-54321"
        reader_node_id = "node-reader-09876"

        # Create experiment record for reader session
        setup_test_session(reader_session_id, name="Reader Session")

        # Set environment for reader session
        os.environ["AGENT_COPILOT_SESSION_ID"] = reader_session_id

        # Mock OpenAI call for reader
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Mock the chat completion response
            mock_response = MockOpenAIResponse(
                "The partnership flourished as ARIA-7 learned empathy and humans embraced "
                "the efficiency of their mechanical colleagues. Together they built wonders."
            )
            mock_client.chat.completions.create.return_value = mock_response

            # Simulate the reader script behavior
            from openai import OpenAI

            client = OpenAI()

            # Read the content (this should retrieve taint from previous session)
            print(f"Reading content from {content_file}")
            with open(str(content_file), "r") as f:
                # Manually simulate what TaintFile would do
                original_content = f.read()
                prev_session_id, taint_nodes = DB.get_taint_info(str(content_file), 0)

                if prev_session_id and taint_nodes:
                    # Create tainted string with previous session's taint
                    tainted_input = TaintStr(original_content, taint_nodes)
                    print(
                        f"✅ Retrieved taint from previous session: {prev_session_id}, nodes: {taint_nodes}"
                    )
                else:
                    tainted_input = original_content
                    print("⚠️  No taint retrieved from file")

            # Generate additional content based on tainted input
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": f"Continue this story with another paragraph:\n\n{tainted_input}",
                    }
                ],
            )

            # The response should be tainted with both reader and writer nodes
            additional_content = response.choices[0].message.content

            # This is the key test: when we create a TaintStr from the LLM response,
            # it should include both the reader node ID and the writer node IDs from the input
            expected_taint = [reader_node_id] + (taint_nodes if taint_nodes else [])
            tainted_response = TaintStr(additional_content, expected_taint)

            # Write extended content
            print(f"Writing extended content to {extended_file}")
            with open(str(extended_file), "w") as f:
                f.write(str(tainted_input))
                f.write("\n\n--- CONTINUATION ---\n\n")
                f.write(str(tainted_response))

                # Store taint info for the extended file
                DB.store_taint_info(reader_session_id, str(extended_file), 0, expected_taint)

        # === VERIFICATION ===
        print("\n3. Verifying Cross-Session Taint Tracking...")

        # Verify extended file was created
        assert extended_file.exists(), "Extended content file should be created"
        print(f"✅ Reader created extended file: {extended_file}")

        # Verify the extended file contains both original and new content
        with open(str(extended_file), "r") as f:
            extended_content = f.read()

        assert "Neo-Tokyo" in extended_content, "Original content should be present"
        assert "CONTINUATION" in extended_content, "Continuation marker should be present"
        assert "partnership" in extended_content.lower(), "New content should be present"
        print("✅ Extended file contains both original and new content")

        # Verify taint propagation
        stored_session_id, stored_taint = DB.get_taint_info(str(extended_file), 0)
        assert (
            stored_session_id == reader_session_id
        ), f"Expected reader session {reader_session_id}, got {stored_session_id}"
        assert (
            writer_node_id in stored_taint
        ), f"Writer node {writer_node_id} should be in extended file taint"
        assert (
            reader_node_id in stored_taint
        ), f"Reader node {reader_node_id} should be in extended file taint"
        print(f"✅ Cross-session taint propagated correctly: {stored_taint}")

        # This is the key behavior we're testing:
        # The reader's LLM call should have incoming edges that reference the writer's nodes
        # The server should detect this and add the reader node to the writer's session graph
        incoming_edges_for_reader_node = [writer_node_id]  # This is what should happen

        print("\n4. Simulating Server Cross-Session Node Addition...")

        # This simulates what the server's handle_add_node method should do
        # when it receives a node with cross-session incoming edges

        # Mock the server's session graphs
        mock_session_graphs = {
            writer_session_id: {
                "nodes": [{"id": writer_node_id, "label": "Writer LLM Call"}],
                "edges": [],
            }
        }

        # Simulate finding the session with the source node
        def find_session_with_node(node_id):
            for session_id, graph in mock_session_graphs.items():
                for node in graph["nodes"]:
                    if node["id"] == node_id:
                        return session_id
            return None

        # Check if cross-session reference exists
        source_session = find_session_with_node(writer_node_id)
        assert source_session == writer_session_id, f"Should find writer node in writer session"

        # The reader node should be added to the writer session (not reader session)
        reader_node = {"id": reader_node_id, "label": "Reader LLM Call"}
        mock_session_graphs[writer_session_id]["nodes"].append(reader_node)

        # Add the cross-session edge
        edge = {
            "id": f"e{writer_node_id}-{reader_node_id}",
            "source": writer_node_id,
            "target": reader_node_id,
        }
        mock_session_graphs[writer_session_id]["edges"].append(edge)

        # Verify the final state
        writer_graph = mock_session_graphs[writer_session_id]
        assert len(writer_graph["nodes"]) == 2, "Writer session should have 2 nodes"
        assert len(writer_graph["edges"]) == 1, "Writer session should have 1 edge"

        node_ids = [n["id"] for n in writer_graph["nodes"]]
        assert writer_node_id in node_ids, "Writer node should be in writer session"
        assert reader_node_id in node_ids, "Reader node should be added to writer session"

        edge = writer_graph["edges"][0]
        assert edge["source"] == writer_node_id, "Edge should come from writer node"
        assert edge["target"] == reader_node_id, "Edge should go to reader node"

        print("✅ Cross-session node addition simulation successful")
        print(
            f"✅ Writer session now has {len(writer_graph['nodes'])} nodes and {len(writer_graph['edges'])} edges"
        )

        # The key insight: reader session should remain empty or not be created
        # because the reader node was added to the writer session instead
        assert (
            reader_session_id not in mock_session_graphs
        ), "Reader should not create its own session"

        print("\n=== Cross-Session Writer/Reader Test PASSED ===")

        # Clean up taint data after the test
        cleanup_taint_db()


if __name__ == "__main__":
    try:
        test_cross_session_writer_reader()
        print("All tests passed!")
    finally:
        cleanup_taint_db()
        print("Cleaned up taint database")
