import json
from typing import Any, Dict
import requests
import datetime


def response_to_json(resp: requests.Response) -> str:
    state = resp.__getstate__()
    json_state: Dict[str, Any] = {}
    for key, value in state.items():
        if key == "elapsed":
            json_state[key] = value.total_seconds() if value else 0
        elif key == "headers":
            json_state[key] = dict(value) if value else {}
        elif key == "cookies":
            json_state[key] = requests.utils.dict_from_cookiejar(value) if value else {}
        elif key == "_content":
            json_state[key] = value.decode("utf-8") if value else None
        elif key == "request":
            json_state[key] = None
        elif key == "history":
            json_state[key] = []
        else:
            json_state[key] = value
    return json.dumps(json_state)


def response_from_json(json_str: str) -> requests.Response:
    from requests.structures import CaseInsensitiveDict
    from requests.cookies import cookiejar_from_dict

    json_state = json.loads(json_str)
    resp = requests.Response()
    for key, value in json_state.items():
        if key == "elapsed":
            setattr(
                resp, key, datetime.timedelta(seconds=value) if value else datetime.timedelta(0)
            )
        elif key == "headers":
            setattr(resp, key, CaseInsensitiveDict(value) if value else CaseInsensitiveDict())
        elif key == "cookies":
            setattr(resp, key, cookiejar_from_dict(value) if value else cookiejar_from_dict({}))
        elif key == "_content":
            setattr(resp, key, bytes(value, "utf-8") if value else False)
        else:
            setattr(resp, key, value)
    resp._content_consumed = True
    resp.raw = None
    return resp


def json_str_to_original_inp_dict_together(json_str: str, input_dict: dict) -> dict:
    input_dict["options"] = input_dict["options"].model_validate(json.loads(json_str))
    return input_dict


def func_kwargs_to_json_str_together(input_dict: Dict[str, Any]):
    attachments = []
    return input_dict["options"].model_dump_json(), attachments


def api_obj_to_json_str_together(obj: Any) -> str:
    return response_to_json(obj)


def json_str_to_api_obj_together(new_output_text: str) -> None:
    return response_from_json(new_output_text)


def get_model_together(input_dict: Dict[str, Any]) -> str:
    try:
        return input_dict["options"].params["model"]
    except KeyError:
        return "undefined"
