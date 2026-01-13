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

    # First LLM: Generate a yes/no question
    question_response = await client.aio.models.generate_content(
        model=model,
        contents="Come up with a simple question where there is a pro and contra opinion. Only output the question and nothing else.",
    )
    question = question_response.text

    # Second and Third LLM: Argue "yes" and "no" concurrently
    yes_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'yes'"
    no_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'no'"

    yes_response, no_response = await asyncio.gather(
        client.aio.models.generate_content(
            model=model,
            contents=yes_prompt,
        ),
        client.aio.models.generate_content(
            model=model,
            contents=no_prompt,
        ),
    )

    # Fourth LLM: Judge who won
    judge_prompt = f"Consider the following two paragraphs:\n1. {yes_response.text}\n2. {no_response.text}\nWho won the argument?"
    judge_response = await client.aio.models.generate_content(
        model=model,
        contents=judge_prompt,
    )

    print(f"Question: {question}")
    print(f"\nJudge's verdict: {judge_response.text}")


if __name__ == "__main__":
    asyncio.run(main())
