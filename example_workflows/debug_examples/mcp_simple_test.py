import asyncio
import platform
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters


async def test_filesystem():
    """Simple MCP test using filesystem server."""

    # MCP server parameters for filesystem
    # On macOS, /tmp is a symlink to /private/tmp, so use /private/tmp
    # On Linux, use /tmp directly
    tmp_dir = "/private/tmp" if platform.system() == "Darwin" else "/tmp"
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", tmp_dir],
    )

    # Connect to the MCP server
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # First call: Write to a file
            print("\nFirst call: Writing to test file")
            test_content = "Hello from MCP test! This is a test file with some content written via MCP."
            test_file_path = f"{tmp_dir}/test_mcp.txt"
            result1 = await session.call_tool(
                "write_file",
                arguments={
                    "path": test_file_path,
                    "content": test_content
                }
            )
            print(f"Write result: {result1}")

            # Second call: Read the file back
            print("\nSecond call: Reading test file")
            result2 = await session.call_tool(
                "read_file",
                arguments={"path": test_file_path}
            )

            # Extract the result
            if result2.content:
                value2 = result2.content[0].text
                print(f"Result 2: {value2[:100]}...")  # Print first 100 chars
            else:
                value2 = "No content"
                print("Error: No content from second call")

            # Third call: Use the result from second call
            print("\nThird call: Processing the result")
            # In a real scenario, you might pass this to another tool
            # For now, just show we can access the tainted data
            word_count = len(value2.split())
            print(f"Word count from read result: {word_count}")


async def main():
    """Main function."""
    await test_filesystem()


if __name__ == "__main__":
    asyncio.run(main())
