import uuid
import json
import pickle
from ast import literal_eval
from common.constants import ACO_ATTACHMENT_CACHE
from workflow_edits import db
from workflow_edits.utils import response_to_json
from workflow_edits.utils import stream_hash, save_io_stream
from runtime_tracing.taint_wrappers import untaint_if_needed


class CacheManager:
    """
    Handles persistent caching and retrieval of LLM call inputs/outputs per experiment session.
    """

    def __init__(self):
        # Check if and where to cache attachments.
        # TODO develop-shim determines whether to cache attachments or not
        # TODO server must be able to cope with empty attachment reference
        # TODO we should be able to just remove this init completely.
        # TODO do we even need a class then?
        self.cache_attachments = True
        self.attachment_cache_dir = ACO_ATTACHMENT_CACHE

    def get_subrun_id(self, parent_session_id, name):
        result = db.query_one(
            "SELECT session_id FROM experiments WHERE parent_session_id = ? AND name = ?",
            (parent_session_id, name),
        )
        if result is None:
            return None
        else:
            return result["session_id"]

    def get_parent_session_id(self, session_id):
        result = db.query_one(
            "SELECT parent_session_id FROM experiments WHERE session_id=?",
            (session_id,),
        )
        return result["parent_session_id"]

    def cache_file(self, file_id, file_name, io_stream):
        if not getattr(self, "cache_attachments", False):
            return
        # Early exit if file_id already exists
        if db.query_one("SELECT file_id FROM attachments WHERE file_id=?", (file_id,)):
            return
        # Check if with same content already exists.
        content_hash = stream_hash(io_stream)
        row = db.query_one(
            "SELECT file_path FROM attachments WHERE content_hash=?", (content_hash,)
        )
        # Get appropriate file_path.
        if row is not None:
            file_path = row["file_path"]
        else:
            file_path = save_io_stream(io_stream, file_name, self.attachment_cache_dir)
        # Insert the file_id mapping
        db.execute(
            "INSERT INTO attachments (file_id, content_hash, file_path) VALUES (?, ?, ?)",
            (file_id, content_hash, file_path),
        )

    def get_file_path(self, file_id):
        if not getattr(self, "cache_attachments", False):
            return None
        row = db.query_one("SELECT file_path FROM attachments WHERE file_id=?", (file_id,))
        if row is not None:
            return row["file_path"]
        return None

    def get_in_out(self, session_id, model, input):
        input = untaint_if_needed(input)
        model = untaint_if_needed(model)

        input_hash = db.hash_input(str(input))

        input_string = json.dumps(input)

        # If model is not specified, check for input overwrite but not for cached output.
        row = db.query_one(
            "SELECT input, input_overwrite, node_id FROM llm_calls WHERE session_id=? AND input_hash=?",
            (session_id, input_hash),
        )

        if row is None:
            # Insert new row with a new node_id
            node_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO llm_calls (session_id, model, input, input_hash, node_id) VALUES (?, ?, ?, ?, ?)",
                (session_id, model, input_string, input_hash, node_id),
            )
            return input, None, node_id

        # Use data from previous LLM call.
        input_val = json.loads(row["input"])
        assert input_val is not None
        if isinstance(row["input_overwrite"], str):
            input_overwrite_val = row["input_overwrite"]
        else:
            input_overwrite_val = json.loads(row["input_overwrite"])

        if input_overwrite_val is not None:
            input_to_use = input_overwrite_val
        else:
            input_to_use = input_val

        node_id = row["node_id"]

        # If model is specified, also check for cached output.
        output = None
        if model:
            row = db.query_one(
                "SELECT output FROM llm_calls WHERE session_id=? AND node_id=?",
                (session_id, node_id),
            )
            output = row["output"]

        return input_to_use, output, node_id

    def cache_output(self, session_id, node_id, output, api_type, model=None):
        # Serialize Response object to JSON
        output_to_store = response_to_json(output, api_type)

        if model:
            # This is needed as sometimes the model is unknown when creating the row.
            db.execute(
                "UPDATE llm_calls SET output=?, api_type=?, model=? WHERE session_id=? AND node_id=?",
                (output_to_store, api_type, model, session_id, node_id),
            )
        else:
            db.execute(
                "UPDATE llm_calls SET output=?, api_type=? WHERE session_id=? AND node_id=?",
                (output_to_store, api_type, session_id, node_id),
            )

    def get_finished_runs(self):
        return db.query_all(
            "SELECT session_id, timestamp FROM experiments ORDER BY timestamp DESC", ()
        )

    def get_all_experiments_sorted(self):
        """Get all experiments sorted by timestamp (most recent first)"""
        return db.query_all(
            "SELECT session_id, timestamp, color_preview, name, success, notes, log FROM experiments ORDER BY timestamp DESC",
            (),
        )

    def get_graph(self, session_id):
        return db.query_one(
            "SELECT graph_topology FROM experiments WHERE session_id=?", (session_id,)
        )

    def get_color_preview(self, session_id):
        row = db.query_one(
            "SELECT color_preview FROM experiments WHERE session_id=?", (session_id,)
        )
        if row and row["color_preview"]:
            return json.loads(row["color_preview"])
        return []

    def get_parent_environment(self, parent_session_id):
        return db.query_one(
            "SELECT cwd, command, environment FROM experiments WHERE session_id=?",
            (parent_session_id,),
        )

    def update_color_preview(self, session_id, colors):
        color_preview_json = json.dumps(colors)
        db.execute(
            "UPDATE experiments SET color_preview=? WHERE session_id=?",
            (color_preview_json, session_id),
        )

    def get_exec_command(self, session_id):
        row = db.query_one(
            "SELECT cwd, command, environment FROM experiments WHERE session_id=?", (session_id,)
        )
        if row is None:
            return None, None, None
        return row["cwd"], row["command"], json.loads(row["environment"])

    def clear_db(self):
        """Delete all records from experiments and llm_calls tables."""
        db.execute("DELETE FROM experiments")
        db.execute("DELETE FROM llm_calls")
        # TODO: Should we delete the entire DB file + all attachments?

    def get_session_name(self, session_id):
        row = db.query_one("SELECT name FROM experiments WHERE session_id=?", (session_id,))
        return row["name"]


CACHE = CacheManager()
