# API Patching

AO uses monkey patching to intercept LLM API calls, record their inputs/outputs, and taint their responses.

## Overview

When you import an LLM SDK (like OpenAI or Anthropic), AO patches the relevant methods to:

1. Record the call inputs
2. Execute the original API call
3. Record the outputs
4. Wrap outputs with taint information
5. Report the call to the server

## Supported APIs

AO intercepts LLM calls via HTTP library patches:

| Patch | Covers |
|-------|--------|
| `httpx_patch.py` | OpenAI, Anthropic (via httpx) |
| `requests_patch.py` | APIs using requests library |
| `genai_patch.py` | Google GenAI |
| `mcp_patches.py` | MCP tool calls |
| `randomness_patch.py` | numpy, torch, uuid seeding |

## How Patches Are Applied

Patches are applied lazily when you import the relevant module. The `LAZY_PATCHES` dict in `apply_monkey_patches.py` maps module names to patch functions:

```python
LAZY_PATCHES = {
    "httpx": ("ao.runner.monkey_patching.patches.httpx_patch", "httpx_patch"),
    "requests": ("ao.runner.monkey_patching.patches.requests_patch", "requests_patch"),
    "google.genai": ("ao.runner.monkey_patching.patches.genai_patch", "genai_patch"),
    "mcp": ("ao.runner.monkey_patching.patches.mcp_patches", "mcp_patch"),
    ...
}
```

When you `import httpx`, AO's import hook triggers `httpx_patch()` before returning the module.

## Patch Structure

A typical patch follows this pattern (see `httpx_patch.py` for a complete example):

```
def patched_function(self, *args, **kwargs):
    api_type = "my_api.method"

    # 1. Build input dict from args/kwargs
    input_dict = get_input_dict(original_function, *args, **kwargs)

    # 2. Read taint origins from the stack
    taint_origins = builtins.TAINT_STACK.read()

    # 3. Check cache or call the LLM
    cache_output = DB.get_in_out(input_dict, api_type)
    if cache_output.output is None:
        result = original_function(**cache_output.input_dict)
        DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

    # 4. Report node and edges to server
    send_graph_node_and_edges(
        node_id=cache_output.node_id,
        input_dict=cache_output.input_dict,
        output_obj=cache_output.output,
        source_node_ids=taint_origins,
        api_type=api_type,
    )

    # 5. Update taint stack with this node's ID
    builtins.TAINT_STACK.update([cache_output.node_id])
    return cache_output.output
```

## Writing New Patches

### Step 1: Identify the Target

Determine which method you need to patch. For example:

```
# We want to patch:
client.chat.completions.create(...)
```

### Step 2: Create the Patch File

Add a new file in `src/runner/monkey_patching/patches/`:

```
# src/runner/monkey_patching/patches/my_api_patch.py

from functools import wraps
import builtins
from ao.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from ao.server.database_manager import DB

def patch_my_api_send(original_send):
    @wraps(original_send)
    def patched_send(self, *args, **kwargs):
        # Your patching logic here (see httpx_patch.py for full example)
        pass
    return patched_send
```

### Step 3: Create the Patch Function

In your patch file, create a function that applies the patches when called:

```python
def my_api_patch():
    try:
        from my_api import Client
    except ImportError:
        logger.info("my_api not installed, skipping patches")
        return

    def create_patched_init(original_init):
        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            # Apply method patches here
            patch_my_api_send(self, type(self))
        return patched_init

    Client.__init__ = create_patched_init(Client.__init__)
```

### Step 4: Register in LAZY_PATCHES

Add your patch to the `LAZY_PATCHES` dict in `apply_monkey_patches.py`:

```python
LAZY_PATCHES = {
    "httpx": ("ao.runner.monkey_patching.patches.httpx_patch", "httpx_patch"),
    "my_api": ("ao.runner.monkey_patching.patches.my_api_patch", "my_api_patch"),  # Add here
    ...
}
```

The patch will be applied automatically when users `import my_api`.

## Example: httpx Patch

Here's a simplified view of how the httpx patch works (used by OpenAI, Anthropic, etc.):

```
def patch_httpx_send(bound_obj, bound_cls):
    original_function = bound_obj.send

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        api_type = "httpx.Client.send"
        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = builtins.TAINT_STACK.read()

        # Check if URL is whitelisted (LLM endpoint)
        request = input_dict["request"]
        if not is_whitelisted_endpoint(str(request.url), request.url.path):
            return original_function(*args, **kwargs)

        # Get cached result or call LLM
        cache_output = DB.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = original_function(**cache_output.input_dict)
            DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

        # Report to server and update taint stack
        send_graph_node_and_edges(...)
        builtins.TAINT_STACK.update([cache_output.node_id])
        return cache_output.output

    bound_obj.send = patched_function.__get__(bound_obj, bound_cls)
```

## Async Support

Many LLM APIs are async. Patches must handle both sync and async methods:

```
def patch_method(original):
    if asyncio.iscoroutinefunction(original):
        @wraps(original)
        async def async_patched(*args, **kwargs):
            # async implementation
            pass
        return async_patched
    else:
        @wraps(original)
        def sync_patched(*args, **kwargs):
            # sync implementation
            pass
        return sync_patched
```

## API Parsers

Each LLM API has different request/response formats. API parsers extract relevant information:

```
src/runner/monkey_patching/api_parsers/
├── httpx_api_parser.py    # OpenAI, Anthropic (via httpx)
├── requests_api_parser.py # APIs using requests
├── genai_api_parser.py    # Google GenAI
└── mcp_api_parser.py      # MCP tool calls
```

Parsers normalize HTTP responses into a common format for caching and display. See `api_parser.py` for the main interface that routes to the appropriate parser based on `api_type`.

## Maintenance

LLM APIs change frequently. To detect API changes:

1. Run tests after upgrading SDK versions
2. Check for deprecation warnings
3. Review SDK changelogs

## Next Steps

- [Testing](testing.md) - Running the test suite
- [Architecture](architecture.md) - System overview
