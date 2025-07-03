# Running the Copilot

NOTE: Below is out-dated.

## UI
We assume the user uses Python to run their agentic workflow, e.g.:

 - `python -m foo.bar`
 - `ENV_VAR=5 python script.py --some-flag`

All they change is the Python command. Whenever they want to develop their script with us, they run:

 - `develop -m foo.bar`
 - `ENV_VAR=5 develop script.py --some-flag`

This will feel *exactly* the same as running Python but also analyzes their code, populates our VS Code extension, etc. Specfically:

 - Programn prints to terminal and crashes the same
 - User can use VS Code debugger

## Architecture

When the user runs `develop script.py`, he just runs a little CLI shim that (1) monkey patches the user's code, (2) installs a `sys.setprofile` hook which records function calls and returns and send them back to a supervisor server, (3) runs the user's Python command exactly as the user wanted to (debugger works, same dir, env vars, if the user does weird stuff like relative imports, that will also work). (shim code)

We have a supervisor server running in the background. This server (1) communicates with the VS Code extension, (2) restarts Python (shim) processes if the user wants to re-run due to an LLM input edit (it kills the Python (shim) process and then restart the shim), (4) communicates with the Pyre server (our static analysis tool), (5) keeps some state. (server code)


## Develop

### Server

Manually starting and stoping server:

 - `python src/agent_copilot/develop_server.py start` 
 - `python src/agent_copilot/develop_server.py stop`

Some basics: 

 - To check if the server process is still running: `ps aux | grep develop_server.py` 

 - To check if the socket is still in use (and which process is holding it): `lsof -i :5959`
