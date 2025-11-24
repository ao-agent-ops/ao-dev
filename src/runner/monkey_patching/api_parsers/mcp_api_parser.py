import json
from typing import Any, Dict, List, Tuple


def func_kwargs_to_json_str_mcp(
    input_dict: Dict[str, Any],
) -> Tuple[str, List[str]]:
    return (
        json.dumps(input_dict["request"].model_dump(by_alias=True, mode="json", exclude_none=True)),
        [],
    )


def api_obj_to_json_str_mcp(obj: Any) -> str:
    return json.dumps(obj.model_dump(by_alias=True, mode="json", exclude_none=True))


def json_str_to_api_obj_mcp(new_output_text: str) -> dict:
    return json.loads(new_output_text)


def json_str_to_original_inp_dict_mcp(json_str: str, input_dict: dict) -> dict:
    input_dict["request"] = input_dict["request"].model_validate(json.loads(json_str))
    return input_dict


def get_model_mcp(input_dict: Dict[str, Any]) -> str:
    return input_dict["request"].root.method + ":" + input_dict["request"].root.params.name
