#!/usr/bin/env python3
"""
Modified version of openai_document_query.py that writes output to a file.
This will create tainted output that can be read by another script.
The file operations are automatically wrapped with TaintFile through monkey patching.
"""

import os
from openai import OpenAI

client = OpenAI()
model = "gpt-3.5-turbo"

# Example files
current_dir = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(current_dir, "user_files", "example.pdf")
PNG_PATH = os.path.join(current_dir, "user_files", "example.png")
DOCX_PATH = os.path.join(current_dir, "user_files", "example.docx")

print("=== Document Processing Session ===")
print(f"Session ID: {os.environ.get('AGENT_COPILOT_SESSION_ID', 'unknown')}")

# Generate a system prompt
response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "user", "content": "Output a system prompt for a document processing LLM (e.g., you're a helpful assistant)."}
    ]
)

system_prompt = response.choices[0].message.content
print(f"Generated system prompt: {system_prompt[:50]}...")

# Process the PDF (simplified version without actual file upload)
with open(PDF_PATH, "rb") as f:
    assert os.path.isfile(PDF_PATH), f"File not found: {PDF_PATH}"
    # Simulate document processing
    print(f"Processing document: {PDF_PATH}")

# Generate a summary based on the "document"
summary_response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Summarize a research paper about machine learning techniques. Include key findings and methodology."}
    ]
)

summary = summary_response.choices[0].message.content

# Write the results to a file (automatically wrapped with TaintFile through monkey patching)
output_file = os.path.join(current_dir, "document_summary.txt")
print(f"\nWriting summary to {output_file}")

with open(output_file, "w") as f:
    f.write("=== Document Processing Results ===\n")
    f.write(f"Source: {PDF_PATH}\n")
    f.write(f"Model: {model}\n")
    f.write(f"System Prompt: {system_prompt}\n")
    f.write("\n--- Summary ---\n")
    f.write(summary)
    f.write("\n\n=== End of Results ===\n")

print(f"Summary written to {output_file}")
print("The output is tainted with the LLM node IDs.")
print("\nRun openai_document_reader.py next to see cross-session taint tracking!")