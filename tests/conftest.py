"""
Global test configuration - blocks all external HTTP calls and sets dummy API keys.
"""

import os
import re
import pytest
import responses
from common.utils import scan_user_py_files_and_modules
from runner.fstring_rewriter import (
    install_fstring_rewriter,
    set_user_py_files,
    set_module_to_user_file,
)
from runner.monkey_patching.apply_monkey_patches import apply_all_monkey_patches

# Set dummy API keys globally
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-dummy-google-key")


@pytest.fixture(autouse=True)
def block_external_http():
    """Block all external HTTP calls, allow localhost only."""
    if not responses:
        yield
        return

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        # Allow local connections for our develop server
        rsps.add_passthru("http://localhost")
        rsps.add_passthru("http://127.0.0.1")

        # Block everything else - but don't assert that this mock is called
        # since cached responses might not make HTTP calls
        rsps.add(
            responses.POST,
            re.compile(r"https?://(?!localhost|127\.0\.0\.1).*"),
            json={"blocked": True},
            status=200,
        )

        yield rsps


def pytest_configure(config):
    """Configure pytest to set up f-string rewriting."""
    # Get the project root directory (parent of tests directory)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)

    # Scan for all Python files in the project
    user_py_files, file_to_module, module_to_file = scan_user_py_files_and_modules(project_root)

    # Set up the f-string rewriter
    set_user_py_files(user_py_files, file_to_module)
    set_module_to_user_file(module_to_file)
    install_fstring_rewriter()

    # apply the monkey patches
    apply_all_monkey_patches()


@pytest.fixture
def http_calls(block_external_http):
    """Access HTTP call information in tests."""
    return block_external_http
