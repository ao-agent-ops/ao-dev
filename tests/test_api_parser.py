"""
Tests for api_parser.py _get_input_openai_chat_completions_create function.

This module tests the content extraction logic for all 6 ChatCompletionMessageParam types
and their various content formats to ensure proper string conversion.
"""

from runner.monkey_patching.api_parser import _get_input_openai_chat_completions_create


class TestGetInputOpenAIChatCompletionsCreate:
    """Test cases for _get_input_openai_chat_completions_create function."""

    def test_developer_message_with_string_content(self):
        """Test ChatCompletionDeveloperMessageParam with string content."""
        input_dict = {"messages": [{"role": "developer", "content": "This is a developer message"}]}
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "This is a developer message"
        assert attachments == []

    def test_developer_message_with_text_parts(self):
        """Test ChatCompletionDeveloperMessageParam with text parts content."""
        input_dict = {
            "messages": [
                {
                    "role": "developer",
                    "content": [
                        {"type": "text", "text": "First part"},
                        {"type": "text", "text": "Second part"},
                    ],
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "First part Second part"
        assert attachments == []

    def test_system_message_with_string_content(self):
        """Test ChatCompletionSystemMessageParam with string content."""
        input_dict = {"messages": [{"role": "system", "content": "You are a helpful assistant"}]}
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "You are a helpful assistant"
        assert attachments == []

    def test_system_message_with_text_parts(self):
        """Test ChatCompletionSystemMessageParam with text parts content."""
        input_dict = {
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": "System instruction 1"},
                        {"type": "text", "text": "System instruction 2"},
                    ],
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "System instruction 1 System instruction 2"
        assert attachments == []

    def test_user_message_with_string_content(self):
        """Test ChatCompletionUserMessageParam with string content."""
        input_dict = {"messages": [{"role": "user", "content": "Hello, how are you?"}]}
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "Hello, how are you?"
        assert attachments == []

    def test_user_message_with_mixed_content(self):
        """Test ChatCompletionUserMessageParam with mixed content types."""
        input_dict = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Look at this image:"},
                        {"type": "image", "image_url": {"url": "http://example.com/image.png"}},
                        {"type": "text", "text": "What do you see?"},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": "base64data", "format": "mp3"},
                        },
                        {
                            "type": "file",
                            "file": {"filename": "document.pdf", "file_id": "file123"},
                        },
                    ],
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert (
            content == "Look at this image: [Image] What do you see? [Audio] [File: document.pdf]"
        )
        assert attachments == []

    def test_user_message_with_file_no_filename(self):
        """Test ChatCompletionUserMessageParam with file content but no filename."""
        input_dict = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Check this file:"},
                        {"type": "file", "file": {"file_id": "file123"}},
                    ],
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "Check this file: [File: file]"
        assert attachments == []

    def test_assistant_message_with_string_content(self):
        """Test ChatCompletionAssistantMessageParam with string content."""
        input_dict = {"messages": [{"role": "assistant", "content": "I'm doing well, thank you!"}]}
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "I'm doing well, thank you!"
        assert attachments == []

    def test_assistant_message_with_none_content_and_function_call(self):
        """Test ChatCompletionAssistantMessageParam with None content but function_call."""
        input_dict = {
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": "get_weather",
                        "arguments": '{"location": "New York"}',
                    },
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == 'Function call: get_weather with args: {"location": "New York"}'
        assert attachments == []

    def test_assistant_message_with_none_content_and_tool_calls(self):
        """Test ChatCompletionAssistantMessageParam with None content but tool_calls."""
        input_dict = {
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"function": {"name": "get_weather"}},
                        {"function": {"name": "send_email"}},
                    ],
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "Tool calls: get_weather, send_email"
        assert attachments == []

    def test_assistant_message_with_text_and_refusal_parts(self):
        """Test ChatCompletionAssistantMessageParam with text and refusal content parts."""
        input_dict = {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "I can help with that, but"},
                        {
                            "type": "refusal",
                            "refusal": "I cannot provide information about harmful activities",
                        },
                    ],
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert (
            content
            == "I can help with that, but I cannot provide information about harmful activities"
        )
        assert attachments == []

    def test_tool_message_with_string_content(self):
        """Test ChatCompletionToolMessageParam with string content."""
        input_dict = {
            "messages": [
                {
                    "role": "tool",
                    "content": "Weather in New York: 72°F, sunny",
                    "tool_call_id": "call_123",
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "Weather in New York: 72°F, sunny"
        assert attachments == []

    def test_tool_message_with_text_parts(self):
        """Test ChatCompletionToolMessageParam with text parts content."""
        input_dict = {
            "messages": [
                {
                    "role": "tool",
                    "content": [
                        {"type": "text", "text": "Result part 1"},
                        {"type": "text", "text": "Result part 2"},
                    ],
                    "tool_call_id": "call_123",
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "Result part 1 Result part 2"
        assert attachments == []

    def test_function_message_with_string_content(self):
        """Test ChatCompletionFunctionMessageParam with string content."""
        input_dict = {
            "messages": [
                {
                    "role": "function",
                    "name": "get_weather",
                    "content": "Weather data retrieved successfully",
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "Weather data retrieved successfully"
        assert attachments == []

    def test_function_message_with_none_content(self):
        """Test ChatCompletionFunctionMessageParam with None content."""
        input_dict = {"messages": [{"role": "function", "name": "get_weather", "content": None}]}
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == ""
        assert attachments == []

    def test_unknown_role_message(self):
        """Test message with unknown role falls back to string conversion."""
        input_dict = {"messages": [{"role": "unknown_role", "content": "Some content"}]}
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "Some content"
        assert attachments == []

    def test_empty_messages_list(self):
        """Test with empty messages list."""
        input_dict = {"messages": []}
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == ""
        assert attachments == []

    def test_no_messages_key(self):
        """Test with missing messages key."""
        input_dict = {}
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == ""
        assert attachments == []

    def test_multiple_messages_uses_last(self):
        """Test that function uses the last message when multiple are present."""
        input_dict = {
            "messages": [
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "Assistant response"},
                {"role": "user", "content": "Last message"},
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "Last message"
        assert attachments == []

    def test_user_message_with_only_non_text_content(self):
        """Test user message with only non-text content types."""
        input_dict = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image_url": {"url": "http://example.com/image.png"}},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": "base64data", "format": "mp3"},
                        },
                    ],
                }
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == "[Image] [Audio]"
        assert attachments == []

    def test_content_with_non_dict_items_in_iterable(self):
        """Test content with non-dict items in iterable skips non-dict items."""
        input_dict = {
            "messages": [
                {"role": "user", "content": ["not a dict", {"type": "text", "text": "valid text"}]}
            ]
        }
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        # Non-dict items should be ignored, only valid dict items processed
        assert content == "valid text"
        assert attachments == []

    def test_assistant_message_with_empty_tool_calls(self):
        """Test ChatCompletionAssistantMessageParam with empty tool_calls list."""
        input_dict = {"messages": [{"role": "assistant", "content": None, "tool_calls": []}]}
        content, attachments = _get_input_openai_chat_completions_create(input_dict)
        assert content == ""
        assert attachments == []


if __name__ == "__main__":
    test_obj = TestGetInputOpenAIChatCompletionsCreate()
    test_obj.test_assistant_message_with_none_content_and_function_call()
