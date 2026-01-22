"""
Langchain patch for tool node visualization.

This patch intercepts langchain tool calls to create tool nodes in the dataflow graph.
LLM calls are handled by the httpx patch; this patch only adds the missing tool nodes.

We patch BOTH run/arun AND invoke/ainvoke to cover all cases:
- run/arun: Called directly by AgentExecutor
- invoke/ainvoke: Called by langgraph ToolNode, LCEL chains

Since invoke() calls run() internally, we use a guard to prevent duplicate nodes.

Flow: LLM (httpx) → Tool (this patch) → LLM (httpx)
"""

from functools import wraps
import uuid
import threading
from ao.runner.monkey_patching.patching_utils import send_graph_node_and_edges
from ao.runner.context_manager import (
    get_langchain_pending_tool_parent,
    set_langchain_pending_llm_parent,
)
from ao.common.logger import logger

# Thread-local storage to prevent duplicate node creation when invoke calls run
_tool_call_guard = threading.local()


def _is_inside_tool_call():
    """Check if we're already inside a patched tool call."""
    return getattr(_tool_call_guard, "active", False)


def _set_tool_call_active(active):
    """Set the tool call guard."""
    _tool_call_guard.active = active


def _create_tool_node(tool_name, tool_input, result, api_type):
    """Create and send a tool node to the server."""
    # Get parent LLM node (set by httpx patch)
    parent_node_id = get_langchain_pending_tool_parent()
    source_node_ids = [parent_node_id] if parent_node_id else []

    # Create tool node
    node_id = str(uuid.uuid4())
    input_dict = {"tool_name": tool_name, "input": tool_input}

    # Set this tool as parent for the next LLM call
    set_langchain_pending_llm_parent(node_id)

    # Send node to server
    send_graph_node_and_edges(
        node_id=node_id,
        input_dict=input_dict,
        output_obj=result,
        source_node_ids=source_node_ids,
        api_type=api_type,
    )

    logger.info(
        f"[langchain_patch] Tool '{tool_name}' node created: {node_id[:8]}, parent: {parent_node_id[:8] if parent_node_id else 'None'}"
    )


def langchain_patch():
    """Apply monkey patches to langchain BaseTool to create tool nodes."""
    try:
        from langchain_core.tools import BaseTool
    except ImportError:
        logger.info("langchain_core not installed, skipping langchain patches")
        return

    # Store original methods
    original_run = BaseTool.run
    original_arun = BaseTool.arun
    original_invoke = BaseTool.invoke
    original_ainvoke = BaseTool.ainvoke

    # ==================== run/arun patches ====================
    # These catch direct calls from AgentExecutor

    @wraps(original_run)
    def patched_run(
        self, tool_input, verbose=None, start_color="green", color="green", callbacks=None, **kwargs
    ):
        # If we're already inside invoke, just run without creating another node
        if _is_inside_tool_call():
            return original_run(self, tool_input, verbose, start_color, color, callbacks, **kwargs)

        # Direct run() call - create node
        _set_tool_call_active(True)
        try:
            result = original_run(
                self, tool_input, verbose, start_color, color, callbacks, **kwargs
            )
            _create_tool_node(self.name, tool_input, result, "langchain.BaseTool.run")
            return result
        finally:
            _set_tool_call_active(False)

    @wraps(original_arun)
    async def patched_arun(
        self, tool_input, verbose=None, start_color="green", color="green", callbacks=None, **kwargs
    ):
        # If we're already inside ainvoke, just run without creating another node
        if _is_inside_tool_call():
            return await original_arun(
                self, tool_input, verbose, start_color, color, callbacks, **kwargs
            )

        # Direct arun() call - create node
        _set_tool_call_active(True)
        try:
            result = await original_arun(
                self, tool_input, verbose, start_color, color, callbacks, **kwargs
            )
            _create_tool_node(self.name, tool_input, result, "langchain.BaseTool.arun")
            return result
        finally:
            _set_tool_call_active(False)

    # ==================== invoke/ainvoke patches ====================
    # These catch calls from langgraph ToolNode, LCEL, etc.

    @wraps(original_invoke)
    def patched_invoke(self, input, config=None, **kwargs):
        # Set guard so nested run() call doesn't create duplicate node
        _set_tool_call_active(True)
        try:
            result = original_invoke(self, input, config, **kwargs)
            _create_tool_node(self.name, input, result, "langchain.BaseTool.invoke")
            return result
        finally:
            _set_tool_call_active(False)

    @wraps(original_ainvoke)
    async def patched_ainvoke(self, input, config=None, **kwargs):
        # Set guard so nested arun() call doesn't create duplicate node
        _set_tool_call_active(True)
        try:
            result = await original_ainvoke(self, input, config, **kwargs)
            _create_tool_node(self.name, input, result, "langchain.BaseTool.ainvoke")
            return result
        finally:
            _set_tool_call_active(False)

    # Apply all patches
    BaseTool.run = patched_run
    BaseTool.arun = patched_arun
    BaseTool.invoke = patched_invoke
    BaseTool.ainvoke = patched_ainvoke
    logger.info("langchain BaseTool patches applied (run/arun + invoke/ainvoke)")
