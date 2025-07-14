#!/usr/bin/env python3
"""
Develop command entry point.

This module provides the 'develop' command functionality by importing
and running the main function from develop_shim.py.
"""

from agent_copilot.develop_shim import main
from common.utils import ensure_project_root_in_copilot_yaml
import os

# Ensure copilot.yaml has project_root set before anything else
default_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'configs', 'copilot.yaml')
default_config_path = os.path.abspath(default_config_path)
ensure_project_root_in_copilot_yaml(default_config_path)

def run():
    """Entry point for the develop command."""
    main()

if __name__ == "__main__":
    main() 