# Parse a Python code base


## Static analysis

### Pysa pitfalls

We use Pysa (from Pyre) for the static analysis. Some pitfalls:

 - `ƛ Invalid configuration: Cannot find any source files to analyze. Either source_directories or targets must be specified.`: Try to add `__init__.py__` to the porject repo (and parent). Maybe this is always needed? But I would like to not make any modifications to the repos, so I'll loo into this more.

 - Sometimes you need to `export PYRE_VERSION=client_and_binary`, the error message will state that clearly.

 - When you run from command line directly (`pyre analyze --save-results-to=here`), you need to be inside `src/parser/pyre_static_analysis`. Also, `src/parser/pyre_static_analysis/.pyre_configuration` contains which repo you parse.

### Hacky implementation

We use stub implementations for the analysis (i.e., for the analysis, we import fake openAI calls etc.)

In the future, I need to figure out how we can treat a repo as "read-only", i.e., analyze it without modifying it. But for now we need to copy stubs and taint config into it.

TODO Command
