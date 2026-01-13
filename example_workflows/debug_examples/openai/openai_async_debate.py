from openai import AsyncOpenAI
import asyncio


async def main():
    client = AsyncOpenAI()

    # First LLM: Generate a yes/no question
    question_response = await client.responses.create(
        model="gpt-4o-mini",
        input="Come up with a simple question where there is a pro and contra opinion. Only output the question and nothing else.",
    )
    question = question_response.output_text

    # Second and Third LLM: Argue "yes" and "no" concurrently
    yes_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'yes'"
    no_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'no'"

    yes_response, no_response = await asyncio.gather(
        client.responses.create(model="gpt-4o-mini", input=yes_prompt, temperature=0),
        client.responses.create(model="gpt-4o-mini", input=no_prompt, temperature=0),
    )

    # Fourth LLM: Judge who won
    judge_prompt = f"Consider the following two paragraphs:\n1. {yes_response.output_text}\n2. {no_response.output_text}\nWho won the argument?"
    judge_response = await client.responses.create(
        model="gpt-4o-mini", input=judge_prompt, temperature=0
    )

    print(f"Question: {question}")
    print(f"\nJudge's verdict: {judge_response.output_text}")


if __name__ == "__main__":
    asyncio.run(main())
