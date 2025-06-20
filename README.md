# Agent copilot

See README's in src dirs for more details.

## Launch VS Code extension

### Dependencies
The project has python dependencies but also others (for front end). I recommend you use a conda env. Run the following in project root dir:

```
conda env create -f conda-environment.yml
conda activate copilot
pip install -e .
```

### Launch front end
Then see [here](/src/user_interface/README.md) to launch exporer window with extension installed.


## Env vars
TODO (I should automate some of that)

`export PYRE_VERSION=client_and_binary`

## Further resources

 - [Google drive folder](https://drive.google.com/drive/folders/1Syc77Cko6PFlr_wnxBMa6PB-_aXCOt1v?usp=sharing)
 - [Project description](https://docs.google.com/document/d/13L2eVu8jAGZwmgp49OoXigCrmA7CUExQOpSmC5HhDls/edit?usp=sharing)
 - [Initial brainstorming doc](https://docs.google.com/document/d/1B0YCZXxEa1St744XfLSZR2Yzt_zihRdUB-d_c1wFw3Q/edit?tab=t.0#heading=h.ltj5f1i4sgpz)


## Dev

### Architecture

These are the processes running. 

1. The users launch processes of their program by running `devlop their_script.py` which feels exactly like running their script normally with `python their_script.py` --- they can also use the debugger to run their script, which also feels completely normal. Under the hood the `develop` command monkey patches certain functions and logs runtime events to the `Python server`.
2. The `Python server` is the core of the system and responsbible for all analysis. It receives the logs from the user process and updates the UI according to its analyses.
3. The red boxes are the UI of the VS Code extension. The UI gets updated by the `Python server`. The VS Code extension spawn the `Python server` and tear it down. They also exchange a heart beat for failures and unclean VS Code exits.

![Processes overview](./media/processes.png)

### Keep dependencies up to date

Keep dependencies up to date:

`conda env export --no-builds --from-history > conda-environment.yml`


### TODOs

pyre is hacky (static analysis):
 - We want to set llm calls as source and sink but somehow I couldn't figure out how. We now define other functions as sources and sinks and make stubs for the LLM calls (e.g., we create folder structure to exactly reflect `openai.resources.responses.responses.create` and add a the create function to contain sources and sinks for taint). However, these stubs don't work if they're just in our code base (e.g., `pyre_static_analysis`) but only worked when I placed them directly into the user repo. That sucks ...

