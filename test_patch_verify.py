#!/usr/bin/env python3
"""
Test script to verify that the file patching is working correctly.
Run this through agent_copilot to check if open() is being patched.
"""

import os

print("=== Testing File Monkey Patching ===")
print(f"Session ID: {os.environ.get('AGENT_COPILOT_SESSION_ID', 'NOT SET')}")

# Test 1: Check if open is patched
print("\n1. Checking if built-in open() is patched:")
import builtins
print(f"   builtins.open = {builtins.open}")
print(f"   Is it the original? {builtins.open.__name__ == 'open'}")

# Test 2: Open a file and check its type
print("\n2. Opening a test file:")
with open("test_patch.txt", "w") as f:
    print(f"   File object type: {type(f)}")
    print(f"   File object class: {f.__class__.__name__}")
    f.write("Testing monkey patch")

# Test 3: Read the file back
print("\n3. Reading the test file:")
with open("test_patch.txt", "r") as f:
    print(f"   File object type: {type(f)}")
    print(f"   File object class: {f.__class__.__name__}")
    content = f.read()
    print(f"   Content type: {type(content)}")
    print(f"   Content: {content}")

# Clean up
os.remove("test_patch.txt")
print("\n4. Test file cleaned up")

print("\n=== Expected Results ===")
print("- builtins.open should be 'patched_open'")
print("- File objects should be TaintFile type")
print("- Content should be TaintStr type")
print("\nIf these are not showing, the monkey patch is not being applied!")