#!/usr/bin/env python3
"""
Generic test case runner for taint integration tests.

This module can be used to run any test case module when called via:
    develop -m taint.integration.test_case_runner <module_name>

It will import the specified module and run all test functions found in it.
"""

import sys
import json
import traceback
import importlib
from pathlib import Path


def discover_test_functions(module):
    """Discover all test functions in a module."""
    test_functions = []

    # Get standalone test functions
    for name in dir(module):
        if name.startswith("test_") and callable(getattr(module, name)):
            test_functions.append(name)

    # Get test methods from test classes
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and (name.startswith("Test") or name.startswith("test_")):
            # This is a test class
            for method_name in dir(obj):
                if method_name.startswith("test_") and callable(getattr(obj, method_name)):
                    # Format as class::method for easy identification
                    test_functions.append(f"{name}::{method_name}")

    return sorted(test_functions)


def run_test_function(module, test_name):
    """Run a single test function and return result."""
    try:
        if "::" in test_name:
            # This is a class method
            class_name, method_name = test_name.split("::")
            test_class = getattr(module, class_name)
            test_instance = test_class()
            test_func = getattr(test_instance, method_name)
        else:
            # This is a standalone function
            test_func = getattr(module, test_name)

        # Run the test
        test_func()
        return {"status": "passed", "message": f"{test_name} passed"}

    except AssertionError as e:
        tb = traceback.format_exc()
        error_msg = str(e) if str(e) else "Assertion failed"
        return {
            "status": "failed",
            "message": f"{error_msg}\\n\\nTraceback:\\n{tb}",
            "type": "assertion",
            "traceback": tb,
        }

    except Exception as e:
        tb = traceback.format_exc()
        return {
            "status": "error",
            "message": f"{str(e)}\\n\\nTraceback:\\n{tb}",
            "type": type(e).__name__,
            "traceback": tb,
        }


def main():
    """Main entry point for running test cases."""
    if len(sys.argv) < 2:
        print("Usage: python test_case_runner.py <module_name>")
        sys.exit(1)

    module_name = sys.argv[1]

    print("=" * 50)
    print(f"Running taint test cases from {module_name}")
    print("=" * 50)

    try:
        # Import the test module
        # Handle both full module names (taint.general_functions.re_test_cases)
        # and short names (re_test_cases)
        if not module_name.startswith("taint.general_functions."):
            if module_name.endswith("_test_cases"):
                module_name = f"taint.general_functions.{module_name}"
            else:
                module_name = f"taint.general_functions.{module_name}_test_cases"

        # Add tests directory to path
        tests_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(tests_dir))

        # Import the test module
        module = importlib.import_module(module_name)
        test_functions = discover_test_functions(module)

        print(f"Found {len(test_functions)} test functions: {test_functions}")
        print("=" * 50)

        results = {}
        for test_name in test_functions:
            print(f"Running {test_name}...", end="")
            result = run_test_function(module, test_name)
            results[test_name] = result

            if result["status"] == "passed":
                print(" ✓")
            else:
                print(f" ✗ {result['status']}")
                # Only print detailed message for failures to reduce output
                if result["status"] in ["failed", "error"]:
                    print(f"  {result.get('message', 'No message')}")

        # Count results
        passed = sum(1 for r in results.values() if r.get("status") == "passed")
        failed = sum(1 for r in results.values() if r.get("status") == "failed")
        errors = sum(1 for r in results.values() if r.get("status") == "error")

        # Print summary
        print("\\n" + "=" * 50)
        print("TEST SUMMARY:")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Errors: {errors}")
        print(f"  Total:  {len(results)}")
        print("=" * 50)

        # Output JSON results for the test harness
        print("\\nJSON_RESULTS_START")
        print(json.dumps(results, indent=2))
        print("JSON_RESULTS_END")

        # Exit code
        sys.exit(0 if (failed == 0 and errors == 0) else 1)

    except Exception as e:
        print(f"\\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
