import os
import anthropic
import base64

client = anthropic.Anthropic()
model = "claude-3-5-haiku-20241022"  # Fastest and most cost-effective model
PDF_PATH = "/Users/ferdi/Downloads/ken_udbms_execution.pdf"

# First, get a response to use as instructions
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=10,
    messages=[
        {
            "role": "user",
            "content": "Just output: 'summarize the document` and nothing else."
        }
    ]
)

task = response.content[0].text

# Upload the file to Anthropic
with open(PDF_PATH, "rb") as f:
    assert os.path.isfile(PDF_PATH), f"File not found: {PDF_PATH}"
    file_response = client.beta.files.upload(
        file=f
    )
    file_content = file_response.id

print(f"File uploaded with ID: {file_content}")

# List files to verify upload
files_list = client.beta.files.list()
print(f"Total files uploaded: {len(files_list.data)}")

# Get file metadata
file_metadata = client.beta.files.retrieve_metadata(file_id=file_content)
print(f"File metadata: {file_metadata}")

# Now ask a question about the document by reading the file content and encoding it
with open(PDF_PATH, "rb") as f:
    file_bytes = f.read()
    file_base64 = base64.b64encode(file_bytes).decode('utf-8')

# Create a message with the file content embedded
query_response = client.messages.create(
    model=model,
    max_tokens=1000,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": task
                },
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": file_base64
                    }
                }
            ]
        }
    ]
)

# Get the response content
message_content = query_response.content[0].text
print(f"Response: {message_content}")

# Clean up - delete the uploaded file
client.beta.files.delete(file_id=file_content)
print(f"File {file_content} deleted")
