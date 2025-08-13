import os
from openai import OpenAI


client = OpenAI()
model = "gpt-3.5-turbo"

# Example files.
current_dir = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(current_dir, "user_files", "example.pdf")
PNG_PATH = os.path.join(current_dir, "user_files", "example.png")
DOCX_PATH = os.path.join(current_dir, "user_files", "example.docx")

response = client.responses.create(
    model=model,
    input="Output a system prompt for a document processing LLM (e.g., you're a helpful assistant).",
)

with open(PDF_PATH, "rb") as f:
    assert os.path.isfile(PDF_PATH), f"File not found: {PDF_PATH}"
    file_response = client.files.create(
        file=(os.path.basename(PDF_PATH), f, "application/pdf"), purpose="assistants"
    )
    file_content = file_response.id

assistant = client.beta.assistants.create(
    name="Document Assistant",
    instructions=response.output_text,
    model=model,
    tools=[{"type": "file_search"}],
)
# Create a thread and attach the file to the message
thread = client.beta.threads.create(
    messages=[
        {
            "role": "user",
            "content": "Summarize the file.",
            # Attach the new file to the message.
            "attachments": [{"file_id": file_content, "tools": [{"type": "file_search"}]}],
        }
    ]
)

run = client.beta.threads.runs.create_and_poll(thread_id=thread.id, assistant_id=assistant.id)

messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))
message_content = messages[0].content[0].text
annotations = message_content.annotations
