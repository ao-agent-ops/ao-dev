"""
Global test configuration - blocks all external HTTP calls and sets dummy API keys.
"""

import os
import re
import pytest
import responses
from aco.runner.monkey_patching.apply_monkey_patches import apply_all_monkey_patches

# Apply the monkey patches for LLM APIs
apply_all_monkey_patches()

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


@pytest.fixture
def http_calls(block_external_http):
    """Access HTTP call information in tests."""
    return block_external_http
