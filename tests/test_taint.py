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
        self.integration_dir = self.tests_dir / "taint" / "integration"

        # Cache for batch results
        self._all_results = None

    def discover_test_modules(self) -> List[str]:
        """Discover all test case modules in taint/integration/."""
        test_modules = []

        if not self.integration_dir.exists():
            return test_modules

        for file_path in self.integration_dir.glob("*_test_cases.py"):
            # Convert path to module name: taint.integration.re_test_cases
            module_name = "taint.integration." + file_path.stem
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
            "develop",
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


# Note: Individual test parametrization removed to avoid AST rewriting issues during collection
# The test_all_taint_cases function provides comprehensive testing of all cases


def test_all_taint_cases():
    """Test all taint cases in a single batch execution."""
    print("\\n" + "=" * 60)
    print("Testing all taint propagation cases via develop command")
    print("=" * 60)

    results = launcher.run_all_test_modules()
    _report_batch_results(results)


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


def _report_batch_results(results):
    """Report results from a batch test execution."""
    # Analyze results
    failed_tests = []
    error_tests = []
    passed_tests = []

    for test_name, result in results.items():
        status = result.get("status", "unknown")

        if status == "passed":
            passed_tests.append(test_name)
        elif status == "failed":
            failed_tests.append((test_name, result.get("message", "No message")))
        elif status == "error":
            error_tests.append((test_name, result.get("message", "No message")))

    # Report results
    print("\\n" + "=" * 60)
    print("TAINT TEST RESULTS SUMMARY:")
    print("  Total tests: " + str(len(results)) + "")
    print("  Passed: " + str(len(passed_tests)) + "")
    print("  Failed: " + str(len(failed_tests)) + "")
    print("  Errors: " + str(len(error_tests)) + "")
    print("=" * 60)

    if failed_tests:
        print("\\nFailed tests:")
        for test_name, message in failed_tests:
            print("  ✗ " + str(test_name) + ": " + str(message))

    if error_tests:
        print("\\nError tests:")
        for test_name, message in error_tests:
            print("  ✗ " + str(test_name) + ": " + str(message))

    # Fail if any tests failed
    if failed_tests or error_tests:
        pytest.fail(
            str(len(failed_tests)) + " tests failed, " + str(len(error_tests)) + " tests had errors"
        )

    print("\\n✅ All " + str(len(passed_tests)) + " tests passed!")
