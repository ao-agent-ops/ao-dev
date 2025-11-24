import json
from typing import Any, Dict, List, Tuple


def func_kwargs_to_json_str_google(
    input_dict: Dict[str, Any],
) -> Tuple[str, List[str]]:
    return json.dumps(input_dict), []


def api_obj_to_json_str_google(obj: Any | list) -> str:
    def get_obj_dump(_obj: Any):
        body_json = json.loads(_obj.body)
        complete_json = {"headers": _obj.headers, "body": body_json}
        return json.dumps(complete_json)

    if isinstance(obj, list):
        result = json.dumps([get_obj_dump(chunk) for chunk in obj])
    else:
        result = get_obj_dump(obj)
    return result


def json_str_to_api_obj_google(new_output_text: str) -> None:
    from google.genai.types import HttpResponse

    json_dict = json.loads(new_output_text)
    if isinstance(json_dict, list):
        result = [
            HttpResponse(headers=chunk["headers"], body=json.dumps(chunk["body"]))
            for chunk in map(json.loads, json_dict)
        ]
    else:
        result = HttpResponse(headers=json_dict["headers"], body=json.dumps(json_dict["body"]))
    return result


def get_model_google(input_dict: Dict[str, Any]) -> str:
    try:
        return input_dict["request_dict"]["_url"]["model"]
    except Exception:
        pass

    try:
        path = input_dict["path"]
        if ":" in path:
            return path.split(":")[-2]
        return path
    except Exception:
        return "undefined"
