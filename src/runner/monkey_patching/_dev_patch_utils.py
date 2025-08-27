import asyncio
from openai import OpenAI
from html.parser import HTMLParser
from claude_code_sdk import query, ClaudeSDKClient, ClaudeCodeOptions


# 1. Write get_input function.
def _1_get_input(input_dict, function_id):
    function_signature = f"def _get_input_{function_id}(input_dict: any) -> str:"
    prompt = GET_INPUT.format(input_dict=input_dict, function_name=function_signature)
    return _call_openai(prompt)


# 2. Write set_input function.
def _2_set_input(get_function, function_id):
    function_signature = (
        f"def _set_input_{function_id}(prev_input_pickle: bytes, new_input_text: str) -> bytes:"
    )
    prompt = SET_INPUT.format(get_function=get_function, function_name=function_signature)
    return _call_openai(prompt)


# 3. Write get_output function.
def _3_get_output(output_obj, function_id):
    function_signature = f"def _get_output_{function_id}(response_obj: bytes) -> str:"
    prompt = GET_OUTPUT.format(output_obj=output_obj, function_name=function_signature)
    return _call_openai(prompt)


# 4. Write set_output function.
def _4_set_output(get_function, function_id):
    function_signature = (
        f"def _set_output_{function_id}(prev_input_pickle: bytes, new_output_text: str) -> bytes:"
    )
    prompt = SET_OUTPUT.format(get_function=get_function, function_name=function_signature)
    return _call_openai(prompt)


# 5. Write get_model function.
def _5_get_model(input_dict, function_id):
    func_signature = f"def _set_output_{function_id}(input_dict: Dict[str, Any]) -> str:"
    prompt = GET_MODEL.format(input_dict=input_dict, function_name=func_signature)
    return _call_openai(prompt)


# 6. Install set and get.
def _6_install_set_and_get(api_type, get_input, set_input, get_output, set_output, get_model):
    prompt = INSTALL_SET_AND_GET.format(
        api_type=api_type,
        get_input=get_input,
        set_input=set_input,
        get_output=get_output,
        set_output=set_output,
        get_model=get_model,
    )
    return _call_claude_code(prompt)


# 7. Similar patches written before?
def _7_similar_patch(api_type):
    prompt = SIMILAR_PATCHES.format(api_type=api_type)
    options = ["Read", "Bash"]
    return _call_claude_code(prompt, options)


# 8. Write patch.
def _8_write_patch(api_type, patch_plan):
    prompt = WRITE_PATCH.format(api_type=api_type, doc_and_similar=patch_plan)
    patch = _call_claude_code(prompt)
    patch_dict = extract_tag_content(patch)
    implementation = patch_dict["implementation"]
    explanation = patch_dict["explanation"]
    return implementation, explanation


# 9. Install patch
def _9_install_patch(api_type, implementation, file_name):
    prompt = INSTALL_PATCH.format(api_type=api_type, patch=implementation, file_name=file_name)
    return _call_claude_code(prompt)


# =================================================
# Call LLM helpers.
# =================================================
client = OpenAI()


def _call_openai(input, model="gpt-4o"):
    response = client.responses.create(model=model, input=input, temperature=0)
    return response.output[0].content[0].text


def _call_claude_code(prompt, options=None):
    if options is None:
        options = ["Read", "Write", "Bash", "Replace", "Edit", "FileWrite", "FileEdit"]

    return asyncio.run(_async_call_claude_code(prompt, options))


async def _async_call_claude_code(prompt, options):
    options = ClaudeCodeOptions(
        permission_mode="acceptEdits",
        allowed_tools=options,
    )

    # Use the query function directly, not ClaudeSDKClient
    last_message = None
    async for message in query(prompt=prompt, options=options):
        print(f"\033[90mClaude reasoning message: {message}\033[0m")
        last_message = message

    return last_message.result


# =================================================
# Parse LLM response.
# =================================================
class TagContentExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = {}
        self.current_tag = None
        self.current_data = []

    def handle_starttag(self, tag, attrs):
        """Called when an opening tag is encountered"""
        self.current_tag = tag
        self.current_data = []  # Reset data collection for new tag

    def handle_endtag(self, tag):
        """Called when a closing tag is encountered"""
        if self.current_tag == tag and self.current_data:
            # Join all data pieces and strip whitespace
            content = "".join(self.current_data).strip()
            if content:  # Only add non-empty content
                self.result[tag] = content
        self.current_tag = None
        self.current_data = []

    def handle_data(self, data):
        """Called when text data is encountered"""
        if self.current_tag:
            self.current_data.append(data)

    def get_result(self):
        """Return the extracted dictionary"""
        return self.result


def extract_tag_content(html_string):
    """
    Extract content from HTML-like tags into a dictionary.
    """
    parser = TagContentExtractor()
    parser.feed(html_string)
    return parser.get_result()


# =================================================
# Prompts.
# =================================================

GET_INPUT = """Below is the full input kwargs dict to an LLM API call:

{input_dict}

You need to write function `{function_name}` that extracts the LLM input from the dict (i.e., disregarding further parameters such as model choice). This involves retrieving the right fields from the dictionary, which may be nested. You need to extract the input_string (i.e., the prompt) and, if there are attachments in the input, extract them as a list (however, there may not be any attachments). If the API call supports passing several inputs (i.e., a list of inputs), just take the last one at index -1. Specifically, your response should look as follows:

# If there are no attachments
return input_string, []

# If there are attachments
return input_string, list_of_attachments

Now, write `{function_name}`. Format your response as follows:

<identify_input>
Locate the input string and potentially the attachments in the given dict. Describe how they can be extracted.
</identify_input>

<implementation>
Provide the full implementation of `{function_name}` (signature, input extraction, and the return statement). Don't provide anything else except Python code.
</implementation>
"""

SET_INPUT = """The function below extracts the input from an input kwargs dict to an API LLM call.

{get_function}

We now want to write the corresponding `set` function `{function_name}`. Specifically, we want to overwrite the `input_string` retrieved in the `get` function with `new_input_text`. Ignore attachments. Since the modification happens in-place, there's no need to return anything, typically the function body is a single line.

Now implement `{function_name}`.

Format your response as follows:

<overwrite_plan>
Determine what the `input_string` field is that you need to overwrite. Refer to the `get` function above.
</overwrite_plan>

<implementation>
Provide the full implementation of `{function_name}` (signature and overwrite). Don't provide anything else except Python code.
</implementation>
"""

GET_OUTPUT = """Below is the output object returned by an LLM API call:

{output_obj}

You need to write function `{function_name}` that extracts the output from it. The output may be a simple response string, or a string indicating which function/tool the LLM wants to call. Extracting it involves accessing the right variables, which may be nested. Return a single string, which is the LLM response or the name of the tool it wants to call.

Format your response as follows:

<identify_output>
Locate the output: Is there a response string that you can extract? Is there a tool string that you can extract? If there is a tool, you need to extract the tool string. Otherwise, you need to extract the response string.
</identify_output>

<implementation>
Provide the full implementation of `{function_name}` (signature, function body for extracting the output, return statement of string). Don't provide anything else except Python code.
</implementation>
"""

SET_OUTPUT = """The function below extracts the output from a response object returned by an LLM API call.

{get_function}

We now want to write the corresponding `set` function `{function_name}`. Specifically, we want to overwrite the output that was retrieved in the `get` function with `new_output_text`. Since the modification happens in-place, there's no need to return anything, typically the function body is a single line.

Now implement `{function_name}`.

Format your response as follows:

<overwrite_plan>
Determine what the `output` field is that you need to overwrite. Refer to the `get` function above.
</overwrite_plan>

<implementation>
Provide the full implementation of `{function_name}` (signature and overwrite). Don't provide anything else except Python code.
</implementation>
"""

GET_MODEL = """Below is the full input kwargs dict to an LLM API call:

{input_dict}

You need to write function `{function_name}` that extracts the model name from the dict. This involves retrieving the right fields from the dictionary, which may be nested. Just return the model name as a string.

Format your response as follows:

<identify_input>
Locate the input string and potentially the attachments in the given dict. Describe how they can be extracted.
</identify_input>

<implementation>
Provide the full implementation of `{function_name}` (signature, model extraction, and the return statement). Don't provide anything else except Python code.
</implementation>
"""

INSTALL_SET_AND_GET = """@api_parser.py contains functions that get and set values of the input dicts and repsonse objects of LLM API calls.

Your task is to add support for another API type: {api_type}

You're given the following helper functions to handle this new API type:

```python
# ===============================================
# {api_type}
# ===============================================

{get_input}

{set_input}

{get_output}

{set_output}

{get_model}
```

Adding support for {api_type} consists of the following steps:

1. Read @api_parser.py to see how the support for other API types is implemented.
2. Add the helper functions to @api_parser.py. Are they consistent and do they make sense? If you are sure that there's an incosistency, fix it.
3. Register the helper functions with the router functions `get_input`, `set_input`, `get_output` and `set_output`, `get_model_name`, `cache_format` function respectively.
"""

SIMILAR_PATCHES = """I want to write a monkey patch for the LLM API call {api_type}. The ultimate goal of the patch is to implement something like the following:

```python
# Patch for OpenAI.responses.create is called patch_openai_responses_create
def patch_openai_responses_create(responses):
    try:
        from openai.resources.responses import Responses
    except ImportError:
        return

    # Original OpenAI.responses.create function
    original_function = responses.create

    # Patched function (executed instead of OpenAI.responses.create)
    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "OpenAI.responses.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            result = original_function(**input_to_use)  # Call LLM.
            CACHE.cache_output(node_id, result)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_to_use,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    responses.create = patched_function.__get__(responses, Responses)

```

However, sometimes a patch should only pass taint through or only call an API without modifying the input.

Before implementing anything, do the following:

1. Fetch the documentation for {api_type}. Understand what precisely the function does.
2. Search all patches in @patches/ and see if there are similar patches.
3. Give me a concise description what {api_type} does and if there are similar functions with existing patches.
"""


WRITE_PATCH = """I want to write a monkey patch for the LLM API call {api_type}. I already wrote some patches for other API functions and they can be found in @monkey_patches. The ultimate goal of the patch is to implement something like the following:

```python
# Patch for OpenAI.responses.create is called patch_openai_responses_create
def patch_openai_responses_create(responses):
    try:
        from openai.resources.responses import Responses
    except ImportError:
        return

    # Original OpenAI.responses.create function
    original_function = responses.create

    # Patched function (executed instead of OpenAI.responses.create)
    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "OpenAI.responses.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            result = original_function(**input_to_use)  # Call LLM.
            CACHE.cache_output(node_id, result)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_to_use,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    # Install patch.
    responses.create = patched_function.__get__(responses, Responses)

```

However, sometimes a patch should only pass taint through or only call an API without modifying the input. 

{doc_and_similar}

Format your response as follows.

<plan>
Precisely describe what the particular patch for {api_type} needs to achieve.
</plan>
<implementation>
Provide the full implementation of the patch alone (i.e., def patched_function). Only include python code. Follow the format of previous patches, like the example above, as closely as possible.
</implemetation>
<explanation>
Explain to me how your patch works and why it works. If you think it doesn't work, explain to me why.
</explanation>
"""

INSTALL_PATCH = """I want to write a monkey patch for the LLM API call {api_type}. I already wrote some patches for other API functions and they can be found in @monkey_patches. 

Below is the patch I wrote:

{patch}

Install it in {file_name}. Look at how other patches are installed in @patches and ensure you do the following:

 - You need to install the patch (i.e., overwrite the original function as original_function so the patch can use it, and then overwrite it to install the patch. Follow the example of other patches for this.
 - You need to register the patching function with the __init__ of the client. Again, refer to how other patches in @patches do this.
"""

ADD_API_TEST = """
TODO
"""
