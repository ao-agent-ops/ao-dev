from openai import AsyncOpenAI
import asyncio


async def main():
    client = AsyncOpenAI()

    response = await client.responses.create(
        model="gpt-5-nano", input=f"Output the number 42 and nothing else"
    )

    response = response.output_text

    prompt_add_1 = f"Add 1 to {response} and just output the result."
    prompt_add_2 = f"Add 2 to {response} and just output the result."

    response1 = await client.responses.create(
        model="gpt-3.5-turbo", input=prompt_add_1, temperature=0
    )

    response2 = await client.responses.create(
        model="gpt-3.5-turbo", input=prompt_add_2, temperature=0
    )

    sum_prompt = f"Add these two numbers together and just output the result: {response1.output_text} + {response2.output_text}"

    final_sum = await client.responses.create(
        model="gpt-3.5-turbo", input=sum_prompt, temperature=0
    )
    print(final_sum)


if __name__ == "__main__":
    asyncio.run(main())
