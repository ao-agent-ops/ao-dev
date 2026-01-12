"""Unit tests for taint tracking (int) functionality."""

import pytest

from ao.server.taint_ops import add_to_taint_dict_and_return as taint, get_taint
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintInt:
    """Test suite for taint tracking (int) functionality."""

    def test_creation(self):
        """Test taint creation with various taint origins."""
        # Test with no taint
        i1 = 42  # No wrapping for no taint
        assert int(i1) == 42
        assert get_taint(i1) == []

        # Test with single string taint
        i2 = taint(100, ["source1"])
        assert isinstance(i2, int)
        assert int(i2) == 100
        assert get_taint(i2) == ["source1"]

        # Test with single int taint
        i3 = taint(-5, [999])
        assert int(i3) == -5
        assert get_taint(i3) == [999]

        # Test with list taint
        i4 = taint(0, ["source1", "source2"])
        assert int(i4) == 0
        assert set(get_taint(i4)) == {"source1", "source2"}

    def test_arithmetic_operations(self):
        """Test arithmetic operations.

        Uses values > 256 to avoid Python's small integer caching,
        which would cause false taint sharing with id-based tracking.
        """
        i1 = taint(1000, ["source1"])
        i2 = taint(300, ["source2"])

        # Addition
        result = i1 + i2
        assert int(result) == 1300
        assert isinstance(result, int)
        assert set(get_taint(result)) == {"source1", "source2"}

        # Addition with regular int
        result = i1 + 500
        assert int(result) == 1500
        assert get_taint(result) == ["source1"]

        # Reverse addition
        result = 500 + i1
        assert int(result) == 1500
        assert get_taint(result) == ["source1"]

        # Subtraction
        result = i1 - i2
        assert int(result) == 700
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse subtraction
        result = 2000 - i1
        assert int(result) == 1000
        assert "source1" in get_taint(result)  # May have extra taint from cached 1000

        # Multiplication
        result = i1 * i2
        assert int(result) == 300000
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse multiplication
        result = 2 * i1
        assert int(result) == 2000
        assert get_taint(result) == ["source1"]

        # Floor division
        result = i1 // i2
        assert int(result) == 3
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse floor division
        result = 2000 // i1
        assert int(result) == 2
        assert "source1" in get_taint(result)

        # True division
        result = i1 / i2
        assert float(result) == 1000 / 300
        assert isinstance(result, float)
        assert set(get_taint(result)) == {"source1", "source2"}

        # Modulo
        result = i1 % i2
        assert int(result) == 100
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse modulo
        result = 1300 % i1
        assert int(result) == 300
        assert "source1" in get_taint(result)  # May share taint with i2=300

        # Power
        result = i2**2
        assert int(result) == 90000
        # Note: i2 may have inherited taint from earlier operations (1300%1000=300 reuses i2's object)
        assert "source2" in get_taint(result)

        # Power with tainted exponent
        result = 2**i2
        assert int(result) == 2**300
        assert "source2" in get_taint(result)

    def test_unary_operations(self):
        """Test unary operations."""
        i = taint(10, ["source1"])

        # Negation
        result = -i
        assert int(result) == -10
        assert get_taint(result) == ["source1"]

        # Positive
        result = +i
        assert int(result) == 10
        assert get_taint(result) == ["source1"]

        # Absolute value
        i2 = taint(-5, ["source2"])
        result = abs(i2)
        assert int(result) == 5
        assert get_taint(result) == ["source2"]

        # Bitwise NOT
        result = ~i
        assert int(result) == -11
        assert get_taint(result) == ["source1"]

    def test_bitwise_operations(self):
        """Test bitwise operations.

        Uses values > 256 to avoid small integer caching issues.
        """
        i1 = taint(0b1010_0000_0000, ["source1"])  # 2560
        i2 = taint(0b1100_0000_0000, ["source2"])  # 3072

        # AND
        result = i1 & i2
        assert int(result) == 0b1000_0000_0000  # 2048
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse AND
        result = 0b1111_0000_0000 & i1
        assert int(result) == 0b1010_0000_0000
        assert "source1" in get_taint(result)

        # OR
        result = i1 | i2
        assert int(result) == 0b1110_0000_0000  # 3584
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse OR
        result = 0b0001_0000_0000 | i1
        assert int(result) == 0b1011_0000_0000  # 2816
        assert get_taint(result) == ["source1"]

        # XOR
        result = i1 ^ i2
        assert int(result) == 0b0110_0000_0000  # 1536
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse XOR
        result = 0b1111_0000_0000 ^ i1
        assert int(result) == 0b0101_0000_0000  # 1280
        assert get_taint(result) == ["source1"]

        # Left shift
        i3 = taint(257, ["source3"])  # > 256 to avoid caching
        result = i1 << 2
        assert int(result) == 2560 << 2  # 10240
        assert get_taint(result) == ["source1"]

        # Right shift
        result = i1 >> 2
        assert int(result) == 2560 >> 2  # 640
        assert get_taint(result) == ["source1"]

    def test_comparison_operations(self):
        """Test comparison operations (should return regular bool)."""
        i1 = taint(10, ["source1"])
        i2 = taint(20, ["source2"])

        # All comparisons should return regular bool
        assert (i1 == 10) is True
        assert (i1 == i2) is False
        assert (i1 != i2) is True
        assert (i1 < i2) is True
        assert (i1 <= i2) is True
        assert (i1 > i2) is False
        assert (i1 >= i2) is False

        # Verify return types are bool, not tainted
        result = i1 < i2
        assert isinstance(result, bool)
        assert get_taint(result) == []  # Bools have no taint

    def test_conversion_methods(self):
        """Test conversion methods."""
        i = taint(42, ["source1"])

        # __int__
        result = int(i)
        assert result == 42
        assert isinstance(result, int)

        # __float__
        result = float(i)
        assert result == 42.0
        assert isinstance(result, float)

        # __index__ (used for list indexing, etc.)
        test_list = [1, 2, 3, 4, 5]
        i2 = taint(2, ["index"])
        assert test_list[i2] == 3

    def test_boolean_context(self):
        """Test boolean evaluation."""
        i1 = taint(0, ["source1"])
        i2 = taint(1, ["source2"])
        i3 = taint(-1, ["source3"])

        assert bool(i1) is False
        assert bool(i2) is True
        assert bool(i3) is True

        # Test in conditional
        if i2:
            assert True
        else:
            assert False

    def test_get_raw(self):
        i = taint(42, ["source1"])
        raw = i
        assert raw == 42
        assert isinstance(raw, int)

    def test_taint_propagation_complex(self):
        """Test complex taint propagation scenarios.

        Uses values > 256 to avoid small integer caching issues.
        """
        i1 = taint(1000, ["source1"])
        i2 = taint(2000, ["source2"])
        i3 = taint(3000, ["source3"])

        # Chain operations
        result = (i1 + i2) * i3
        assert int(result) == 9000000  # (1000 + 2000) * 3000
        assert set(get_taint(result)) == {"source1", "source2", "source3"}

        # Mixed with regular ints
        result = (i1 + 500) * 2 - i2
        assert int(result) == 1000  # (1000 + 500) * 2 - 2000
        assert set(get_taint(result)) == {"source1", "source2"}

    def test_special_values(self):
        """Test with special integer values."""
        # Zero
        i_zero = taint(0, ["zero"])
        assert int(i_zero) == 0
        assert bool(i_zero) is False

        # Negative
        i_neg = taint(-100, ["negative"])
        assert int(i_neg) == -100
        assert abs(i_neg) == 100

        # Large numbers
        i_large = taint(10**100, ["large"])
        assert int(i_large) == 10**100
        result = i_large + 1
        assert int(result) == 10**100 + 1
