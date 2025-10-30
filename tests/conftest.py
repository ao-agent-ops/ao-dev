"""
Global test configuration - blocks all external HTTP calls and sets dummy API keys.
"""

import os
import re
import random
import pytest
import responses
from aco.common.utils import scan_user_py_files_and_modules
from aco.runner.patching_import_hook import set_module_to_user_file, install_patch_hook
from aco.runner.monkey_patching.apply_monkey_patches import apply_all_monkey_patches

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

    os.environ["ACO_SEED"] = str(random.randint(0, 2**31 - 1))

    # Scan for all Python files in the project
    _, _, module_to_file = scan_user_py_files_and_modules(project_root)
    set_module_to_user_file(module_to_file)
    install_patch_hook()

    # apply the monkey patches
    apply_all_monkey_patches()


@pytest.fixture(autouse=True)
def cleanup_taint_registry():
    """Clean up global taint registry between tests to prevent state leakage."""
    from aco.runner.taint_wrappers import obj_id_to_taint_origin

    # Clean up before test
    obj_id_to_taint_origin.clear()

    yield

    # Clean up after test
    obj_id_to_taint_origin.clear()


@pytest.fixture
def http_calls(block_external_http):
    """Access HTTP call information in tests."""
    return block_external_http
