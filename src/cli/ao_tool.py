import atexit
import os
import sys
import json
import shlex
import uuid
import time
import signal
import tempfile
import subprocess
from argparse import ArgumentParser, REMAINDER
from dataclasses import dataclass
from typing import Optional

from ao.common.constants import AO_TOOL_LOG_DIR
from ao.server.database_manager import DB

SESSION_WAIT_TIMEOUT = 5  # Max seconds to wait for session_id from agent_runner
TERMINATE_TIMEOUT = 5  # Seconds to wait for graceful exit before force kill


def output_json(data: dict) -> None:
    """Print JSON to stdout and exit with appropriate code."""
    print(json.dumps(data))
    sys.exit(0 if data.get("status") != "error" else 1)


# ===========================================================
# Shared helpers for reusable logic
# ===========================================================


@dataclass
class SpawnResult:
    """Result of spawning a subprocess."""
    process: subprocess.Popen
    session_id: str
    log_file: str


def _apply_edit(session_id: str, node_id: str, field: str, new_value: str) -> dict:
    """
    Apply an edit to a node's input or output.

    Returns dict with status info. Does NOT call output_json or exit.
    On success: {"status": "success", "session_id": ..., "node_id": ..., "field": ...}
    On error: {"status": "error", "error": "..."}
    """
    # Get the node's current data to get api_type and raw dict
    if field == "input":
        row = DB.query_one_llm_call_input(session_id, node_id)
    else:
        row = DB.query_one_llm_call_output(session_id, node_id)

    if not row:
        return {"status": "error", "error": f"Node {node_id} not found in session {session_id}"}

    api_type = row["api_type"]

    # Parse the current stored data to get the raw dict
    if field == "input":
        current_data = json.loads(row["input"])
        # Input format: {"input": "<json with raw/to_show>", "attachments": [...], "model": "..."}
        inner_json = current_data.get("input", "{}")
        inner_data = json.loads(inner_json)
    else:
        inner_data = json.loads(row["output"])

    raw_dict = inner_data.get("raw", {})

    # Try to parse the new value as JSON (this is the new to_show)
    try:
        new_to_show = json.loads(new_value)
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"Invalid JSON: {e}"}

    # Validate by attempting to merge and parse
    from ao.runner.monkey_patching.api_parser import merge_filtered_into_raw, json_str_to_api_obj

    try:
        # Validate by merging - this ensures the to_show keys are compatible with raw
        merge_filtered_into_raw(raw_dict, new_to_show)
    except Exception as e:
        return {"status": "error", "error": f"Failed to merge edit: {e}"}

    # Build the new complete structure (keep raw unchanged, store new to_show)
    new_complete = {"raw": raw_dict, "to_show": new_to_show}
    new_json_str = json.dumps(new_complete, sort_keys=True)

    # For output, validate it can be converted to API object
    if field == "output":
        try:
            json_str_to_api_obj(new_json_str, api_type)
        except Exception as e:
            return {"status": "error", "error": f"Validation failed: {e}"}

    # Apply the edit
    if field == "input":
        DB.set_input_overwrite(session_id, node_id, new_json_str)
    else:
        DB.set_output_overwrite(session_id, node_id, new_json_str)

    return {
        "status": "success",
        "session_id": session_id,
        "node_id": node_id,
        "field": field,
    }


def _spawn_rerun(session_id: str) -> SpawnResult | dict:
    """
    Spawn a rerun process for a session.

    Returns SpawnResult on success, or error dict on failure.
    """
    # Get the original command, cwd, and environment from DB
    cwd, command, environment = DB.get_exec_command(session_id)

    if not command:
        return {"status": "error", "error": f"Session not found or no command stored: {session_id}"}

    # Create temp file for session_id IPC
    run_id = str(uuid.uuid4())[:8]
    session_file = os.path.join(tempfile.gettempdir(), f"ao-session-{run_id}.json")

    def cleanup_session_file():
        try:
            if os.path.exists(session_file):
                os.unlink(session_file)
        except OSError:
            pass

    atexit.register(cleanup_session_file)

    # Create log file
    log_file = os.path.join(AO_TOOL_LOG_DIR, f"rerun-{run_id}.log")

    # Set up environment: restore original env + set rerun session ID
    env = os.environ.copy()
    env.update(environment)
    env["AO_SESSION_ID"] = session_id  # Tell agent_runner to reuse this session
    env["AO_SESSION_FILE"] = session_file

    # Parse and execute the original command
    cmd_parts = shlex.split(command)

    # Spawn process with stdout/stderr redirected to log file
    with open(log_file, "w") as log_handle:
        process = subprocess.Popen(
            cmd_parts,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )

    # Wait for session_id from agent_runner (confirms handshake)
    session_data = wait_for_session_file(session_file, SESSION_WAIT_TIMEOUT)

    # Clean up temp file
    cleanup_session_file()
    atexit.unregister(cleanup_session_file)

    if not session_data:
        return {
            "status": "error",
            "error": "Timeout waiting for session handshake",
            "pid": process.pid,
            "log_file": log_file,
        }

    return SpawnResult(process=process, session_id=session_id, log_file=log_file)


def _handle_process_completion(
    process: subprocess.Popen,
    session_id: str,
    log_file: str,
    wait: bool,
    timeout: Optional[float],
) -> dict:
    """
    Handle process completion - either wait or return immediately.

    Returns the appropriate output dict.
    """
    if wait:
        start_time = time.time()
        try:
            exit_code = process.wait(timeout=timeout)
            duration = time.time() - start_time
            return {
                "status": "completed" if exit_code == 0 else "failed",
                "session_id": session_id,
                "exit_code": exit_code,
                "duration_seconds": round(duration, 2),
                "log_file": log_file,
            }
        except subprocess.TimeoutExpired:
            process.terminate()
            return {
                "status": "timeout",
                "session_id": session_id,
                "pid": process.pid,
                "log_file": log_file,
            }
    else:
        # Return immediately with started status
        return {
            "status": "started",
            "session_id": session_id,
            "pid": process.pid,
            "log_file": log_file,
        }


def wait_for_session_file(session_file: str, timeout: float) -> dict | None:
    """Poll for session file to be written by agent_runner.

    Returns the parsed JSON data if successful, None on timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(session_file):
            try:
                with open(session_file, "r") as f:
                    data = json.load(f)
                    if "session_id" in data:
                        return data
            except (json.JSONDecodeError, IOError):
                pass  # File not fully written yet
        time.sleep(0.1)
    return None


def record_command(args) -> None:
    """Spawn ao-record as background process, return session_id via JSON."""
    # 1. Validate script exists (unless -m module mode)
    if not args.module and not os.path.isfile(args.script_path):
        output_json({"status": "error", "error": f"Script not found: {args.script_path}"})

    # 2. Create temp file for session_id IPC (cleaned up via atexit)
    run_id = str(uuid.uuid4())[:8]
    session_file = os.path.join(tempfile.gettempdir(), f"ao-session-{run_id}.json")

    def cleanup_session_file():
        try:
            if os.path.exists(session_file):
                os.unlink(session_file)
        except OSError:
            pass

    atexit.register(cleanup_session_file)

    # 3. Create log file
    log_file = os.path.join(AO_TOOL_LOG_DIR, f"run-{run_id}.log")

    # 4. Build command: python -m ao.cli.ao_record [options] script_path [args...]
    cmd = [sys.executable, "-m", "ao.cli.ao_record"]
    if args.run_name:
        cmd.extend(["--run-name", args.run_name])
    if args.module:
        cmd.append("-m")
    cmd.append(args.script_path)
    cmd.extend(args.script_args)

    # 5. Set up environment with session file path
    env = os.environ.copy()
    env["AO_SESSION_FILE"] = session_file

    # 6. Spawn process with stdout/stderr redirected to log file
    with open(log_file, "w") as log_handle:
        process = subprocess.Popen(
            cmd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )

    # 7. Wait for session_id from agent_runner (written after handshake)
    session_data = wait_for_session_file(session_file, SESSION_WAIT_TIMEOUT)

    # Clean up temp file now that we've read it
    cleanup_session_file()
    atexit.unregister(cleanup_session_file)

    if not session_data:
        output_json({
            "status": "error",
            "error": "Timeout waiting for session_id from agent runner",
            "pid": process.pid,
            "log_file": log_file,
        })

    session_id = session_data["session_id"]

    # 8. Handle --wait mode: block until process completes
    if args.wait:
        start_time = time.time()
        try:
            exit_code = process.wait(timeout=args.timeout)
            duration = time.time() - start_time
            output_json({
                "status": "completed" if exit_code == 0 else "failed",
                "session_id": session_id,
                "exit_code": exit_code,
                "duration_seconds": round(duration, 2),
                "log_file": log_file,
            })
        except subprocess.TimeoutExpired:
            process.terminate()
            output_json({
                "status": "timeout",
                "session_id": session_id,
                "pid": process.pid,
                "log_file": log_file,
            })
    else:
        # Return immediately with started status
        output_json({
            "status": "started",
            "session_id": session_id,
            "pid": process.pid,
            "log_file": log_file,
        })


def probe_command(args) -> None:
    """Query the state of a session - metadata, topology, or specific nodes."""
    session_id = args.session_id

    # Get experiment metadata
    experiment = DB.get_experiment_metadata(session_id)
    if not experiment:
        output_json({"status": "error", "error": f"Session not found: {session_id}"})

    # Parse graph topology from JSON
    graph_topology = json.loads(experiment["graph_topology"]) if experiment["graph_topology"] else {"nodes": [], "edges": []}
    edges = graph_topology.get("edges", [])

    # Build parent/child relationships from edges
    parent_ids = {}  # node_id -> list of parent node_ids
    child_ids = {}   # node_id -> list of child node_ids
    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        parent_ids.setdefault(tgt, []).append(src)
        child_ids.setdefault(src, []).append(tgt)

    # Handle --node or --nodes: return detailed info for specific node(s)
    if args.node or args.nodes:
        node_ids = [args.node] if args.node else args.nodes.split(",")
        nodes_data = []
        for node_id in node_ids:
            llm_call = DB.get_llm_call_full(session_id, node_id.strip())
            if not llm_call:
                output_json({"status": "error", "error": f"Node not found: {node_id}"})

            # Parse input/output JSON, extracting to_show fields
            input_to_show = None
            output_to_show = None
            if llm_call["input"]:
                input_data = json.loads(llm_call["input"])
                # input_data has {input: "<json string>", attachments: [...], model: "..."}
                # Parse the nested input JSON to get to_show
                if input_data.get("input"):
                    inner_input = json.loads(input_data["input"])
                    input_to_show = inner_input.get("to_show")

            if llm_call["output"]:
                output_data = json.loads(llm_call["output"])
                # output_data has {raw: {...}, to_show: {...}}
                output_to_show = output_data.get("to_show")

            node_info = {
                "node_id": llm_call["node_id"],
                "session_id": session_id,
                "api_type": llm_call["api_type"],
                "label": llm_call["label"],
                "timestamp": str(llm_call["timestamp"]) if llm_call["timestamp"] else None,
                "parent_ids": parent_ids.get(node_id.strip(), []),
                "child_ids": child_ids.get(node_id.strip(), []),
                "has_input_overwrite": llm_call["input_overwrite"] is not None,
                "stack_trace": llm_call["stack_trace"],
            }

            # Include content if requested or default for single node
            if args.include_content or args.node:
                node_info["input"] = input_to_show
                node_info["output"] = output_to_show

            nodes_data.append(node_info)

        if args.node:
            # Single node: return just the node object
            output_json(nodes_data[0])
        else:
            # Multiple nodes: return array
            output_json({"nodes": nodes_data})
        return

    # Handle --topology: return only graph structure
    if args.topology:
        topology_nodes = []
        for node in graph_topology.get("nodes", []):
            node_id = node["id"]
            topology_nodes.append({
                "node_id": node_id,
                "label": node.get("label", ""),
                "parent_ids": parent_ids.get(node_id, []),
                "child_ids": child_ids.get(node_id, []),
            })
        output_json({
            "session_id": session_id,
            "status": "finished",  # TODO: track running status
            "nodes": topology_nodes,
            "edges": [{"source": e["source"], "target": e["target"]} for e in edges],
        })
        return

    # Default: full probe - metadata + graph summary
    output_json({
        "session_id": session_id,
        "name": experiment["name"],
        "status": "finished",  # TODO: track running status
        "timestamp": str(experiment["timestamp"]) if experiment["timestamp"] else None,
        "result": experiment["success"] if experiment["success"] else None,
        "version_date": experiment["version_date"],
        "node_count": len(graph_topology.get("nodes", [])),
        "nodes": [
            {
                "node_id": n["id"],
                "label": n.get("label", ""),
                "parent_ids": parent_ids.get(n["id"], []),
                "child_ids": child_ids.get(n["id"], []),
            }
            for n in graph_topology.get("nodes", [])
        ],
        "edges": [{"source": e["source"], "target": e["target"]} for e in edges],
    })


def experiments_command(args) -> None:
    """List experiments from the database."""
    import re

    # Parse range (format: "start:end", ":end", "start:", or "start")
    range_str = args.range or ":50"

    if ":" in range_str:
        parts = range_str.split(":", 1)
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else None
    else:
        start = int(range_str)
        end = start + 1  # Single item

    # Get all experiments sorted by timestamp (most recent first)
    all_experiments = DB.get_all_experiments_sorted()
    total_count = len(all_experiments)

    # Apply range first
    if end is not None:
        experiments = all_experiments[start:end]
    else:
        experiments = all_experiments[start:]

    # Apply regex filter on top of the range
    if args.regex:
        try:
            pattern = re.compile(args.regex)
        except re.error as e:
            output_json({"status": "error", "error": f"Invalid regex: {e}"})
        experiments = [exp for exp in experiments if pattern.search(exp["name"] or "")]

    # Format output
    result = []
    for exp in experiments:
        timestamp = exp["timestamp"]
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()

        result.append({
            "session_id": exp["session_id"],
            "name": exp["name"],
            "timestamp": str(timestamp) if timestamp else None,
            "result": exp["success"],
            "version_date": exp["version_date"],
        })

    output_json({"experiments": result, "total": total_count, "range": f"{start}:{end if end else ''}"})


def terminate_command(args) -> None:
    """Terminate a running process by PID."""
    pid = args.pid

    # Check if process exists
    try:
        os.kill(pid, 0)
    except OSError:
        output_json({"status": "error", "error": f"Process {pid} not found"})

    # Send SIGTERM (graceful termination)
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        output_json({"status": "error", "error": f"Failed to terminate: {e}"})

    # Wait for process to exit gracefully
    start = time.time()
    while time.time() - start < TERMINATE_TIMEOUT:
        try:
            os.kill(pid, 0)
            time.sleep(0.1)
        except OSError:
            output_json({"status": "terminated", "pid": pid})

    # Still alive after timeout - force kill
    try:
        os.kill(pid, signal.SIGKILL)
        output_json({"status": "terminated", "pid": pid})
    except OSError:
        output_json({"status": "terminated", "pid": pid})


def edit_command(args) -> None:
    """Edit a node's input or output."""
    result = _apply_edit(args.session_id, args.node_id, args.field, args.value)
    output_json(result)


def rerun_command(args) -> None:
    """Re-run an existing session using cached/edited values."""
    spawn_result = _spawn_rerun(args.session_id)

    # Check for error
    if isinstance(spawn_result, dict):
        output_json(spawn_result)

    # Handle completion
    result = _handle_process_completion(
        spawn_result.process,
        spawn_result.session_id,
        spawn_result.log_file,
        args.wait,
        args.timeout,
    )
    output_json(result)


def _copy_experiment(session_id: str, run_name: str | None = None) -> str | dict:
    """
    Clones the experiment and llm-calls entries for the given session_id in the DB
    and writes them into new entries in the DB with a new session id we generate here.
    Returns the new session id, or an error dict if the session doesn't exist.

    Args:
        session_id: The session to copy
        run_name: Optional name for the new run. If None, defaults to "Edit of <original name>"
    """
    from datetime import datetime

    # Get the original experiment metadata
    experiment = DB.get_experiment_metadata(session_id)
    if not experiment:
        return {"status": "error", "error": f"Session not found: {session_id}"}

    # Get execution info (cwd, command, environment)
    cwd, command, environment = DB.get_exec_command(session_id)
    if not command:
        return {"status": "error", "error": f"No command stored for session: {session_id}"}

    # Generate new session ID
    new_session_id = str(uuid.uuid4())

    # Determine run name
    if run_name is None:
        run_name = f"Edit of {experiment['name']}"

    # Create new experiment with copied data but new session_id and timestamp
    DB.add_experiment(
        session_id=new_session_id,
        name=run_name,
        timestamp=datetime.now(),
        cwd=cwd,
        command=command,
        environment=environment,
        parent_session_id=new_session_id,  # Self-referential for new top-level run
        user_id=None,
        version_date=experiment["version_date"],
    )

    # Copy graph topology from original
    if experiment["graph_topology"]:
        graph = json.loads(experiment["graph_topology"])
        DB.update_graph_topology(new_session_id, graph)

    # Copy all LLM calls to new session
    DB.copy_llm_calls(session_id, new_session_id)

    return new_session_id


def edit_and_rerun_command(args) -> None:
    """Edit a node and immediately rerun the session."""
    session_id = args.session_id
    node_id = args.node_id

    # Determine field and value from mutually exclusive args
    if args.input:
        field = "input"
        value = args.input
    else:
        field = "output"
        value = args.output

    if args.as_new_run:
        result = _copy_experiment(session_id, args.run_name)
        if isinstance(result, dict):
            output_json(result)
        session_id = result

    # Step 1: Apply the edit
    edit_result = _apply_edit(session_id, node_id, field, value)
    if edit_result.get("status") == "error":
        output_json(edit_result)

    # Step 2: Spawn rerun
    spawn_result = _spawn_rerun(session_id)

    # Check for spawn error
    if isinstance(spawn_result, dict):
        # Include edit info in error response
        spawn_result["edited_field"] = field
        spawn_result["node_id"] = node_id
        output_json(spawn_result)

    # Step 3: Handle completion
    result = _handle_process_completion(
        spawn_result.process,
        spawn_result.session_id,
        spawn_result.log_file,
        args.wait,
        args.timeout,
    )

    # Add edit info to result
    result["node_id"] = node_id
    result["edited_field"] = field
    output_json(result)


def create_parser() -> ArgumentParser:
    """Create the argument parser with subcommands."""
    parser = ArgumentParser(
        prog="ao-tool",
        description="CLI for programmatic interaction with AO dataflow system. All output is JSON.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # record subcommand
    record = subparsers.add_parser(
        "record",
        help="Start recording a script execution",
        description="Spawn ao-record as a background process and return session_id.",
    )
    record.add_argument("script_path", help="Script to execute (or module name with -m)")
    record.add_argument("script_args", nargs=REMAINDER, help="Arguments to pass to the script")
    record.add_argument(
        "-m", "--module",
        action="store_true",
        help="Run script_path as a Python module (like python -m)",
    )
    record.add_argument("--run-name", help="Human-readable name for this run")
    record.add_argument(
        "--wait",
        action="store_true",
        help="Block until execution completes instead of returning immediately",
    )
    record.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout in seconds when using --wait",
    )

    # probe subcommand
    probe = subparsers.add_parser(
        "probe",
        help="Query session state",
        description="Query metadata, graph topology, or specific nodes of a session.",
    )
    probe.add_argument("session_id", help="Session ID to probe")
    probe.add_argument(
        "--topology",
        action="store_true",
        help="Return only graph structure (nodes and edges, no content)",
    )
    probe.add_argument(
        "--node",
        help="Return detailed info for a single node",
    )
    probe.add_argument(
        "--nodes",
        help="Return detailed info for multiple nodes (comma-separated IDs)",
    )
    probe.add_argument(
        "--include-content",
        action="store_true",
        help="Include full input/output content when probing multiple nodes",
    )

    # experiments subcommand
    experiments = subparsers.add_parser(
        "experiments",
        help="List experiments from database",
        description="List experiments with optional range. Range format: ':50' (first 50), '50:100' (50-99), '10:' (from 10 onwards).",
    )
    experiments.add_argument(
        "--range",
        default=":50",
        help="Range of experiments to return (default: ':50'). Format: 'start:end', ':end', 'start:'",
    )
    experiments.add_argument(
        "--regex",
        help="Filter experiments by name using regex pattern",
    )

    # terminate subcommand
    terminate = subparsers.add_parser(
        "terminate",
        help="Terminate a running process",
        description="Terminate a running ao-record process by PID.",
    )
    terminate.add_argument("pid", type=int, help="Process ID to terminate")

    # edit subcommand
    edit = subparsers.add_parser(
        "edit",
        help="Edit a node's input or output",
        description="Edit a node's input or output value. The value should be a JSON object representing the to_show structure.",
    )
    edit.add_argument("session_id", help="Session ID containing the node")
    edit.add_argument("node_id", help="Node ID to edit")
    edit.add_argument("field", choices=["input", "output"], help="Field to edit")
    edit.add_argument("value", help="New value as JSON (the to_show structure)")

    # rerun subcommand
    rerun = subparsers.add_parser(
        "rerun",
        help="Re-run an existing session",
        description="Re-execute a session using cached/edited values.",
    )
    rerun.add_argument("session_id", help="Session ID to re-run")
    rerun.add_argument(
        "--wait",
        action="store_true",
        help="Block until execution completes instead of returning immediately",
    )
    rerun.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout in seconds when using --wait",
    )

    # edit-and-rerun subcommand
    edit_and_rerun = subparsers.add_parser(
        "edit-and-rerun",
        help="Edit a node and immediately rerun",
        description="Edit a node's input or output and immediately rerun the session.",
    )
    edit_and_rerun.add_argument("session_id", help="Session ID containing the node")
    edit_and_rerun.add_argument("node_id", help="Node ID to edit")
    edit_and_rerun_group = edit_and_rerun.add_mutually_exclusive_group(required=True)
    edit_and_rerun_group.add_argument(
        "--input",
        help="New input value as JSON (the to_show structure)",
    )
    edit_and_rerun_group.add_argument(
        "--output",
        help="New output value as JSON (the to_show structure)",
    )
    edit_and_rerun.add_argument(
        "--wait",
        action="store_true",
        help="Block until execution completes instead of returning immediately",
    )
    edit_and_rerun.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout in seconds when using --wait",
    )
    edit_and_rerun.add_argument(
        "--as-new-run",
        action="store_true",
        help="Create a new session instead of reusing the existing one",
    )
    edit_and_rerun.add_argument(
        "--run-name",
        help="Name for the new run (only used with --as-new-run). Defaults to 'Edit of <original name>'",
    )

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "record":
        record_command(args)
    elif args.command == "probe":
        probe_command(args)
    elif args.command == "experiments":
        experiments_command(args)
    elif args.command == "terminate":
        terminate_command(args)
    elif args.command == "edit":
        edit_command(args)
    elif args.command == "rerun":
        rerun_command(args)
    elif args.command == "edit-and-rerun":
        edit_and_rerun_command(args)


if __name__ == "__main__":
    main()
