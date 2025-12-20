import os
import asyncio
from google import genai
from google.genai.types import HttpOptions

model = "gemini-2.5-flash"

if "GOOGLE_API_KEY" in os.environ:
    del os.environ["GOOGLE_API_KEY"]

async def main():
    # Create an async Vertex AI client using default credentials
    client = genai.Client(http_options=HttpOptions(api_version="v1"))

    response = await client.aio.models.generate_content(
        model=model,
        contents="Output the number 42 and nothing else",
    )

    response = response.text

    prompt_add_1 = f"Add 1 to {response} and just output the result."
    prompt_add_2 = f"Add 2 to {response} and just output the result."

    # Run the two additions concurrently
    response1, response2 = await asyncio.gather(
        client.aio.models.generate_content(
            model=model,
            contents=prompt_add_1,
        ),
        client.aio.models.generate_content(
            model=model,
            contents=prompt_add_2,
        ),
    )

    sum_prompt = f"Add these two numbers together and just output the result: {response1.text} + {response2.text}"

    final_sum = await client.aio.models.generate_content(
        model=model,
        contents=sum_prompt,
    )

    print(f"Final result: {final_sum.text}")


if __name__ == "__main__":
    asyncio.run(main())
