import json
from typing import Any, Dict


def json_str_to_original_inp_dict_httpx(json_str: str, input_dict: dict) -> dict:
    # For httpx, modify the body parameter
    input_dict["request"]._content = json_str.encode("utf-8")
    return input_dict


def func_kwargs_to_json_str_httpx(input_dict: Dict[str, Any]):
    # For httpx, extract content from request object
    json_str = json.dumps(json.loads(input_dict["request"].content.decode("utf-8")))
    return json_str, []


def api_obj_to_json_str_httpx(obj: Any) -> str:
    import dill
    import base64
    from httpx import Response

    obj: Response

    out_dict = {}
    encoding = obj.encoding if hasattr(obj, "encoding") else "utf-8"
    out_bytes = dill.dumps(obj)
    out_dict["_obj_str"] = base64.b64encode(out_bytes).decode(encoding)
    out_dict["_encoding"] = encoding
    out_dict["content"] = json.loads(obj.content.decode(encoding))
    return json.dumps(out_dict)


def json_str_to_api_obj_httpx(new_output_text: str) -> None:
    import dill
    import base64
    from httpx._decoders import TextDecoder

    out_dict = json.loads(new_output_text)
    encoding = out_dict["_encoding"] if "_encoding" in out_dict else "utf-8"
    obj = dill.loads(base64.b64decode(out_dict["_obj_str"].encode(encoding)))

    # For httpx.Response, update the content and text using the TextDecoder
    obj._content = json.dumps(out_dict["content"]).encode(encoding)
    decoder = TextDecoder(encoding=encoding)
    obj._text = "".join([decoder.decode(obj._content), decoder.flush()])
    return obj


def get_model_httpx(input_dict: Dict[str, Any]) -> str:
    try:
        # For httpx, extract content from request object
        json_str = input_dict["request"].content.decode("utf-8")
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
