import os
from google import genai
from google.genai.types import HttpOptions


def main():
    model = "gemini-2.5-flash"

    if "GOOGLE_API_KEY" in os.environ:
        del os.environ["GOOGLE_API_KEY"]

    # Create a Vertex AI client using default credentials
    client = genai.Client(http_options=HttpOptions(api_version="v1"))

    # First LLM: Generate a yes/no question
    question_response = client.models.generate_content(
        model=model,
        contents="Come up with a simple question where there is a pro and contra opinion. Only output the question and nothing else.",
    )
    question = question_response.text

    # Second LLM: Argue "yes"
    yes_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'yes'"
    yes_response = client.models.generate_content(
        model=model,
        contents=yes_prompt,
    )

    # Third LLM: Argue "no"
    no_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'no'"
    no_response = client.models.generate_content(
        model=model,
        contents=no_prompt,
    )

    # Fourth LLM: Judge who won
    judge_prompt = f"Consider the following two paragraphs:\n1. {yes_response.text}\n2. {no_response.text}\nWho won the argument?"
    judge_response = client.models.generate_content(
        model=model,
        contents=judge_prompt,
    )

    print(f"Question: {question}")
    print(f"\nJudge's verdict: {judge_response.text}")


if __name__ == "__main__":
    main()
