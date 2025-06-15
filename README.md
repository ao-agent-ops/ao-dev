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


## Running brainstorming doc

https://docs.google.com/document/d/1B0YCZXxEa1St744XfLSZR2Yzt_zihRdUB-d_c1wFw3Q/edit?tab=t.0#heading=h.ltj5f1i4sgpz

## Dev

### Keep dependencies up to date

Keep dependencies in pyproject.toml up to date:

`conda env export --no-builds --from-history > conda-environment.yml`


### TODOs

pyre is hacky (static analysis):
 - We want to set llm calls as source and sink but somehow I couldn't figure out how. We now define other functions as sources and sinks and make stubs for the LLM calls (e.g., we create folder structure to exactly reflect `openai.resources.responses.responses.create` and add a the create function to contain sources and sinks for taint). However, these stubs don't work if they're just in our code base (e.g., `pyre_static_analysis`) but only worked when I placed them directly into the user repo. That sucks ...
