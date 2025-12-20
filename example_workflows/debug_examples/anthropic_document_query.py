import os
import anthropic
import base64

client = anthropic.Anthropic()
model = "claude-sonnet-4-5"

# Example files.
current_dir = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(current_dir, "user_files", "example.pdf")
PNG_PATH = os.path.join(current_dir, "user_files", "example.png")
DOCX_PATH = os.path.join(current_dir, "user_files", "example.docx")

# First, get a response to use as instructions
response = client.messages.create(
    model=model,
    max_tokens=10,
    messages=[
        {"role": "user", "content": "Just output: 'summarize the document` and nothing else."}
    ],
)

task = response.content[0].text

# Upload the file to Anthropic
with open(PDF_PATH, "rb") as f:
    assert os.path.isfile(PDF_PATH), f"File not found: {PDF_PATH}"
    file_response = client.beta.files.upload(file=f)
    file_content = file_response.id

# List files to verify upload
files_list = client.beta.files.list()

# Get file metadata
file_metadata = client.beta.files.retrieve_metadata(file_id=file_content)

# Now ask a question about the document by reading the file content and encoding it
with open(PDF_PATH, "rb") as f:
    file_bytes = f.read()
    file_base64 = base64.b64encode(file_bytes).decode("utf-8")

# Create a message with the file content embedded
query_response = client.messages.create(
    model=model,
    max_tokens=1000,
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": task},
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": file_base64,
                    },
                },
            ],
        }
    ],
)

# Get the response content
message_content = query_response.content[0].text

# Clean up - delete the uploaded file
client.beta.files.delete(file_id=file_content)
