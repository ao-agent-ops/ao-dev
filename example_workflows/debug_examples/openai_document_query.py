import os
from openai import OpenAI


client = OpenAI()
model = "gpt-5.1"

# Example files.
current_dir = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(current_dir, "user_files", "example.pdf")
PNG_PATH = os.path.join(current_dir, "user_files", "example.png")
DOCX_PATH = os.path.join(current_dir, "user_files", "example.docx")

# Generate system prompt using Responses API
response = client.responses.create(
    model=model,
    input="Output a system prompt for a document processing LLM (e.g., you're a helpful assistant).",
)
system_prompt = response.output_text

# Create a vector store for file search
vector_store = client.vector_stores.create(name="Document Processing Store")

# Upload file to vector store
with open(PDF_PATH, "rb") as f:
    assert os.path.isfile(PDF_PATH), f"File not found: {PDF_PATH}"
    file_response = client.files.create(file=f, purpose="assistants")

    # Attach file to vector store
    client.vector_stores.files.create(
        vector_store_id=vector_store.id,
        file_id=file_response.id
    )

# Wait for file to be processed (optional but recommended)
import time
while True:
    vector_store_status = client.vector_stores.retrieve(vector_store.id)
    if vector_store_status.file_counts.completed > 0:
        break
    time.sleep(1)

# Query the document using Responses API with file_search tool
document_response = client.responses.create(
    model=model,
    input=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Summarize the file."}
    ],
    tools=[{
        "type": "file_search",
        "vector_store_ids": [vector_store.id]
    }]
)

# Extract the response content
message_content = document_response.output_text
print(f"Summary: {message_content}")
