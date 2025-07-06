#!/usr/bin/env python3
"""
Develop command entry point.

This module provides the 'develop' command functionality by importing
and running the main function from develop_shim.py.
"""

from .develop_shim import main

def run():
    """Entry point for the develop command."""
    main()

if __name__ == "__main__":
    main() 