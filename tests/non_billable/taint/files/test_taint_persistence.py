#!/usr/bin/env python3
"""
Test script for cross-session taint tracking.

This script demonstrates:
1. Session 1: Write tainted data to a file
2. Session 2: Read from the file and see the taint from Session 1
"""

import os
import sys
from pathlib import Path
from aco.runner.taint_wrappers import TaintFile, TaintStr, get_taint_origins

from tests.utils import cleanup_taint_db, setup_test_session


def session1_write():
    """Session 1: Write tainted data to a file"""
    print("=== SESSION 1: Writing tainted data ===")

    # Set session ID for this test
    os.environ["AGENT_COPILOT_SESSION_ID"] = "session-001"

    # Create experiment record for this session
    setup_test_session("session-001", name="Session 1 - Writer")

    # Create some tainted data with node IDs as taint origins
    tainted_data1 = TaintStr("This is line 1 with secret data\n", taint_origin="node-001")
    tainted_data2 = TaintStr("This is line 2 with more secrets\n", taint_origin="node-002")
    tainted_data3 = TaintStr(
        "This is line 3 with combined data\n", taint_origin=["node-001", "node-003"]
    )

    print(f"Tainted data 1 origins: {get_taint_origins(tainted_data1)}")
    print(f"Tainted data 2 origins: {get_taint_origins(tainted_data2)}")
    print(f"Tainted data 3 origins: {get_taint_origins(tainted_data3)}")

    # Write to a file using TaintFile
    with TaintFile.open("test_taint_data.txt", "w") as f:
        f.write(tainted_data1)
        f.write(tainted_data2)
        f.write(tainted_data3)

    print("Data written to test_taint_data.txt")
    print()


def session2_read():
    """Session 2: Read from the file and check taint"""
    print("=== SESSION 2: Reading tainted data ===")

    # Set a different session ID
    os.environ["AGENT_COPILOT_SESSION_ID"] = "session-002"

    # Create experiment record for this session
    setup_test_session("session-002", name="Session 2 - Reader")

    # Read from the file using TaintFile
    with TaintFile.open("test_taint_data.txt", "r") as f:
        line1 = f.readline()
        line2 = f.readline()
        line3 = f.readline()

    print(f"Line 1: {line1.strip()}")
    print(f"Line 1 taint origins: {get_taint_origins(line1)}")
    print()

    print(f"Line 2: {line2.strip()}")
    print(f"Line 2 taint origins: {get_taint_origins(line2)}")
    print()

    print(f"Line 3: {line3.strip()}")
    print(f"Line 3 taint origins: {get_taint_origins(line3)}")
    print()


def cleanup():
    """Clean up test files"""
    if os.path.exists("test_taint_data.txt"):
        os.remove("test_taint_data.txt")
        print("Cleaned up test_taint_data.txt")


if __name__ == "__main__":
    try:
        # Clean up any existing taint data before running
        cleanup_taint_db()

        # Run Session 1
        session1_write()

        # Run Session 2
        session2_read()

        print("=== TEST COMPLETE ===")
        print("Check the Agent Copilot UI to see the cross-session taint graph!")

    finally:
        # Clean up
        cleanup()
