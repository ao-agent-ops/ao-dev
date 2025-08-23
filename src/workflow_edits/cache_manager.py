import uuid
import json
import dill
from common.constants import ACO_ATTACHMENT_CACHE
from workflow_edits import db
from common.utils import stream_hash, save_io_stream
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

    def attachment_ids_to_paths(self, attachment_ids):
        # file_path can be None if user doesn't want to cache?
        file_paths = [self.get_file_path(attachment_id) for attachment_id in attachment_ids]
        # assert all(f is not None for f in file_paths), "All file paths should be non-None"
        return [f for f in file_paths if f is not None]

    def get_in_out(self, input_dict, api_type, cache=True):
        from agent_copilot.context_manager import get_session_id

        # Pickle input object.
        input_dict = untaint_if_needed(input_dict)

        input_pickle = dill.dumps(input_dict)
        input_hash = db.hash_input(input_pickle)
        print(f"[cache] Input hash: {input_hash}")

        # Check if API call with same session_id & input has been made before.
        session_id = get_session_id()
        print(f"[cache] Looking up in session: {session_id}, hash: {input_hash}")
        row = db.query_one(
            "SELECT node_id, input, input_overwrite, output FROM llm_calls WHERE session_id=? AND input_hash=?",
            (session_id, input_hash),
        )
        print(f"[cache] Database lookup result: {'FOUND' if row else 'NOT_FOUND'}")

        if row is None:
            # Insert new row with a new node_id.
            print(f"[cache] Row is None, creating new entry")
            node_id = str(uuid.uuid4())
            if cache:
                db.execute(
                    "INSERT INTO llm_calls (session_id, input, input_hash, node_id, api_type) VALUES (?, ?, ?, ?, ?)",
                    (session_id, input_pickle, input_hash, node_id, api_type),
                )
            return input_dict, None, node_id

        # Use data from previous LLM call.
        print(f"[cache] Row found! node_id: {row['node_id']}")
        node_id = row["node_id"]
        output = None

        if row["input_overwrite"] is not None:
            print(f"[cache] Using input_overwrite")
            input_dict = dill.loads(row["input_overwrite"])
        if row["output"] is not None:
            print(f"[cache] Found cached output!")
            output = dill.loads(row["output"])
        else:
            print(f"[cache] No cached output found (output column is None)")
        print(
            f"[cache] Returning input_dict, output={'FOUND' if output else 'NONE'}, node_id={node_id}"
        )
        return input_dict, output, node_id

    def cache_output(self, node_id, output_obj):
        from agent_copilot.context_manager import get_session_id

        session_id = get_session_id()
        output_pickle = dill.dumps(output_obj)
        db.execute(
            "UPDATE llm_calls SET output=? WHERE session_id=? AND node_id=?",
            (output_pickle, session_id, node_id),
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
        # Get all subrun names for this parent session
        rows = db.query_all("SELECT name FROM experiments WHERE parent_session_id=?", (session_id,))
        if not rows:
            return []  # Return empty list if no subruns found
        return [row["name"] for row in rows if row["name"] is not None]


CACHE = CacheManager()
