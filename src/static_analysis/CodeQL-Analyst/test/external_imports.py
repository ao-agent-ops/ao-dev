import openai
import anthropic


# Initialize clients
openai_client = openai.OpenAI(api_key="test-key")
anthropic_client = anthropic.Anthropic(api_key="test-key")


class A:

    def __init__(self):

        self.client = openai.OpenAI(api_key="test-key")

    def run(self, x):

        return self.client.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": x}]
        )
