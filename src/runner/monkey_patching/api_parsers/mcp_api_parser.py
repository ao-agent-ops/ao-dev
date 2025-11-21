from typing import Any, Dict


def _get_input_mcp_client_session_call_tool(input_dict: dict):
    # Structure of this dict is always:
    #   name: str,
    #   arguments: dict[str, Any] | None = None,
    #   read_timeout_seconds: timedelta | None = None,
    #   progress_callback: ProgressFnT | None = None,
    # see <env-path>/lib/python3.13/site-packages/mcp/client/session.py
    # We are only interested in name (this classifies as tool) and the arguments.
    # The arguments can contain attachments.
    arguments = input_dict["arguments"]
    tools = [input_dict["name"]]
    attachments = []
    return str(arguments), attachments, tools


def _get_model_mcp_client_session_call_tool(
    input_dict: Dict[str, Any],
) -> str:
    """Extract model name from MCP client session call_tool."""
    return input_dict.get("name", "unknown")


def _get_output_mcp_client_session_call_tool(response_obj: Any) -> str:
    """Extract output in MCP call tool and serialize to JSON for reversibility"""
    import json
    from mcp.types import (
        ContentBlock,
        CallToolResult,
        TextContent,
        ImageContent,
        AudioContent,
        ResourceLink,
        EmbeddedResource,
    )

    response_obj: CallToolResult
    content_list = []

    content: ContentBlock
    for content in response_obj.content:
        if isinstance(content, TextContent):
            content_list.append({"type": "TextContent", "data": {"text": content.text}})
        elif isinstance(content, ImageContent):
            content_list.append(
                {
                    "type": "ImageContent",
                    "data": {"data": content.data, "mimeType": content.mimeType},
                }
            )
        elif isinstance(content, AudioContent):
            content_list.append(
                {
                    "type": "AudioContent",
                    "data": {"data": content.data, "mimeType": content.mimeType},
                }
            )
        elif isinstance(content, ResourceLink):
            content_list.append(
                {
                    "type": "ResourceLink",
                    "data": {
                        "name": content.name,
                        "uri": str(content.uri),
                        "description": content.description,
                        "mimeType": content.mimeType,
                        "size": content.size,
                    },
                }
            )
        elif isinstance(content, EmbeddedResource):
            resource_data = {}
            if hasattr(content.resource, "text"):
                resource_data = {"type": "TextResourceContents", "text": content.resource.text}
            elif hasattr(content.resource, "blob"):
                resource_data = {"type": "BlobResourceContents", "blob": content.resource.blob}

            content_list.append(
                {
                    "type": "EmbeddedResource",
                    "data": {"type": content.type, "resource": resource_data},
                }
            )
        else:
            content_list.append({"type": "Unknown", "data": {"type_name": str(type(content))}})

    return json.dumps({"content": content_list}, indent=4)


def _set_input_mcp_client_session_call_tool(
    input_dict: Dict[str, Any], new_input_text: str
) -> None:
    """Set new input text in MCP input."""
    import ast

    input_dict["arguments"] = ast.literal_eval(new_input_text)


def _set_output_mcp_client_session_call_tool(original_output_obj: Any, output_text: str) -> None:
    """Set new output text in MCP response by deserializing JSON back to MCP objects."""
    import json
    from mcp.types import (
        TextContent,
        ImageContent,
        AudioContent,
        ResourceLink,
        EmbeddedResource,
        TextResourceContents,
        BlobResourceContents,
    )

    try:
        data = json.loads(output_text)
        new_content = []

        for item in data.get("content", []):
            content_type = item.get("type")
            content_data = item.get("data", {})

            if content_type == "TextContent":
                new_content.append(TextContent(type="text", text=content_data["text"]))
            elif content_type == "ImageContent":
                new_content.append(
                    ImageContent(
                        type="image",
                        data=content_data["data"],
                        mimeType=content_data.get("mimeType", "image/png"),
                    )
                )
            elif content_type == "AudioContent":
                new_content.append(
                    AudioContent(
                        type="audio",
                        data=content_data["data"],
                        mimeType=content_data.get("mimeType", "audio/wav"),
                    )
                )
            elif content_type == "ResourceLink":
                new_content.append(
                    ResourceLink(
                        type="resource_link",
                        name=content_data.get("name", "resource"),
                        uri=content_data["uri"],
                        description=content_data.get("description"),
                        mimeType=content_data.get("mimeType"),
                        size=content_data["size"],
                    )
                )
            elif content_type == "EmbeddedResource":
                resource_data = content_data.get("resource", {})
                resource_type = resource_data.get("type")

                if resource_type == "TextResourceContents":
                    resource = TextResourceContents(text=resource_data["text"])
                elif resource_type == "BlobResourceContents":
                    resource = BlobResourceContents(blob=resource_data["blob"])
                else:
                    continue

                new_content.append(EmbeddedResource(type=content_data["type"], resource=resource))

        original_output_obj.content = new_content

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"Failed to deserialize MCP output: {e}")
