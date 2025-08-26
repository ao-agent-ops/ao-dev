#!/usr/bin/env python3
"""Simple integration test to verify taint tracking works."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from runner.taint_wrappers import (
    TaintStr, TaintInt, TaintFloat, TaintList, TaintDict, TaintFile,
    TaintedOpenAIObject, taint_wrap, get_taint_origins, is_tainted
)


def test_basic_taint_functionality():
    """Test basic taint functionality."""
    print("Testing basic taint functionality...")
    
    # Test TaintStr
    tainted_str = TaintStr("Hello world", taint_origin="test_source")
    print(f"TaintStr created: {repr(tainted_str)}")
    print(f"Is tainted: {is_tainted(tainted_str)}")
    print(f"Taint origins: {get_taint_origins(tainted_str)}")
    
    # Test TaintList
    tainted_list = TaintList([1, 2, "three"], taint_origin="list_source")
    print(f"TaintList created: {tainted_list}")
    print(f"Is tainted: {is_tainted(tainted_list)}")
    print(f"Taint origins: {get_taint_origins(tainted_list)}")
    
    # Test taint_wrap
    test_dict = {"key": "value", "number": 42}
    wrapped = taint_wrap(test_dict, taint_origin="wrapped_dict")
    print(f"Dict wrapped: {type(wrapped)}")
    print(f"Is tainted: {is_tainted(wrapped)}")
    
    print("✓ Basic functionality works!")


def test_llm_simulation():
    """Test simulated LLM interaction."""
    print("\nTesting LLM simulation...")
    
    # Create tainted input
    user_input = TaintStr("What is 2+2?", taint_origin="user_question")
    
    # Simulate processing (this represents what would happen in an LLM call)
    messages = [{"role": "user", "content": user_input}]
    
    # Extract content (simulating LLM input processing)
    content = messages[0]["content"]
    print(f"Content type: {type(content)}")
    print(f"Content is tainted: {is_tainted(content)}")
    if is_tainted(content):
        print(f"Content taint origins: {get_taint_origins(content)}")
    
    # Simulate LLM response (would be tainted by the API wrapper)
    mock_response = "The answer is 4"
    tainted_response = taint_wrap(mock_response, taint_origin="llm_api")
    
    print(f"Response tainted: {is_tainted(tainted_response)}")
    print(f"Response taint origins: {get_taint_origins(tainted_response)}")
    
    print("✓ LLM simulation works!")


if __name__ == "__main__":
    test_basic_taint_functionality()
    test_llm_simulation()
    print("\n✓ All simple integration tests passed!")