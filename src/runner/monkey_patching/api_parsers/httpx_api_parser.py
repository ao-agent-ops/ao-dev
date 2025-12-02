import json
from typing import Any, Dict
from aco.common.logger import logger


def json_str_to_original_inp_dict_httpx(json_str: str, input_dict: dict) -> dict:
    input_dict["body"] = json.loads(json_str)
    return input_dict


def func_kwargs_to_json_str_httpx(input_dict: Dict[str, Any]):
    return input_dict["request"].content.decode("utf-8"), []


def api_obj_to_json_str_httpx(obj: Any) -> str:
    import dill
    import base64
    from httpx import Response

    obj: Response

    out_dict = {}
    encoding = obj.encoding or "utf-8"
    out_bytes = dill.dumps(obj)
    out_dict["_obj_str"] = base64.b64encode(out_bytes).decode(encoding)
    out_dict["_encoding"] = encoding
    out_dict["content"] = obj.content.decode(encoding)
    # This is for debugging:
    # _transformed_back_obj = json_str_to_api_obj_httpx(json.dumps(out_dict))
    return json.dumps(out_dict)


def json_str_to_api_obj_httpx(new_output_text: str) -> None:
    import dill
    import base64
    from json import JSONDecodeError
    from httpx._decoders import TextDecoder

    out_dict = json.loads(new_output_text)
    encoding = out_dict["_encoding"] or "utf-8"
    obj = dill.loads(base64.b64decode(out_dict["_obj_str"].encode(encoding)))

    try:
        out_dict = json.loads(new_output_text)
        # check parsing of the modified content
        json.loads(out_dict["content"])
    except JSONDecodeError as e:
        logger.error(f"Error json loading modified output: {e}")
        return obj

    obj._content = out_dict["content"].encode(encoding)
    decoder = TextDecoder(encoding=encoding or "utf-8")
    obj._text = "".join([decoder.decode(obj._content), decoder.flush()])
    return obj


def get_model_httpx(input_dict: Dict[str, Any]) -> str:
    try:
        return json.loads(input_dict["request"].content.decode("utf-8"))["model"]
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
