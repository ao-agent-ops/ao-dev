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

1. **Recording LLM calls:** We "[monkey-patch](/src/runner/monkey_patching/)" LLM calls. When the user imports a package (e.g., `import OpenAI`), we give them an OpenAI package where classes and methods are patched such that (i) they log LLM calls to the server (e.g., input and outputs), and (ii) they wrap the output object inside a "[taint wrapper](/src/runner/taint_wrappers.py)", which records that the output was produced by the specific LLM call.
2. **Propagating taint:** After an LLM produced an output, we need to track how this output is propagated through the program until it is eventually used as input to another LLM (imagine: llm_1's output is parsed and used in a Google search. The result is then used as input to llm_2. There's data flow from llm_1 to llm_2). We achieve this through (i) operations on taint wrappers correctly propagate taint (e.g., `TaintStr("hello") + " world"` becomes `TaintStr("Hello world")`), (ii) third-party library calls (e.g., `a = os.path.join(b, c)`) are rewritten ([AST transformer](/src/server/ast_transformer.py)) such that their output carries the same taint as their outputs (we describe this in more detail [here](/src/server/README.md)). 

### Putting it Together: Execution Flow
1. The server spawns a [File Watcher](/src/server/file_watcher.py) daemon process that continuously polls `.py` files in the user's code base.
    - If a file changed (i.e., the user edited its code), the [File Watcher](/src/server/file_watcher.py) reads the file and uses the [AST Transformer](/src/server/ast_transformer.py) to rewrite the file. Third-party library calls become: `untaint inputs -> run function call normally -> taint outputs (record origins of inputs)` 
    - After rewriting a file, the [File Watcher](/src/server/file_watcher.py) compiles it and saves the binary as `.pyc` file in the correct `__pycache__` directory.

2. The user runs a script in their repo using `aco-launch script.py`. 
   - An import hook (`ast_rewrite_hook.py`) is installed to ensure AST-rewritten `.pyc` files exist before any user module imports
   - Python loads the compiled `.pyc` binary --- Remember: This binary has been rewritten by the [File Watcher](/src/server/file_watcher.py) and propagates taint through third-party functions.
   - We install [monkey patches](/src/runner/monkey_patching/) for relevant imports made in the script (e.g., when the user does `import OpenAI`, they import a patched version of OpenAI). These patches serve a similar purpose as the AST rewrites and transform LLM calls into: `untaint inputs -> make LLM call -> taint the output (record it was produced in this call)`

3. The tainted output from the LLM call is propagated through the program using the transformed, taint-propagating code produced by the [File Watcher](/src/server/file_watcher.py). It eventually arrives at another LLM, which untaints its inputs, realizes the origin of the input and tells the server to insert an edge in the data flow graph accordingly. 

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
