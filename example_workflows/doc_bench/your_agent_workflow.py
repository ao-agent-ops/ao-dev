import os

from openai import OpenAI

client = OpenAI()


def call_openai_doc(pdf_path, prompt):
    with open(pdf_path, "rb") as f:
        assert os.path.isfile(pdf_path), f"File not found: {pdf_path}"
        file_response = client.files.create(
            file=(os.path.basename(pdf_path), f, "application/pdf"), purpose="assistants"
        )
        file_content = file_response.id

        assistant = client.beta.assistants.create(
            name="Document Assistant",
            instructions="You are a helpful assistant that helps users answer questions based on the given document.",
            model="gpt-4o",
            tools=[{"type": "file_search"}],
        )
        # Create a thread and attach the file to the message
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    # Attach the new file to the message.
                    "attachments": [{"file_id": file_content, "tools": [{"type": "file_search"}]}],
                }
            ]
        )
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id, assistant_id=assistant.id
        )
        messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))
        message_content = messages[0].content[0].text
        annotations = message_content.annotations
        for index, annotation in enumerate(annotations):
            message_content.value = message_content.value.replace(annotation.text, "")
        return message_content.value


def call_openai_msg(prompt):
    output = client.responses.create(model="gpt-4o", input=prompt)
    return output.output[-1].content[-1].text


def your_agent_workflow(pdf_path, q_string, sample_folder):
    prompt = f"""Given the large prompt below, rewrite it into several smaller prompts that each contains one quesiton. The new, smaller prompts should state the task in the beginning and then the question. They should be concise and contain all necessary information. Separate different prompts in your output with `PROMPT:`. So for example.

PROMPT:    
State the task and then the question.
PROMPT:
State the task and then the question.

Original, large prompt that should be broken down:

{q_string}
"""

    output = call_openai_msg(prompt)

    prompts = output.split("PROMPT:")[1:]
    print("prompts", prompts)
    outputs = []
    for prompt in prompts:
        print("-" * 10)
        print(prompt)
        print("-" * 10)
        out = call_openai_doc(pdf_path, prompt)
        outputs.append(out)

    combine_prompt = f"""{q_string}

The answers are the following:
"""

    for out in outputs:
        combine_prompt += f"{out}\n"

    combine_prompt += "Your task is to form the final response such that it has the right output format. Just output the final, formatted answer and nothing else."

    print(combine_prompt)

    ouput = call_openai_msg(combine_prompt)

    # return call_open_ai_doc(pdf_path, prompt)
    return output
