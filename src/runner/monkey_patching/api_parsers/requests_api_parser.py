import json
from typing import Any, Dict


def json_str_to_original_inp_dict_requests(json_str: str, input_dict: dict) -> dict:
    # For requests, modify the request body
    input_dict["request"].body = json_str.encode("utf-8")
    input_dict["request"].prepare_content_length(json_str.encode("utf-8"))
    return input_dict


def func_kwargs_to_json_str_requests(input_dict: Dict[str, Any]):
    # For requests, extract body from request object
    json_str = json.dumps(json.loads(input_dict["request"].body.decode("utf-8")), sort_keys=True)
    return json_str, []


def api_obj_to_json_str_requests(obj: Any) -> str:
    import dill
    import base64

    out_dict = {}
    encoding = obj.encoding if hasattr(obj, "encoding") else "utf-8"
    out_bytes = dill.dumps(obj)
    out_dict["_obj_str"] = base64.b64encode(out_bytes).decode(encoding)
    out_dict["_encoding"] = encoding
    out_dict["content"] = json.loads(obj.content.decode(encoding))
    return json.dumps(out_dict, sort_keys=True)


def json_str_to_api_obj_requests(new_output_text: str) -> None:
    import dill
    import base64

    out_dict = json.loads(new_output_text)
    encoding = out_dict["_encoding"] if "_encoding" in out_dict else "utf-8"
    obj = dill.loads(base64.b64decode(out_dict["_obj_str"].encode(encoding)))

    # For requests.Response, update the content and text attributes
    obj._content = json.dumps(out_dict["content"]).encode(encoding)
    # requests.Response doesn't have a decoder like httpx, it computes _text on access
    # So we just need to clear the cached _text to force recomputation
    if hasattr(obj, "_content_consumed"):
        obj._content_consumed = False
    return obj


def get_model_requests(input_dict: Dict[str, Any]) -> str:
    try:
        # For requests, extract body from request object
        json_str = input_dict["request"].body.decode("utf-8")
        return json.loads(json_str)["model"]
    except KeyError:
        # Fallback: try to extract model name from URL path
        # Pattern: /v1/models/{model_name}:generateContent or similar
        try:
            import re

            path = input_dict["request"].url.path
            # Match patterns like /v1/models/gemini-2.5-flash:generateContent
            match = re.search(r"/models/([^/]+?)(?::|$)", path)
            if match:
                return match.group(1)
        except (AttributeError, KeyError):
            pass
        return "undefined"
