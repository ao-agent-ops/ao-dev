#!/usr/bin/env python3
"""
Script 1: Process a document and write tainted output to a file.
This simulates an LLM processing a PDF and writing results.
"""

import os
import sys

# Add src to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from runner.taint_wrappers import TaintFile, TaintStr, get_taint_origins
from openai import OpenAI

def main():
    print("=== SESSION 1: Document Processing with Tainted Output ===")
    
    # Set session ID for this run
    session_id = os.environ.get('AGENT_COPILOT_SESSION_ID', 'doc-session-001')
    print(f"Session ID: {session_id}")
    
    # Initialize OpenAI client
    client = OpenAI()
    model = "gpt-3.5-turbo"
    
    # Path to the example PDF
    current_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(current_dir, "example_workflows", "debug_examples", "user_files", "example.pdf")
    
    print(f"Processing PDF: {pdf_path}")
    
    # Create a simple query (simulating document processing)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a document analyzer."},
            {"role": "user", "content": "Generate a brief analysis of a hypothetical research paper about AI safety."}
        ]
    )
    
    # The response content is now tainted with the node ID from the LLM call
    analysis_text = response.choices[0].message.content
    
    # Get the taint origin from the response (this would be the node ID in the actual system)
    # For demonstration, we'll manually create tainted strings
    tainted_analysis = TaintStr(analysis_text, taint_origin="llm-node-001")
    
    print(f"\nAnalysis has taint origins: {get_taint_origins(tainted_analysis)}")
    
    # Write the analysis to a file using TaintFile
    output_file = "document_analysis.txt"
    with TaintFile.open(output_file, "w", session_id=session_id) as f:
        f.write("=== Document Analysis Report ===\n")
        f.write(f"Source: {pdf_path}\n")
        f.write("Analysis:\n")
        f.write(tainted_analysis)
        f.write("\n=== End of Report ===\n")
    
    print(f"\nAnalysis written to {output_file}")
    print("The taint information has been stored in the database.")
    print("\nNow run test_taint_pdf_reader.py to see cross-session taint tracking!")

if __name__ == "__main__":
    main()