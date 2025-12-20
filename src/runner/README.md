# Running a user script

## agent_runner.py

This is the wrapper around the user's python command. It works like this:

1. User types `aco-launch script.py` (instead of `python script.py`)
2. This drops into an "agent runner". The agent runner installs monkey patches, establishes a connection to the server, and then runs the user's actual python program using `runpy.run_module`.
Through the monkey patches, the agent runner communicates events in the user's code to the server (e.g., LLM call happened + inputs and outputs). Its stdin, stdout, stderr, etc. will be shown to the user's terminal as is. The goal here is to provide the illusion that the user just types `python script.py`.


## context_manager.py

Manages context like the session ids for different threads.

Sometimes the user wants to do "subruns" within their `aco-launch` run. For example, if the user runs an eval script, they may want each sample to be a separate run. The can do this as follows:

```
for sample in samples:
    with aco_launch("run name"):
        eval_sample(prompt)
```

This can also be used to run many samples concurrently (see examples in `example_workflows/debug_examples/`).

The implementation of the aco_launch context manager is in `context_manager.py`. The diagram below depicts its message sequence chart:

![Subruns](/docs/media/subrun.png)


## Computing data flow

To log LLM inputs and outputs and trace data flow ("taint") from LLM to LLM, we use two mechanisms:

1. **Recording LLM calls:** We "[monkey-patch](/src/runner/monkey_patching/)" LLM calls. When the user imports a package (e.g., `import OpenAI`), patched methods (i) log LLM calls to the server, and (ii) use ACTIVE_TAINT to pass taint information back to user code, where results are wrapped in "[taint wrappers](/src/runner/taint_wrappers.py)".

2. **Propagating taint:** We track how LLM outputs propagate through the program until used as input to another LLM. This uses a strict boundary between user code and third-party code:
   - **User code:** TaintWrapper objects track data provenance (e.g., `taint_wrap("hello") + " world"` becomes `TaintWrapper("Hello world")`)  
   - **Third-party code:** Receives only untainted data, with taint managed via ACTIVE_TAINT
   - **Boundary crossing:** AST-rewritten calls (e.g., `os.path.join(b, c)`) use [exec_func](/src/server/ast_transformer.py) to transfer taint through ACTIVE_TAINT 

### Putting it Together: Execution Flow
1. The server spawns a [File Watcher](/src/server/file_watcher.py) daemon process that continuously polls `.py` files in the user's code base.
    - If a file changed, the [File Watcher](/src/server/file_watcher.py) uses the [AST Transformer](/src/server/ast_transformer.py) to rewrite third-party library calls using the ACTIVE_TAINT pattern
    - After rewriting a file, the [File Watcher](/src/server/file_watcher.py) compiles it and saves the binary as `.pyc` file in the correct `__pycache__` directory.

2. The user runs a script using `aco-launch script.py`. 
   - An import hook (`ast_rewrite_hook.py`) ensures AST-rewritten `.pyc` files exist before user module imports
   - Python loads the compiled `.pyc` binary with ACTIVE_TAINT-based taint propagation
   - [Monkey patches](/src/runner/monkey_patching/) are installed for LLM libraries (e.g., OpenAI), which use ACTIVE_TAINT to communicate taint with user code

3. TaintWrapper objects propagate through user code while third-party functions receive clean data via ACTIVE_TAINT. When tainted data reaches another LLM call, the monkey patch extracts taint origins from ACTIVE_TAINT and tells the server to create dataflow graph edges. 

> [!NOTE]
> The AST rewrites and monkey patches serve very similar purposes. However: 
>  - For LLM calls, we want to have custom handling (parse inputs and outputs for custom APIs). Monkey patches make it easier to perform such targeted overwrites on specific methods. 
> - For general library calls, we don't distinguish between different libraries/classes/methods and just want to pass taint through. AST rewrites make it easier to cover a broad range of libraries.



## Maintainance

We need to patch a lot of API functions. Maintaining them will be challenging but since all of the patches follow a similar pattern, the hope is that AI tools will be pretty good at generating them. Please make your code as clean as possible and try to follow existing conventions. For our own sanity but also so the AI tools work better.

TODO: We need CI/CD tests that detect API changes. Can simply be if API changed (pip upgrade openai, etc) and then send email with change log link.

### Writing a monkey patch

First look at `patch_openai_responses_create` in `monkey_patches/openai_patches.py` to understand how a patch looks like. Also check how patches are applied inside the `__init__` of a client. For many patches, you can use our patching agent (`_dev_patch.py`). Run it from this folder as it contains hardcoded the prompts contain relative paths.

1. Before patching the function, you must specify which file the patch should be written to. You might need to create a new file for this. 

2. The patch needs to be installed inside a client `__init__`. If you're writing the first patch for a client, you need to write a patch for the client `__init__`:
   
```python
def openai_patch():
    try:
        from openai import OpenAI
    except ImportError:
        logger.info("OpenAI not installed, skipping OpenAI patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)

        return patched_init

    OpenAI.__init__ = create_patched_init(OpenAI.__init__)
```

You then need to register this patching function in `apply_monkey_patches.py`. Many times this

3. Set up the agent by following the instructions in `_dev_patch.py`.

4. `python _dev_patch.py`
