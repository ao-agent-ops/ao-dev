import os
from openai import OpenAI


client = OpenAI()
PDF_PATH = "/Users/ferdi/Downloads/ken_udbms_execution.pdf"

response = client.responses.create(
    model="gpt-3.5-turbo",
    input="Output a system prompt for a document processing LLM (e.g., you're a helpful assistant)."
)

with open(PDF_PATH, "rb") as f:
    assert os.path.isfile(PDF_PATH), f"File not found: {PDF_PATH}"
    file_response = client.files.create(
        file=(os.path.basename(PDF_PATH), f, "application/pdf"),
        purpose="assistants"
    )
    file_content = file_response.id

assistant = client.beta.assistants.create(
    name="Document Assistant",
    instructions=response.output_text,
    model="gpt-3.5-turbo",
    tools=[{"type": "file_search"}],
)
# Create a thread and attach the file to the message
thread = client.beta.threads.create(
    messages=[{
        "role": "user", "content": "Summarize the file.",
        # Attach the new file to the message.
        "attachments": [{ "file_id": file_content, "tools": [{"type": "file_search"}] }],
    }]
)

run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id, assistant_id=assistant.id
)

messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))
message_content = messages[0].content[0].text
annotations = message_content.annotations


