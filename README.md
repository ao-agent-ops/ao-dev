# Agent Ops

See README's in src dirs for more details.

## User workflow
We assume the user coded their workflow in Python, i.e., runs it with something like:

 - `python -m foo.bar`
 - `ENV_VAR=5 python script.py --some-flag`

All they change is the Python command. Whenever they want to develop their script with us, they run:

 - `aco-launch -m foo.bar`
 - `ENV_VAR=5 aco-launch script.py --some-flag`

This will feel *exactly* the same as running Python but also analyzes their code, populates our VS Code extension, etc. Specfically:

 - Program prints/reads to/from same terminal, crashes the same, etc.
 - [User can use VS Code debugger](https://github.com/ferdiko/agent-copilot/blob/9af2cbc27fef1e6a0a6bb63c7ad678cf04cdb205/.vscode/launch.json#L11)

## Getting started
### Installation
If you're starting from a clean sheet, create a blank conda environment and activate it. We recommend Python 3.13, but Python versions >=3.10 are supported.
```bash
conda create -n aco python=3.13 -y && conda activate aco
```

> [!NOTE]  
> If you are a developer of this project, jump to the [Development](#development) section for installation instructions.

For non-developers, install the project like so:
```bash
pip install -e .
# Because the extension is not packaged yet, you need to install UI dependencies as well
cd src/user_interfaces && npm install
npm run build:all
```

### Running the extension
Open this project in a new window. Select the "Run Extension" option from the debugger and run it. This will open a new window with the extension enabled ([more details](/src/user_interface/README.md)).

![Setup Extension](docs/media/setup_extension.gif)

### Try an example
In the new window, you can now open any project that you are working on. We will run an example from our [examples](./example_workflows/debug_examples/) folder. Note that this example depends on the OpenAI API.
```bash
aco-launch ./example_workflows/debug_examples/openai_add_numbers.py
```

![Running Example](docs/media/execute_example.gif)


## Further resources

 - [Join our discord server](https://discord.gg/fjsNSa6TAh).
 - [Project goals](https://docs.google.com/document/d/1YzljXW03Hp94rb-eAa8bcLglmiVTaBGIOWf3LSWhivQ/edit?usp=sharing)
 - [Google drive folder](https://drive.google.com/drive/folders/1Syc77Cko6PFlr_wnxBMa6PB-_aXCOt1v?usp=sharing)


## Development

Please install the dependencies required for developing
```bash
pip install -e ".[dev]"
pre-commit install
cd src/user_interfaces && npm run build:all
```

Some Python linters will (incorrectly) say that the modules inside our code base can't be found. Run the following in the project root to make these linters happy:

```
ln -s src aco
```

### Server commands and log
To manually start and stop our server. Just do:

 - `aco-server start`
 - `aco-server stop`

If you make changes to the server code, you can also do `aco-server restart` so the changes are reflected in the running server. If you want to clear all recorded runs and cached LLM calls, do `aco-server clear`.

If the server isn't running already, it will automatically be started upon running `aco-launch`.

If you want to print the server logs, do `aco-server logs`. The server logs can be found in `~/.cache/agent-copilot/logs/server.log`.

### Architecture

These are the processes running. 

1. Run user program (green): The users launch processes of their program by running `aco-launch their_script.py` which feels exactly like running their script normally with `python their_script.py` --- they can also use the debugger to run their script, which also feels completely normal. Under the hood the `aco-launch` command monkey patches certain functions and logs runtime events to the `develop server`. The `develop runner` runs the actual python program of the user. The `develop orchestrator` manages the life cycle of the runner. For example, when the user presses the restart button in the UI, the orchestrator with kill the current runner and re-launch it. [Code](src/runner/)
2. Develop server (blue): The `develop server` is the core of the system and responsbible for all analysis. It receives the logs from the user process and updates the UI according to its analyses. All communication to/from the `develop server` happens over a TCP socket (default: 5959). [Code](src/server/)
3. UI (red): The red boxes are the UI of the VS Code extension. The UI gets updated by the `develop server`. TODO: The VS Code extension spawns the `develop server` and tears it down. They also exchange a heart beat for failures and unclean VS Code exits. [Code](src/user_interfaces/)

![Processes overview](docs/media/processes.png)

### Publishing

#### pip package

1. ‼️ Check `pyproject.toml`: Does everything look like what you want to upload (version number, package name). The package description that will appear on PyPI is in `PKG_README.md`.
2. Install `pip install build twine` if you haven't already.
3. Run `python -m build` in root dir. This wil create a `dist/` dir.
4. Test locally: `pip install dist/agops_bird-0.0.2-py3-none-any.whl` (you need to check the name of the `.whl` file).
5. Do a test upload, it's worth it. Publish to TestPyPI first: `python -m twine upload --repository testpypi dist/*`. Then try to install from TestPyPi. Ask Ferdi if you don't have the key to our TestPyPI account.
6. When installing from TestPyPI, do the following (just swap out the package name at the end of the command): `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ agops-bird==0.0.6`
7. Upload to PyPI: `python -m twine upload dist/*`. Ask Ferdi if you don't have the key to our PyPI account.


#### VS Code extension

1. ‼️ Look at `src/user_interface/package.json`. Make sure name, description, version are what you want.
1. Install `npm install -g @vscode/vsce` if you haven't already.
2. `cd src/user_interface`
3. Create VSIX package: `vsce package` . If you get errors like `npm error extraneous`, you need to `rm -rf node_modules package-lock.json`
4. `vsce publish`. Ask Ferdi for personal access token if you don't have it.