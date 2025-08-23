from openai.types.responses.response import Response
from openai.types.responses import ResponseOutputMessage, ResponseOutputText
import json
from openai import NOT_GIVEN as OPENAI_NOT_GIVEN
from anthropic import NOT_GIVEN as ANTHROPIC_NOT_GIVEN
from anthropic.types import Message, TextBlock, Usage


def create_anthropic_input(text):
    return {
        "max_tokens": 10,
        "messages": [{"role": "user", "content": text}],
        "model": "undefined_model",  # Make sure cache is used.
        "metadata": ANTHROPIC_NOT_GIVEN,
        "service_tier": ANTHROPIC_NOT_GIVEN,
        "stop_sequences": ANTHROPIC_NOT_GIVEN,
        "stream": ANTHROPIC_NOT_GIVEN,
        "system": ANTHROPIC_NOT_GIVEN,
        "temperature": ANTHROPIC_NOT_GIVEN,
        "thinking": ANTHROPIC_NOT_GIVEN,
        "tool_choice": ANTHROPIC_NOT_GIVEN,
        "tools": ANTHROPIC_NOT_GIVEN,
        "top_k": ANTHROPIC_NOT_GIVEN,
        "top_p": ANTHROPIC_NOT_GIVEN,
        "extra_headers": None,
        "extra_query": None,
        "extra_body": None,
        "timeout": ANTHROPIC_NOT_GIVEN,
    }


def create_anthropic_response(text):
    return Message(
        id="msg_01EgYHvwZ3SUdZ8P1a15sAzM",
        content=[TextBlock(citations=None, text=text, type="text")],
        model="undefined_model",  # Make sure cache is used.
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=Usage(
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
            input_tokens=16,
            output_tokens=5,
            server_tool_use=None,
            service_tier="standard",
            cache_creation={"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
        ),
    )


def create_openai_input(text):
    return {
        "background": OPENAI_NOT_GIVEN,
        "include": OPENAI_NOT_GIVEN,
        "input": text,
        "instructions": OPENAI_NOT_GIVEN,
        "max_output_tokens": OPENAI_NOT_GIVEN,
        "max_tool_calls": OPENAI_NOT_GIVEN,
        "metadata": OPENAI_NOT_GIVEN,
        "model": "undefined_model",  # Make sure cache is used.
        "parallel_tool_calls": OPENAI_NOT_GIVEN,
        "previous_response_id": OPENAI_NOT_GIVEN,
        "prompt": OPENAI_NOT_GIVEN,
        "prompt_cache_key": OPENAI_NOT_GIVEN,
        "reasoning": OPENAI_NOT_GIVEN,
        "safety_identifier": OPENAI_NOT_GIVEN,
        "service_tier": OPENAI_NOT_GIVEN,
        "store": OPENAI_NOT_GIVEN,
        "stream": OPENAI_NOT_GIVEN,
        "stream_options": OPENAI_NOT_GIVEN,
        "temperature": 0,
        "text": OPENAI_NOT_GIVEN,
        "tool_choice": OPENAI_NOT_GIVEN,
        "tools": OPENAI_NOT_GIVEN,
        "top_logprobs": OPENAI_NOT_GIVEN,
        "top_p": OPENAI_NOT_GIVEN,
        "truncation": OPENAI_NOT_GIVEN,
        "user": OPENAI_NOT_GIVEN,
        "extra_headers": None,
        "extra_query": None,
        "extra_body": None,
        "timeout": OPENAI_NOT_GIVEN,
    }


def create_openai_response(text):
    # Mock OpenAI Responses API response structure based on the actual format
    return Response(
        id="resp_68a083fbeb68819a99c352f92320ddf30d623fcb04a141a6",
        created_at=1755350012.0,
        error=None,
        incomplete_details=None,
        instructions=None,
        metadata={},
        model="undefined_model",  # Make sure cache is used.
        object="response",
        output=[
            ResponseOutputMessage(
                id="msg_68a083fc7aa4819aa7f1f6a9b91b36cd0d623fcb04a141a6",
                content=[
                    ResponseOutputText(annotations=[], text=text, type="output_text", logprobs=[])
                ],
                role="assistant",
                status="completed",
                type="message",
            )
        ],
        parallel_tool_calls=True,
        temperature=0.0,
        tool_choice="auto",
        tools=[],
        top_p=1.0,
        max_output_tokens=None,
        previous_response_id=None,
        service_tier="default",
        status="completed",
        truncation="disabled",
        user=None,
        background=False,
        max_tool_calls=None,
        prompt_cache_key=None,
        safety_identifier=None,
        store=True,
        top_logprobs=0,
    )


def create_vertexai_input(text):
    return {
        "model": "gemini-2.5-flash",
        "contents": text,
        "extra_headers": None,
        "extra_query": None,
        "extra_body": None,
        "timeout": OPENAI_NOT_GIVEN,  # Using OpenAI's NOT_GIVEN as placeholder
    }


def create_vertexai_response(text):
    return json.dumps(
        {
            "sdk_http_response": "headers={'content-type': 'application/json; charset=UTF-8', 'vary': 'Origin, X-Origin, Referer', 'content-encoding': 'gzip', 'date': 'Sat, 09 Aug 2025 21:48:18 GMT', 'server': 'scaffolding on HTTPServer2', 'x-xss-protection': '0', 'x-frame-options': 'SAMEORIGIN', 'x-content-type-options': 'nosniff', 'server-timing': 'gfet4t7; dur=662', 'alt-svc': 'h3=\":443\"; ma=2592000,h3-29=\":443\"; ma=2592000', 'transfer-encoding': 'chunked'} body=None",
            "candidates": [
                f"content=Content(\n  parts=[\n    Part(\n      text='{text}'\n    ),\n  ],\n  role='model'\n) citation_metadata=None finish_message=None token_count=None finish_reason=<FinishReason.STOP: 'STOP'> url_context_metadata=None avg_logprobs=None grounding_metadata=None index=0 logprobs_result=None safety_ratings=None"
            ],
            "create_time": None,
            "model_version": "gemini-2.5-flash",
            "prompt_feedback": None,
            "response_id": "IsKXaOm3OoWW1MkPoMj8mAk",
            "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=2 candidates_tokens_details=None prompt_token_count=19 prompt_tokens_details=[ModalityTokenCount(\n  modality=<MediaModality.TEXT: 'TEXT'>,\n  token_count=19\n)] thoughts_token_count=77 tool_use_prompt_token_count=None tool_use_prompt_tokens_details=None total_token_count=98 traffic_type=None",
            "automatic_function_calling_history": [],
            "parsed": None,
        }
    )
