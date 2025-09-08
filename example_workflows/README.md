# Agent examples

We implement example workflows here, including solutions for benchmarks.

All example workflows except for `debug_examples/` are git modules that live in separate github repos. These are private repos inside our organization and you might need to ask for permission to access them. To clone one of these repos, follow the README.md in the corresponding dir.

If you want to add a new workflow, do the following:
1. Your example workflow will live in its OWN private github repo inside our agops-project organization. It will not be automatically cloned with `agent-copilot`. Create that private repo and ask for help if you don't have the permissions to do so.
2.  Create a decriptive name for the example (e.g, `example_workflows/chess_text2sql`). The actual example repo will be inside that folder (e.g., `chess_text2sql/CHESS`).
3.  Create a `README.md` inside the example folder (e.g., `chess_text2sql/README.md`) and describe how to clone the submodule (e.g., see `chess_text2sql`) and add some notes that help to get it running (e.g., installs, where files are, weird quirks).
4.  `cd` into `agent_copilot` project root.
5.  Add the new example repo (e.g., `chess_text2sql/CHESS`) as a submodule:
```
git submodule add https://github.com/agops-project/SOMETHING.git
  example_workflows/example_folder/SOMETHING
```
6. Add a short description of your workflow below.

## Simple workflows

 - `debug_examples`: Simple workflows to debug our code.

 - `doc_bench`: Questions over PDFs.

 - `human-eval`: Evaluate model-generated code. Download data from https://github.com/openai/human-eval.

## Medium workflows

 - `chess_text2sql`: Used to be SOTA on the BIRD Text2SQL benchmark. https://github.com/ShayanTalaei/CHESS

## Complex workflows

 - `DeepResearch`: MiroFlow open-source deep research agent.

 - `SWE-bench`: SWE-bench benchmark with our own agent created by Claude code.
