"""Unit tests for TaintFloat class."""

import pytest
import math

from ao.runner.taint_wrappers import TaintFloat, get_taint_origins, is_tainted


class TestTaintFloat:
    """Test suite for TaintFloat class."""

    def test_creation(self):
        """Test TaintFloat creation with various taint origins."""
        # Test with no taint
        f1 = TaintFloat(3.14)
        assert float(f1) == 3.14
        assert f1._taint_origin == []
        assert not is_tainted(f1)

        # Test with single string taint
        f2 = TaintFloat(2.718, taint_origin="source1")
        assert float(f2) == 2.718
        assert f2._taint_origin == ["source1"]
        assert is_tainted(f2)

        # Test with single int taint
        f3 = TaintFloat(-1.5, taint_origin=999)
        assert float(f3) == -1.5
        assert f3._taint_origin == [999]
        assert is_tainted(f3)

        # Test with list taint
        f4 = TaintFloat(0.0, taint_origin=["source1", "source2"])
        assert float(f4) == 0.0
        assert f4._taint_origin == ["source1", "source2"]
        assert is_tainted(f4)

        # Test invalid taint origin type
        with pytest.raises(TypeError):
            TaintFloat(1.0, taint_origin={})

    def test_arithmetic_operations(self):
        """Test arithmetic operations."""
        f1 = TaintFloat(10.5, taint_origin="source1")
        f2 = TaintFloat(2.5, taint_origin="source2")

        # Addition
        result = f1 + f2
        assert float(result) == 13.0
        assert isinstance(result, TaintFloat)
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Addition with regular float
        result = f1 + 4.5
        assert float(result) == 15.0
        assert get_taint_origins(result) == ["source1"]

        # Reverse addition
        result = 4.5 + f1
        assert float(result) == 15.0
        assert get_taint_origins(result) == ["source1"]

        # Subtraction
        result = f1 - f2
        assert float(result) == 8.0
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse subtraction
        result = 20.0 - f1
        assert float(result) == 9.5
        assert get_taint_origins(result) == ["source1"]

        # Multiplication
        result = f1 * f2
        assert float(result) == 26.25
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse multiplication
        result = 2.0 * f1
        assert float(result) == 21.0
        assert get_taint_origins(result) == ["source1"]

        # Floor division
        result = f1 // f2
        assert float(result) == 4.0
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse floor division
        result = 20.0 // f1
        assert float(result) == 1.0
        assert get_taint_origins(result) == ["source1"]

        # True division
        result = f1 / f2
        assert float(result) == 4.2
        assert isinstance(result, TaintFloat)
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse true division
        result = 21.0 / f1
        assert float(result) == 2.0
        assert get_taint_origins(result) == ["source1"]

        # Modulo
        result = f1 % f2
        assert float(result) == 0.5
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Reverse modulo
        result = 13.0 % f1
        assert float(result) == 2.5
        assert get_taint_origins(result) == ["source1"]

        # Power
        f3 = TaintFloat(2.0, taint_origin="source3")
        result = f3**3
        assert float(result) == 8.0
        assert get_taint_origins(result) == ["source3"]

        # Power with tainted exponent
        result = 2.0**f3
        assert float(result) == 4.0
        assert get_taint_origins(result) == ["source3"]

    def test_unary_operations(self):
        """Test unary operations."""
        f = TaintFloat(10.5, taint_origin="source1")

        # Negation
        result = -f
        assert float(result) == -10.5
        assert get_taint_origins(result) == ["source1"]

        # Positive
        result = +f
        assert float(result) == 10.5
        assert get_taint_origins(result) == ["source1"]

        # Absolute value
        f2 = TaintFloat(-5.5, taint_origin="source2")
        result = abs(f2)
        assert float(result) == 5.5
        assert get_taint_origins(result) == ["source2"]

    def test_comparison_operations(self):
        """Test comparison operations (should return regular bool)."""
        f1 = TaintFloat(10.5, taint_origin="source1")
        f2 = TaintFloat(20.5, taint_origin="source2")

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
        assert not hasattr(result, "_taint_origin")

    def test_conversion_methods(self):
        """Test conversion methods."""
        f = TaintFloat(42.7, taint_origin="source1")

        # __int__
        result = int(f)
        assert result == 42
        assert isinstance(result, int)

        # __float__
        result = float(f)
        assert result == 42.7
        assert isinstance(result, float)
        assert not isinstance(result, TaintFloat)

        # __index__ (should work for integer-valued floats)
        f2 = TaintFloat(3.0, taint_origin="index")
        test_list = [1, 2, 3, 4, 5]
        assert test_list[int(f2)] == 4

    def test_boolean_context(self):
        """Test boolean evaluation."""
        f1 = TaintFloat(0.0, taint_origin="source1")
        f2 = TaintFloat(1.5, taint_origin="source2")
        f3 = TaintFloat(-1.5, taint_origin="source3")

        assert bool(f1) is False
        assert bool(f2) is True
        assert bool(f3) is True

        # Test in conditional
        if f2:
            assert True
        else:
            assert False

    def test_get_raw(self):
        """Test get_raw method."""
        f = TaintFloat(42.5, taint_origin="source1")
        raw = f.get_raw()
        assert raw == 42.5
        assert isinstance(raw, float)
        assert not isinstance(raw, TaintFloat)

    def test_special_values(self):
        """Test with special float values."""
        # Zero
        f_zero = TaintFloat(0.0, taint_origin="zero")
        assert float(f_zero) == 0.0
        assert bool(f_zero) is False

        # Negative zero
        f_neg_zero = TaintFloat(-0.0, taint_origin="neg_zero")
        assert float(f_neg_zero) == -0.0

        # Infinity
        f_inf = TaintFloat(float("inf"), taint_origin="infinity")
        assert math.isinf(float(f_inf))

        # Negative infinity
        f_neg_inf = TaintFloat(float("-inf"), taint_origin="neg_infinity")
        assert math.isinf(float(f_neg_inf))

        # NaN
        f_nan = TaintFloat(float("nan"), taint_origin="not_a_number")
        assert math.isnan(float(f_nan))

        # Very small numbers
        f_small = TaintFloat(1e-308, taint_origin="small")
        assert float(f_small) == 1e-308

        # Very large numbers
        f_large = TaintFloat(1e308, taint_origin="large")
        assert float(f_large) == 1e308

    def test_taint_propagation_complex(self):
        """Test complex taint propagation scenarios."""
        f1 = TaintFloat(10.5, taint_origin="source1")
        f2 = TaintFloat(20.5, taint_origin="source2")
        f3 = TaintFloat(30.5, taint_origin="source3")

        # Chain operations
        result = (f1 + f2) * f3
        assert float(result) == (10.5 + 20.5) * 30.5
        assert set(get_taint_origins(result)) == {"source1", "source2", "source3"}

        # Mixed with regular floats
        result = (f1 + 5.5) * 2.0 - f2
        assert float(result) == (10.5 + 5.5) * 2.0 - 20.5
        assert set(get_taint_origins(result)) == {"source1", "source2"}

    def test_precision(self):
        """Test floating point precision is maintained."""
        f1 = TaintFloat(0.1, taint_origin="source1")
        f2 = TaintFloat(0.2, taint_origin="source2")

        # This should have the same precision issues as regular floats
        result = f1 + f2
        regular_result = 0.1 + 0.2
        assert float(result) == regular_result
        assert abs(float(result) - 0.3) < 1e-10  # Not exactly 0.3 due to float precision
