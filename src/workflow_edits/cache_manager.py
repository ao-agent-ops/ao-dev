import hashlib
import pickle
import diskcache as dc
import yaml
import uuid

from common.utils import rel_path_to_abs
from workflow_edits.utils import oai_v2_response_to_json
from . import db
from openai.types.responses.response import Response


def cache_key(fn, args, kwargs):
    context = {
        "fn": fn.__module__ + '.' + fn.__qualname__,
        "args": args,
        "kwargs": kwargs,
    }
    try:
        raw = pickle.dumps(context)
    except Exception as e:
        # print("CACHE_KEY PICKLE ERROR")
        # print("Function:", fn)
        # print("Args:", args)
        # print("Kwargs:", kwargs)
        # print("Exception:", e)
        raise
    return raw


class CacheManager:
    """
    Handles persistent caching and retrieval of LLM call inputs/outputs per experiment session.
    Uses the nodes table in the workflow edits database.
    """
    @staticmethod
    def untaint_if_needed(val):
        if hasattr(val, 'get_raw'):
            return val.get_raw()
        return val

    def get_in_out(self, session_id, model, input):
        input = self.untaint_if_needed(input)
        input_hash = db.hash_input(input)
        # print(f"[CACHE] Looking up: session_id={session_id}, model={model}, input_hash={input_hash}")
        row = db.query_one(
            "SELECT input, input_overwrite, output, node_id FROM nodes WHERE session_id=? AND model=? AND input_hash=?",
            (session_id, model, input_hash)
        )
        # print(f"[CACHE] DB lookup result: {row}")
        if row is None:
            # Insert new row with a new node_id
            node_id = str(uuid.uuid4())
            # print(f"[CACHE] No row found, creating new with node_id={node_id}")
            db.execute(
                "INSERT INTO nodes (session_id, model, input, input_hash, node_id) VALUES (?, ?, ?, ?, ?)",
                (session_id, model, input, input_hash, node_id)
            )
            return input, None, None
        input_val = row["input"]
        input_overwrite = row["input_overwrite"]
        output = row["output"]
        node_id = row["node_id"]
        # print(f"[CACHE] Found row: input_val={input_val}, input_overwrite={input_overwrite}, output={output is not None}, node_id={node_id}")
        if output is not None:
            # print(f"[CACHE] Returning cached output")
            return None, output, node_id
        if input_overwrite is not None:
            # print(f"[CACHE] Returning overwritten input: {input_overwrite}")
            return input_overwrite, None, node_id
        # print(f"[CACHE] Returning original input")
        return input, None, node_id

    def cache_output(self, session_id, model, input, output, api_type, node_id=None):
        input_hash = db.hash_input(input)
        # If v2, serialize Response object to JSON
        if api_type == 'openai_v2' and isinstance(output, Response):
            output_to_store = oai_v2_response_to_json(output)
        else:
            output_to_store = output
        
        if node_id:
            db.execute(
                "UPDATE nodes SET output=?, api_type=?, node_id=? WHERE session_id=? AND model=? AND input_hash=?",
                (output_to_store, api_type, node_id, session_id, model, input_hash)
            )
        else:
            db.execute(
                "UPDATE nodes SET output=?, api_type=? WHERE session_id=? AND model=? AND input_hash=?",
                (output_to_store, api_type, session_id, model, input_hash)
            )


CACHE = CacheManager()
