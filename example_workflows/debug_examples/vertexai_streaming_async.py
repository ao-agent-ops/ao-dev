import asyncio
from google import genai
from google.genai.types import HttpOptions

model = "gemini-2.5-flash"


async def main():
    # Create a Vertex AI client using default credentials
    client = genai.Client(http_options=HttpOptions(api_version="v1"))

    # First call: Get a number using streaming
    print("Getting initial number...")
    stream = await client.aio.models.generate_content_stream(
        model=model,
        contents="Output the number 42 and nothing else",
    )

    initial_response = ""
    async for chunk in stream:
        if chunk.text:
            print(f"Chunk: {chunk.text}")
            initial_response += chunk.text

    print(f"Initial number: {initial_response}")

    # Second call: Add to the number using streaming
    prompt = f"Add 10 to {initial_response} and just output the result."
    print(f"\nPrompt: {prompt}")

    stream2 = await client.aio.models.generate_content_stream(
        model=model,
        contents=prompt,
    )

    final_response = ""
    async for chunk in stream2:
        if chunk.text:
            print(f"Chunk: {chunk.text}")
            final_response += chunk.text

    print(f"\nFinal result: {final_response}")


if __name__ == "__main__":
    asyncio.run(main())
