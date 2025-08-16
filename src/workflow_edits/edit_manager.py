import json
from common.constants import (
    DEFAULT_LOG,
    DEFAULT_NOTE,
    DEFAULT_SUCCESS,
    SUCCESS_COLORS,
    SUCCESS_STRING,
)
from workflow_edits import db
from workflow_edits.utils import set_input_string, set_output_string


class EditManager:
    """
    Handles user edits to LLM call inputs and outputs, updating the persistent database.
    Uses the llm_calls table in the workflow edits database.
    """

    def set_input_overwrite(self, session_id, node_id, new_input):
        # Overwrite input for node.
        row = db.query_one(
            "SELECT input, api_type FROM llm_calls WHERE session_id=? AND node_id=?",
            (session_id, node_id),
        )
        input_overwrite = set_input_string(row["input"], new_input, row["api_type"])
        db.execute(
            "UPDATE llm_calls SET input_overwrite=?, output=NULL WHERE session_id=? AND node_id=?",
            (input_overwrite, session_id, node_id),
        )

    def set_output_overwrite(self, session_id, node_id, new_output):
        # Overwrite output for node.
        row = db.query_one(
            "SELECT output, api_type FROM llm_calls WHERE session_id=? AND node_id=?",
            (session_id, node_id),
        )
        output_overwrite = set_output_string(row["output"], new_output, row["api_type"])
        db.execute(
            "UPDATE llm_calls SET output=? WHERE session_id=? AND node_id=?",
            (output_overwrite, session_id, node_id),
        )

    def erase(self, session_id):
        default_graph = json.dumps({"nodes": [], "edges": []})
        db.execute("DELETE FROM llm_calls WHERE session_id=?", (session_id,))
        db.execute(
            "UPDATE experiments SET graph_topology=? WHERE session_id=?",
            (default_graph, session_id),
        )

    def add_experiment(
        self, session_id, name, timestamp, cwd, command, environment, parent_session_id=None
    ):
        # Initial values.
        default_graph = json.dumps({"nodes": [], "edges": []})
        parent_session_id = parent_session_id if parent_session_id else session_id

        env_json = json.dumps(environment)
        db.execute(
            "INSERT INTO experiments (session_id, parent_session_id, name, graph_topology, timestamp, cwd, command, environment, success, notes, log) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                parent_session_id,
                name,
                default_graph,
                timestamp,
                cwd,
                command,
                env_json,
                DEFAULT_SUCCESS,
                DEFAULT_NOTE,
                DEFAULT_LOG,
            ),
        )

    def update_graph_topology(self, session_id, graph_dict):
        graph_json = json.dumps(graph_dict)
        db.execute(
            "UPDATE experiments SET graph_topology=? WHERE session_id=?", (graph_json, session_id)
        )

    def update_timestamp(self, session_id, timestamp):
        """Update the timestamp of an experiment (used for reruns)"""
        db.execute("UPDATE experiments SET timestamp=? WHERE session_id=?", (timestamp, session_id))

    def _color_graph_nodes(self, graph, color):
        # Update border_color for each node
        for node in graph.get("nodes", []):
            node["border_color"] = color

        # Create color preview list with one color entry per node
        color_preview = [color for _ in graph.get("nodes", [])]

        return graph, color_preview

    def add_log(self, session_id, success, new_entry):
        # Write success and new_entry to DB under certain conditions.
        row = db.query_one(
            "SELECT log, success, graph_topology FROM experiments WHERE session_id=?", (session_id,)
        )

        existing_log = row["log"]
        existing_success = row["success"]
        graph = json.loads(row["graph_topology"])

        # Handle log entry logic
        if new_entry is None:
            # If new_entry is None, leave the existing entry
            updated_log = existing_log
        elif existing_log == DEFAULT_LOG:
            # If the log is empty, set it to the new entry
            updated_log = new_entry
        else:
            # If log has entries, append the new entry
            updated_log = existing_log + "\n" + new_entry

        # Handle success logic
        if success is None:
            updated_success = existing_success
        else:
            updated_success = SUCCESS_STRING[success]

        # Color nodes.
        node_color = SUCCESS_COLORS[updated_success]
        updated_graph, updated_color_preview = self._color_graph_nodes(graph, node_color)

        # Update experiments table with new `log`, `success`, `color_preview`, and `graph_topology`
        graph_json = json.dumps(updated_graph)
        color_preview_json = json.dumps(updated_color_preview)
        db.execute(
            "UPDATE experiments SET log=?, success=?, color_preview=?, graph_topology=? WHERE session_id=?",
            (updated_log, updated_success, color_preview_json, graph_json, session_id),
        )

        return updated_graph


EDIT = EditManager()
