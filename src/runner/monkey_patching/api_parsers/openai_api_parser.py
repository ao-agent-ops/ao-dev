import json
from typing import Any, Dict, List, Tuple


def json_str_to_original_inp_dict_openai(json_str: str, input_dict: dict) -> dict:
    input_dict["body"] = json.loads(json_str)
    return input_dict


def func_kwargs_to_json_str_openai(input_dict: Dict[str, Any]):
    return json.dumps(input_dict["body"]), []


def api_obj_to_json_str_openai(obj: Any) -> str:
    json_str = json.dumps(obj.to_dict(mode="json"))
    return json_str


def json_str_to_api_obj_openai(new_output_text: str) -> None:
    from openai._models import construct_type
    from openai.types.chat import ChatCompletion
    from openai.types.responses import Response

    output_dict = json.loads(new_output_text)

    if output_dict["object"] == "response":
        type_ = Response
    elif output_dict["object"] == "chat.completion":
        type_ = ChatCompletion
    else:
        raise TypeError(f"Unknown object type {output_dict['object']}")

    output_obj = construct_type(value=output_dict, type_=type_)
    return output_obj


def get_model_openai(input_dict: Dict[str, Any]) -> str:
    try:
        return input_dict["body"]["model"]
    except KeyError:
        return "undefined"
