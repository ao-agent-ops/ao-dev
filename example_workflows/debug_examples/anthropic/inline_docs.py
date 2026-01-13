"""
Anthropic Claude API example with inline base64 documents and images.

This example demonstrates:
1. Sending images (JPEG, PNG) and documents (PDF) to Claude using base64 encoding
2. Dataflow between LLM calls (outputs from earlier calls used as inputs to later calls)

Note: Anthropic's document type only supports PDF, not DOCX/XLSX.
"""
import os
import base64
import anthropic

client = anthropic.Anthropic()
model = "claude-sonnet-4-5"

# Load example files
current_dir = os.path.dirname(os.path.abspath(__file__))
JPEG_PATH = os.path.join(current_dir, "user_files", "sample_program.jpg")
PNG_PATH = os.path.join(current_dir, "user_files", "example.png")
PDF_PATH = os.path.join(current_dir, "user_files", "example.pdf")

# Read and encode all files
with open(JPEG_PATH, "rb") as f:
    jpeg_base64 = base64.b64encode(f.read()).decode("utf-8")

with open(PNG_PATH, "rb") as f:
    png_base64 = base64.b64encode(f.read()).decode("utf-8")

with open(PDF_PATH, "rb") as f:
    pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

# Step 1: Describe the JPEG image
jpeg_response = client.messages.create(
    model=model,
    max_tokens=300,
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image in 2-3 sentences."},
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": jpeg_base64},
                },
            ],
        }
    ],
)
jpeg_description = jpeg_response.content[0].text
print(f"JPEG description: {jpeg_description}\n")

# Step 2: Describe the PNG image
png_response = client.messages.create(
    model=model,
    max_tokens=300,
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image in 2-3 sentences."},
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": png_base64},
                },
            ],
        }
    ],
)
png_description = png_response.content[0].text
print(f"PNG description: {png_description}\n")

# Step 3: Summarize the PDF document
pdf_response = client.messages.create(
    model=model,
    max_tokens=500,
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Summarize this document in 2-3 sentences."},
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_base64},
                },
            ],
        }
    ],
)
pdf_summary = pdf_response.content[0].text
print(f"PDF summary: {pdf_summary}\n")

# Step 4: Create a combined analysis using all previous outputs (dataflow!)
combined_response = client.messages.create(
    model=model,
    max_tokens=800,
    messages=[
        {
            "role": "user",
            "content": f"""I have analyzed several files. Here are the results:

IMAGE 1 (JPEG): {jpeg_description}

IMAGE 2 (PNG): {png_description}

DOCUMENT (PDF): {pdf_summary}

Based on these descriptions and summaries, what common themes or connections do you see across all these files? Provide a brief unified analysis.""",
        }
    ],
)
combined_analysis = combined_response.content[0].text
print(f"Combined analysis: {combined_analysis}")
