# API Patching

Agent Copilot uses monkey patching to intercept LLM API calls, record their inputs/outputs, and taint their responses.

## Overview

When you import an LLM SDK (like OpenAI or Anthropic), Agent Copilot patches the relevant methods to:

1. Record the call inputs
2. Execute the original API call
3. Record the outputs
4. Wrap outputs with taint information
5. Report the call to the server

## Supported APIs

Currently supported LLM APIs:

- **OpenAI** - Chat completions, responses API
- **Anthropic** - Messages API
- **Google GenAI** - Generate content
- **LangChain** - Various LLM wrappers

## How Patches Are Applied

Patches are applied when you run `aco-launch`. The process:

1. **Import hook** - Catches imports of LLM SDKs
2. **Apply patches** - Wraps SDK methods with our instrumentation
3. **Transparent execution** - Your code runs normally, unaware of patches

## Patch Structure

A typical patch follows this pattern:

```python
def create_patched_method(original_method):
    @wraps(original_method)
    def patched_method(self, *args, **kwargs):
        # 1. Untaint inputs
        clean_args = untaint_if_needed(args)
        clean_kwargs = untaint_if_needed(kwargs)

        # 2. Collect taint origins from inputs
        input_origins = get_taint_origins(args) + get_taint_origins(kwargs)

        # 3. Execute original method
        result = original_method(self, *clean_args, **clean_kwargs)

        # 4. Report to server
        report_llm_call(inputs=clean_args, output=result, origins=input_origins)

        # 5. Taint the output
        return taint_wrap(result, taint_origin=[node_id])

    return patched_method
```

## Writing New Patches

### Step 1: Identify the Target

Determine which method you need to patch. For example:

```python
# We want to patch:
client.chat.completions.create(...)
```

### Step 2: Create the Patch File

Add a new file in `src/runner/monkey_patching/patches/`:

```python
# src/runner/monkey_patching/patches/my_api_patches.py

from functools import wraps
from aco.runner.taint_wrappers import get_taint_origins, untaint_if_needed, taint_wrap
from aco.runner.monkey_patching.patching_utils import report_llm_call

def patch_my_api_create(original_create):
    @wraps(original_create)
    def patched_create(self, *args, **kwargs):
        # Your patching logic here
        pass
    return patched_create
```

### Step 3: Register the Patch

In `apply_monkey_patches.py`, add your patch:

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
            self.completions.create = patch_my_api_create(
                self.completions.create
            )
        return patched_init

    Client.__init__ = create_patched_init(Client.__init__)
```

### Step 4: Add to Patch Registry

In `apply_monkey_patches.py`:

```python
def apply_all_monkey_patches():
    openai_patch()
    anthropic_patch()
    my_api_patch()  # Add your patch here
```

## Example: OpenAI Patch

Here's a simplified view of how the OpenAI patch works:

```python
def patch_openai_responses_create(original_create):
    @wraps(original_create)
    async def patched_create(self, *args, **kwargs):
        # Clean inputs
        clean_kwargs = untaint_if_needed(kwargs)

        # Get taint origins
        origins = get_taint_origins(kwargs)

        # Call original
        response = await original_create(self, *args, **clean_kwargs)

        # Parse and report
        parsed = parse_openai_response(response)
        node_id = report_llm_call(
            model=parsed.model,
            input=parsed.input,
            output=parsed.output,
            origins=origins,
        )

        # Taint the response
        return taint_wrap(response, taint_origin=[node_id])

    return patched_create
```

## Async Support

Many LLM APIs are async. Patches must handle both sync and async methods:

```python
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
├── openai_api_parser.py
├── anthropic_api_parser.py
├── genai_api_parser.py
└── ...
```

Parsers normalize the data for the server:

```python
def parse_openai_response(response):
    return {
        "model": response.model,
        "input": extract_messages(response),
        "output": response.choices[0].message.content,
        "usage": response.usage,
    }
```

## Maintenance

LLM APIs change frequently. To detect API changes:

1. Run tests after upgrading SDK versions
2. Check for deprecation warnings
3. Review SDK changelogs

## Next Steps

- [Testing](testing.md) - Running the test suite
- [Architecture](architecture.md) - System overview
