import os
import asyncio
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters


# Configuration
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")


async def google_search(query: str) -> str:
    """Perform a Google search using the Serper API via MCP server."""

    if SERPER_API_KEY == "":
        return "[ERROR]: SERPER_API_KEY is not set, google_search tool is not available."

    # MCP server parameters for the Serper search server
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "serper-search-scrape-mcp-server"],
        env={"SERPER_API_KEY": SERPER_API_KEY},
    )

    # Search arguments
    arguments = {
        "q": query,
        "gl": "us",  # Country context
        "hl": "en",  # Language
        "num": 10,  # Number of results
        "page": 1,  # Page number
        "autocorrect": False,
    }

    # Connect to the MCP server and perform the search
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Call the google_search tool
            tool_result = await session.call_tool("google_search", arguments=arguments)

            # Extract the result content
            if tool_result.content:
                return tool_result.content[-1].text
            else:
                return "[ERROR]: No content returned from search"


async def main():
    """Main function to demonstrate the Google search functionality."""

    # The search prompt
    prompt = "Search the latest news about OpenAI."

    print(f"Searching for: {prompt}")
    print("-" * 50)

    # Perform the search
    result = await google_search(prompt)

    # Log the result
    print("Search Results:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
