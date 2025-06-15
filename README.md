# Agent copilot

## Install
`pip install -r requirements.txt`


## Env vars
TODO (I should automate some of that)

`export PYRE_VERSION=client_and_binary`


## Running brainstorming doc

https://docs.google.com/document/d/1B0YCZXxEa1St744XfLSZR2Yzt_zihRdUB-d_c1wFw3Q/edit?tab=t.0#heading=h.ltj5f1i4sgpz

## TODOs

pyre is hacky (static analysis):
 - We want to set llm calls as source and sink but somehow I couldn't figure out how. We now define other functions as sources and sinks and make stubs for the LLM calls (e.g., we create folder structure to exactly reflect `openai.resources.responses.responses.create` and add a the create function to contain sources and sinks for taint). However, these stubs don't work if they're just in our code base (e.g., `pyre_static_analysis`) but only worked when I placed them directly into the user repo. That sucks ...

## Run VS Code extension

To launch exporer window with extension installed see [here](/agent-copilot/blob/main/src/user_interface/README.md).
