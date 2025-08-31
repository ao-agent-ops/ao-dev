#!/usr/bin/env python3
"""
Simple test for cross-session taint tracking without direct TaintFile import.
The file operations are automatically wrapped through monkey patching.
"""

import os
from openai import OpenAI

def test_writer():
    """First session: Generate content and write to file"""
    print("=== Writer Session ===")
    print(f"Session ID: {os.environ.get('AGENT_COPILOT_SESSION_ID', 'unknown')}")
    
    client = OpenAI()
    
    # Make an LLM call - this creates a node and taints the output
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": "Write a haiku about coding"}
        ]
    )
    
    haiku = response.choices[0].message.content
    print(f"Generated haiku:\n{haiku}")
    
    # Write to a file - the monkey-patched open() will use TaintFile
    with open("haiku.txt", "w") as f:
        f.write("=== AI Generated Haiku ===\n")
        f.write(haiku)
        f.write("\n=== End ===\n")
    
    print("Haiku written to haiku.txt")
    print("The LLM output's taint (node ID) has been stored in the database.")

def test_reader():
    """Second session: Read the file and use its content"""
    print("\n=== Reader Session ===")
    print(f"Session ID: {os.environ.get('AGENT_COPILOT_SESSION_ID', 'unknown')}")
    
    # Read the file - the monkey-patched open() will use TaintFile
    with open("haiku.txt", "r") as f:
        content = f.read()
    
    print(f"Read {len(content)} characters from haiku.txt")
    
    # Extract just the haiku
    lines = content.split('\n')
    haiku_lines = [l for l in lines if l and not l.startswith('===')]
    haiku_text = '\n'.join(haiku_lines)
    
    # Use the content in a new LLM call
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a poetry critic."},
            {"role": "user", "content": f"Rate this haiku from 1-10:\n{haiku_text}"}
        ]
    )
    
    rating = response.choices[0].message.content
    print(f"\nRating: {rating[:100]}...")
    
    print("\n=== Expected Behavior ===")
    print("1. The writer session created a node for generating the haiku")
    print("2. The reader session created a node for rating the haiku")
    print("3. There should be an edge from reader to writer node")
    print("4. This shows data flow across sessions through the file!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "read":
        test_reader()
    else:
        test_writer()
        print("\nNow run: python test_simple_taint.py read")
        print("(Make sure to run it through agent_copilot for tracking)")