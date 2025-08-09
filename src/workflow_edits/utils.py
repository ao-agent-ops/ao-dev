import hashlib
import json
import os


# === Anthropic Response helpers ===
def _anthropic_response_to_json(response) -> str:
    """Serialize an Anthropic Response object to a JSON string for storage."""
    if hasattr(response, 'model_dump'):
        return json.dumps(response.model_dump())
    elif hasattr(response, '__dict__'):
        return json.dumps(response.__dict__, default=str)
    else:
        return json.dumps(str(response))

def _anthropic_json_to_response(json_str: str):
    """Deserialize a JSON string from the DB to an Anthropic Response object."""
    try:
        from anthropic.types import Message as AnthropicMessage
    except ImportError:
        raise ImportError("Anthropic library not installed. Cannot deserialize Anthropic response.")
    
    data = json.loads(json_str)
    try:
        return AnthropicMessage(**data)
    except Exception:
        return str(data)

def _anthropic_swap_output(output_text: str, json_response: str) -> str:
    # Parse the JSON response
    response_data = json.loads(json_response)
    
    # Replace the text content in Anthropic response format
    if 'content' in response_data and isinstance(response_data['content'], list):
        for content_item in response_data['content']:
            if content_item.get('type') == 'text':
                content_item['text'] = output_text
                break
    
    return json.dumps(response_data, indent=2)

def _anthropic_extract_output_text(response):
    """Extract the output string from an Anthropic Response object or dict."""
    if hasattr(response, 'get_raw'):
        response = response.get_raw()
    try:
        return response.content[0].text
    except Exception:
        return str(response)

# === OpenAI v2 Response helpers ===
def _oai_v2_response_to_json(response) -> str:
    """Serialize an OpenAI v2 Response object to a JSON string for storage."""
    return json.dumps(response.model_dump())

def _oai_v2_json_to_response(json_str: str):
    """Deserialize a JSON string from the DB to an OpenAI v2 Response object."""
    try:
        from openai.types.responses.response import Response
    except ImportError:
        raise ImportError("OpenAI library not installed. Cannot deserialize OpenAI response.")
    
    data = json.loads(json_str)
    try:
        return Response(**data)
    except Exception:
        return str(data)

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
    try:
        return response.content[0].text.value
    except Exception:
        return str(response) 

def _oai_v2_extract_output_text(response):
    """Extract the output string from an Response object."""
    if hasattr(response, 'get_raw'):
        response = response.get_raw()
    try:
        return response.output[0].content[0].text
    except Exception:
        return str(response) 

# === VertexAI Response helpers ===
def _vertexai_extract_output_text(response):
    """Extract the output string from a Vertex AI Response object."""
    if hasattr(response, 'get_raw'):
        response = response.get_raw()
    try:
        return response.text
    except Exception:
        return str(response) 

def _vertexai_response_to_json(response) -> str:
    """Convert Vertex AI response to JSON string."""
    return json.dumps({
        "output_text": response.output_text if hasattr(response, 'output_text') else str(response)
    }, indent=2)

def _vertexai_json_to_response(json_str: str):
    """Convert JSON string back to Vertex AI response-like object."""
    data = json.loads(json_str)
    
    try:
        from google.genai.types import GenerateContentResponse
    except ImportError:
        raise ImportError("VertexAI library not installed. Cannot deserialize VertexAI response.")

    try:
        response = GenerateContentResponse()
        response.output_text = data.get("output_text", "")
        return response
    except Exception:
        return str(data)

def _vertexai_swap_output(output_text: str, json_response: str) -> str:
    # Parse the JSON response
    response_data = json.loads(json_response)
    
    # Replace the output_text content in Vertex AI response format
    response_data["output_text"] = output_text
    return json.dumps(response_data, indent=2)
        
# === General Response helpers ===
def swap_output(output_text: str, json_response: str, api_type):
    if api_type == "openai_v2_response":
        return _oai_v2_swap_output(output_text, json_response)
    elif api_type == "anthropic_messages":
        return _anthropic_swap_output(output_text, json_response)
    elif api_type == "vertexai_generate_content":
        return _vertexai_swap_output(output_text, json_response)
    else:
        raise ValueError(f"Unknown API type {api_type}")
    
def extract_output_text(response, api_type):
    if api_type == "openai_v2_response":
        return _oai_v2_extract_output_text(response)
    elif api_type == "openai_assistant_query":
        return _oai_assistant_query_extract_output_text(response)
    elif api_type == "anthropic_messages":
        return _anthropic_extract_output_text(response)
    elif api_type == "vertexai_generate_content":
        return _vertexai_extract_output_text(response)
    else:
        raise ValueError(f"Unknown API type {api_type}")

def response_to_json(output, api_type):
    if api_type == "openai_v2_response":
        return _oai_v2_response_to_json(output)
    elif api_type == "anthropic_messages":
        return _anthropic_response_to_json(output)
    elif api_type == "vertexai_generate_content":
        return _vertexai_response_to_json(output)
    else:
        raise ValueError(f"Unknown API type {api_type}")

def json_to_response(json_str, api_type):
    if api_type == "openai_v2_response":
        return _oai_v2_json_to_response(json_str)
    elif api_type == "anthropic_messages":
        return _anthropic_json_to_response(json_str)
    elif api_type == "vertexai_generate_content":
        return _vertexai_json_to_response(json_str)
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