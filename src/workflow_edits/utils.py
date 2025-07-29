import hashlib
import json
import os
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
        
def _oai_assistant_query_extract_output_text(response):
    """Extract the output string from a Response object or dict."""
    if hasattr(response, 'get_raw'):
        response = response.get_raw()
    return response.content[0].text.value

def _oai_v2_extract_output_text(response):
    """Extract the output string from a Response object or dict."""
    if hasattr(response, 'get_raw'):
        response = response.get_raw()
    try:
        # v2 OpenAI Response object or dict
        return response.output[0].content[0].text
    except Exception:
        try:
            # If dict. TODO: Why would it be a dict?
            return response['output'][0]['content'][0]['text']
        except Exception:
            return str(response) 
        
# === General Response helpers ===
def swap_output(output_text: str, json_response: str, api_type):
    if api_type == "openai_v2_response":
        return _oai_v2_swap_output(output_text, json_response)
    else:
        raise ValueError(f"Unknown API type {api_type}")
    
def extract_output_text(response, api_type):
    if api_type == "openai_v2_response":
        return _oai_v2_extract_output_text(response)
    elif api_type == "openai_assistant_query":
        return _oai_assistant_query_extract_output_text(response)
    else:
        raise ValueError(f"Unknown API type {api_type}")

def response_to_json(output, api_type):
    if api_type == "openai_v2_response":
        return oai_v2_response_to_json(output)
    else:
        raise ValueError(f"Unknown API type {api_type}")

def json_to_response(json_str, api_type):
    if api_type == "openai_v2_response":
        return oai_v2_json_to_response(json_str)
    else:
        raise ValueError(f"Unknown API type {api_type}")

# === Write files to disk helpers ===
def stream_hash(stream):
    """Compute SHA-256 hash of a binary stream (reads full content into memory)."""
    content = stream.read()
    stream.seek(0)
    return hashlib.sha256(content).hexdigest()

def save_io_stream(stream, filename, dest_dir):
    """
    Save stream to dest_dir/filename. If filename already exists, find new unique one.
    """
    stream.seek(0)
    desired_path = os.path.join(dest_dir, filename)
    if not os.path.exists(desired_path):
        # No conflict, write directly
        with open(desired_path, 'wb') as f:
            f.write(stream.read())
        stream.seek(0)
        return desired_path

    # Different content, find a unique name
    base, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_filename = f"{base}_{counter}{ext}"
        new_path = os.path.join(dest_dir, new_filename)
        if not os.path.exists(new_path):
            with open(new_path, 'wb') as f:
                f.write(stream.read())
            stream.seek(0)
            return new_path

        counter += 1