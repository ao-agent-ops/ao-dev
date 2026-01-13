import asyncio
import anthropic


async def main():
    client = anthropic.AsyncAnthropic()

    # First LLM: Generate a yes/no question
    question_response = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": "Come up with a simple question where there is a pro and contra opinion. Only output the question and nothing else.",
            }
        ],
    )
    question = question_response.content[0].text

    # Second and Third LLM: Argue "yes" and "no" concurrently
    yes_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'yes'"
    no_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'no'"

    yes_response, no_response = await asyncio.gather(
        client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": yes_prompt}],
        ),
        client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": no_prompt}],
        ),
    )

    # Fourth LLM: Judge who won
    judge_prompt = f"Consider the following two paragraphs:\n1. {yes_response.content[0].text}\n2. {no_response.content[0].text}\nWho won the argument?"
    judge_response = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": judge_prompt}],
    )

    print(f"Question: {question}")
    print(f"\nJudge's verdict: {judge_response.content[0].text}")


if __name__ == "__main__":
    asyncio.run(main())
