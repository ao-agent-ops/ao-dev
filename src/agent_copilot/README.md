# Core functionalities

![Running develop command](/media/develop_spawn.png)


## Server

This is basically the core of the tool. All analysis happens here. It receives messages from the user's shim processes and controls the UI. I.e., communication goes shim <-> server <-> UI.


Manually start, stop, restart server:

 - `python develop_server.py start` 
 - `python develop_server.py stop`
 - `python develop_server.py restart`

Some basics: 

 - To check if the server process is still running: `ps aux | grep develop_server.py` or check which processes are holding the port: `lsof -i :5959`

 - When you make changes to `develop_server.py`, remember to restart the server to see them take effect.


## develop_shim.py

This is the wrapper arond the user's python command. It works like this:

1. User types `develop script.py` (instead of `develop script.py`)
2. This drops into an "orchestrator". It registers to the develop_server as "shim-control". It's needed for restarting (i.e., managing the lifecycle of the actual process running the user's code) It's communication with develop_server is about things like receiving "restart" or "shutdown" commands. Orchestrator spawns a child with `Popen` that will run the monkey-patched user code. 
3. Child installs monkey patches. It registers to the develop_server as "shim-runner". It runs the actual python code from the user. It communicates with the server about inputs and outputs to LLM calls (etc). Its stdin, stdout, stderr, etc. will be forwarded to the user's terminal as is.

ALTERNATIVELY: If the user doesn't run `develop script.py` from terminal but from a debugger, things work similarly but there's small changes into how the child process is started and restarted by the orchestrator.
