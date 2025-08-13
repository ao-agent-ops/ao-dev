# Runtime tracing

## Registering calls

See which functions are executed at runtime.

`sitecustomize.py` applies the monkey patching. It intercepts all calls to LLMs and sends to the `develop_server`: Their input, output, file and line number, and the thread / asynio thread the LLM were called from.


## Data flow between LLM calls

Generally, we use wrappers around primitives, which are defined in `taint_wrappers.py`: For example, strings (`str`) are wrapped in `TaintStr`

The wrappers contain the origin of their "taint" (i.e., which LLM call they stem from) and implement functions such as `__add__`, so when you have `str + TaintStr` or `TaintStr + TaintStr`, taint is propagated through these operators. 

The difficult part are things like f-strings (`f"hello {world}"`) and `format`s (`Hello {}".format(world)`), since those cannot be handled by simply overwriting a string operator. To handle them, we do AST rewrites at runtime:


### AST Rewriting for f-strings and `.format()`
The core logic for rewriting f-strings and .format() calls is in `src/runtime_tracing/fstring_rewriter.py`:
`FStringTransformer` (subclass of `ast.NodeTransformer`):
`visit_JoinedStr`: This method is called for every f-string node in the AST. It replaces the f-string with a call to `taint_fstring_join`, e.g.:
 - `f"{a} {b}"` becomes `taint_fstring_join(a, b)`. This ensures that any taint on the interpolated values is preserved and propagated.
 - `visit_Call`: This method looks for `.format()` calls on string constants and replaces them with a call to taint_format_string, e.g.: `"Hello {}".format(name)` becomes `taint_format_string("Hello {}", name)`
  
`taint_fstring_join` and `taint_format_string`: These functions (also in `fstring_rewriter.py`) use the taint logic from taint_wrappers.py to combine taint from all arguments and return a TaintStr if any argument is tainted.

### How the AST Rewriter is Installed
 - The function `install_fstring_rewriter()` in `fstring_rewriter.py`:
Installs a custom import hook (`FStringImportFinder`) into sys.meta_path.
    - This import hook ensures that whenever a user module is imported, its source code is parsed, transformed (f-strings and `.format()` calls rewritten), and then executed.
    - The rewriter is installed at runtime by code in:
`src/runtime_tracing/sitecustomize.py` (which is loaded early via PYTHONPATH tricks).
 - The shim logic in develop_shim.py ensures that the environment is set up so that `sitecustomize.py` is loaded for user scripts.

### Taint Propagation
 - `TaintStr` (in `taint_wrappers.py`): A subclass of str that carries a `_taint_origin` attribute.
 - All string operations (+, format, slicing, etc.) are overridden to propagate taint.
 - `taint_wrap`: Used to wrap values (including OpenAI responses) with taint metadata.

### Putting it Together: Execution Flow
1. User script is run via the develop shim (develop_shim.py).
2. The shim sets up the environment so that:
 - The custom sitecustomize.py is loaded.
 - The f-string rewriter is installed for all user modules.
3. When a user module is imported, the import hook rewrites f-strings and .format() calls to use taint-aware functions.
4. When the user code executes f-strings or .format(), the taint-aware functions are called, and taint is propagated using TaintStr.
5. When LLM calls are made, the taint on the input is checked and, if present, the output is wrapped with a new taint node, allowing you to track data flow between LLM calls.

## Maintainance

We need to patch a lot of API functions. The idea is that, given a long list of working patches, AI tools can generate patches for new functions as APIs change. 

TODO: We need CI/CD tests that detect API changes. Can simply be if API changed (pip upgrade openai, etc) and then send email with change log link.