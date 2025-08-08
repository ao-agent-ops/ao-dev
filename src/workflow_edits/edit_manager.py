from workflow_edits import db
import json
from openai.types.responses.response import Response
from workflow_edits.utils import swap_output

class EditManager:
    """
    Handles user edits to LLM call inputs and outputs, updating the persistent database.
    Uses the llm_calls table in the workflow edits database.
    """

    def set_input_overwrite(self, session_id, node_id, new_input):
        # original_input, api_type = READ FROM DB
        # TODO: Implement an overwrite input in utils (assume api_type = "openai_v2_response" for now)
        # new_input = overwrite_input(original_input, new_input, api_type)
        new_input_hash = db.hash_input(new_input)
        print("~~~~~~~~~ execute SQL", new_input, new_input_hash, node_id)
        a = db.execute(
            "UPDATE llm_calls SET input_overwrite=?, input_overwrite_hash=?, output=NULL WHERE session_id=? AND node_id=?",
            (new_input, new_input_hash, session_id, node_id)
        )
        print("~~~~~~~~~ executed SQL", a)
        row = db.query_one("SELECT * FROM llm_calls WHERE session_id=? AND node_id=?", (session_id, node_id))
        print("~~~~~~~~~ row after update:", row["input_overwrite"], row["session_id"], row["input_hash"], row["input"])

    def set_output_overwrite(self, session_id, node_id, new_output):
        # Get api_type and output for the given session_id and node_id
        row = db.query_one(
            "SELECT api_type, output FROM llm_calls WHERE session_id=? AND node_id=?",
            (session_id, node_id)
        )
        if not row or row["output"] is None:
            raise ValueError(f"No output found for session_id={session_id}, node_id={node_id}")
        api_type = row["api_type"]
        existing_output = row["output"]
        updated_output_json = swap_output(new_output, existing_output, api_type)
        db.execute(
            "UPDATE llm_calls SET output=? WHERE session_id=? AND node_id=?",
            (updated_output_json, session_id, node_id)
        )

    def erase(self, session_id):
        default_graph = json.dumps({"nodes": [], "edges": []})
        db.execute("DELETE FROM llm_calls WHERE session_id=?", (session_id,))
        db.execute(
            "UPDATE experiments SET graph_topology=? WHERE session_id=?",
            (default_graph, session_id)
        )

    def add_experiment(self, session_id, timestamp, cwd, command):
        default_graph = json.dumps({"nodes": [], "edges": []})
        db.execute(
            "INSERT INTO experiments (session_id, graph_topology, timestamp, cwd, command) VALUES (?, ?, ?, ?, ?)",
            (session_id, default_graph, timestamp, cwd, command)
        )

    def update_graph_topology(self, session_id, graph_dict):
        import json
        graph_json = json.dumps(graph_dict)
        db.execute(
            "UPDATE experiments SET graph_topology=? WHERE session_id=?",
            (graph_json, session_id)
        )
    
    def update_timestamp(self, session_id, timestamp):
        """Update the timestamp of an experiment (used for reruns)"""
        db.execute(
            "UPDATE experiments SET timestamp=? WHERE session_id=?",
            (timestamp, session_id)
        )

EDIT = EditManager() 