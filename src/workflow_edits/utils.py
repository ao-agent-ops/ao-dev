import json
from openai.types.responses.response import Response


# === OpenAI v2 Response helpers ===
def oai_v2_response_to_json(response: Response) -> str:
    """Serialize an OpenAI v2 Response object to a JSON string for storage."""
    return json.dumps(response.model_dump())

def oai_v2_json_to_response(json_str: str) -> Response:
    """Deserialize a JSON string from the DB to an OpenAI v2 Response object."""
    data = json.loads(json_str)
    return Response(**data)

def _oai_v2_swap_output(output_text: str, json_response: str) -> str:
    # Parse the JSON response
    response_data = json.loads(json_response)
    
    # Make sure dict format is as we expect.
    assert (response_data.get("output") and 
        isinstance(response_data["output"], list) and 
        len(response_data["output"]) > 0 and
        response_data["output"][0].get("content") and
        isinstance(response_data["output"][0]["content"], list) and
        len(response_data["output"][0]["content"]) > 0 and
        response_data["output"][0]["content"][0].get("type"))
        
    # Replace the text field
    response_data["output"][0]["content"][0]["text"] = output_text
    
    # Return the updated JSON as a string
    return json.dumps(response_data, indent=2)
        
def _oai_v2_extract_output_text(response):
    """Extract the output string from a Response object or dict."""
    if hasattr(response, 'get_raw'):
        response = response.get_raw()
    try:
        # v2 OpenAI Response object or dict
        return response.output[0].content[0].text
    except Exception:
        try:
            # If dict
            return response['output'][0]['content'][0]['text']
        except Exception:
            return str(response) 
        
# === General Response helpers ===
def swap_output(output_text: str, json_response: str, api_type):
    if api_type == "openai_v2":
        return _oai_v2_swap_output(output_text, json_response)
    else:
        raise ValueError(f"Unknown API type {api_type}")
    
def extract_output_text(response, api_type):
    if api_type == "openai_v2":
        return _oai_v2_extract_output_text(response)
    else:
        raise ValueError(f"Unknown API type {api_type}")
