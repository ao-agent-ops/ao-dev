#!/usr/bin/env python3
"""Configuration management for Pyre-Analyst."""

import json
from pathlib import Path
from typing import Dict, Any


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json."""
    config_path = Path(__file__).parent.parent / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        return json.load(f)


def create_test_code() -> str:
    """Create test file content for demonstration."""
    return '''# Test LLM data flow detection
import openai
import anthropic

def example_workflow():
    """Example showing LLM data flow that should be detected"""
    
    # OpenAI call 
    openai_response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )
    
    # Flow: OpenAI -> variable -> Anthropic
    user_input = openai_response.choices[0].message.content
    
    anthropic_response = anthropic.messages.create(
        model="claude-3",
        messages=[{"role": "user", "content": user_input}]
    )
    
    return anthropic_response

def independent_call():
    """This call should not be part of the flow"""
    return openai.chat.completions.create(
        model="gpt-4", 
        messages=[{"role": "user", "content": "Independent call"}]
    )

# Dictionary assignment (should work with Pyre defaults)
x = openai.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": "hello"}])
y = {}
y["key"] = x
result = anthropic.messages.create(model="claude-3", messages=[{"role": "user", "content": y}])
'''
