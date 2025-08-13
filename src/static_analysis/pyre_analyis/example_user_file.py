# Example user file for testing LLM data flow detection
# This file demonstrates various patterns that should be detected

import openai
import anthropic

# Initialize clients
openai_client = openai.OpenAI(api_key="test")
anthropic_client = anthropic.Anthropic(api_key="test")


def func1():
    """Simple OpenAI call"""
    response = openai_client.chat.completions.create(
        model="gpt-4", messages=[{"role": "user", "content": "Hello"}]
    )
    return response


def func2(data):
    """Anthropic call that takes input"""
    result = anthropic_client.messages.create(
        model="claude-3", messages=[{"role": "user", "content": data}]
    )
    return result


def vulnerable():
    """Data flow: OpenAI -> Anthropic (should be detected)"""
    openai_response = func1()
    anthropic_result = func2(openai_response)
    return anthropic_result


def independent_openai():
    """Independent OpenAI call (not part of flow)"""
    return openai_client.chat.completions.create(
        model="gpt-4", messages=[{"role": "user", "content": "Independent call"}]
    )


# Dictionary assignment pattern (Pyre should handle this)
x = openai_client.chat.completions.create(
    model="gpt-4", messages=[{"role": "user", "content": "hello"}]
)
y = {}
y["key"] = x
final_result = anthropic_client.messages.create(
    model="claude-3", messages=[{"role": "user", "content": y}]
)


# Class-based pattern
class LLMProcessor:
    def __init__(self):
        self.openai = openai.OpenAI()
        self.anthropic = anthropic.Anthropic()

    def process_with_flow(self, user_input):
        """Method with LLM data flow"""
        # Step 1: Get response from OpenAI
        openai_response = self.openai.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": user_input}]
        )

        # Step 2: Pass to Anthropic (creates flow)
        final_response = self.anthropic.messages.create(
            model="claude-3",
            messages=[{"role": "user", "content": openai_response.choices[0].message.content}],
        )

        return final_response

    def process_independently(self, user_input):
        """Independent processing (no flow between calls)"""
        openai_result = self.openai.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": user_input}]
        )

        anthropic_result = self.anthropic.messages.create(
            model="claude-3", messages=[{"role": "user", "content": "Different input"}]
        )

        return [openai_result, anthropic_result]


# Expected flows to detect:
# 1. func1() -> func2() via vulnerable()
# 2. x -> y["key"] -> final_result (dictionary flow)
# 3. LLMProcessor.process_with_flow(): openai_response -> final_response
#
# Should NOT detect:
# - independent_openai() (standalone)
# - LLMProcessor.process_independently() (no flow between calls)
