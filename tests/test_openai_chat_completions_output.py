"""
Test suite for OpenAI chat completions output serialization.

This test suite verifies that we can correctly serialize and deserialize
ChatCompletion response objects using real OpenAI SDK types, including:
- Complete response structure (id, object, created, model)
- Choices with different message types and finish reasons
- Usage statistics with token details
- Optional fields (system_fingerprint, service_tier)
- Tool calls and function calls in responses
- Logprobs and annotations
"""

import json
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice, ChoiceLogprobs
from openai.types.chat.chat_completion_message import ChatCompletionMessage, FunctionCall
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)
from openai.types.chat.chat_completion_token_logprob import ChatCompletionTokenLogprob, TopLogprob
from openai.types.completion_usage import (
    CompletionUsage,
    CompletionTokensDetails,
    PromptTokensDetails,
)

from aco.runner.monkey_patching.api_parsers.openai_api_parser import (
    _get_output_openai_chat_completions_create,
    _set_output_openai_chat_completions_create,
)


def test_simple_text_response():
    """Test simple text response serialization."""
    # Create response using real OpenAI types
    message = ChatCompletionMessage(
        role="assistant",
        content="Hello! How can I help you today?",
    )

    choice = Choice(
        index=0,
        message=message,
        finish_reason="stop",
    )

    usage = CompletionUsage(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
    )

    response = ChatCompletion(
        id="chatcmpl-123",
        object="chat.completion",
        created=1677652288,
        model="gpt-4o",
        choices=[choice],
        usage=usage,
    )

    # Serialize
    json_str = _get_output_openai_chat_completions_create(response)

    # Verify it's valid JSON
    parsed = json.loads(json_str)
    assert parsed["id"] == "chatcmpl-123"
    assert parsed["object"] == "chat.completion"
    assert parsed["created"] == 1677652288
    assert parsed["model"] == "gpt-4o"
    assert len(parsed["choices"]) == 1
    assert parsed["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
    assert parsed["choices"][0]["finish_reason"] == "stop"
    assert parsed["usage"]["total_tokens"] == 30

    # Deserialize
    new_response = ChatCompletion(
        id="",
        object="chat.completion",
        created=0,
        model="",
        choices=[
            Choice(index=0, message=ChatCompletionMessage(role="assistant"), finish_reason="stop")
        ],
    )
    _set_output_openai_chat_completions_create(new_response, json_str)

    # Verify round-trip
    assert new_response.id == "chatcmpl-123"
    assert new_response.choices[0].message.content == "Hello! How can I help you today?"
    assert new_response.usage.total_tokens == 30


def test_response_with_tool_calls():
    """Test response with tool calls using real OpenAI types."""
    # Create tool call
    function = Function(
        name="get_weather",
        arguments='{"location": "San Francisco"}',
    )

    tool_call = ChatCompletionMessageToolCall(
        id="call_abc123",
        type="function",
        function=function,
    )

    message = ChatCompletionMessage(
        role="assistant",
        content=None,
        tool_calls=[tool_call],
    )

    choice = Choice(
        index=0,
        message=message,
        finish_reason="tool_calls",
    )

    response = ChatCompletion(
        id="chatcmpl-456",
        object="chat.completion",
        created=1677652300,
        model="gpt-4o",
        choices=[choice],
    )

    # Serialize
    json_str = _get_output_openai_chat_completions_create(response)

    # Verify
    parsed = json.loads(json_str)
    assert parsed["choices"][0]["message"]["content"] is None
    assert parsed["choices"][0]["finish_reason"] == "tool_calls"
    assert len(parsed["choices"][0]["message"]["tool_calls"]) == 1
    assert parsed["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_weather"

    # Deserialize
    new_response = ChatCompletion(
        id="",
        object="chat.completion",
        created=0,
        model="",
        choices=[
            Choice(index=0, message=ChatCompletionMessage(role="assistant"), finish_reason="stop")
        ],
    )
    _set_output_openai_chat_completions_create(new_response, json_str)

    # Verify round-trip
    assert new_response.choices[0].finish_reason == "tool_calls"
    assert new_response.choices[0].message.tool_calls[0].function.name == "get_weather"


def test_response_with_refusal():
    """Test response with refusal."""
    message = ChatCompletionMessage(
        role="assistant",
        content=None,
        refusal="I cannot assist with that request.",
    )

    choice = Choice(
        index=0,
        message=message,
        finish_reason="stop",
    )

    response = ChatCompletion(
        id="chatcmpl-789",
        object="chat.completion",
        created=1677652350,
        model="gpt-4o",
        choices=[choice],
        system_fingerprint="fp_123",
        service_tier="default",
    )

    # Serialize
    json_str = _get_output_openai_chat_completions_create(response)

    # Verify
    parsed = json.loads(json_str)
    assert parsed["choices"][0]["message"]["refusal"] == "I cannot assist with that request."
    assert parsed["system_fingerprint"] == "fp_123"
    assert parsed["service_tier"] == "default"

    # Deserialize
    new_response = ChatCompletion(
        id="",
        object="chat.completion",
        created=0,
        model="",
        choices=[
            Choice(index=0, message=ChatCompletionMessage(role="assistant"), finish_reason="stop")
        ],
    )
    _set_output_openai_chat_completions_create(new_response, json_str)

    # Verify round-trip
    assert new_response.choices[0].message.refusal == "I cannot assist with that request."
    assert new_response.system_fingerprint == "fp_123"


def test_response_with_usage_details():
    """Test response with detailed usage statistics."""
    prompt_details = PromptTokensDetails(
        cached_tokens=50,
        audio_tokens=10,
    )

    completion_details = CompletionTokensDetails(
        reasoning_tokens=100,
        audio_tokens=20,
        accepted_prediction_tokens=5,
        rejected_prediction_tokens=2,
    )

    usage = CompletionUsage(
        prompt_tokens=200,
        completion_tokens=150,
        total_tokens=350,
        prompt_tokens_details=prompt_details,
        completion_tokens_details=completion_details,
    )

    message = ChatCompletionMessage(
        role="assistant",
        content="Complex response with reasoning.",
    )

    choice = Choice(
        index=0,
        message=message,
        finish_reason="stop",
    )

    response = ChatCompletion(
        id="chatcmpl-reasoning",
        object="chat.completion",
        created=1677652400,
        model="o1-preview",
        choices=[choice],
        usage=usage,
    )

    # Serialize
    json_str = _get_output_openai_chat_completions_create(response)

    # Verify
    parsed = json.loads(json_str)
    assert parsed["usage"]["total_tokens"] == 350
    assert parsed["usage"]["prompt_tokens_details"]["cached_tokens"] == 50
    assert parsed["usage"]["completion_tokens_details"]["reasoning_tokens"] == 100

    # Deserialize
    new_response = ChatCompletion(
        id="",
        object="chat.completion",
        created=0,
        model="",
        choices=[
            Choice(index=0, message=ChatCompletionMessage(role="assistant"), finish_reason="stop")
        ],
    )
    _set_output_openai_chat_completions_create(new_response, json_str)

    # Verify round-trip
    assert new_response.usage.total_tokens == 350
    assert new_response.usage.prompt_tokens_details.cached_tokens == 50


def test_multiple_choices():
    """Test response with multiple choices (n > 1)."""
    choices = [
        Choice(
            index=0,
            message=ChatCompletionMessage(role="assistant", content="First alternative response."),
            finish_reason="stop",
        ),
        Choice(
            index=1,
            message=ChatCompletionMessage(role="assistant", content="Second alternative response."),
            finish_reason="stop",
        ),
        Choice(
            index=2,
            message=ChatCompletionMessage(role="assistant", content="Third alternative response."),
            finish_reason="stop",
        ),
    ]

    response = ChatCompletion(
        id="chatcmpl-multi",
        object="chat.completion",
        created=1677652500,
        model="gpt-4o",
        choices=choices,
    )

    # Serialize
    json_str = _get_output_openai_chat_completions_create(response)

    # Verify
    parsed = json.loads(json_str)
    assert len(parsed["choices"]) == 3
    assert parsed["choices"][0]["message"]["content"] == "First alternative response."
    assert parsed["choices"][1]["index"] == 1
    assert parsed["choices"][2]["message"]["content"] == "Third alternative response."

    # Deserialize
    new_response = ChatCompletion(
        id="",
        object="chat.completion",
        created=0,
        model="",
        choices=choices,  # Use same choices for initialization
    )
    _set_output_openai_chat_completions_create(new_response, json_str)

    # Verify round-trip
    assert len(new_response.choices) == 3
    assert new_response.choices[1].message.content == "Second alternative response."


def test_response_with_function_call():
    """Test deprecated function_call field."""
    function_call = FunctionCall(
        name="calculator",
        arguments='{"expression": "2+2"}',
    )

    message = ChatCompletionMessage(
        role="assistant",
        content=None,
        function_call=function_call,
    )

    choice = Choice(
        index=0,
        message=message,
        finish_reason="function_call",
    )

    response = ChatCompletion(
        id="chatcmpl-func",
        object="chat.completion",
        created=1677652600,
        model="gpt-3.5-turbo",
        choices=[choice],
    )

    # Serialize
    json_str = _get_output_openai_chat_completions_create(response)

    # Verify
    parsed = json.loads(json_str)
    assert parsed["choices"][0]["finish_reason"] == "function_call"
    assert parsed["choices"][0]["message"]["function_call"]["name"] == "calculator"

    # Deserialize
    new_response = ChatCompletion(
        id="",
        object="chat.completion",
        created=0,
        model="",
        choices=[
            Choice(index=0, message=ChatCompletionMessage(role="assistant"), finish_reason="stop")
        ],
    )
    _set_output_openai_chat_completions_create(new_response, json_str)

    # Verify round-trip
    assert new_response.choices[0].message.function_call.name == "calculator"


def test_response_with_logprobs():
    """Test response with logprobs information."""
    # Create top logprobs
    top_logprobs = [
        TopLogprob(
            token="Hello",
            logprob=-0.5,
            bytes=[72, 101, 108, 108, 111],
        ),
        TopLogprob(
            token="Hi",
            logprob=-2.3,
            bytes=[72, 105],
        ),
    ]

    # Create token logprobs
    token_logprobs = [
        ChatCompletionTokenLogprob(
            token="Hello",
            logprob=-0.5,
            bytes=[72, 101, 108, 108, 111],
            top_logprobs=top_logprobs,
        ),
        ChatCompletionTokenLogprob(
            token="!",
            logprob=-0.1,
            bytes=[33],
            top_logprobs=[
                TopLogprob(token="!", logprob=-0.1, bytes=[33]),
                TopLogprob(token=".", logprob=-3.2, bytes=[46]),
            ],
        ),
    ]

    # Create choice logprobs
    logprobs = ChoiceLogprobs(
        content=token_logprobs,
        refusal=None,
    )

    message = ChatCompletionMessage(
        role="assistant",
        content="Hello!",
    )

    choice = Choice(
        index=0,
        message=message,
        finish_reason="stop",
        logprobs=logprobs,
    )

    response = ChatCompletion(
        id="chatcmpl-logprobs",
        object="chat.completion",
        created=1677652700,
        model="gpt-4o",
        choices=[choice],
    )

    # Serialize
    json_str = _get_output_openai_chat_completions_create(response)

    # Verify
    parsed = json.loads(json_str)
    assert "logprobs" in parsed["choices"][0]
    assert parsed["choices"][0]["logprobs"]["content"] is not None
    assert len(parsed["choices"][0]["logprobs"]["content"]) == 2
    assert parsed["choices"][0]["logprobs"]["content"][0]["token"] == "Hello"
    assert parsed["choices"][0]["logprobs"]["content"][0]["logprob"] == -0.5
    assert parsed["choices"][0]["logprobs"]["content"][0]["bytes"] == [72, 101, 108, 108, 111]
    assert len(parsed["choices"][0]["logprobs"]["content"][0]["top_logprobs"]) == 2
    assert parsed["choices"][0]["logprobs"]["content"][0]["top_logprobs"][0]["token"] == "Hello"

    # Deserialize
    new_response = ChatCompletion(
        id="",
        object="chat.completion",
        created=0,
        model="",
        choices=[
            Choice(index=0, message=ChatCompletionMessage(role="assistant"), finish_reason="stop")
        ],
    )
    _set_output_openai_chat_completions_create(new_response, json_str)

    # Verify round-trip - logprobs should be reconstructed as proper ChoiceLogprobs object
    assert new_response.choices[0].logprobs is not None
    assert isinstance(new_response.choices[0].logprobs, ChoiceLogprobs)
    assert len(new_response.choices[0].logprobs.content) == 2
    assert new_response.choices[0].logprobs.content[0].token == "Hello"
    assert new_response.choices[0].logprobs.content[0].logprob == -0.5
    assert len(new_response.choices[0].logprobs.content[0].top_logprobs) == 2


def test_empty_response():
    """Test edge case with empty/minimal response."""
    message = ChatCompletionMessage(
        role="assistant",
        content="",
    )

    choice = Choice(
        index=0,
        message=message,
        finish_reason="length",
    )

    response = ChatCompletion(
        id="",
        object="chat.completion",
        created=0,
        model="",
        choices=[choice],
    )

    # Serialize
    json_str = _get_output_openai_chat_completions_create(response)

    # Verify
    parsed = json.loads(json_str)
    assert parsed["id"] == ""
    assert parsed["choices"][0]["message"]["content"] == ""
    assert parsed["choices"][0]["finish_reason"] == "length"

    # Deserialize
    new_response = ChatCompletion(
        id="temp",
        object="chat.completion",
        created=1,
        model="temp",
        choices=[
            Choice(index=0, message=ChatCompletionMessage(role="assistant"), finish_reason="stop")
        ],
    )
    _set_output_openai_chat_completions_create(new_response, json_str)

    # Verify round-trip
    assert new_response.choices[0].message.content == ""


if __name__ == "__main__":
    test_simple_text_response()
    print("✓ test_simple_text_response")

    test_response_with_tool_calls()
    print("✓ test_response_with_tool_calls")

    test_response_with_refusal()
    print("��� test_response_with_refusal")

    test_response_with_usage_details()
    print("✓ test_response_with_usage_details")

    test_multiple_choices()
    print("✓ test_multiple_choices")

    test_response_with_function_call()
    print("✓ test_response_with_function_call")

    test_response_with_logprobs()
    print("✓ test_response_with_logprobs")

    test_empty_response()
    print("✓ test_empty_response")

    print("\n✅ All output serialization tests passed!")
