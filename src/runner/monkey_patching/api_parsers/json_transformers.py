
import json
from aco.runner.monkey_patching.api_parsers.json_transformer_utils import JsonTransformer, TransformSpec


class OpenaiV1Responses(JsonTransformer):
    specs = [
        TransformSpec("Outputs[*].Contents[*].Text", "output[*].content[*].text"),
        TransformSpec("Outputs[*].Role", "output[*].role"),
        TransformSpec("Model", "model"),
    ]



if __name__ == "__main__":
    # Test new patch.
    copy_pasted_dict = {
    "id": "resp_0e6b2ff1a04a887800692b2523b1b48190974be8f3a7b6dfde",
    "object": "response",
    "created_at": 1764435235,
    "status": "completed",
    "background": False,
    "billing": {
        "payer": "developer"
    },
    "error": None,
    "incomplete_details": None,
    "instructions": None,
    "max_output_tokens": None,
    "max_tool_calls": None,
    "model": "gpt-3.5-turbo-0125",
    "output": [
        {
        "id": "msg_0e6b2ff1a04a887800692b2523f4c08190adb488fa642278df",
        "type": "message",
        "status": "completed",
        "content": [
            {
            "type": "output_text",
            "annotations": [],
            "logprobs": [],
            "text": "The capital of France is Paris. Paris has been the capital of France since the 10th century and is the largest city in the country. It is known for its rich history, cultural significance, and iconic landmarks such as the Eiffel Tower, Louvre Museum, and Notre-Dame Cathedral. Paris is also a major center for art, fashion, cuisine, and commerce, making it a fitting choice for the capital of France."
            }
        ],
        "role": "assistant"
        }
    ],
    "parallel_tool_calls": True,
    "previous_response_id": None,
    "prompt_cache_key": None,
    "prompt_cache_retention": None,
    "reasoning": {
        "effort": None,
        "summary": None
    },
    "safety_identifier": None,
    "service_tier": "default",
    "store": True,
    "temperature": 0.0,
    "text": {
        "format": {
        "type": "text"
        },
        "verbosity": "medium"
    },
    "tool_choice": "auto",
    "tools": [],
    "top_logprobs": 0,
    "top_p": 1.0,
    "truncation": "disabled",
    "usage": {
        "input_tokens": 16,
        "input_tokens_details": {
        "cached_tokens": 0
        },
        "output_tokens": 89,
        "output_tokens_details": {
        "reasoning_tokens": 0
        },
        "total_tokens": 105
    },
    "user": None,
    "metadata": {}
    }

    extracted = OpenaiV1Responses.extract(copy_pasted_dict)
    print(f"Extracted: {json.dumps(extracted, indent=2)}")