"""
OpenAI Vision API example with inline base64 images.

This example demonstrates:
1. Sending images (JPEG, PNG) to GPT-4 Vision using base64 data URLs
2. Dataflow between LLM calls (outputs from earlier calls used as inputs to later calls)

Note: OpenAI doesn't support inline PDF/DOCX - use Anthropic for those.
"""
import os
import base64
from openai import OpenAI

client = OpenAI()
model = "gpt-4o"

# Load example files
current_dir = os.path.dirname(os.path.abspath(__file__))
JPEG_PATH = os.path.join(current_dir, "user_files", "sample_program.jpg")
PNG_PATH = os.path.join(current_dir, "user_files", "example.png")

# Read and encode the JPEG
with open(JPEG_PATH, "rb") as f:
    jpeg_base64 = base64.b64encode(f.read()).decode("utf-8")
jpeg_data_url = f"data:image/jpeg;base64,{jpeg_base64}"

# Read and encode the PNG
with open(PNG_PATH, "rb") as f:
    png_base64 = base64.b64encode(f.read()).decode("utf-8")
png_data_url = f"data:image/png;base64,{png_base64}"

# Step 1: Describe the JPEG image
jpeg_response = client.chat.completions.create(
    model=model,
    max_tokens=300,
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image in 2-3 sentences."},
                {"type": "image_url", "image_url": {"url": jpeg_data_url}},
            ],
        }
    ],
)
jpeg_description = jpeg_response.choices[0].message.content
print(f"JPEG description: {jpeg_description}\n")

# Step 2: Describe the PNG image
png_response = client.chat.completions.create(
    model=model,
    max_tokens=300,
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image in 2-3 sentences."},
                {"type": "image_url", "image_url": {"url": png_data_url}},
            ],
        }
    ],
)
png_description = png_response.choices[0].message.content
print(f"PNG description: {png_description}\n")

# Step 3: Compare using previous descriptions (dataflow!)
comparison_response = client.chat.completions.create(
    model=model,
    max_tokens=500,
    messages=[
        {
            "role": "user",
            "content": f"""I have two image descriptions:

IMAGE 1 (JPEG): {jpeg_description}

IMAGE 2 (PNG): {png_description}

Based on these descriptions, what are the main similarities and differences between the two images? Provide a brief comparison.""",
        }
    ],
)
comparison = comparison_response.choices[0].message.content
print(f"Comparison: {comparison}")
