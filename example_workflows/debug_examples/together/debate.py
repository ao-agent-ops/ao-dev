from together import Together


def main():
    client = Together()
    model = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"

    # First LLM: Generate a yes/no question
    question_response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Come up with a simple question where there is a pro and contra opinion. Only output the question and nothing else.",
            }
        ],
        temperature=0,
    )
    question = question_response.choices[0].message.content

    # Second LLM: Argue "yes"
    yes_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'yes'"
    yes_response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": yes_prompt}],
        temperature=0,
    )

    # Third LLM: Argue "no"
    no_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'no'"
    no_response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": no_prompt}],
        temperature=0,
    )

    # Fourth LLM: Judge who won
    yes_text = yes_response.choices[0].message.content
    no_text = no_response.choices[0].message.content
    judge_prompt = f"Consider the following two paragraphs:\n1. {yes_text}\n2. {no_text}\nWho won the argument?"
    judge_response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": judge_prompt}],
        temperature=0,
    )

    print(f"Question: {question}")
    print(f"\nJudge's verdict: {judge_response.choices[0].message.content}")


if __name__ == "__main__":
    main()
