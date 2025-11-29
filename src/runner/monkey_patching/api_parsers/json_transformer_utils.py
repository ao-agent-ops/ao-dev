import copy
from dataclasses import dataclass


def get_path(obj, path: str):
    """
    Get value at path, supporting [*] for list mapping.
    """
    parts = path.replace('[*]', '.[*].').split('.')
    parts = [p for p in parts if p]
    
    def traverse(current, remaining_parts):
        if not remaining_parts:
            return current
        
        part = remaining_parts[0]
        rest = remaining_parts[1:]
        
        if part == '[*]':
            return [traverse(item, rest) for item in current]
        else:
            return traverse(current[part], rest)
    
    return traverse(obj, parts)


def set_path(obj, path: str, value):
    """
    Set value at path, supporting [*] for list mapping.
    """
    parts = path.replace('[*]', '.[*].').split('.')
    parts = [p for p in parts if p]
    
    def traverse(current, remaining_parts, val):
        if len(remaining_parts) == 1:
            current[remaining_parts[0]] = val
            return
        
        part = remaining_parts[0]
        rest = remaining_parts[1:]
        
        if part == '[*]':
            for item, v in zip(current, val):
                traverse(item, rest, v)
        else:
            if part not in current:
                current[part] = {}
            traverse(current[part], rest, val)
    
    traverse(obj, parts, value)


def ensure_structure(path: str, value):
    """
    Build a nested structure based on the new_key path and populate with value.
    Supports [*] to indicate list structures.
    """
    parts = path.replace('[*]', '.[*].').split('.')
    parts = [p for p in parts if p]
    
    def build(remaining_parts, val):
        if not remaining_parts:
            return val
        
        part = remaining_parts[0]
        rest = remaining_parts[1:]
        
        if part == '[*]':
            # val should be a list, recurse into each element
            return [build(rest, v) for v in val]
        else:
            return {part: build(rest, val)}
    
    return build(parts, value)


def deep_merge(base: dict, update: dict) -> dict:
    """
    Recursively merge update into base.
    Lists are merged element-wise if same length.
    """
    result = copy.deepcopy(base)
    
    for key, value in update.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                # Merge lists element-wise
                merged_list = []
                for r_item, v_item in zip(result[key], value):
                    if isinstance(r_item, dict) and isinstance(v_item, dict):
                        merged_list.append(deep_merge(r_item, v_item))
                    else:
                        merged_list.append(v_item)
                result[key] = merged_list
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result


@dataclass
class TransformSpec:
    new_key: str
    original_path: str


class JsonTransformer:
    specs: list[TransformSpec] = []

    @classmethod
    def extract(cls, original: dict) -> dict:
        """Extract fields from original into a structured new format"""
        result = {}
        for spec in cls.specs:
            value = get_path(original, spec.original_path)
            structure = ensure_structure(spec.new_key, value)
            result = deep_merge(result, structure)
        return result

    @classmethod
    def apply(cls, original: dict, new: dict) -> dict:
        """Apply changes from new format back to original structure"""
        result = copy.deepcopy(original)
        for spec in cls.specs:
            value = get_path(new, spec.new_key)
            set_path(result, spec.original_path, value)
        return result

"""
# Usage example;

class OpenaiV1Responses(JsonTransformer):
    specs = [
        TransformSpec("Outputs[*].Content[*].Text", "output[*].content[*].text"),
        TransformSpec("Outputs[*].Content[*].Type", "output[*].content[*].type"),
        TransformSpec("Outputs[*].Role", "output[*].role"),
        TransformSpec("Outputs[*].Id", "output[*].id"),
        TransformSpec("Model", "model"),
    ]


if __name__ == "__main__":
    # Test OpenAI response reshaping
    print("=== OpenAI Response Transform ===")
    openai_response = {
        "model": "gpt-3.5-turbo-0125",
        "output": [
            {
                "id": "msg_0e6b2ff1a04a",
                "type": "message",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [],
                        "text": "The capital of France is Paris."
                    },
                    {
                        "type": "output_text",
                        "annotations": [],
                        "text": "It's a beautiful city."
                    }
                ],
                "role": "assistant"
            },
            {
                "id": "msg_abc123",
                "type": "message",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [],
                        "text": "Another message here."
                    }
                ],
                "role": "assistant"
            }
        ],
        "parallel_tool_calls": True,
    }

    extracted = OpenaiV1Responses.extract(openai_response)
    print("Extracted:")
    import json
    print(json.dumps(extracted, indent=2))
    
    # Modify and apply back
    extracted["Outputs"][0]["Content"][0]["Text"] = "MODIFIED TEXT"
    extracted["Outputs"][0]["Role"] = "user"
    updated = OpenaiV1Responses.apply(openai_response, extracted)
    print("\nAfter modification:")
    print(f"First message text: {updated['output'][0]['content'][0]['text']}")
    print(f"First message role: {updated['output'][0]['role']}")
    print(f"Preserved status: {updated['output'][0]['status']}")
    print()
"""