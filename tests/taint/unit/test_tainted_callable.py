"""Unit tests for TaintedCallable class."""

import pytest

from runner.taint_wrappers import (
    TaintedCallable,
    TaintStr,
    TaintInt,
    TaintList,
    TaintDict,
    get_taint_origins,
)


def sample_function(x, y):
    """Simple function for testing."""
    return x + y


def function_returns_dict():
    """Function that returns a dictionary."""
    return {"result": "success", "value": 42}


def function_returns_list():
    """Function that returns a list."""
    return ["item1", "item2", "item3"]


def function_with_kwargs(a, b, c=10):
    """Function that accepts keyword arguments."""
    return a + b + c


def function_returns_nested():
    """Function that returns nested data structures."""
    return {"data": {"nested": ["a", "b", "c"], "value": 123}, "status": "complete"}


def function_returns_none():
    """Function that returns None."""
    return None


def function_raises_error():
    """Function that raises an error."""
    raise ValueError("Test error")


class MockCallableClass:
    """Mock class with callable methods."""

    def __init__(self, base_value=0):
        self.base_value = base_value
        self.call_count = 0

    def method(self, x):
        """Instance method."""
        self.call_count += 1
        return self.base_value + x

    def method_with_kwargs(self, a, b=5, c=10):
        """Instance method with kwargs."""
        return self.base_value + a + b + c

    @classmethod
    def class_method(cls, value):
        """Class method."""
        return f"class result: {value}"

    @staticmethod
    def static_method(value):
        """Static method."""
        return value * 2

    def method_returns_self(self):
        """Method that returns self."""
        return self


class TestTaintedCallable:
    """Test suite for TaintedCallable class."""

    def test_creation(self):
        """Test TaintedCallable creation with various taint origins."""
        # Test with no taint
        t1 = TaintedCallable(sample_function)
        assert t1._wrapped is sample_function
        assert t1._taint_origin == []

        # Test with single string taint
        t2 = TaintedCallable(sample_function, taint_origin="user_input")
        assert t2._taint_origin == ["user_input"]

        # Test with single int taint
        t3 = TaintedCallable(sample_function, taint_origin=123)
        assert t3._taint_origin == [123]

        # Test with list taint
        t4 = TaintedCallable(sample_function, taint_origin=["source1", "source2"])
        assert t4._taint_origin == ["source1", "source2"]

        # Test invalid taint origin type
        with pytest.raises(TypeError):
            TaintedCallable(sample_function, taint_origin={})

    def test_call_simple_function(self):
        """Test calling a simple function through TaintedCallable."""
        tainted_func = TaintedCallable(sample_function, taint_origin="test_origin")

        # Call with simple arguments
        result = tainted_func(10, 20)
        assert result == 30
        # Result should be tainted
        assert isinstance(result, TaintInt)
        assert get_taint_origins(result) == ["test_origin"]

    def test_call_with_kwargs(self):
        """Test calling a function with keyword arguments."""
        tainted_func = TaintedCallable(function_with_kwargs, taint_origin="kwargs_test")

        # Call with positional and keyword arguments
        result = tainted_func(5, 10, c=15)
        assert result == 30
        assert isinstance(result, TaintInt)
        assert get_taint_origins(result) == ["kwargs_test"]

        # Call with all keyword arguments
        result2 = tainted_func(a=1, b=2, c=3)
        assert result2 == 6
        assert isinstance(result2, TaintInt)
        assert get_taint_origins(result2) == ["kwargs_test"]

    def test_function_returns_dict(self):
        """Test function that returns a dictionary."""
        tainted_func = TaintedCallable(function_returns_dict, taint_origin="dict_test")

        result = tainted_func()
        assert isinstance(result, TaintDict)
        assert result["result"] == "success"
        assert result["value"] == 42
        assert get_taint_origins(result) == ["dict_test"]

        # Check that individual items are also tainted
        assert isinstance(result["result"], TaintStr)
        assert get_taint_origins(result["result"]) == ["dict_test"]

    def test_function_returns_list(self):
        """Test function that returns a list."""
        tainted_func = TaintedCallable(function_returns_list, taint_origin="list_test")

        result = tainted_func()
        assert isinstance(result, TaintList)
        assert len(result) == 3
        assert result[0] == "item1"
        assert get_taint_origins(result) == ["list_test"]

        # Check that individual items are also tainted
        assert isinstance(result[0], TaintStr)
        assert get_taint_origins(result[0]) == ["list_test"]

    def test_function_returns_nested(self):
        """Test function that returns nested data structures."""
        tainted_func = TaintedCallable(function_returns_nested, taint_origin="nested_test")

        result = tainted_func()
        assert isinstance(result, TaintDict)
        assert "data" in result
        assert "status" in result

        # Check nested dictionary
        data = result["data"]
        assert isinstance(data, TaintDict)
        assert get_taint_origins(data) == ["nested_test"]

        # Check nested list
        nested_list = data["nested"]
        assert isinstance(nested_list, TaintList)
        assert len(nested_list) == 3
        assert get_taint_origins(nested_list) == ["nested_test"]

    def test_function_returns_none(self):
        """Test function that returns None."""
        tainted_func = TaintedCallable(function_returns_none, taint_origin="none_test")

        result = tainted_func()
        assert result is None

    def test_function_raises_error(self):
        """Test that exceptions are properly propagated."""
        tainted_func = TaintedCallable(function_raises_error, taint_origin="error_test")

        with pytest.raises(ValueError, match="Test error"):
            tainted_func()

    def test_instance_method(self):
        """Test wrapping instance methods."""
        obj = MockCallableClass(base_value=100)
        tainted_method = TaintedCallable(obj.method, taint_origin="method_test")

        result = tainted_method(50)
        assert result == 150
        assert isinstance(result, TaintInt)
        assert get_taint_origins(result) == ["method_test"]
        assert obj.call_count == 1

    def test_class_method(self):
        """Test wrapping class methods."""
        tainted_method = TaintedCallable(
            MockCallableClass.class_method, taint_origin="class_method_test"
        )

        result = tainted_method("test")
        assert result == "class result: test"
        assert isinstance(result, TaintStr)
        assert get_taint_origins(result) == ["class_method_test"]

    def test_static_method(self):
        """Test wrapping static methods."""
        tainted_method = TaintedCallable(
            MockCallableClass.static_method, taint_origin="static_test"
        )

        result = tainted_method(25)
        assert result == 50
        assert isinstance(result, TaintInt)
        assert get_taint_origins(result) == ["static_test"]

    def test_getattr(self):
        """Test __getattr__ delegation to wrapped callable."""

        def func_with_attr():
            return "result"

        func_with_attr.custom_attr = "custom_value"
        func_with_attr.__name__ = "func_with_attr"

        tainted_func = TaintedCallable(func_with_attr, taint_origin="attr_test")

        # Test accessing attributes
        assert tainted_func.custom_attr == "custom_value"
        assert tainted_func.__name__ == "func_with_attr"
        # __doc__ is handled specially by TaintedCallable's class

    def test_repr(self):
        """Test __repr__ method."""
        tainted_func = TaintedCallable(sample_function, taint_origin="repr_test")

        repr_str = repr(tainted_func)
        assert "TaintedCallable" in repr_str
        assert "sample_function" in repr_str
        assert "repr_test" in repr_str

    def test_get_raw(self):
        """Test get_raw method."""
        tainted_func = TaintedCallable(sample_function, taint_origin="raw_test")

        raw_func = tainted_func.get_raw()
        assert raw_func is sample_function
        assert not hasattr(raw_func, "_taint_origin")

    def test_lambda_function(self):
        """Test wrapping lambda functions."""
        lambda_func = lambda x, y: x * y
        tainted_lambda = TaintedCallable(lambda_func, taint_origin="lambda_test")

        result = tainted_lambda(3, 4)
        assert result == 12
        assert isinstance(result, TaintInt)
        assert get_taint_origins(result) == ["lambda_test"]

    def test_builtin_function(self):
        """Test wrapping built-in functions."""
        tainted_abs = TaintedCallable(abs, taint_origin="builtin_test")

        result = tainted_abs(-42)
        assert result == 42
        assert isinstance(result, TaintInt)
        assert get_taint_origins(result) == ["builtin_test"]

    def test_multiple_taint_origins(self):
        """Test callable with multiple taint origins."""
        tainted_func = TaintedCallable(
            sample_function, taint_origin=["origin1", "origin2", "origin3"]
        )

        result = tainted_func(10, 15)
        assert result == 25
        assert isinstance(result, TaintInt)
        origins = get_taint_origins(result)
        assert "origin1" in origins
        assert "origin2" in origins
        assert "origin3" in origins

    def test_function_with_tainted_arguments(self):
        """Test calling function with already tainted arguments."""
        # Create tainted arguments
        tainted_arg1 = TaintInt(10, taint_origin="arg1_taint")
        tainted_arg2 = TaintStr("test", taint_origin="arg2_taint")

        # Create tainted function
        def concat_func(num, text):
            return f"{text}: {num}"

        tainted_func = TaintedCallable(concat_func, taint_origin="func_taint")

        # Call with tainted arguments
        result = tainted_func(tainted_arg1, tainted_arg2)
        assert str(result) == "test: 10"

        # Result should have taint from function
        origins = get_taint_origins(result)
        assert "func_taint" in origins

    def test_method_returns_self(self):
        """Test method that returns self (for chaining)."""
        obj = MockCallableClass(base_value=50)
        tainted_method = TaintedCallable(obj.method_returns_self, taint_origin="chain_test")

        result = tainted_method()
        # Result should be the same object but tainted
        assert result.base_value == 50
        # The result should be tainted
        if hasattr(result, "_taint_origin"):
            assert get_taint_origins(result) == ["chain_test"]

    def test_generator_function(self):
        """Test wrapping generator functions."""

        def gen_func(n):
            for i in range(n):
                yield i * 2

        tainted_gen = TaintedCallable(gen_func, taint_origin="gen_test")

        # Call the tainted generator function
        result = tainted_gen(3)
        # Result should be a generator (wrapped)
        values = list(result)
        assert values == [0, 2, 4]

    def test_function_with_default_args(self):
        """Test function with default arguments."""

        def func_with_defaults(a, b=10, c=20):
            return a + b + c

        tainted_func = TaintedCallable(func_with_defaults, taint_origin="default_test")

        # Call with only required argument
        result1 = tainted_func(5)
        assert result1 == 35
        assert isinstance(result1, TaintInt)

        # Call with some optional arguments
        result2 = tainted_func(5, b=15)
        assert result2 == 40
        assert isinstance(result2, TaintInt)

        # Call with all arguments
        result3 = tainted_func(5, 15, 25)
        assert result3 == 45
        assert isinstance(result3, TaintInt)

    def test_function_with_varargs(self):
        """Test function with *args and **kwargs."""

        def varargs_func(*args, **kwargs):
            return {"args": args, "kwargs": kwargs, "sum": sum(args) + sum(kwargs.values())}

        tainted_func = TaintedCallable(varargs_func, taint_origin="varargs_test")

        result = tainted_func(1, 2, 3, x=4, y=5)
        assert isinstance(result, TaintDict)
        assert len(result["args"]) == 3
        assert len(result["kwargs"]) == 2
        assert result["sum"] == 15
        assert get_taint_origins(result) == ["varargs_test"]

    def test_nested_tainted_callables(self):
        """Test nesting TaintedCallable wrappers."""
        # First level of taint
        tainted_func1 = TaintedCallable(sample_function, taint_origin="level1")

        # Second level of taint (wrapping already tainted callable)
        tainted_func2 = TaintedCallable(tainted_func1, taint_origin="level2")

        result = tainted_func2(10, 20)
        assert result == 30
        # When nested, the inner TaintedCallable is called which applies its taint
        assert get_taint_origins(result) == ["level1"]

    def test_callable_object(self):
        """Test wrapping callable objects (objects with __call__ method)."""

        class CallableClass:
            def __init__(self, multiplier):
                self.multiplier = multiplier

            def __call__(self, value):
                return value * self.multiplier

        callable_obj = CallableClass(multiplier=3)
        tainted_callable = TaintedCallable(callable_obj, taint_origin="callable_obj_test")

        result = tainted_callable(10)
        assert result == 30
        assert isinstance(result, TaintInt)
        assert get_taint_origins(result) == ["callable_obj_test"]

    def test_partial_function(self):
        """Test wrapping partial functions."""
        from functools import partial

        # Create a partial function
        partial_func = partial(sample_function, 10)

        # Wrap it with TaintedCallable
        tainted_partial = TaintedCallable(partial_func, taint_origin="partial_test")

        result = tainted_partial(20)
        assert result == 30
        assert isinstance(result, TaintInt)
        assert get_taint_origins(result) == ["partial_test"]

    def test_decorated_function(self):
        """Test wrapping decorated functions."""

        def decorator(func):
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                return result * 2

            return wrapper

        @decorator
        def decorated_func(x):
            return x + 10

        tainted_decorated = TaintedCallable(decorated_func, taint_origin="decorated_test")

        result = tainted_decorated(5)
        assert result == 30  # (5 + 10) * 2
        assert isinstance(result, TaintInt)
        assert get_taint_origins(result) == ["decorated_test"]
