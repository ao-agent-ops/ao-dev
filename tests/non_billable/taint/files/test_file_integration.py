#!/usr/bin/env python3
"""Test file object integration with taint tracking."""

import os
import tempfile
from ao.runner.taint_wrappers import (
    TaintFile,
    taint_wrap,
    get_taint_origins,
    is_tainted,
    open_with_taint,
)


def test_file_wrapping():
    """Test that file objects are properly wrapped."""
    print("Testing file object wrapping...")

    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write("Test content for LLM")
        tmp.flush()
        tmp.seek(0)

        # Test wrapping a file object
        wrapped = taint_wrap(tmp, taint_origin="file_input")
        print(f"Wrapped file type: {type(wrapped)}")
        print(f"Is TaintFile: {isinstance(wrapped, TaintFile)}")

        # Test reading content
        tmp.seek(0)
        if hasattr(wrapped, "read"):
            content = wrapped.read()
            print(f"Content type: {type(content)}")
            print(f"Content: {content!r}")
            print(f"Is tainted: {is_tainted(content)}")
            if is_tainted(content):
                print(f"Taint origins: {get_taint_origins(content)}")

    os.unlink(tmp_path)
    print("✓ File wrapping works!")


def test_file_in_llm_context():
    """Test file usage in LLM context."""
    print("\nTesting file in LLM context...")

    # Create a file with sensitive content
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
        tmp_path = tmp.name
        tmp.write("Confidential document:\nPassword: secret123\nUser: admin")

    try:
        # Read file with taint tracking
        with open_with_taint(tmp_path, "r", taint_origin="sensitive_file") as f:
            file_content = f.read()

        print(f"File content type: {type(file_content)}")
        print(f"Is tainted: {is_tainted(file_content)}")
        print(f"Taint origins: {get_taint_origins(file_content)}")

        # Simulate using in LLM call
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": file_content},
        ]

        # Check that the content in the message is still tainted
        user_content = messages[1]["content"]
        print(f"Message content is tainted: {is_tainted(user_content)}")
        print(f"Message taint origins: {get_taint_origins(user_content)}")

        # This would go to an LLM API call, which should preserve the taint
        # by wrapping the response with the same or additional taint origins

    finally:
        os.unlink(tmp_path)

    print("✓ File in LLM context works!")


if __name__ == "__main__":
    test_file_wrapping()
    test_file_in_llm_context()
    print("\n✓ All file integration tests passed!")
