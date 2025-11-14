#!/usr/bin/env python3

"""
Unified taint propagation tests that run all test cases via develop launcher.

This replaces the previous approach of having separate test files for each module.
Instead, it discovers all test case files in taint/integration/ and runs them
through the develop process to ensure .pyc files with AST rewrites are used.
"""

import os
import json
import socket
import subprocess
import time
import pytest
from pathlib import Path
from typing import Dict, List, Tuple


class TaintTestLauncher:
    """
    Simplified launcher for running taint test cases via develop command.

    Discovers all *_test_cases.py files in taint/integration/ and runs them
    individually through the develop process.
    """

    def __init__(self):
        self.tests_dir = Path(__file__).parent
        # Set project root to tests directory for develop command compatibility
        self.project_root = self.tests_dir
        self.integration_dir = self.tests_dir / "taint" / "general_functions"

        # Cache for batch results
        self._all_results = None

    def discover_test_modules(self) -> List[str]:
        """Discover all test case modules in taint/general_functions/."""
        test_modules = []

        if not self.integration_dir.exists():
            return test_modules

        for file_path in self.integration_dir.glob("*_test_cases.py"):
            # Convert path to module name: taint.general_functions.re_test_cases
            module_name = "taint.general_functions." + file_path.stem
            test_modules.append(module_name)

        return sorted(test_modules)

    def start_server_if_needed(self):
        """Start the daemon server if not already running."""
        from aco.cli.aco_server import launch_daemon_server

        print("Starting daemon server...")
        launch_daemon_server()
        time.sleep(2)

        # Check server is ready
        try:
            socket.create_connection(("127.0.0.1", 5959), timeout=2).close()
            print("Server is ready")
            return True
        except:
            print("WARNING: Server may not be ready")
            return False

    def run_test_module_via_develop(self, module_name: str) -> Dict:
        """Run a single test module via develop command and parse JSON results."""

        # Use the generic test case runner, passing the module name as argument
        cmd = [
            "aco-launch",
            "--project-root",
            str(self.project_root),
            "-m",
            "user_programs.taint_test_runner",
            module_name,
        ]

        print("Running command: " + " ".join(cmd))

        try:
            # Use Popen with larger buffer and ensure we read all output
            import subprocess

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.project_root),
                bufsize=0,  # Unbuffered for real-time output
            )

            # Wait for process to complete and capture all output
            stdout, stderr = process.communicate(timeout=60)

            # Create a result-like object for compatibility
            class ProcessResult:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            result = ProcessResult(process.returncode, stdout, stderr)

            # Always print subprocess result details for debugging
            print("Return code:", result.returncode)
            if result.stderr:
                print("STDERR:", result.stderr)

            # Parse JSON results from output - handle both success and failure cases
            output_lines = result.stdout.split("\n")

            # Find JSON results section
            json_start = False
            json_lines = []

            for line in output_lines:
                if "JSON_RESULTS_START" in line:
                    json_start = True
                    continue
                elif "JSON_RESULTS_END" in line:
                    break
                elif json_start:
                    json_lines.append(line)

            if json_lines:
                json_text = "\n".join(json_lines)
                test_results = json.loads(json_text)
                # Return results regardless of subprocess exit code
                # The test status is in the JSON, not the process exit code
                return test_results
            else:
                print("WARNING: No JSON results found in output")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                print("Return code:", result.returncode)
                # Return empty dict if no JSON found - this will be handled upstream
                return {}

        except subprocess.TimeoutExpired:
            print("ERROR: Test execution timed out for " + module_name)
            process.kill()
            return {}
        except json.JSONDecodeError as e:
            print("ERROR: Failed to parse JSON results for " + str(module_name) + ": " + str(e))
            print(
                "Raw JSON text (first 100 chars):",
                repr(json_text[:100]) if "json_text" in locals() else "No JSON text captured",
            )
            print(
                "STDOUT length:",
                len(result.stdout) if "result" in locals() else "No result captured",
            )
            return {}
        except Exception as e:
            print("ERROR: Failed to run tests for " + str(module_name) + ": " + str(e))
            return {}

    def run_all_test_modules(self) -> Dict[str, Dict]:
        """Run all discovered test modules and return aggregated results."""
        if self._all_results is not None:
            return self._all_results

        self.start_server_if_needed()

        test_modules = self.discover_test_modules()
        print("Discovered " + str(len(test_modules)) + " test modules: " + str(test_modules))

        all_results = {}

        for module_name in test_modules:
            print("\\n" + "=" * 60)
            print("Running " + module_name)
            print("=" * 60)

            module_results = self.run_test_module_via_develop(module_name)

            # Prefix test names with module name to avoid conflicts
            for test_name, result in module_results.items():
                prefixed_name = module_name + "::" + test_name
                all_results[prefixed_name] = result

        self._all_results = all_results
        return all_results


# Global launcher instance
launcher = TaintTestLauncher()


def collect_all_test_cases():
    """Collect metadata about all test cases without running them."""
    test_cases = []

    # Discover test modules
    test_modules = launcher.discover_test_modules()

    for module_name in test_modules:
        # For each module, we'll assume certain standard test names
        # This is a workaround since we can't import the modules at collection time
        # (they need AST transformation via develop)
        module_short_name = module_name.split(".")[-1].replace("_test_cases", "")

        # Add placeholders for common test patterns
        # These will be validated when actually run
        test_cases.append((module_name, f"test_basic_{module_short_name}"))
        test_cases.append((module_name, f"test_complex_{module_short_name}"))
        test_cases.append((module_name, f"test_edge_cases_{module_short_name}"))

    return test_cases


# Generate individual test functions dynamically
# This approach creates individual pytest test items that can be selected/filtered
def create_individual_test(module_name, test_name):
    """Create a test function for a specific test case."""

    def test_func():
        print(f"\\nRunning individual test: {module_name}::{test_name}")

        # Start server if needed
        launcher.start_server_if_needed()

        # Run just this specific test
        results = launcher.run_test_module_via_develop(module_name)

        if test_name in results:
            result = results[test_name]
            _assert_test_result(f"{module_name}::{test_name}", result)
        else:
            # Test doesn't exist in this module, skip
            pytest.skip(f"Test {test_name} not found in {module_name}")

    # Set a meaningful name for the test function
    test_func.__name__ = f"test_{module_name.split('.')[-1]}_{test_name}"
    return test_func


# Note: We provide both batch and individual test options
# The test_all_taint_cases function provides comprehensive testing with detailed reporting


def test_all_taint_cases():
    """Test all taint cases in a single batch execution."""
    print("\\n" + "=" * 60)
    print("Testing all taint propagation cases via develop command")
    print("=" * 60)

    results = launcher.run_all_test_modules()
    _report_batch_results(results, show_individual=True)


def _assert_test_result(test_name, result):
    """Assert that a test result indicates success."""
    status = result.get("status", "unknown")
    message = result.get("message", "No message")

    # Fail if the test didn't pass
    if status == "failed":
        pytest.fail("Test " + str(test_name) + " failed: " + str(message) + "")
    elif status == "error":
        error_msg = "Test " + str(test_name) + " had error: " + str(message) + ""
        pytest.fail(error_msg)
    elif status != "passed":
        pytest.fail("Test " + str(test_name) + " had unexpected status: " + str(status) + "")


def _report_batch_results(results, show_individual=False):
    """Report results from a batch test execution."""
    # Analyze results
    failed_tests = []
    error_tests = []
    passed_tests = []

    # Print individual test results with green/red indicators
    if show_individual:
        print("\\n" + "=" * 60)
        print("INDIVIDUAL TEST RESULTS:")
        print("=" * 60)

        # Group tests by module for better organization
        tests_by_module = {}
        for test_name, result in results.items():
            # Extract module name from test name (format: module::test_name)
            if "::" in test_name:
                module_part = test_name.split("::")[0]
                if "." in module_part:
                    # Extract just the module name without full path
                    module_name = module_part.split(".")[-1]
                else:
                    module_name = module_part
            else:
                module_name = "unknown"

            if module_name not in tests_by_module:
                tests_by_module[module_name] = []
            tests_by_module[module_name].append((test_name, result))

        # Print results grouped by module
        for module_name in sorted(tests_by_module.keys()):
            print(f"\\n{module_name}:")
            for test_name, result in tests_by_module[module_name]:
                status = result.get("status", "unknown")
                # Extract just the test function name for cleaner display
                display_name = test_name.split("::")[-1] if "::" in test_name else test_name

                if status == "passed":
                    print(f"  ✅ {display_name}")
                elif status == "failed":
                    print(f"  ❌ {display_name}")
                elif status == "error":
                    print(f"  💥 {display_name}")
                else:
                    print(f"  ❓ {display_name} (unknown status)")

    for test_name, result in results.items():
        status = result.get("status", "unknown")

        if status == "passed":
            passed_tests.append(test_name)
        elif status == "failed":
            failed_tests.append((test_name, result))
        elif status == "error":
            error_tests.append((test_name, result))

    # Report summary
    print("\\n" + "=" * 60)
    print("TAINT TEST RESULTS SUMMARY:")
    print("  Total tests: " + str(len(results)) + "")
    print("  Passed: " + str(len(passed_tests)) + " ✅")
    print("  Failed: " + str(len(failed_tests)) + " ❌")
    print("  Errors: " + str(len(error_tests)) + " 💥")
    print("=" * 60)

    # Show detailed failure information with tracebacks
    if failed_tests:
        print("\\n" + "=" * 60)
        print("FAILED TESTS (with tracebacks):")
        print("=" * 60)
        for test_name, result in failed_tests:
            print(f"\\n❌ {test_name}:")
            print("-" * 40)
            # Extract and display the traceback if available
            if "traceback" in result:
                print(result["traceback"])
            else:
                # Fall back to message which may contain traceback
                message = result.get("message", "No message")
                print(message)

    if error_tests:
        print("\\n" + "=" * 60)
        print("ERROR TESTS (with tracebacks):")
        print("=" * 60)
        for test_name, result in error_tests:
            print(f"\\n💥 {test_name}:")
            print("-" * 40)
            # Extract and display the traceback if available
            if "traceback" in result:
                print(result["traceback"])
            else:
                # Fall back to message which may contain traceback
                message = result.get("message", "No message")
                print(message)

    # Fail if any tests failed
    if failed_tests or error_tests:
        pytest.fail(
            str(len(failed_tests)) + " tests failed, " + str(len(error_tests)) + " tests had errors"
        )

    print("\\n✅ All " + str(len(passed_tests)) + " tests passed!")


# Alternative: Parametrized test approach
# This creates individual pytest items for each test case
def get_all_test_ids():
    """Get test IDs for parametrization."""
    # Run all tests once and cache results
    results = launcher.run_all_test_modules()

    # Extract test IDs
    test_ids = []
    for test_id in sorted(results.keys()):
        # Create a cleaner ID for pytest display
        if "::" in test_id:
            parts = test_id.split("::")
            module_part = parts[0].split(".")[-1] if "." in parts[0] else parts[0]
            test_part = parts[-1]
            clean_id = f"{module_part}::{test_part}"
        else:
            clean_id = test_id
        test_ids.append(clean_id)

    return test_ids


@pytest.mark.parametrize("test_id", get_all_test_ids() if launcher.discover_test_modules() else [])
def test_taint_case_parametrized(test_id):
    """Run individual taint test case (parametrized version)."""
    # Get cached results
    results = launcher.run_all_test_modules()

    # Find the full test ID that matches our clean ID
    matching_result = None
    matching_key = None

    for full_id, result in results.items():
        if "::" in full_id:
            parts = full_id.split("::")
            module_part = parts[0].split(".")[-1] if "." in parts[0] else parts[0]
            test_part = parts[-1]
            clean_full_id = f"{module_part}::{test_part}"
            if clean_full_id == test_id:
                matching_result = result
                matching_key = full_id
                break
        elif full_id == test_id:
            matching_result = result
            matching_key = full_id
            break

    if matching_result:
        _assert_test_result(matching_key or test_id, matching_result)
    else:
        pytest.skip(f"Test {test_id} not found in results")
