"""Unit tests for taint tracking (dict) functionality."""

import pytest

from ao.server.taint_ops import add_to_taint_dict_and_return as taint, get_taint
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintDict:
    """Test suite for taint tracking (dict) functionality."""

    def test_creation(self):
        """Test taint with dicts and various taint origins."""
        # Test with no taint
        d1 = {"a": 1, "b": 2}  # No wrapping for no taint
        assert dict(d1) == {"a": 1, "b": 2}
        assert get_taint(d1) == []

        # Test with single string taint
        d2 = taint({"x": 10}, ["source1"])
        assert dict(d2) == {"x": 10}
        assert get_taint(d2) == ["source1"]

        # Test with single int taint
        d3 = taint({"key": "value"}, [999])
        assert dict(d3) == {"key": "value"}
        assert get_taint(d3) == [999]

        # Test with list taint
        d4 = taint({}, ["source1", "source2"])
        assert dict(d4) == {}
        assert set(get_taint(d4)) == {"source1", "source2"}

        # Test with tainted values - dict's own taint is separate from value taint
        tainted_str = taint("tainted", ["value_source"])
        d5 = taint({"key": tainted_str, "normal": "value"}, ["dict_source"])
        # Dict has its own taint
        assert "dict_source" in get_taint(d5)
        # Value has its own taint (accessed via subscript)
        assert "value_source" in get_taint(d5["key"])

    def test_setitem_getitem(self):
        """Test __setitem__ and __getitem__ methods."""
        d = taint({"a": 1}, ["original"])

        # Set normal value
        d["b"] = 2
        assert d["b"] == 2
        assert dict(d) == {"a": 1, "b": 2}
        assert get_taint(d) == ["original"]

        # Set tainted value - dict keeps its own taint, value has its own
        tainted = taint("tainted", ["new_value"])
        d["c"] = tainted
        assert d["c"] == "tainted"
        # Dict still has its original taint
        assert "original" in get_taint(d)
        # Value has its own taint
        assert "new_value" in get_taint(d["c"])

        # Override existing key
        d["a"] = tainted
        assert d["a"] == "tainted"
        assert "new_value" in get_taint(d["a"])

    def test_delitem(self):
        """Test __delitem__ method."""
        tainted1 = taint("t1", ["value1"])
        tainted2 = taint("t2", ["value2"])
        d = taint({"a": tainted1, "b": "normal", "c": tainted2}, ["original"])

        # Delete key with normal value
        del d["b"]
        assert len(d) == 2
        assert "a" in d
        assert "c" in d
        # Dict still has its original taint
        assert "original" in get_taint(d)

        # Delete key with tainted value
        del d["a"]
        assert len(d) == 1
        assert "c" in d
        # Dict still has its original taint
        assert "original" in get_taint(d)

    def test_update(self):
        """Test update method."""
        d = taint({"a": 1}, ["original"])

        # Update with normal dict
        d.update({"b": 2, "c": 3})
        assert d["b"] == 2
        assert d["c"] == 3
        assert "original" in get_taint(d)

        # Update with tainted values
        tainted1 = taint("t1", ["update1"])
        tainted2 = taint("t2", ["update2"])
        d.update({"d": tainted1, "e": tainted2})
        assert d["d"] == "t1"
        assert d["e"] == "t2"
        # Dict keeps its own taint, values have their own
        assert "original" in get_taint(d)
        assert "update1" in get_taint(d["d"])
        assert "update2" in get_taint(d["e"])

        # Update with keyword arguments
        tainted3 = taint("t3", ["kwarg"])
        d.update(f=tainted3, g="normal")
        assert d["f"] == "t3"
        assert d["g"] == "normal"
        assert "kwarg" in get_taint(d["f"])

        # Update with list of tuples
        tainted4 = taint("t4", ["tuple"])
        d.update([("h", tainted4), ("i", "normal")])
        assert d["h"] == "t4"
        assert d["i"] == "normal"
        assert "tuple" in get_taint(d["h"])

    def test_setdefault(self):
        """Test setdefault method."""
        d = taint({"a": 1}, ["original"])

        # setdefault with existing key
        result = d.setdefault("a", 999)
        assert result == 1
        assert "original" in get_taint(d)

        # setdefault with new key (normal default)
        result = d.setdefault("b", 2)
        assert result == 2
        assert d["b"] == 2
        assert "original" in get_taint(d)

        # setdefault with new key (tainted default)
        tainted = taint("default", ["default_value"])
        result = d.setdefault("c", tainted)
        assert result == "default"
        assert d["c"] == "default"
        # Dict keeps its own taint
        assert "original" in get_taint(d)
        # Value has its own taint
        assert "default_value" in get_taint(d["c"])

        # setdefault with no default (None)
        result = d.setdefault("d")
        assert result is None
        assert d["d"] is None

    def test_pop(self):
        """Test pop method."""
        tainted1 = taint("t1", ["value1"])
        tainted2 = taint("t2", ["value2"])
        d = taint({"a": tainted1, "b": "normal", "c": tainted2}, ["original"])

        # Pop existing key
        popped = d.pop("b")
        assert popped == "normal"
        assert len(d) == 2
        # Dict still has its original taint
        assert "original" in get_taint(d)

        # Pop with default
        result = d.pop("missing", "default")
        assert result == "default"
        # Dict should be unchanged
        assert len(d) == 2

        # Pop missing key without default (should raise KeyError)
        with pytest.raises(KeyError):
            d.pop("missing")

    def test_popitem(self):
        """Test popitem method."""
        tainted1 = taint("t1", ["value1"])
        tainted2 = taint("t2", ["value2"])
        d = taint({"a": tainted1, "b": tainted2}, ["original"])

        # Pop an item
        key, value = d.popitem()
        assert key in ["a", "b"]
        assert value in ["t1", "t2"]
        assert len(d) == 1
        # Dict still has its original taint
        assert "original" in get_taint(d)

        # Pop last item
        d.popitem()
        assert len(d) == 0
        # Dict still has its original taint
        assert "original" in get_taint(d)

        # Pop from empty dict (should raise KeyError)
        with pytest.raises(KeyError):
            d.popitem()

    def test_clear(self):
        """Test clear method."""
        tainted = taint("tainted", ["value"])
        d = taint({"a": 1, "b": tainted}, ["original"])

        d.clear()
        assert len(d) == 0
        # Still retains the original dict taint
        assert "original" in get_taint(d)

    def test_get_raw(self):
        tainted = taint("tainted", ["value"])
        d = taint({"a": 1, "b": tainted, "c": "normal"}, ["original"])

        raw = d
        assert raw["a"] == 1
        assert raw["c"] == "normal"
        assert type(raw) == dict

    def test_dict_methods(self):
        """Test standard dict methods work correctly."""
        tainted = taint("tainted", ["value"])
        d = taint({"a": 1, "b": tainted, "c": 3}, ["original"])

        # keys()
        keys = list(d.keys())
        assert set(keys) == {"a", "b", "c"}

        # values()
        values = list(d.values())
        assert set(values) == {1, tainted, 3}

        # items()
        items = list(d.items())
        expected_items = {("a", 1), ("b", tainted), ("c", 3)}
        assert set(items) == expected_items

        # get()
        assert d.get("a") == 1
        assert d.get("b") == tainted
        assert d.get("missing") is None
        assert d.get("missing", "default") == "default"

    def test_dict_operations(self):
        """Test dict-like operations."""
        tainted = taint("tainted", ["value"])
        d = taint({"a": 1, "b": tainted}, ["original"])

        # len
        assert len(d) == 2

        # in operator
        assert "a" in d
        assert "b" in d
        assert "missing" not in d

        # iter (iterates over keys)
        keys = []
        for key in d:
            keys.append(key)
        assert set(keys) == {"a", "b"}

        # bool
        assert bool(d) is True
        empty = taint({}, ["empty"])
        assert bool(empty) is False

    def test_nested_taint_propagation(self):
        """Test taint propagation with nested structures."""
        # Create nested tainted items
        inner_dict = taint({"x": 1}, ["inner"])
        tainted_str = taint("nested", ["string"])

        outer = taint({"inner": inner_dict, "str": tainted_str}, ["outer"])

        # Outer dict has its own taint
        assert "outer" in get_taint(outer)

        # Nested items have their own taint (accessed via subscript)
        assert "inner" in get_taint(outer["inner"])
        assert "string" in get_taint(outer["str"])

        # Modify inner dict
        inner_dict["y"] = taint("new", ["added"])

        # Outer dict still has its original taint
        assert "outer" in get_taint(outer)

    def test_comparison_with_regular_dicts(self):
        """Test that tainted dicts behave like regular dicts in comparisons."""
        d1 = taint({"a": 1, "b": 2}, ["source1"])
        d2 = {"a": 1, "b": 2}
        d3 = taint({"a": 1, "b": 2}, ["source2"])

        # Should be equal regardless of taint
        assert d1 == d2
        assert d1 == d3
        assert d2 == d3

        # Different contents should not be equal
        d4 = taint({"a": 1, "b": 3}, ["source1"])
        assert d1 != d4

    def test_copy_operations(self):
        """Test copy and deepcopy operations."""
        import copy

        tainted = taint("tainted", ["value"])
        d = taint({"a": 1, "b": tainted}, ["original"])

        # Shallow copy using dict.copy()
        d_copy = d.copy()
        assert d_copy["a"] == 1
        assert d_copy["b"] == "tainted"

        # Deep copy
        d_deep = copy.deepcopy(d)
        assert d_deep["a"] == 1

    def test_fromkeys_classmethod(self):
        """Test dict.fromkeys() if available."""
        keys = ["a", "b", "c"]
        tainted_value = taint("default", ["default"])

        # This creates a regular dict
        result = dict.fromkeys(keys, tainted_value)
        assert result["a"] == "default"
        assert result["b"] == "default"
        assert result["c"] == "default"
