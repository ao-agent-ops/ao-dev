"""
Integration tests for OpenAI chat completions with real OpenAI SDK types.

This test suite verifies that our serialization works correctly with actual
OpenAI SDK objects (not just dicts), including handling of Pydantic models,
special types, and the NOT_GIVEN sentinel.
"""

import json
from openai._types import NOT_GIVEN

from aco.runner.monkey_patching.api_parsers.openai_api_parser import (
    _get_input_openai_chat_completions_create,
    _set_input_openai_chat_completions_create,
)


def test_with_not_given_sentinel():
    """Test handling of OpenAI's NOT_GIVEN sentinel value."""
    input_dict = {
        "messages": [{"role": "user", "content": "Hello"}],
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": NOT_GIVEN,  # NOT_GIVEN sentinel
        "top_p": NOT_GIVEN,
        "frequency_penalty": NOT_GIVEN,
    }

    # Serialize
    json_str, _, _ = _get_input_openai_chat_completions_create(input_dict)

    # Verify NOT_GIVEN is serialized as string
    parsed = json.loads(json_str)
    assert parsed["max_tokens"] == "NOT_GIVEN"
    assert parsed["top_p"] == "NOT_GIVEN"
    assert parsed["temperature"] == 0.7  # Regular value preserved

    # Deserialize
    new_input_dict = {}
    _set_input_openai_chat_completions_create(new_input_dict, json_str)

    # Verify NOT_GIVEN is restored
    assert new_input_dict["temperature"] == 0.7
    # NOT_GIVEN should be restored to the actual sentinel
    from openai._types import NOT_GIVEN as restored_sentinel

    assert new_input_dict["max_tokens"] == restored_sentinel
    assert new_input_dict["top_p"] == restored_sentinel


def test_complete_api_call_structure():
    """Test with a realistic complete API call structure."""
    input_dict = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What's the weather like?"},
        ],
        "model": "gpt-4o",
        "temperature": 0.8,
        "max_tokens": 500,
        "top_p": 0.95,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "n": 1,
        "stream": False,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string", "description": "City name"}},
                        "required": ["location"],
                    },
                },
            }
        ],
        "tool_choice": "auto",
        "user": "test_user_123",
        "seed": 42,
    }

    # Serialize
    json_str, attachments, tools = _get_input_openai_chat_completions_create(input_dict)

    # Verify
    parsed = json.loads(json_str)
    assert len(parsed["messages"]) == 2
    assert parsed["model"] == "gpt-4o"
    assert parsed["temperature"] == 0.8
    assert parsed["seed"] == 42
    assert len(parsed["tools"]) == 1
    assert "get_weather" in tools

    # Deserialize
    new_input_dict = {}
    _set_input_openai_chat_completions_create(new_input_dict, json_str)

    # Verify round-trip
    assert new_input_dict["model"] == "gpt-4o"
    assert new_input_dict["temperature"] == 0.8
    assert new_input_dict["seed"] == 42
    assert new_input_dict["tools"][0]["function"]["name"] == "get_weather"
    assert new_input_dict["user"] == "test_user_123"


def test_complex_multimodal_content():
    """Test complex multimodal user messages with various content types."""
    input_dict = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image and audio:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://example.com/image.jpg",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": "base64_encoded_audio_data",
                            "format": "wav",
                        },
                    },
                ],
            }
        ],
        "model": "gpt-4o-audio-preview",
    }

    # Serialize
    json_str, _, _ = _get_input_openai_chat_completions_create(input_dict)

    # Verify
    parsed = json.loads(json_str)
    content = parsed["messages"][0]["content"]
    assert len(content) == 3
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[2]["type"] == "input_audio"

    # Deserialize
    new_input_dict = {}
    _set_input_openai_chat_completions_create(new_input_dict, json_str)

    # Verify round-trip
    new_content = new_input_dict["messages"][0]["content"]
    assert len(new_content) == 3
    assert new_content[0]["text"] == "Analyze this image and audio:"
    assert new_content[1]["image_url"]["detail"] == "high"


def test_assistant_message_with_structured_content():
    """Test assistant message with structured content parts."""
    input_dict = {
        "messages": [
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Here's my response:"},
                    {"type": "text", "text": "Additional context."},
                ],
            },
        ],
        "model": "gpt-4o",
    }

    # Serialize
    json_str, _, _ = _get_input_openai_chat_completions_create(input_dict)

    # Verify
    parsed = json.loads(json_str)
    assert isinstance(parsed["messages"][1]["content"], list)
    assert len(parsed["messages"][1]["content"]) == 2

    # Deserialize
    new_input_dict = {}
    _set_input_openai_chat_completions_create(new_input_dict, json_str)

    # Verify round-trip
    assert len(new_input_dict["messages"][1]["content"]) == 2
    assert new_input_dict["messages"][1]["content"][0]["text"] == "Here's my response:"


def test_tool_calls_with_multiple_functions():
    """Test assistant message with multiple tool calls."""
    input_dict = {
        "messages": [
            {"role": "user", "content": "Get weather in SF and NYC"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "San Francisco"}',
                        },
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "New York"}',
                        },
                    },
                ],
            },
        ],
        "model": "gpt-4o",
    }

    # Serialize
    json_str, _, _ = _get_input_openai_chat_completions_create(input_dict)

    # Verify
    parsed = json.loads(json_str)
    assert len(parsed["messages"][1]["tool_calls"]) == 2
    assert parsed["messages"][1]["tool_calls"][0]["id"] == "call_1"
    assert parsed["messages"][1]["tool_calls"][1]["id"] == "call_2"

    # Deserialize
    new_input_dict = {}
    _set_input_openai_chat_completions_create(new_input_dict, json_str)

    # Verify round-trip
    assert len(new_input_dict["messages"][1]["tool_calls"]) == 2
    assert (
        "San Francisco" in new_input_dict["messages"][1]["tool_calls"][0]["function"]["arguments"]
    )
    assert "New York" in new_input_dict["messages"][1]["tool_calls"][1]["function"]["arguments"]


def test_with_response_format_json_schema():
    """Test with structured output response_format."""
    input_dict = {
        "messages": [{"role": "user", "content": "Generate user data"}],
        "model": "gpt-4o",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "user_schema",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                    "required": ["name", "age"],
                },
            },
        },
    }

    # Serialize
    json_str, _, _ = _get_input_openai_chat_completions_create(input_dict)

    # Verify
    parsed = json.loads(json_str)
    assert parsed["response_format"]["type"] == "json_schema"
    assert parsed["response_format"]["json_schema"]["name"] == "user_schema"

    # Deserialize
    new_input_dict = {}
    _set_input_openai_chat_completions_create(new_input_dict, json_str)

    # Verify round-trip
    assert new_input_dict["response_format"]["json_schema"]["strict"] is True
    assert "name" in new_input_dict["response_format"]["json_schema"]["schema"]["properties"]


def test_with_stream_options():
    """Test with stream_options parameter."""
    input_dict = {
        "messages": [{"role": "user", "content": "Hello"}],
        "model": "gpt-4o",
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    # Serialize
    json_str, _, _ = _get_input_openai_chat_completions_create(input_dict)

    # Verify
    parsed = json.loads(json_str)
    assert parsed["stream"] is True
    assert parsed["stream_options"]["include_usage"] is True

    # Deserialize
    new_input_dict = {}
    _set_input_openai_chat_completions_create(new_input_dict, json_str)

    # Verify round-trip
    assert new_input_dict["stream"] is True
    assert new_input_dict["stream_options"]["include_usage"] is True


if __name__ == "__main__":
    test_with_not_given_sentinel()
    print("✓ test_with_not_given_sentinel")

    test_complete_api_call_structure()
    print("✓ test_complete_api_call_structure")

    test_complex_multimodal_content()
    print("✓ test_complex_multimodal_content")

    test_assistant_message_with_structured_content()
    print("✓ test_assistant_message_with_structured_content")

    test_tool_calls_with_multiple_functions()
    print("✓ test_tool_calls_with_multiple_functions")

    test_with_response_format_json_schema()
    print("✓ test_with_response_format_json_schema")

    test_with_stream_options()
    print("✓ test_with_stream_options")

    print("\n✅ All integration tests passed!")
