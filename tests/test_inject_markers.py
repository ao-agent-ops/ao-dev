"""
Test suite for inject_random_marker function.

Tests that inject_random_marker works recursively on various object types
and only injects markers into TaintStr objects that have position tracking.
"""

import pytest
from runner.taint_wrappers import (
    inject_random_marker,
    TaintStr,
    Position,
    get_random_positions,
)


class TestInjectRandomMarker:
    """Test cases for inject_random_marker function."""

    def test_regular_string_unchanged(self):
        """Regular strings should not be modified."""
        regular_str = "hello world"
        result = inject_random_marker(regular_str)
        assert result == "hello world"
        assert type(result) == str

    def test_taint_str_without_positions_unchanged(self):
        """TaintStr without positions should not be modified."""
        taint_str = TaintStr("hello world", taint_origin=["origin"])
        result = inject_random_marker(taint_str)
        assert result == "hello world"
        assert isinstance(result, TaintStr)
        assert result._taint_origin == ["origin"]

    def test_taint_str_with_positions_gets_markers(self):
        """TaintStr with positions should get markers injected."""
        positions = [Position(6, 11)]  # "world" in "hello world"
        taint_str = TaintStr("hello world", taint_origin=["origin"], random_pos=positions)
        result = inject_random_marker(taint_str)
        assert result == "hello >>world<<"
        assert isinstance(result, str)  # inject_random_marker_str returns str

    def test_list_with_mixed_strings(self):
        """Lists should be processed recursively, preserving structure."""
        positions = [Position(0, 5)]  # "hello"
        taint_str = TaintStr("hello", taint_origin=["origin"], random_pos=positions)
        regular_str = "world"

        input_list = [taint_str, regular_str, 42]
        result = inject_random_marker(input_list)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == ">>hello<<"  # TaintStr with positions -> marked
        assert result[1] == "world"  # regular string -> unchanged
        assert result[2] == 42  # number -> unchanged

    def test_tuple_preservation(self):
        """Tuples should be preserved as tuples."""
        positions = [Position(0, 3)]  # "foo"
        taint_str = TaintStr("foo", taint_origin=["origin"], random_pos=positions)

        input_tuple = (taint_str, "bar")
        result = inject_random_marker(input_tuple)

        assert isinstance(result, tuple)
        assert result == (">>foo<<", "bar")

    def test_dict_processing(self):
        """Dictionaries should be processed recursively."""
        positions = [Position(0, 3)]  # "key"
        taint_key = TaintStr("key", taint_origin=["origin"], random_pos=positions)
        positions_val = [Position(0, 5)]  # "value"
        taint_val = TaintStr("value", taint_origin=["origin"], random_pos=positions_val)

        input_dict = {"normal": taint_val, "another": "regular"}
        result = inject_random_marker(input_dict)

        assert isinstance(result, dict)
        assert result["normal"] == ">>value<<"
        assert result["another"] == "regular"

    def test_set_processing(self):
        """Sets should be processed recursively."""
        positions = [Position(0, 4)]  # "item"
        taint_str = TaintStr("item", taint_origin=["origin"], random_pos=positions)

        input_set = {taint_str, "regular", 123}
        result = inject_random_marker(input_set)

        assert isinstance(result, set)
        assert ">>item<<" in result
        assert "regular" in result
        assert 123 in result

    def test_nested_structures(self):
        """Complex nested structures should be processed correctly."""
        positions = [Position(0, 4)]  # "deep"
        taint_str = TaintStr("deep", taint_origin=["origin"], random_pos=positions)

        nested = {"level1": [{"level2": taint_str}, ("tuple", "with", taint_str)]}

        result = inject_random_marker(nested)

        assert isinstance(result, dict)
        assert isinstance(result["level1"], list)
        assert isinstance(result["level1"][0], dict)
        assert result["level1"][0]["level2"] == ">>deep<<"
        assert isinstance(result["level1"][1], tuple)
        # Debug: check what we actually got vs expected
        actual = result["level1"][1][2]
        expected = ">>deep<<"
        print(f"DEBUG: Expected {repr(expected)}, got {repr(actual)}")
        assert actual == expected

    def test_custom_object_with_dict(self):
        """Custom objects with __dict__ should be processed."""

        class CustomObj:
            def __init__(self):
                positions = [Position(0, 4)]  # "attr"
                self.tainted = TaintStr("attr", taint_origin=["origin"], random_pos=positions)
                self.normal = "regular"

        obj = CustomObj()
        result = inject_random_marker(obj)

        assert isinstance(result, CustomObj)
        assert result.tainted == ">>attr<<"
        assert result.normal == "regular"
        # Original should be unchanged
        assert obj.tainted != result.tainted

    def test_primitive_types_unchanged(self):
        """Primitive types should be returned unchanged."""
        primitives = [42, 3.14, True, False, None]

        for primitive in primitives:
            result = inject_random_marker(primitive)
            assert result == primitive
            assert type(result) == type(primitive)

    def test_circular_reference_handling(self):
        """Function should handle circular references without infinite recursion."""
        obj1 = {"name": "obj1"}
        obj2 = {"name": "obj2", "ref": obj1}
        obj1["ref"] = obj2  # Create circular reference

        # Should not raise RecursionError
        result = inject_random_marker(obj1)
        assert isinstance(result, dict)

    def test_max_depth_limit(self):
        """Function should respect max depth limit."""
        # Create a deeply nested structure
        nested = "base"
        for i in range(15):  # More than default max_depth of 10
            nested = [nested]

        # Should not cause issues due to depth limit
        result = inject_random_marker(nested, _max_depth=5)
        assert isinstance(result, list)

    def test_char_level_marking(self):
        """Function should support character-level marking."""
        positions = [Position(6, 11)]  # "world" in "hello world"
        taint_str = TaintStr("hello world", taint_origin=["origin"], random_pos=positions)

        result = inject_random_marker(taint_str, level="char")
        expected = "hello >>w<<>>o<<>>r<<>>l<<>>d<<"
        assert result == expected

    def test_empty_structures(self):
        """Empty structures should be handled correctly."""
        empty_list = []
        empty_dict = {}
        empty_set = set()
        empty_tuple = ()

        assert inject_random_marker(empty_list) == []
        assert inject_random_marker(empty_dict) == {}
        assert inject_random_marker(empty_set) == set()
        assert inject_random_marker(empty_tuple) == ()

    def test_mixed_taint_str_types(self):
        """Should handle mix of TaintStr with and without positions."""
        pos_taint = TaintStr("marked", taint_origin=["origin"], random_pos=[Position(0, 6)])
        no_pos_taint = TaintStr("unmarked", taint_origin=["origin"])

        input_list = [pos_taint, no_pos_taint]
        result = inject_random_marker(input_list)

        assert result[0] == ">>marked<<"
        assert result[1] == "unmarked"
        assert isinstance(result[1], TaintStr)  # Should preserve TaintStr type when no positions
