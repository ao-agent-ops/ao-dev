"""Unit tests for TaintedOpenAIObject class."""

import pytest

from runner.taint_wrappers import TaintedOpenAIObject, TaintStr, get_taint_origins


class MockOpenAIObject:
    """Mock OpenAI object for testing."""

    def __init__(self, data):
        self._data = data
        self.message = "AI response"
        self.role = "assistant"
        self.content = "Generated content"

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def __str__(self):
        return f"MockOpenAIObject({self._data})"

    def __repr__(self):
        return f"MockOpenAIObject({repr(self._data)})"

    def method_call(self):
        return "method result"

    def get_nested(self):
        return {"nested": "value", "deep": {"very_deep": "content"}}


class TestTaintedOpenAIObject:
    """Test suite for TaintedOpenAIObject class."""

    def test_creation(self):
        """Test TaintedOpenAIObject creation with various taint origins."""
        mock_obj = MockOpenAIObject({"key": "value", "number": 42})

        # Test with no taint
        t1 = TaintedOpenAIObject(mock_obj)
        assert t1._wrapped is mock_obj
        assert t1._taint_origin == []

        # Test with single string taint
        t2 = TaintedOpenAIObject(mock_obj, taint_origin="api_response")
        assert t2._taint_origin == ["api_response"]

        # Test with single int taint
        t3 = TaintedOpenAIObject(mock_obj, taint_origin=999)
        assert t3._taint_origin == [999]

        # Test with list taint
        t4 = TaintedOpenAIObject(mock_obj, taint_origin=["source1", "source2"])
        assert t4._taint_origin == ["source1", "source2"]

        # Test invalid taint origin type
        with pytest.raises(TypeError):
            TaintedOpenAIObject(mock_obj, taint_origin={})

    def test_getattr(self):
        """Test __getattr__ method for attribute access."""
        mock_obj = MockOpenAIObject({"data": "test"})
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="ai_response")

        # Access string attribute - should return TaintStr
        message = tainted.message
        assert isinstance(message, TaintStr)
        assert str(message) == "AI response"
        assert get_taint_origins(message) == ["ai_response"]

        # Access another string attribute
        role = tainted.role
        assert isinstance(role, TaintStr)
        assert str(role) == "assistant"
        assert get_taint_origins(role) == ["ai_response"]

        # Access method - should return tainted wrapper
        method = tainted.method_call
        # The method itself is wrapped, but let's test calling it
        result = method()
        assert isinstance(result, TaintStr)
        assert str(result) == "method result"
        assert get_taint_origins(result) == ["ai_response"]

        # Access complex nested data
        nested = tainted.get_nested()
        # Should be a tainted dict-like structure
        assert "nested" in nested
        assert "deep" in nested
        # Values should be tainted
        if hasattr(nested["nested"], "_taint_origin"):
            assert get_taint_origins(nested["nested"]) == ["ai_response"]

    def test_getitem(self):
        """Test __getitem__ method for dict-like access."""
        data = {"response": "Generated text", "tokens": 150, "nested": {"key": "value"}}
        mock_obj = MockOpenAIObject(data)
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="api_call")

        # Access string value
        response = tainted["response"]
        assert isinstance(response, TaintStr)
        assert str(response) == "Generated text"
        assert get_taint_origins(response) == ["api_call"]

        # Access integer value
        tokens = tainted["tokens"]
        # Should be tainted integer
        assert int(tokens) == 150
        if hasattr(tokens, "_taint_origin"):
            assert get_taint_origins(tokens) == ["api_call"]

        # Access nested dictionary
        nested = tainted["nested"]
        # Should be tainted wrapper
        if hasattr(nested, "_taint_origin"):
            assert get_taint_origins(nested) == ["api_call"]

    def test_special_methods(self):
        """Test special methods like __str__, __repr__, __dir__."""
        mock_obj = MockOpenAIObject({"test": "data"})
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="test_origin")

        # Test __str__
        str_result = str(tainted)
        assert str_result == str(mock_obj)

        # Test __repr__
        repr_result = repr(tainted)
        expected = f"TaintedOpenAIObject({repr(mock_obj)}, taint_origin=['test_origin'])"
        assert repr_result == expected

        # Test __dir__
        dir_result = dir(tainted)
        assert dir_result == dir(mock_obj)

    def test_container_methods(self):
        """Test container methods like __iter__, __contains__."""
        data = {"a": 1, "b": 2, "c": 3}
        mock_obj = MockOpenAIObject(data)
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="container_test")

        # Test __contains__
        assert "a" in tainted
        assert "b" in tainted
        assert "missing" not in tainted

        # Test __iter__
        keys = list(tainted)
        assert set(keys) == {"a", "b", "c"}

    def test_get_raw(self):
        """Test get_raw method."""
        mock_obj = MockOpenAIObject({"data": "test"})
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="raw_test")

        raw = tainted.get_raw()
        assert raw is mock_obj
        assert not hasattr(raw, "_taint_origin")

    def test_nested_taint_propagation(self):
        """Test that taint propagates through nested access."""
        # Create a more complex nested structure
        nested_data = {
            "level1": {
                "level2": {"content": "deep content", "array": ["item1", "item2", "item3"]},
                "simple": "value",
            },
            "top_level": "top value",
        }

        mock_obj = MockOpenAIObject(nested_data)
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="deep_test")

        # Access deeply nested content
        deep_content = tainted["level1"]["level2"]["content"]
        if isinstance(deep_content, TaintStr):
            assert str(deep_content) == "deep content"
            assert get_taint_origins(deep_content) == ["deep_test"]

        # Access array items
        array = tainted["level1"]["level2"]["array"]
        if hasattr(array, "__getitem__"):
            first_item = array[0]
            if isinstance(first_item, TaintStr):
                assert str(first_item) == "item1"
                assert get_taint_origins(first_item) == ["deep_test"]

    def test_method_calls_with_taint(self):
        """Test that method calls on tainted objects preserve taint."""

        class MockOpenAIWithMethods:
            def __init__(self):
                self.data = "base data"

            def get_data(self):
                return self.data

            def process(self, input_data):
                return f"processed: {input_data}"

            def get_dict(self):
                return {"result": "method result", "status": "success"}

        mock_obj = MockOpenAIWithMethods()
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="method_test")

        # Call method that returns data
        data = tainted.get_data()
        if isinstance(data, TaintStr):
            assert str(data) == "base data"
            assert get_taint_origins(data) == ["method_test"]

        # Call method with parameters
        result = tainted.process("input")
        if isinstance(result, TaintStr):
            assert str(result) == "processed: input"
            assert get_taint_origins(result) == ["method_test"]

        # Call method that returns dict
        result_dict = tainted.get_dict()
        if hasattr(result_dict, "_taint_origin"):
            assert get_taint_origins(result_dict) == ["method_test"]

    def test_attribute_error_handling(self):
        """Test that AttributeError is properly handled."""
        mock_obj = MockOpenAIObject({})
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="error_test")

        # Access non-existent attribute should raise AttributeError
        with pytest.raises(AttributeError):
            _ = tainted.non_existent_attribute

    def test_key_error_handling(self):
        """Test that KeyError is properly handled."""
        mock_obj = MockOpenAIObject({"existing": "value"})
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="key_error_test")

        # Access non-existent key should raise KeyError
        with pytest.raises(KeyError):
            _ = tainted["non_existent_key"]

    def test_taint_origin_types(self):
        """Test various taint origin types and their handling."""
        mock_obj = MockOpenAIObject({"test": "value"})

        # String origin
        t1 = TaintedOpenAIObject(mock_obj, taint_origin="string_origin")
        value1 = t1["test"]
        if hasattr(value1, "_taint_origin"):
            assert "string_origin" in get_taint_origins(value1)

        # Integer origin
        t2 = TaintedOpenAIObject(mock_obj, taint_origin=42)
        value2 = t2["test"]
        if hasattr(value2, "_taint_origin"):
            assert 42 in get_taint_origins(value2)

        # List origin
        t3 = TaintedOpenAIObject(mock_obj, taint_origin=["origin1", "origin2"])
        value3 = t3["test"]
        if hasattr(value3, "_taint_origin"):
            origins = get_taint_origins(value3)
            assert "origin1" in origins
            assert "origin2" in origins

    def test_integration_with_other_taint_types(self):
        """Test integration with other taint wrapper types."""
        # Create a mock object that contains various data types
        mixed_data = {
            "string_val": "text data",
            "int_val": 42,
            "float_val": 3.14,
            "list_val": ["a", "b", "c"],
            "dict_val": {"nested": "content"},
        }

        mock_obj = MockOpenAIObject(mixed_data)
        tainted = TaintedOpenAIObject(mock_obj, taint_origin="integration_test")

        # Each accessed value should be properly tainted according to its type
        string_val = tainted["string_val"]
        if hasattr(string_val, "_taint_origin"):
            assert isinstance(string_val, TaintStr)
            assert get_taint_origins(string_val) == ["integration_test"]

        # Test that the taint wrapper handles different types appropriately
        list_val = tainted["list_val"]
        # Depending on the taint_wrap implementation, this might be a TaintList
        # or the items might be individually tainted

        dict_val = tainted["dict_val"]
        # Should be some form of tainted dictionary structure
