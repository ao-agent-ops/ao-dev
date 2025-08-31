#!/usr/bin/env python3
"""
Script 2: Read the analysis file created by the first script.
This will demonstrate cross-session taint tracking.
"""

import os
import sys

# Add src to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from runner.taint_wrappers import TaintFile, get_taint_origins
from openai import OpenAI

def main():
    print("=== SESSION 2: Reading Previous Analysis with Taint Tracking ===")
    
    # Set a different session ID for this run
    session_id = os.environ.get('AGENT_COPILOT_SESSION_ID', 'reader-session-002')
    print(f"Session ID: {session_id}")
    
    # Read the analysis file created by the previous script
    output_file = "document_analysis.txt"
    
    if not os.path.exists(output_file):
        print(f"Error: {output_file} not found. Please run test_taint_pdf_writer.py first.")
        return
    
    print(f"\nReading analysis from {output_file}")
    
    # Read using TaintFile to preserve taint
    with TaintFile.open(output_file, "r", session_id=session_id) as f:
        lines = f.readlines()
    
    print(f"\nRead {len(lines)} lines from the file.")
    
    # Check taint for each line
    for i, line in enumerate(lines[:5]):  # Show first 5 lines
        taint_origins = get_taint_origins(line)
        if taint_origins:
            print(f"\nLine {i+1}: {line.strip()[:50]}...")
            print(f"  Taint origins: {taint_origins}")
    
    # Now use the tainted data in a new LLM call
    print("\n--- Making a new LLM call with tainted input ---")
    
    # Extract the analysis part (lines after "Analysis:")
    analysis_start = False
    analysis_lines = []
    for line in lines:
        if "Analysis:" in line:
            analysis_start = True
            continue
        if analysis_start and "=== End of Report ===" in line:
            break
        if analysis_start:
            analysis_lines.append(line)
    
    tainted_content = "".join(analysis_lines)
    print(f"Analysis content has taint: {get_taint_origins(tainted_content)}")
    
    # Use the tainted content in a new API call
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Summarize this in one sentence: {tainted_content[:500]}"}
        ]
    )
    
    summary = response.choices[0].message.content
    print(f"\nGenerated summary: {summary[:100]}...")
    
    # The summary should now have taint from both the original analysis and this new call
    print(f"Summary taint origins: {get_taint_origins(summary)}")
    
    print("\n=== CROSS-SESSION TAINT TRACKING COMPLETE ===")
    print("Check the Agent Copilot UI to see:")
    print("1. The node from the first session (document analysis)")
    print("2. The node from this session (summary generation)")
    print("3. An edge connecting them due to the tainted data flow!")

if __name__ == "__main__":
    main()