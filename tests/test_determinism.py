"""
NOTE: Order matters for pytest. test_python_determinsim should be
executed before uuid because this messes with the random state.
"""

import random
from uuid import uuid4


def test_python_determinsim():
    """Test numpy determinism"""
    rand = random.random()
    assert rand == 0.8444218515250481, f"Python random not deterministic {rand}"


def test_determinism():
    """Test that UUID.hex returns a TaintStr."""
    random.seed(0)
    hex_one = uuid4().hex
    random.seed(0)
    hex_two = uuid4().hex

    assert hex_one == hex_two, "uuid4().hex not deterministic"


def test_numpy_determinsim():
    """Test numpy determinism"""
    try:
        from numpy import random
    except ImportError:
        return

    rand = random.randn()
    assert rand == 1.764052345967664, "Numpy not deterministic"


def test_torch_determinsim():
    """Test numpy determinism"""
    try:
        from torch import randn
    except ImportError:
        return

    rand = randn((1,)).item()
    assert rand == 1.5409960746765137, "Torch not deterministic"
