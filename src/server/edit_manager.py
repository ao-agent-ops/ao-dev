import json
from aco.common.logger import logger
from aco.common.constants import (
    DEFAULT_LOG,
    DEFAULT_NOTE,
    DEFAULT_SUCCESS,
    SUCCESS_COLORS,
    SUCCESS_STRING,
)
from aco.server.database_manager import DB
from aco.runner.monkey_patching.api_parser import json_str_to_api_obj


class EditManager:
    """
    Handles user edits to LLM call inputs and outputs, updating the persistent database.
    Uses the llm_calls table in the workflow edits database.
    """

    def set_input_overwrite(self, session_id, node_id, new_input):
        # Overwrite input for node.
        row = DB.query_one_llm_call_input(session_id, node_id)
        input_overwrite = json.loads(row["input"])
        input_overwrite["input"] = new_input
        input_overwrite = json.dumps(input_overwrite)
        DB.set_input_overwrite_query(input_overwrite, session_id, node_id)

    def set_output_overwrite(self, session_id, node_id, new_output: str):
        # Overwrite output for node.
        row = DB.query_one_llm_call_output(session_id, node_id)

        if not row:
            logger.error(
                f"No llm_calls record found for session_id={session_id}, node_id={node_id}"
            )
            return

        try:
            # try to parse the edit of the user
            json_str_to_api_obj(new_output, row["api_type"])
            DB.set_output_overwrite_query(new_output, session_id, node_id)
        except Exception as e:
            logger.error(f"Failed to parse output edit into API object: {e}")

    def erase(self, session_id):
        default_graph = json.dumps({"nodes": [], "edges": []})
        DB.delete_llm_calls_query(session_id)
        DB.update_experiment_graph_topology_query(default_graph, session_id)

    def add_experiment(
        self, session_id, name, timestamp, cwd, command, environment, parent_session_id=None
    ):
        # Initial values.
        default_graph = json.dumps({"nodes": [], "edges": []})
        parent_session_id = parent_session_id if parent_session_id else session_id
        env_json = json.dumps(environment)

        # Use database manager to execute backend-specific SQL
        DB.add_experiment_query(
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
        )

    def update_graph_topology(self, session_id, graph_dict):
        graph_json = json.dumps(graph_dict)
        DB.update_experiment_graph_topology_query(graph_json, session_id)

    def update_timestamp(self, session_id, timestamp):
        """Update the timestamp of an experiment (used for reruns)"""
        DB.update_experiment_timestamp_query(timestamp, session_id)

    def update_run_name(self, session_id, run_name):
        """Update the experiment name/title."""
        DB.update_experiment_name_query(run_name, session_id)

    def update_result(self, session_id, result):
        """Update the experiment result/success status."""
        DB.update_experiment_result_query(result, session_id)

    def update_notes(self, session_id, notes):
        """Update the experiment notes."""
        DB.update_experiment_notes_query(notes, session_id)

    def _color_graph_nodes(self, graph, color):
        # Update border_color for each node
        for node in graph.get("nodes", []):
            node["border_color"] = color

        # Create color preview list with one color entry per node
        color_preview = [color for _ in graph.get("nodes", [])]

        return graph, color_preview

    def add_log(self, session_id, success, new_entry):
        # Write success and new_entry to DB under certain conditions.
        row = DB.query_one(
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
        DB.update_experiment_log_query(
            updated_log, updated_success, color_preview_json, graph_json, session_id
        )

        return updated_graph


EDIT = EditManager()
