"""Unit tests for taint tracking (float) functionality."""

import pytest
import math

from ao.server.taint_ops import add_to_taint_dict_and_return as taint, get_taint
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintFloat:
    """Test suite for taint tracking (float) functionality."""

    def test_creation(self):
        """Test taint creation with various taint origins."""
        # Test with no taint
        f1 = 3.14  # No wrapping for no taint
        assert get_taint(f1) == []

        # Test with single string taint
        f2 = taint(2.718, ["source1"])
        assert isinstance(f2, float)
        assert float(f2) == 2.718
        assert get_taint(f2) == ["source1"]

        # Test with single int taint
        f3 = taint(-1.5, [999])
        assert float(f3) == -1.5
        assert get_taint(f3) == [999]

        # Test with list taint
        f4 = taint(0.0, ["source1", "source2"])
        assert float(f4) == 0.0
        assert set(get_taint(f4)) == {"source1", "source2"}

    def test_arithmetic_operations(self):
        """Test arithmetic operations."""
        f1 = taint(10.5, ["source1"])
        f2 = taint(2.5, ["source2"])

        # Addition
        result = f1 + f2
        assert float(result) == 13.0
        assert isinstance(result, float)
        assert set(get_taint(result)) == {"source1", "source2"}

        # Addition with regular float
        result = f1 + 4.5
        assert float(result) == 15.0
        assert get_taint(result) == ["source1"]

        # Reverse addition
        result = 4.5 + f1
        assert float(result) == 15.0
        assert get_taint(result) == ["source1"]

        # Subtraction
        result = f1 - f2
        assert float(result) == 8.0
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse subtraction
        result = 20.0 - f1
        assert float(result) == 9.5
        assert get_taint(result) == ["source1"]

        # Multiplication
        result = f1 * f2
        assert float(result) == 26.25
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse multiplication
        result = 2.0 * f1
        assert float(result) == 21.0
        assert get_taint(result) == ["source1"]

        # Floor division
        result = f1 // f2
        assert float(result) == 4.0
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse floor division
        result = 20.0 // f1
        assert float(result) == 1.0
        assert get_taint(result) == ["source1"]

        # True division
        result = f1 / f2
        assert float(result) == 4.2
        assert isinstance(result, float)
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse true division
        result = 21.0 / f1
        assert float(result) == 2.0
        assert get_taint(result) == ["source1"]

        # Modulo
        result = f1 % f2
        assert float(result) == 0.5
        assert set(get_taint(result)) == {"source1", "source2"}

        # Reverse modulo
        result = 13.0 % f1
        assert float(result) == 2.5
        assert get_taint(result) == ["source1"]

        # Power
        f3 = taint(2.0, ["source3"])
        result = f3**3
        assert float(result) == 8.0
        assert get_taint(result) == ["source3"]

        # Power with tainted exponent
        result = 2.0**f3
        assert float(result) == 4.0
        assert get_taint(result) == ["source3"]

    def test_unary_operations(self):
        """Test unary operations."""
        f = taint(10.5, ["source1"])

        # Negation
        result = -f
        assert float(result) == -10.5
        assert get_taint(result) == ["source1"]

        # Positive
        result = +f
        assert float(result) == 10.5
        assert get_taint(result) == ["source1"]

        # Absolute value
        f2 = taint(-5.5, ["source2"])
        result = abs(f2)
        assert float(result) == 5.5
        assert get_taint(result) == ["source2"]

    def test_comparison_operations(self):
        """Test comparison operations (should return regular bool)."""
        f1 = taint(10.5, ["source1"])
        f2 = taint(20.5, ["source2"])

        # All comparisons should return regular bool
        assert (f1 == 10.5) is True
        assert (f1 == f2) is False
        assert (f1 != f2) is True
        assert (f1 < f2) is True
        assert (f1 <= f2) is True
        assert (f1 > f2) is False
        assert (f1 >= f2) is False

        # Verify return types are bool, not tainted
        result = f1 < f2
        assert isinstance(result, bool)
        assert get_taint(result) == []  # Bools have no taint

    def test_conversion_methods(self):
        """Test conversion methods."""
        f = taint(42.7, ["source1"])

        # __int__
        result = int(f)
        assert result == 42
        assert isinstance(result, int)

        # __float__
        result = float(f)
        assert result == 42.7
        assert isinstance(result, float)

        # __index__ (should work for integer-valued floats)
        f2 = taint(3.0, ["index"])
        test_list = [1, 2, 3, 4, 5]
        assert test_list[int(f2)] == 4

    def test_boolean_context(self):
        """Test boolean evaluation."""
        f1 = taint(0.0, ["source1"])
        f2 = taint(1.5, ["source2"])
        f3 = taint(-1.5, ["source3"])

        assert bool(f1) is False
        assert bool(f2) is True
        assert bool(f3) is True

        # Test in conditional
        if f2:
            assert True
        else:
            assert False

    def test_get_raw(self):
        f = taint(42.5, ["source1"])
        raw = f
        assert raw == 42.5
        assert isinstance(raw, float)

    def test_special_values(self):
        """Test with special float values."""
        # Zero
        f_zero = taint(0.0, ["zero"])
        assert float(f_zero) == 0.0
        assert bool(f_zero) is False

        # Negative zero
        f_neg_zero = taint(-0.0, ["neg_zero"])
        assert float(f_neg_zero) == -0.0

        # Infinity
        f_inf = taint(float("inf"), ["infinity"])
        assert math.isinf(float(f_inf))

        # Negative infinity
        f_neg_inf = taint(float("-inf"), ["neg_infinity"])
        assert math.isinf(float(f_neg_inf))

        # NaN
        f_nan = taint(float("nan"), ["not_a_number"])
        assert math.isnan(float(f_nan))

        # Very small numbers
        f_small = taint(1e-308, ["small"])
        assert float(f_small) == 1e-308

        # Very large numbers
        f_large = taint(1e308, ["large"])
        assert float(f_large) == 1e308

    def test_taint_propagation_complex(self):
        """Test complex taint propagation scenarios."""
        f1 = taint(10.5, ["source1"])
        f2 = taint(20.5, ["source2"])
        f3 = taint(30.5, ["source3"])

        # Chain operations
        result = (f1 + f2) * f3
        assert float(result) == (10.5 + 20.5) * 30.5
        assert set(get_taint(result)) == {"source1", "source2", "source3"}

        # Mixed with regular floats
        result = (f1 + 5.5) * 2.0 - f2
        assert float(result) == (10.5 + 5.5) * 2.0 - 20.5
        assert set(get_taint(result)) == {"source1", "source2"}

    def test_precision(self):
        """Test floating point precision is maintained."""
        f1 = taint(0.1, ["source1"])
        f2 = taint(0.2, ["source2"])

        # This should have the same precision issues as regular floats
        result = f1 + f2
        regular_result = 0.1 + 0.2
        assert float(result) == regular_result
        assert abs(float(result) - 0.3) < 1e-10  # Not exactly 0.3 due to float precision
