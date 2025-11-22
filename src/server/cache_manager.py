import uuid
import json
import dill
import random
from dataclasses import dataclass
from typing import Optional, Any
from aco.common.logger import logger
from aco.common.constants import ACO_ATTACHMENT_CACHE
from aco.server.database_manager import DB
from aco.common.utils import stream_hash, save_io_stream, set_seed
from aco.runner.taint_wrappers import untaint_if_needed
from aco.runner.monkey_patching.api_parser import get_input, get_model_name, set_input
from aco.common.utils import hash_input


@dataclass
class CacheOutput:
    """
    Encapsulates the output of cache operations for LLM calls.

    This dataclass stores all the necessary information returned by cache lookups
    and used for cache storage operations.

    Attributes:
        input_dict: The (potentially modified) input dictionary for the LLM call
        output: The cached output object, None if not cached or cache miss
        node_id: Unique identifier for this LLM call node, None if new call
        input_pickle: Serialized input data for caching purposes
        input_hash: Hash of the input for efficient cache lookups
        session_id: The session ID associated with this cache operation
    """

    input_dict: dict
    output: Optional[Any]
    node_id: Optional[str]
    input_pickle: bytes
    input_hash: str
    session_id: str


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
        result = DB.get_subrun_by_parent_and_name_query(parent_session_id, name)
        if result is None:
            return None
        else:
            return result["session_id"]

    def get_parent_session_id(self, session_id):
        result = DB.get_parent_session_id_query(session_id)
        return result["parent_session_id"]

    def cache_file(self, file_id, file_name, io_stream):
        if not getattr(self, "cache_attachments", False):
            return
        # Early exit if file_id already exists
        if DB.check_attachment_exists_query(file_id):
            return
        # Check if with same content already exists.
        content_hash = stream_hash(io_stream)
        row = DB.get_attachment_by_content_hash_query(content_hash)
        # Get appropriate file_path.
        if row is not None:
            file_path = row["file_path"]
        else:
            file_path = save_io_stream(io_stream, file_name, self.attachment_cache_dir)
        # Insert the file_id mapping
        DB.insert_attachment_query(file_id, content_hash, file_path)

    def get_file_path(self, file_id):
        if not getattr(self, "cache_attachments", False):
            return None
        row = DB.get_attachment_file_path_query(file_id)
        if row is not None:
            return row["file_path"]
        return None

    def attachment_ids_to_paths(self, attachment_ids):
        # file_path can be None if user doesn't want to cache?
        file_paths = [self.get_file_path(attachment_id) for attachment_id in attachment_ids]
        # assert all(f is not None for f in file_paths), "All file paths should be non-None"
        return [f for f in file_paths if f is not None]

    def get_in_out(self, input_dict: dict, api_type: str) -> CacheOutput:
        from aco.runner.context_manager import get_session_id

        # Pickle input object.
        input_dict = untaint_if_needed(input_dict)
        prompt, attachments, tools = get_input(input_dict, api_type)
        model = get_model_name(input_dict, api_type)

        cacheable_input = {
            "input": prompt,
            "attachments": attachments,
            "model": model,
            "tools": tools,
        }
        input_pickle = dill.dumps(cacheable_input)
        input_hash = hash_input(input_pickle)

        # Check if API call with same session_id & input has been made before.
        session_id = get_session_id()

        row = DB.get_llm_call_by_session_and_hash_query(session_id, input_hash)

        if row is None:
            return CacheOutput(
                input_dict=input_dict,
                output=None,
                node_id=None,
                input_pickle=input_pickle,
                input_hash=input_hash,
                session_id=session_id,
            )

        # Use data from previous LLM call.
        node_id = row["node_id"]
        output = None

        logger.debug(
            f"Cache HIT, (session_id, node_id, input_hash): {(session_id, node_id, input_hash)}"
        )

        if row["input_overwrite"] is not None:
            # input_overwrite = dill.loads(row["input_overwrite"])
            # input_overwrite = dill.dumps(input_overwrite) # TODO: Tmp, need to refactor the unnecessary dills
            overwrite_pickle = row["input_overwrite"]
            overwrite_text = dill.loads(overwrite_pickle)["input"]
            set_input(input_dict, overwrite_text, api_type)

        if row["output"] is not None:
            output = dill.loads(row["output"])
        else:
            logger.warning(
                f"Found result in the cache, but output is None. Is this call doing something useful?"
            )
        set_seed(node_id)
        return CacheOutput(
            input_dict=input_dict,
            output=output,
            node_id=node_id,
            input_pickle=input_pickle,
            input_hash=input_hash,
            session_id=session_id,
        )

    def cache_output(
        self, cache_result: CacheOutput, output_obj: Any, api_type: str, cache: bool = True
    ) -> None:
        """
        Cache the output of an LLM call using information from a CacheOutput object.

        Args:
            cache_result: CacheOutput object containing cache information
            output_obj: The output object to cache
            api_type: The API type identifier
            cache: Whether to actually cache the result

        Returns:
            The node_id assigned to this LLM call
        """
        # Insert new row with a new node_id. reset randomness to avoid
        # generating exact same UUID when re-running, but MCP generates randomness and we miss cache
        random.seed()
        node_id = str(uuid.uuid4())
        logger.debug(
            f"Cache MISS, (session_id, node_id, input_hash): {(cache_result.session_id, node_id, cache_result.input_hash)}"
        )
        output_pickle = dill.dumps(output_obj)
        if cache:
            DB.insert_llm_call_with_output_query(
                cache_result.session_id,
                cache_result.input_pickle,
                cache_result.input_hash,
                node_id,
                api_type,
                output_pickle,
            )
        cache_result.node_id = node_id
        cache_result.output = output_obj
        set_seed(node_id)

    def get_finished_runs(self):
        return DB.get_finished_runs_query()

    def get_all_experiments_sorted(self):
        """Get all experiments sorted by name (alphabetical)"""
        return DB.get_all_experiments_sorted_query()

    def get_graph(self, session_id):
        return DB.get_experiment_graph_topology_query(session_id)

    def get_color_preview(self, session_id):
        row = DB.get_experiment_color_preview_query(session_id)
        if row and row["color_preview"]:
            return json.loads(row["color_preview"])
        return []

    def get_parent_environment(self, parent_session_id):
        return DB.get_experiment_environment_query(parent_session_id)

    def update_color_preview(self, session_id, colors):
        color_preview_json = json.dumps(colors)
        DB.update_experiment_color_preview_query(color_preview_json, session_id)

    def get_exec_command(self, session_id):
        row = DB.get_experiment_exec_info_query(session_id)
        if row is None:
            return None, None, None
        return row["cwd"], row["command"], json.loads(row["environment"])

    def clear_db(self):
        """Delete all records from experiments and llm_calls tables."""
        DB.delete_all_experiments_query()
        DB.delete_all_llm_calls_query()

    def get_session_name(self, session_id):
        # Get all subrun names for this parent session
        row = DB.get_session_name_query(session_id)
        if not row:
            return []  # Return empty list if no subruns found
        return [row["name"]]


CACHE = CacheManager()
