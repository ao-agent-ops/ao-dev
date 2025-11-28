import json
from typing import Any, Dict, List, Tuple


def func_kwargs_to_json_str_anthropic(
    input_dict: Dict[str, Any],
) -> Tuple[str, List[str]]:
    return json.dumps(input_dict["body"]), []


def api_obj_to_json_str_anthropic(obj: Any) -> str:
    import anthropic
    import anthropic._response
    import anthropic._legacy_response
    import anthropic.types.message

    name2obj = {
        **vars(anthropic._response),
        **vars(anthropic._legacy_response),
        **vars(anthropic.types.message),
    }

    def find_match_str(cls) -> str:
        possible_type_matches = [k for k, v in name2obj.items() if v == cls]
        if not len(possible_type_matches) == 1:
            return f"Error retrieving JSON repr of obj {obj}"
        return possible_type_matches[0]

    _type = find_match_str(obj.__class__)
    if _type == "LegacyAPIResponse":
        json_dict = {"api_response": {}, "http_response": {}}
        json_dict["api_response"]["cast_to"] = find_match_str(obj._cast_to)
        json_dict["api_response"]["client"] = str(obj._client.__class__)
        json_dict["api_response"]["stream"] = obj._stream
        json_dict["api_response"]["stream_cls"] = str(obj._stream_cls)
        json_dict["api_response"]["options"] = {
            k: v
            for k, v in obj._options.model_dump(
                mode="json", exclude_none=True, fallback=lambda _: None
            ).items()
            if v is not None
        }
        json_dict["api_response"]["retries_taken"] = obj.retries_taken
        json_dict["http_response"]["status_code"] = obj.http_response.status_code
        json_dict["http_response"]["content"] = obj.http_response.content.decode(
            encoding=obj.http_response.encoding
        )
        json_dict["http_response"]["encoding"] = obj.http_response.encoding
    else:
        json_dict = obj.to_dict(mode="json")

    json_dict["_type"] = _type
    json_str = json.dumps(json_dict)
    return json_str


def json_str_to_original_inp_dict_anthropic(json_str: str, input_dict: dict) -> dict:
    input_dict["body"] = json.loads(json_str)
    return input_dict


def json_str_to_api_obj_anthropic(new_output_text: str) -> None:
    from anthropic import Stream, AsyncStream, Anthropic, AsyncAnthropic
    from anthropic._models import FinalRequestOptions, construct_type
    from anthropic._legacy_response import LegacyAPIResponse
    import anthropic._response
    import anthropic._legacy_response
    import anthropic.types.message
    from httpx import Response

    name2obj = {
        **vars(anthropic._response),
        **vars(anthropic._legacy_response),
        **vars(anthropic.types.message),
    }

    output_dict = json.loads(new_output_text)
    _type = output_dict.pop("_type", None)
    if not _type:
        raise TypeError("_type not set")

    _cls = name2obj[_type]
    if _cls == LegacyAPIResponse:
        cast_to = name2obj[output_dict["api_response"]["cast_to"]]
        client = (
            AsyncAnthropic()
            if "AsyncOpenAI" in output_dict["api_response"]["client"]
            else Anthropic()
        )
        stream = output_dict["api_response"]["stream"]
        stream_cls = (
            AsyncStream if "AsyncStream" in output_dict["api_response"]["stream_cls"] else Stream
        )
        options = FinalRequestOptions.model_validate(output_dict["api_response"]["options"])
        retries_takes = output_dict["api_response"]["retries_taken"]

        status_code = output_dict["http_response"]["status_code"]
        content = output_dict["http_response"]["content"].encode(
            output_dict["http_response"]["encoding"]
        )
        httpx_response = Response(status_code=status_code)
        httpx_response._content = content
        output_obj = LegacyAPIResponse(
            raw=httpx_response,
            cast_to=cast_to,
            client=client,
            stream=stream,
            stream_cls=stream_cls,
            options=options,
            retries_taken=retries_takes,
        )
    else:
        output_obj = construct_type(value=output_dict, type_=_cls)
    return output_obj


def get_model_anthropic(input_dict: Dict[str, Any]) -> str:
    try:
        return input_dict["body"]["model"]
    except KeyError:
        return "undefined"
