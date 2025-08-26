"""Unit tests for TaintInt class."""

import pytest

from runner.taint_wrappers import TaintInt, TaintFloat, get_taint_origins, is_tainted


class TestTaintInt:
    """Test suite for TaintInt class."""

    def test_creation(self):
        """Test TaintInt creation with various taint origins."""
        # Test with no taint
        i1 = TaintInt(42)
        assert int(i1) == 42
        assert i1._taint_origin == []
        assert not is_tainted(i1)

        # Test with single string taint
        i2 = TaintInt(100, taint_origin="source1")
        assert int(i2) == 100
        assert i2._taint_origin == ["source1"]
        assert is_tainted(i2)

        # Test with single int taint
        i3 = TaintInt(-5, taint_origin=999)
        assert int(i3) == -5
        assert i3._taint_origin == [999]
        assert is_tainted(i3)

        # Test with list taint
        i4 = TaintInt(0, taint_origin=["source1", "source2"])
        assert int(i4) == 0
        assert i4._taint_origin == ["source1", "source2"]
        assert is_tainted(i4)

        # Test invalid taint origin type
        with pytest.raises(TypeError):
            TaintInt(10, taint_origin={})

    def test_arithmetic_operations(self):
        """Test arithmetic operations."""
        i1 = TaintInt(10, taint_origin="source1")
        i2 = TaintInt(3, taint_origin="source2")

        # Addition
        result = i1 + i2
        assert int(result) == 13
        assert isinstance(result, TaintInt)
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Addition with regular int
        result = i1 + 5
        assert int(result) == 15
        assert get_taint_origins(result) == ["source1"]

        # Reverse addition
        result = 5 + i1
        assert int(result) == 15
        assert get_taint_origins(result) == ["source1"]

        # Subtraction
        result = i1 - i2
        assert int(result) == 7
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse subtraction
        result = 20 - i1
        assert int(result) == 10
        assert get_taint_origins(result) == ["source1"]

        # Multiplication
        result = i1 * i2
        assert int(result) == 30
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse multiplication
        result = 2 * i1
        assert int(result) == 20
        assert get_taint_origins(result) == ["source1"]

        # Floor division
        result = i1 // i2
        assert int(result) == 3
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse floor division
        result = 20 // i1
        assert int(result) == 2
        assert get_taint_origins(result) == ["source1"]

        # True division (returns TaintFloat)
        result = i1 / i2
        assert float(result) == 10 / 3
        assert isinstance(result, TaintFloat)
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Modulo
        result = i1 % i2
        assert int(result) == 1
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse modulo
        result = 13 % i1
        assert int(result) == 3
        assert get_taint_origins(result) == ["source1"]

        # Power
        result = i2**2
        assert int(result) == 9
        assert get_taint_origins(result) == ["source2"]

        # Power with tainted exponent
        result = 2**i2
        assert int(result) == 8
        assert get_taint_origins(result) == ["source2"]

    def test_unary_operations(self):
        """Test unary operations."""
        i = TaintInt(10, taint_origin="source1")

        # Negation
        result = -i
        assert int(result) == -10
        assert get_taint_origins(result) == ["source1"]

        # Positive
        result = +i
        assert int(result) == 10
        assert get_taint_origins(result) == ["source1"]

        # Absolute value
        i2 = TaintInt(-5, taint_origin="source2")
        result = abs(i2)
        assert int(result) == 5
        assert get_taint_origins(result) == ["source2"]

        # Bitwise NOT
        result = ~i
        assert int(result) == -11
        assert get_taint_origins(result) == ["source1"]

    def test_bitwise_operations(self):
        """Test bitwise operations."""
        i1 = TaintInt(0b1010, taint_origin="source1")  # 10
        i2 = TaintInt(0b1100, taint_origin="source2")  # 12

        # AND
        result = i1 & i2
        assert int(result) == 0b1000  # 8
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse AND
        result = 0b1111 & i1
        assert int(result) == 0b1010
        assert get_taint_origins(result) == ["source1"]

        # OR
        result = i1 | i2
        assert int(result) == 0b1110  # 14
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse OR
        result = 0b0001 | i1
        assert int(result) == 0b1011
        assert get_taint_origins(result) == ["source1"]

        # XOR
        result = i1 ^ i2
        assert int(result) == 0b0110  # 6
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse XOR
        result = 0b1111 ^ i1
        assert int(result) == 0b0101
        assert get_taint_origins(result) == ["source1"]

        # Left shift
        i3 = TaintInt(2, taint_origin="source3")
        result = i1 << i3
        assert int(result) == 40  # 10 << 2
        assert set(get_taint_origins(result)) == {"source1", "source3"}

        # Right shift
        result = i1 >> i3
        assert int(result) == 2  # 10 >> 2
        assert set(get_taint_origins(result)) == {"source1", "source3"}

    def test_comparison_operations(self):
        """Test comparison operations (should return regular bool)."""
        i1 = TaintInt(10, taint_origin="source1")
        i2 = TaintInt(20, taint_origin="source2")

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
        assert not hasattr(result, "_taint_origin")

    def test_conversion_methods(self):
        """Test conversion methods."""
        i = TaintInt(42, taint_origin="source1")

        # __int__
        result = int(i)
        assert result == 42
        assert isinstance(result, int)
        assert not isinstance(result, TaintInt)

        # __float__
        result = float(i)
        assert result == 42.0
        assert isinstance(result, float)

        # __index__ (used for list indexing, etc.)
        test_list = [1, 2, 3, 4, 5]
        i2 = TaintInt(2, taint_origin="index")
        assert test_list[i2] == 3

    def test_boolean_context(self):
        """Test boolean evaluation."""
        i1 = TaintInt(0, taint_origin="source1")
        i2 = TaintInt(1, taint_origin="source2")
        i3 = TaintInt(-1, taint_origin="source3")

        assert bool(i1) is False
        assert bool(i2) is True
        assert bool(i3) is True

        # Test in conditional
        if i2:
            assert True
        else:
            assert False

    def test_get_raw(self):
        """Test get_raw method."""
        i = TaintInt(42, taint_origin="source1")
        raw = i.get_raw()
        assert raw == 42
        assert isinstance(raw, int)
        assert not isinstance(raw, TaintInt)

    def test_taint_propagation_complex(self):
        """Test complex taint propagation scenarios."""
        i1 = TaintInt(10, taint_origin="source1")
        i2 = TaintInt(20, taint_origin="source2")
        i3 = TaintInt(30, taint_origin="source3")

        # Chain operations
        result = (i1 + i2) * i3
        assert int(result) == 900  # (10 + 20) * 30
        assert set(get_taint_origins(result)) == {"source1", "source2", "source3"}

        # Mixed with regular ints
        result = (i1 + 5) * 2 - i2
        assert int(result) == 10  # (10 + 5) * 2 - 20
        assert set(get_taint_origins(result)) == {"source1", "source2"}

    def test_special_values(self):
        """Test with special integer values."""
        # Zero
        i_zero = TaintInt(0, taint_origin="zero")
        assert int(i_zero) == 0
        assert bool(i_zero) is False

        # Negative
        i_neg = TaintInt(-100, taint_origin="negative")
        assert int(i_neg) == -100
        assert abs(i_neg) == 100

        # Large numbers
        i_large = TaintInt(10**100, taint_origin="large")
        assert int(i_large) == 10**100
        result = i_large + 1
        assert int(result) == 10**100 + 1
