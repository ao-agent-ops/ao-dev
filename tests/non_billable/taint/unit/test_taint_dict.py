"""Unit tests for TaintWrapper (dict) functionality."""

import pytest

from ao.server.ast_helpers import taint_wrap, get_taint_origins, untaint_if_needed
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintDict:
    """Test suite for TaintWrapper (dict) functionality."""

    def test_creation(self):
        """Test taint_wrap with dicts and various taint origins."""
        # Test with no taint
        d1 = {"a": 1, "b": 2}  # No wrapping for no taint
        assert dict(d1) == {"a": 1, "b": 2}
        assert get_taint_origins(d1) == []

        # Test with single string taint
        d2 = taint_wrap({"x": 10}, taint_origin="source1")
        assert dict(d2) == {"x": 10}
        assert get_taint_origins(d2) == ["source1"]

        # Test with single int taint
        d3 = taint_wrap({"key": "value"}, taint_origin=999)
        assert dict(d3) == {"key": "value"}
        assert get_taint_origins(d3) == [999]

        # Test with list taint
        d4 = taint_wrap({}, taint_origin=["source1", "source2"])
        assert dict(d4) == {}
        assert set(get_taint_origins(d4)) == {"source1", "source2"}

        # Test with tainted values - dict's own taint is separate from value taint
        tainted_str = taint_wrap("tainted", taint_origin="value_source")
        d5 = taint_wrap({"key": tainted_str, "normal": "value"}, taint_origin="dict_source")
        # Dict has its own taint
        assert "dict_source" in get_taint_origins(d5)
        # Value has its own taint (accessed via subscript)
        assert "value_source" in get_taint_origins(d5["key"])

    def test_setitem_getitem(self):
        """Test __setitem__ and __getitem__ methods."""
        d = taint_wrap({"a": 1}, taint_origin="original")

        # Set normal value
        d["b"] = 2
        assert d["b"] == 2
        assert dict(d) == {"a": 1, "b": 2}
        assert get_taint_origins(d) == ["original"]

        # Set tainted value - dict keeps its own taint, value has its own
        tainted = taint_wrap("tainted", taint_origin="new_value")
        d["c"] = tainted
        assert d["c"] == "tainted"
        # Dict still has its original taint
        assert "original" in get_taint_origins(d)
        # Value has its own taint
        assert "new_value" in get_taint_origins(d["c"])

        # Override existing key
        d["a"] = tainted
        assert d["a"] == "tainted"
        assert "new_value" in get_taint_origins(d["a"])

    def test_delitem(self):
        """Test __delitem__ method."""
        tainted1 = taint_wrap("t1", taint_origin="value1")
        tainted2 = taint_wrap("t2", taint_origin="value2")
        d = taint_wrap({"a": tainted1, "b": "normal", "c": tainted2}, taint_origin="original")

        # Delete key with normal value
        del d["b"]
        assert len(d) == 2
        assert "a" in d
        assert "c" in d
        # Dict still has its original taint
        assert "original" in get_taint_origins(d)

        # Delete key with tainted value
        del d["a"]
        assert len(d) == 1
        assert "c" in d
        # Dict still has its original taint
        assert "original" in get_taint_origins(d)

    def test_update(self):
        """Test update method."""
        d = taint_wrap({"a": 1}, taint_origin="original")

        # Update with normal dict
        d.update({"b": 2, "c": 3})
        assert d["b"] == 2
        assert d["c"] == 3
        assert "original" in get_taint_origins(d)

        # Update with tainted values
        tainted1 = taint_wrap("t1", taint_origin="update1")
        tainted2 = taint_wrap("t2", taint_origin="update2")
        d.update({"d": tainted1, "e": tainted2})
        assert d["d"] == "t1"
        assert d["e"] == "t2"
        # Dict keeps its own taint, values have their own
        assert "original" in get_taint_origins(d)
        assert "update1" in get_taint_origins(d["d"])
        assert "update2" in get_taint_origins(d["e"])

        # Update with keyword arguments
        tainted3 = taint_wrap("t3", taint_origin="kwarg")
        d.update(f=tainted3, g="normal")
        assert d["f"] == "t3"
        assert d["g"] == "normal"
        assert "kwarg" in get_taint_origins(d["f"])

        # Update with list of tuples
        tainted4 = taint_wrap("t4", taint_origin="tuple")
        d.update([("h", tainted4), ("i", "normal")])
        assert d["h"] == "t4"
        assert d["i"] == "normal"
        assert "tuple" in get_taint_origins(d["h"])

    def test_setdefault(self):
        """Test setdefault method."""
        d = taint_wrap({"a": 1}, taint_origin="original")

        # setdefault with existing key
        result = d.setdefault("a", 999)
        assert result == 1
        assert "original" in get_taint_origins(d)

        # setdefault with new key (normal default)
        result = d.setdefault("b", 2)
        assert result == 2
        assert d["b"] == 2
        assert "original" in get_taint_origins(d)

        # setdefault with new key (tainted default)
        tainted = taint_wrap("default", taint_origin="default_value")
        result = d.setdefault("c", tainted)
        assert result == "default"
        assert d["c"] == "default"
        # Dict keeps its own taint
        assert "original" in get_taint_origins(d)
        # Value has its own taint
        assert "default_value" in get_taint_origins(d["c"])

        # setdefault with no default (None)
        result = d.setdefault("d")
        assert result is None
        assert d["d"] is None

    def test_pop(self):
        """Test pop method."""
        tainted1 = taint_wrap("t1", taint_origin="value1")
        tainted2 = taint_wrap("t2", taint_origin="value2")
        d = taint_wrap({"a": tainted1, "b": "normal", "c": tainted2}, taint_origin="original")

        # Pop existing key
        popped = d.pop("b")
        assert popped == "normal"
        assert len(d) == 2
        # Dict still has its original taint
        assert "original" in get_taint_origins(d)

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
        tainted1 = taint_wrap("t1", taint_origin="value1")
        tainted2 = taint_wrap("t2", taint_origin="value2")
        d = taint_wrap({"a": tainted1, "b": tainted2}, taint_origin="original")

        # Pop an item
        key, value = d.popitem()
        assert key in ["a", "b"]
        assert value in ["t1", "t2"]
        assert len(d) == 1
        # Dict still has its original taint
        assert "original" in get_taint_origins(d)

        # Pop last item
        d.popitem()
        assert len(d) == 0
        # Dict still has its original taint
        assert "original" in get_taint_origins(d)

        # Pop from empty dict (should raise KeyError)
        with pytest.raises(KeyError):
            d.popitem()

    def test_clear(self):
        """Test clear method."""
        tainted = taint_wrap("tainted", taint_origin="value")
        d = taint_wrap({"a": 1, "b": tainted}, taint_origin="original")

        d.clear()
        assert len(d) == 0
        # Still retains the original dict taint
        assert "original" in get_taint_origins(d)

    def test_get_raw(self):
        """Test getting raw object via untaint_if_needed."""
        tainted = taint_wrap("tainted", taint_origin="value")
        d = taint_wrap({"a": 1, "b": tainted, "c": "normal"}, taint_origin="original")

        raw = untaint_if_needed(d)
        assert raw["a"] == 1
        assert raw["c"] == "normal"
        # Raw dict from untaint_if_needed
        assert type(raw) == dict

    def test_dict_methods(self):
        """Test standard dict methods work correctly."""
        tainted = taint_wrap("tainted", taint_origin="value")
        d = taint_wrap({"a": 1, "b": tainted, "c": 3}, taint_origin="original")

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
        tainted = taint_wrap("tainted", taint_origin="value")
        d = taint_wrap({"a": 1, "b": tainted}, taint_origin="original")

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
        empty = taint_wrap({}, taint_origin="empty")
        assert bool(empty) is False

    def test_nested_taint_propagation(self):
        """Test taint propagation with nested structures."""
        # Create nested tainted items
        inner_dict = taint_wrap({"x": 1}, taint_origin="inner")
        tainted_str = taint_wrap("nested", taint_origin="string")

        outer = taint_wrap({"inner": inner_dict, "str": tainted_str}, taint_origin="outer")

        # Outer dict has its own taint
        assert "outer" in get_taint_origins(outer)

        # Nested items have their own taint (accessed via subscript)
        assert "inner" in get_taint_origins(outer["inner"])
        assert "string" in get_taint_origins(outer["str"])

        # Modify inner dict
        inner_dict["y"] = taint_wrap("new", taint_origin="added")

        # Outer dict still has its original taint
        assert "outer" in get_taint_origins(outer)

    def test_comparison_with_regular_dicts(self):
        """Test that TaintWrapper behaves like regular dict in comparisons."""
        d1 = taint_wrap({"a": 1, "b": 2}, taint_origin="source1")
        d2 = {"a": 1, "b": 2}
        d3 = taint_wrap({"a": 1, "b": 2}, taint_origin="source2")

        # Should be equal regardless of taint
        assert d1 == d2
        assert d1 == d3
        assert d2 == d3

        # Different contents should not be equal
        d4 = taint_wrap({"a": 1, "b": 3}, taint_origin="source1")
        assert d1 != d4

    def test_copy_operations(self):
        """Test copy and deepcopy operations."""
        import copy

        tainted = taint_wrap("tainted", taint_origin="value")
        d = taint_wrap({"a": 1, "b": tainted}, taint_origin="original")

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
        tainted_value = taint_wrap("default", taint_origin="default")

        # This creates a regular dict
        result = dict.fromkeys(keys, tainted_value)
        assert result["a"] == "default"
        assert result["b"] == "default"
        assert result["c"] == "default"
