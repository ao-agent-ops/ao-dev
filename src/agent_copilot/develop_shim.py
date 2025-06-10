import sys
import os
import socket
import json
import threading
import runpy
import subprocess
import inspect
import asyncio

HOST = '127.0.0.1'
PORT = 5959

# Globals for coordinating restart and shutdown signals
restart_event = threading.Event()
shutdown_flag = False
proc = None  # will hold the subprocess running the user script in non-debug mode

def monkey_patch_llm_call(server_conn):
    """
    Monkey-patch agent_copilot.src.mock.call to intercept LLM calls.
    Sends call details (input, output, file, line, thread, task) to the server.
    """
    try:
        import agent_copilot.src.mock as ac_mock
    except ImportError:
        return  # If the module isn't available, do nothing
    original_call = getattr(ac_mock, "call", None)
    if original_call is None:
        return
    def patched_call(prompt: str) -> str:
        # Invoke the original LLM call (e.g., to get a response or raise an error)
        result = None
        error = None
        try:
            result = original_call(prompt)
        except Exception as e:
            error = e  # capture exception to report it, then re-raise
        # Gather call site info (filename and line number of the caller)
        frame = inspect.currentframe()
        caller = frame.f_back if frame else None
        file_name = caller.f_code.co_filename if caller else "<unknown>"
        line_no = caller.f_lineno if caller else -1
        # Identify thread and asyncio task
        thread_id = threading.get_ident()
        task_id = None
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        if task:
            task_id = id(task)
        # Send the call details to the server
        message = {
            "type": "call",
            "input": prompt,
            "output": result if error is None else str(error),
            "file": file_name,
            "line": line_no,
            "thread": thread_id,
            "task": task_id
        }
        try:
            server_conn.sendall((json.dumps(message) + "\n").encode('utf-8'))
        except Exception:
            pass  # If sending fails (e.g., server down), skip
        if error:
            # Propagate the original exception after logging
            raise error
        return result
    ac_mock.call = patched_call

def listen_for_server_messages(sock):
    """Background thread: listen for 'restart' or 'shutdown' messages from the server."""
    global proc, shutdown_flag
    file_obj = sock.makefile(mode='r')
    for line in file_obj:
        try:
            msg = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        mtype = msg.get("type")
        if mtype == "restart":
            # Extension requested a restart (user edited an LLM prompt)
            # (new_input could be used here to modify the prompt on next run if implemented)
            restart_event.set()
            # If a user script process is currently running, terminate it so we can restart
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
        elif mtype == "shutdown":
            # Server is shutting down – set flag and break out
            shutdown_flag = True
            restart_event.set()  # wake up main thread if waiting
            break
    # If the server connection is closed or thread exits, mark shutdown
    shutdown_flag = True
    restart_event.set()
    try:
        sock.close()
    except Exception:
        pass

def main():
    # Check if this is a child process invocation
    is_child = (len(sys.argv) > 1 and sys.argv[1] == "--child")
    if is_child:
        # Remove the "--child" flag and prepare to run the user script
        sys.argv.pop(1)  # pop the flag
    if len(sys.argv) < 2:
        print("Usage: develop_shim.py [--child] <script.py> [script args...]")
        sys.exit(1)
    script_path = sys.argv[1]
    script_args = sys.argv[2:]

    if is_child:
        # **Child mode**: Run the target script with LLM call monkey-patching
        server_conn = None
        try:
            server_conn = socket.create_connection((HOST, PORT), timeout=5)
        except Exception:
            print("Warning: Could not connect to develop server for logging.")
        if server_conn:
            # Handshake to register as a shim runner
            handshake = {"type": "hello", "role": "shim-runner", "script": os.path.basename(script_path)}
            try:
                server_conn.sendall((json.dumps(handshake) + "\n").encode('utf-8'))
            except Exception:
                pass
            # Apply monkey patch to intercept LLM calls
            monkey_patch_llm_call(server_conn)
        # Set up sys.argv for the script and run it
        sys.argv = [script_path] + script_args
        try:
            runpy.run_path(script_path, run_name="__main__")
        finally:
            if server_conn:
                server_conn.close()
    else:
        # **Parent (orchestrator) mode**: Manage script execution and handle restarts
        # Ensure the develop server is running (start it if not)
        try:
            socket.create_connection((HOST, PORT), timeout=2).close()
        except Exception:
            # Server not running; attempt to start it
            server_py = os.path.join(os.path.dirname(__file__), "develop_server.py")
            try:
                subprocess.Popen([sys.executable, server_py, "start"])
            except Exception as e:
                print(f"Error: Failed to start develop server ({e})")
                sys.exit(1)
            # Wait briefly for the server to come up
            import time; time.sleep(1)
            # Verify server is up
            try:
                socket.create_connection((HOST, PORT), timeout=5).close()
            except Exception:
                print("Error: Develop server did not start.")
                sys.exit(1)
        # Connect to the server for control messages
        try:
            server_conn = socket.create_connection((HOST, PORT), timeout=5)
        except Exception as e:
            print(f"Error: Cannot connect to develop server ({e})")
            sys.exit(1)
        # Handshake as shim controller
        handshake = {"type": "hello", "role": "shim-control", "script": os.path.basename(script_path)}
        try:
            server_conn.sendall((json.dumps(handshake) + "\n").encode('utf-8'))
        except Exception:
            pass
        # Start a background thread to listen for 'restart' or 'shutdown' signals
        listener_thread = threading.Thread(target=listen_for_server_messages, args=(server_conn,), daemon=True)
        listener_thread.start()

        # Detect if running under VS Code debugger (NOTE: we assume debugpy)
        debug_mode = False
        try:
            import debugpy
            if debugpy.is_client_connected():  # Debugger attached
                debug_mode = True
        except Exception:
            debug_mode = True
        if debug_mode:
            # **Debug mode**: Run user script in-process so breakpoints & debug session remain active
            monkey_patch_llm_call(server_conn)  # patch LLM calls for logging
            sys.argv = [script_path] + script_args
            try:
                runpy.run_path(script_path, run_name="__main__")
            finally:
                if restart_event.is_set():
                    # If an edit was requested during debugging, advise using VS Code API to restart
                    # TODO: Send to server. Ultimately, we need to restart in extension typescript (vscode.debug.restartDebugging() --- see OAI parse-copilot/VS Code LLM Extension).
                    print("Edit request received. Please use VS Code to restart the debugging session.")
                server_conn.close()
        else:
            # **Normal mode**: Loop to run and restart the script on demand
            global proc

            while not shutdown_flag:
                # Launch the child runner
                proc = subprocess.Popen(
                    [sys.executable, __file__, "--child", script_path] + script_args
                )

                # Now watch both the process and our restart/shutdown events
                while True:
                    # 1) If the server told us to shut down entirely, stop everything.
                    if shutdown_flag:
                        if proc.poll() is None:
                            proc.kill()
                        break

                    # 2) If user edited an LLM call, kill & restart immediately.
                    if restart_event.is_set():
                        restart_event.clear()
                        if proc.poll() is None:
                            proc.kill()
                        break

                    # 3) Otherwise, check if the child has exited on its own.
                    if proc.poll() is not None:
                        # child has finished normally
                        break

                    # 4) Sleep a short time before polling again.
                    time.sleep(0.1)

                # If we were told to shut down, break out of the outer loop too
                if shutdown_flag:
                    break

                # Otherwise, either restart_event was set (we just cleared it) → restart immediately,
                # or the script exited normally → now wait for the next edit command.
                if proc.returncode is not None and not restart_event.is_set():
                    # Wait indefinitely for a future edit before restarting
                    restart_event.wait()
                    restart_event.clear()
                    if shutdown_flag:
                        break
                    # Loop will restart the script now
                    continue

            # Cleanup
            server_conn.close()

if __name__ == "__main__":
    main()
