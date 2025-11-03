from aco.runner.monkey_patching.api_parser import (
    _get_output_mcp_client_session_call_tool,
    _set_output_mcp_client_session_call_tool,
)


def test_mcp_reversible_serialization():
    """Test that we can serialize and deserialize MCP objects successfully."""
    from mcp.types import (
        CallToolResult,
        TextContent,
        ImageContent,
        ResourceLink,
    )

    # Create a test CallToolResult with mixed content
    original_result = CallToolResult(
        content=[
            TextContent(type="text", text="Hello, world!"),
            ImageContent(type="image", data="base64encodeddata", mimeType="image/png"),
            ResourceLink(
                type="resource_link",
                name="test_resource",
                uri="https://example.com",
                description="Test resource",
                mimeType="text/html",
                size=1024,
            ),
        ]
    )

    # Serialize to JSON string
    json_string = _get_output_mcp_client_session_call_tool(original_result)

    # Create a new CallToolResult to deserialize into
    new_result = CallToolResult(content=[])

    # Deserialize back
    _set_output_mcp_client_session_call_tool(new_result, json_string)

    # Verify the round-trip worked
    assert len(new_result.content) == 3
    assert isinstance(new_result.content[0], TextContent)
    assert new_result.content[0].text == "Hello, world!"
    assert isinstance(new_result.content[1], ImageContent)
    assert new_result.content[1].data == "base64encodeddata"
    assert isinstance(new_result.content[2], ResourceLink)
    assert str(new_result.content[2].uri) == "https://example.com/"
    assert new_result.content[2].description == "Test resource"
    assert new_result.content[2].mimeType == "text/html"
    assert new_result.content[2].size == 1024


def test_mcp_text_content_only():
    """Test serialization with only TextContent."""
    from mcp.types import CallToolResult, TextContent

    original_result = CallToolResult(content=[TextContent(type="text", text="Simple text content")])

    json_string = _get_output_mcp_client_session_call_tool(original_result)
    new_result = CallToolResult(content=[])
    _set_output_mcp_client_session_call_tool(new_result, json_string)

    assert len(new_result.content) == 1
    assert isinstance(new_result.content[0], TextContent)
    assert new_result.content[0].text == "Simple text content"


def test_mcp_empty_content():
    """Test serialization with empty content list."""
    from mcp.types import CallToolResult

    original_result = CallToolResult(content=[])

    json_string = _get_output_mcp_client_session_call_tool(original_result)
    new_result = CallToolResult(content=[])
    _set_output_mcp_client_session_call_tool(new_result, json_string)

    assert len(new_result.content) == 0


if __name__ == "__main__":
    test_mcp_reversible_serialization()
    test_mcp_text_content_only()
    test_mcp_empty_content()
