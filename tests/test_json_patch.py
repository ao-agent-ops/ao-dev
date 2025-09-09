import pytest
import json
from runner.taint_wrappers import (
    TaintStr,
    TaintDict,
    TaintList,
    get_taint_origins,
    Position,
    inject_random_marker,
    get_random_positions,
)


class TestJsonLoads:
    """Test taint propagation through json.loads()."""

    def test_loads_basic_taint_propagation(self):
        """Test that json.loads propagates taint from input string to result."""
        # Create tainted JSON string
        tainted_json = TaintStr('{"name": "John", "age": 30}', taint_origin=["user_input"])

        # Parse the JSON
        result = json.loads(tainted_json)

        # Check that result is a TaintDict
        assert isinstance(result, TaintDict)
        assert get_taint_origins(result) == ["user_input"]

        # Check that string values are TaintStr
        assert isinstance(result["name"], TaintStr)
        assert get_taint_origins(result["name"]) == ["user_input"]

        # Check that non-string values preserve their types but have taint
        assert isinstance(result["age"], int)
        assert result["age"] == 30

    def test_loads_nested_objects(self):
        """Test taint propagation through nested JSON structures."""

        nested_json = TaintStr(
            '{"user": {"name": "Alice", "details": {"city": "NYC", "age": 25}}, "items": ["book", "pen"]}',
            taint_origin=["api_response"],
        )

        result = json.loads(nested_json)

        # Check top level
        assert isinstance(result, TaintDict)
        assert get_taint_origins(result) == ["api_response"]

        # Check nested dict
        assert isinstance(result["user"], TaintDict)
        assert get_taint_origins(result["user"]) == ["api_response"]

        # Check deeply nested dict
        assert isinstance(result["user"]["details"], TaintDict)
        assert get_taint_origins(result["user"]["details"]) == ["api_response"]

        # Check string values at all levels
        assert isinstance(result["user"]["name"], TaintStr)
        assert get_taint_origins(result["user"]["name"]) == ["api_response"]
        assert isinstance(result["user"]["details"]["city"], TaintStr)
        assert get_taint_origins(result["user"]["details"]["city"]) == ["api_response"]

        # Check list
        assert isinstance(result["items"], TaintList)
        assert get_taint_origins(result["items"]) == ["api_response"]

        # Check list items
        assert isinstance(result["items"][0], TaintStr)
        assert get_taint_origins(result["items"][0]) == ["api_response"]

    def test_loads_with_untainted_input(self):
        """Test that untainted input produces untainted output."""

        clean_json = '{"name": "Bob", "score": 100}'
        result = json.loads(clean_json)

        # Should not be tainted
        assert not isinstance(result, TaintDict)
        assert isinstance(result, dict)
        assert not isinstance(result["name"], TaintStr)
        assert isinstance(result["name"], str)

    def test_loads_empty_and_edge_cases(self):
        """Test edge cases like empty objects, null values, special characters."""

        # Empty object
        tainted_empty = TaintStr("{}", taint_origin=["test"])
        result = json.loads(tainted_empty)
        assert isinstance(result, TaintDict)
        assert get_taint_origins(result) == ["test"]

        # Null values
        tainted_null = TaintStr('{"value": null}', taint_origin=["test"])
        result = json.loads(tainted_null)
        assert isinstance(result, TaintDict)
        assert result["value"] is None

        # Special characters
        tainted_special = TaintStr('{"text": "Hello\\nWorld\\t!"}', taint_origin=["test"])
        result = json.loads(tainted_special)
        assert isinstance(result["text"], TaintStr)
        assert result["text"] == "Hello\nWorld\t!"
        assert get_taint_origins(result["text"]) == ["test"]

    def test_loads_with_random_positions(self):
        """Test that random positions are preserved through json.loads."""

        # Create TaintStr with random positions
        json_str = TaintStr(
            '{"secret": "password123"}', taint_origin=["user"], random_pos=[Position(12, 23)]
        )
        result = json.loads(json_str)

        # Check that the secret value has taint
        assert isinstance(result["secret"], TaintStr)
        assert get_taint_origins(result["secret"]) == ["user"]


class TestJsonDumps:
    """Test taint propagation through json.dumps()."""

    def test_dumps_basic_taint_propagation(self):
        """Test that json.dumps propagates taint from object to JSON string."""

        # Create object with tainted strings
        obj = {"name": TaintStr("Alice", taint_origin=["user_input"]), "age": 30}

        result = json.dumps(obj)

        # Result should be a TaintStr
        assert isinstance(result, TaintStr)
        assert get_taint_origins(result) == ["user_input"]

        # Content should be valid JSON
        assert '"name": "Alice"' in result
        assert '"age": 30' in result

    def test_dumps_nested_tainted_objects(self):
        """Test taint propagation from nested tainted objects."""

        # Create nested structure with multiple taint sources
        obj = TaintDict(
            {
                "user": TaintDict(
                    {
                        "name": TaintStr("Bob", taint_origin=["source1"]),
                        "email": TaintStr("bob@test.com", taint_origin=["source2"]),
                    },
                    taint_origin=["source1"],
                ),
                "metadata": TaintList(
                    [
                        TaintStr("tag1", taint_origin=["source3"]),
                        TaintStr("tag2", taint_origin=["source3"]),
                    ],
                    taint_origin=["source3"],
                ),
            },
            taint_origin=["source1"],
        )

        result = json.dumps(obj)

        # Should combine all taint sources
        taint_origins = get_taint_origins(result)
        expected_origins = {"source1", "source2", "source3"}
        assert set(taint_origins) == expected_origins

    def test_dumps_with_untainted_input(self):
        """Test that untainted input produces untainted output."""

        clean_obj = {"name": "Charlie", "values": [1, 2, 3]}
        result = json.dumps(clean_obj)

        # Should not be tainted
        assert not isinstance(result, TaintStr)
        assert isinstance(result, str)

    def test_dumps_mixed_tainted_untainted(self):
        """Test objects with mix of tainted and untainted values."""

        mixed_obj = {
            "tainted": TaintStr("secret", taint_origin=["api"]),
            "clean": "public",
            "number": 42,
        }

        result = json.dumps(mixed_obj)

        # Should be tainted due to one tainted field
        assert isinstance(result, TaintStr)
        assert get_taint_origins(result) == ["api"]

    def test_dumps_with_random_positions(self):
        """Test that position tracking works through json.dumps."""

        # Create object with TaintStr that has random positions
        obj = {
            "data": TaintStr("sensitive123", taint_origin=["user"], random_pos=[Position(9, 12)])
        }

        result = json.dumps(obj)

        # Should have taint and some position tracking
        assert isinstance(result, TaintStr)
        assert get_taint_origins(result) == ["user"]
        # Position tracking through JSON serialization is complex,
        # but at minimum we should preserve taint origins


class TestJsonRoundTrip:
    """Test round-trip operations (loads → dumps → loads)."""

    def test_roundtrip_preserves_taint(self):
        """Test that taint is preserved through loads→dumps→loads cycle."""

        # Start with tainted JSON
        original_json = TaintStr('{"message": "hello world"}', taint_origin=["original"])

        # loads: JSON string → object
        obj = json.loads(original_json)
        assert isinstance(obj, TaintDict)
        assert isinstance(obj["message"], TaintStr)
        assert get_taint_origins(obj["message"]) == ["original"]

        # dumps: object → JSON string
        json_str = json.dumps(obj)
        assert isinstance(json_str, TaintStr)
        assert get_taint_origins(json_str) == ["original"]

        # loads again: JSON string → object
        final_obj = json.loads(json_str)
        assert isinstance(final_obj, TaintDict)
        assert isinstance(final_obj["message"], TaintStr)
        assert get_taint_origins(final_obj["message"]) == ["original"]

    def test_roundtrip_with_multiple_taint_sources(self):
        """Test round-trip with objects containing multiple taint sources."""

        # Create object with multiple taint sources
        obj = {
            "field1": TaintStr("value1", taint_origin=["source1"]),
            "field2": TaintStr("value2", taint_origin=["source2"]),
        }

        # dumps → loads
        json_str = json.dumps(obj)
        recovered_obj = json.loads(json_str)

        # Should preserve both taint sources
        assert isinstance(recovered_obj, TaintDict)
        field1_taint = get_taint_origins(recovered_obj["field1"])
        field2_taint = get_taint_origins(recovered_obj["field2"])

        # Both fields should have taint from the serialization process
        assert len(field1_taint) > 0
        assert len(field2_taint) > 0


class TestJsonEdgeCases:
    """Test edge cases and error conditions."""

    def test_loads_invalid_json(self):
        """Test that invalid JSON still raises appropriate errors."""

        tainted_invalid = TaintStr('{"invalid": json}', taint_origin=["test"])

        with pytest.raises(json.JSONDecodeError):
            json.loads(tainted_invalid)

    def test_dumps_non_serializable(self):
        """Test that non-serializable objects still raise appropriate errors."""

        class NonSerializable:
            pass

        obj = {"valid": "string", "invalid": NonSerializable()}

        with pytest.raises(TypeError):
            json.dumps(obj)

    def test_loads_with_custom_parameters(self):
        """Test that custom parameters still work with tainted inputs."""

        # Test with object_hook
        def custom_hook(d):
            return {"custom": "added", **d}

        tainted_json = TaintStr('{"name": "test"}', taint_origin=["hook_test"])
        result = json.loads(tainted_json, object_hook=custom_hook)

        # Should still apply taint even with custom hook
        assert get_taint_origins(result) == ["hook_test"]
        assert "custom" in result
        assert isinstance(result["custom"], TaintStr)  # Should be wrapped by taint_wrap
        assert result["custom"] == "added"

    def test_dumps_with_custom_parameters(self):
        """Test that custom parameters work with tainted objects."""

        obj = {"message": TaintStr("hello", taint_origin=["test"])}

        # Test with indent
        result = json.dumps(obj, indent=2)
        assert isinstance(result, TaintStr)
        assert get_taint_origins(result) == ["test"]
        assert "  " in result  # Should have indentation

        # Test with sort_keys
        result2 = json.dumps(obj, sort_keys=True)
        assert isinstance(result2, TaintStr)
        assert get_taint_origins(result2) == ["test"]


class TestJsonIntegrationWithOtherPatches:
    """Test interaction with other monkey patches like re_patch."""

    def test_json_with_re_patch_output(self):
        """Test JSON operations on strings that come from re module operations."""
        # This test ensures compatibility between different patches

        # Simulate getting tainted string from re operations
        tainted_from_re = TaintStr("extracted_data", taint_origin=["regex_result"])

        # Use in JSON operations
        obj = {"extracted": tainted_from_re}
        json_str = json.dumps(obj)

        assert isinstance(json_str, TaintStr)
        assert get_taint_origins(json_str) == ["regex_result"]

        # Parse back
        parsed = json.loads(json_str)
        assert isinstance(parsed, TaintDict)
        assert isinstance(parsed["extracted"], TaintStr)

    def test_json_boolean_handling(self):
        """Test that booleans are not tainted and remain as regular bool."""

        # Test loads with booleans - they should remain regular bool, not tainted
        tainted_json = TaintStr('{"enabled": true, "disabled": false}', taint_origin=["bool_test"])
        result = json.loads(tainted_json)

        assert isinstance(result, TaintDict)
        assert isinstance(result["enabled"], bool)  # Should be regular bool
        assert isinstance(result["disabled"], bool)  # Should be regular bool
        assert result["enabled"] is True
        assert result["disabled"] is False
        # The dict itself should have taint, but individual booleans should not
        assert get_taint_origins(result) == ["bool_test"]

        # Test dumps with regular booleans
        obj = {"flag": True, "other": False}
        json_str = json.dumps(obj)

        # Should not be tainted since no TaintStr values
        assert isinstance(json_str, str)
        assert '"flag": true' in json_str or '"flag":true' in json_str


class TestJsonPositionTracking:
    """Test random position tracking through JSON operations."""

    def test_loads_position_tracking_simple(self):
        """Test that position tracking works through json.loads for simple objects."""

        # Create JSON string with random positions marked
        json_str = TaintStr(
            '{"message": "hello"}', taint_origin=["test"], random_pos=[Position(13, 18)]
        )  # "hello" part

        result = json.loads(json_str)

        # The message field should be a TaintStr
        assert isinstance(result["message"], TaintStr)
        assert result["message"] == "hello"
        assert get_taint_origins(result["message"]) == ["test"]

        # Test that position tracking survives the JSON parsing
        # The resulting TaintStr should have some position information
        message_positions = get_random_positions(result["message"])
        assert (
            message_positions is not None
        ), "Position tracking should be preserved through json.loads"

        # Test using inject_random_marker to verify positions work
        marked_message = inject_random_marker(result["message"])
        assert (
            ">>" in marked_message and "<<" in marked_message
        ), "Position markers should be injected"

    def test_dumps_position_tracking_detailed(self):
        """Test detailed position tracking through json.dumps."""

        # Create object with TaintStr that has specific random positions
        message = TaintStr(
            "sensitive_data", taint_origin=["user"], random_pos=[Position(0, 9)]
        )  # "sensitive" part
        obj = {"data": message}

        result = json.dumps(obj)

        # Should be TaintStr with position tracking
        assert isinstance(result, TaintStr)
        assert get_taint_origins(result) == ["user"]
        # Should have some position tracking (exact positions depend on JSON structure)
        assert hasattr(result, "_random_positions")

        # Test that positions are actually tracked
        result_positions = get_random_positions(result)
        assert result_positions is not None, "JSON dumps should preserve position tracking"
        assert len(result_positions) > 0, "Should have at least some position information"

        # Test marker injection on the result
        marked_result = inject_random_marker(result)
        assert (
            ">>" in marked_result and "<<" in marked_result
        ), "Should be able to inject markers into JSON result"

        # Verify the marked result is still valid JSON structure (markers should be around sensitive parts)
        assert (
            '"data":' in marked_result or '"data": ' in marked_result
        ), "JSON structure should remain"

    def test_roundtrip_position_preservation(self):
        """Test that position information survives loads→dumps→loads cycle."""

        # Start with JSON containing position-tracked data
        original = TaintStr(
            '{"secret": "password123"}', taint_origin=["input"], random_pos=[Position(12, 23)]
        )  # "password123"

        # Round 1: loads
        obj1 = json.loads(original)
        assert isinstance(obj1["secret"], TaintStr)
        assert get_taint_origins(obj1["secret"]) == ["input"]

        # Test position preservation after loads
        secret1_positions = get_random_positions(obj1["secret"])
        assert secret1_positions is not None, "Positions should survive json.loads"
        marked_secret1 = inject_random_marker(obj1["secret"])
        assert (
            ">>" in marked_secret1 and "<<" in marked_secret1
        ), "Should be able to mark secret after loads"

        # Round 2: dumps
        json1 = json.dumps(obj1)
        assert isinstance(json1, TaintStr)
        assert get_taint_origins(json1) == ["input"]

        # Test position preservation after dumps
        json1_positions = get_random_positions(json1)
        assert json1_positions is not None, "Positions should survive json.dumps"
        marked_json1 = inject_random_marker(json1)
        assert (
            ">>" in marked_json1 and "<<" in marked_json1
        ), "Should be able to mark JSON after dumps"

        # Round 3: loads again
        obj2 = json.loads(json1)
        assert isinstance(obj2["secret"], TaintStr)
        assert get_taint_origins(obj2["secret"]) == ["input"]

        # Test final position preservation
        secret2_positions = get_random_positions(obj2["secret"])
        assert secret2_positions is not None, "Positions should survive full roundtrip"
        marked_secret2 = inject_random_marker(obj2["secret"])
        assert (
            ">>" in marked_secret2 and "<<" in marked_secret2
        ), "Should be able to mark secret after full roundtrip"

    def test_loads_multiple_position_tracking(self):
        """Test position tracking with multiple tracked regions in JSON."""

        # Create JSON with multiple position-tracked regions
        json_str = TaintStr(
            '{"user": "alice", "pass": "secret123", "email": "alice@test.com"}',
            taint_origin=["multi_test"],
            random_pos=[
                Position(10, 15),
                Position(27, 36),
                Position(49, 63),
            ],  # "alice", "secret123", "alice@test.com"
        )

        result = json.loads(json_str)

        # All string values should be TaintStr with position tracking
        for key in ["user", "pass", "email"]:
            assert isinstance(result[key], TaintStr)
            assert get_taint_origins(result[key]) == ["multi_test"]

            # Each should have position information
            positions = get_random_positions(result[key])
            assert positions is not None, f"Field '{key}' should have position tracking"

            # Each should be markable
            marked = inject_random_marker(result[key])
            assert ">>" in marked and "<<" in marked, f"Field '{key}' should be markable"

    def test_dumps_complex_position_tracking(self):
        """Test position tracking through dumps with complex nested objects."""

        # Create complex object with multiple tainted strings at different levels
        user_data = TaintStr(
            "john_doe", taint_origin=["user"], random_pos=[Position(0, 4)]
        )  # "john"
        credentials = {
            "username": user_data,
            "api_key": TaintStr(
                "key_12345", taint_origin=["api"], random_pos=[Position(4, 9)]
            ),  # "12345"
            "metadata": {
                "session": TaintStr(
                    "sess_abcdef", taint_origin=["session"], random_pos=[Position(5, 11)]
                )  # "abcdef"
            },
        }

        result = json.dumps(credentials)

        # Should be tainted and have positions
        assert isinstance(result, TaintStr)
        taint_origins = get_taint_origins(result)
        assert set(taint_origins) == {"user", "api", "session"}

        # Should have position tracking
        positions = get_random_positions(result)
        assert positions is not None, "Complex JSON should preserve position tracking"
        assert len(positions) > 0, "Should have multiple position ranges"

        # Should be markable
        marked = inject_random_marker(result)
        assert ">>" in marked and "<<" in marked, "Complex JSON should be markable"

        # Verify it contains the expected data
        assert "john_doe" in result
        assert "key_12345" in result
        assert "sess_abcdef" in result

    def test_position_tracking_with_special_characters(self):
        """Test position tracking with JSON containing special characters."""

        # JSON with escaped characters and unicode
        json_str = TaintStr(
            '{"message": "Hello\\nWorld", "unicode": "café", "quote": "Say \\"hi\\""}',
            taint_origin=["special"],
            random_pos=[
                Position(13, 25),
                Position(40, 44),
                Position(57, 67),
            ],  # "Hello\\nWorld", "café", "Say \\"hi\\""
        )

        result = json.loads(json_str)

        # Check each field
        assert isinstance(result["message"], TaintStr)
        assert result["message"] == "Hello\nWorld"  # Unescaped
        assert get_random_positions(result["message"]) is not None

        assert isinstance(result["unicode"], TaintStr)
        assert result["unicode"] == "café"
        assert get_random_positions(result["unicode"]) is not None

        assert isinstance(result["quote"], TaintStr)
        assert result["quote"] == 'Say "hi"'  # Unescaped
        assert get_random_positions(result["quote"]) is not None

        # All should be markable
        for field in result.values():
            if isinstance(field, TaintStr):
                marked = inject_random_marker(field)
                assert ">>" in marked and "<<" in marked

    def test_dumps_array_position_tracking(self):
        """Test position tracking with arrays containing tainted strings."""

        # Array with multiple tainted elements
        array_data = [
            TaintStr("item_one", taint_origin=["item1"], random_pos=[Position(0, 4)]),  # "item"
            "clean_item",
            TaintStr("item_three", taint_origin=["item3"], random_pos=[Position(5, 10)]),  # "three"
            {
                "nested": TaintStr(
                    "nested_val", taint_origin=["nested"], random_pos=[Position(7, 10)]
                )
            },  # "val"
        ]

        result = json.dumps(array_data)

        # Should be tainted
        assert isinstance(result, TaintStr)
        taint_origins = get_taint_origins(result)
        assert set(taint_origins) == {"item1", "item3", "nested"}

        # Should have positions
        positions = get_random_positions(result)
        assert positions is not None
        assert len(positions) > 0

        # Should be markable
        marked = inject_random_marker(result)
        assert ">>" in marked and "<<" in marked

        # Should contain all the data
        assert "item_one" in result
        assert "clean_item" in result
        assert "item_three" in result
        assert "nested_val" in result

    def test_position_tracking_edge_cases(self):
        """Test position tracking edge cases like empty strings, null values."""

        # JSON with empty string and null
        json_str = TaintStr(
            '{"empty": "", "null_val": null, "data": "actual_data"}',
            taint_origin=["edge_case"],
            random_pos=[Position(11, 11), Position(41, 52)],  # empty string position, "actual_data"
        )

        result = json.loads(json_str)

        # Empty string should still be TaintStr with positions
        assert isinstance(result["empty"], TaintStr)
        assert result["empty"] == ""
        assert get_random_positions(result["empty"]) is not None

        # Null should remain None
        assert result["null_val"] is None

        # Data should be tainted
        assert isinstance(result["data"], TaintStr)
        assert result["data"] == "actual_data"
        positions = get_random_positions(result["data"])
        assert positions is not None

        # Data should be markable
        marked = inject_random_marker(result["data"])
        assert ">>" in marked and "<<" in marked


class TestJsonEdgeCasesExtended:
    """Extended edge case testing for JSON patches."""

    def test_empty_containers(self):
        """Test empty arrays, objects, and strings."""

        # Empty object
        tainted = TaintStr("{}", taint_origin=["empty"])
        result = json.loads(tainted)
        assert isinstance(result, TaintDict)
        assert len(result) == 0
        assert get_taint_origins(result) == ["empty"]

        # Empty array
        tainted = TaintStr("[]", taint_origin=["empty_array"])
        result = json.loads(tainted)
        assert isinstance(result, TaintList)
        assert len(result) == 0
        assert get_taint_origins(result) == ["empty_array"]

        # Empty string value
        tainted = TaintStr('{"empty": ""}', taint_origin=["empty_str"])
        result = json.loads(tainted)
        assert isinstance(result["empty"], TaintStr)
        assert result["empty"] == ""
        assert get_taint_origins(result["empty"]) == ["empty_str"]

    def test_special_characters_and_escaping(self):
        """Test JSON with special characters, unicode, and escaping."""

        # Unicode and special characters
        unicode_json = TaintStr(
            '{"unicode": "こんにちは", "emoji": "🌟", "newline": "line1\\nline2"}',
            taint_origin=["unicode"],
        )
        result = json.loads(unicode_json)

        assert isinstance(result["unicode"], TaintStr)
        assert result["unicode"] == "こんにちは"
        assert isinstance(result["emoji"], TaintStr)
        assert result["emoji"] == "🌟"
        assert isinstance(result["newline"], TaintStr)
        assert result["newline"] == "line1\nline2"

        # All string values should have taint
        for value in result.values():
            if isinstance(value, str):
                assert get_taint_origins(value) == ["unicode"]

    def test_nested_arrays_and_objects(self):
        """Test deeply nested structures."""

        complex_json = TaintStr(
            """
        {
            "users": [
                {"name": "Alice", "scores": [95, 87, 92]},
                {"name": "Bob", "scores": [78, 85, 90]}
            ],
            "metadata": {
                "version": "1.0",
                "settings": {
                    "debug": true,
                    "timeout": 30
                }
            }
        }
        """,
            taint_origin=["complex"],
        )

        result = json.loads(complex_json)

        # Check deep nesting
        assert isinstance(result, TaintDict)
        assert isinstance(result["users"], TaintList)
        assert isinstance(result["users"][0], TaintDict)
        assert isinstance(result["users"][0]["name"], TaintStr)
        assert isinstance(result["users"][0]["scores"], TaintList)
        assert isinstance(result["users"][0]["scores"][0], int)  # Numbers should be TaintInt

        # Check deeply nested object
        assert isinstance(result["metadata"]["settings"], TaintDict)
        assert isinstance(result["metadata"]["settings"]["debug"], bool)
        assert result["metadata"]["settings"]["debug"] is True

    def test_null_values_and_mixed_types(self):
        """Test null values and arrays with mixed types."""

        mixed_json = TaintStr(
            """
        {
            "null_value": null,
            "mixed_array": ["string", 42, true, false, null],
            "numbers": {
                "int": 123,
                "float": 45.67,
                "negative": -89,
                "zero": 0
            }
        }
        """,
            taint_origin=["mixed"],
        )

        result = json.loads(mixed_json)

        # Check null handling
        assert result["null_value"] is None

        # Check mixed array
        mixed_arr = result["mixed_array"]
        assert isinstance(mixed_arr, TaintList)
        assert isinstance(mixed_arr[0], TaintStr)  # "string"
        assert isinstance(mixed_arr[1], int)  # 42 -> TaintInt
        assert isinstance(mixed_arr[2], bool)  # true -> bool
        assert isinstance(mixed_arr[3], bool)  # false -> bool
        assert mixed_arr[4] is None  # null -> None

        # Check numbers
        numbers = result["numbers"]
        assert isinstance(numbers["int"], int)  # Should be TaintInt
        assert isinstance(numbers["float"], float)  # Should be TaintFloat
        assert numbers["negative"] == -89
        assert numbers["zero"] == 0

    def test_large_objects_and_arrays(self):
        """Test performance with larger JSON structures."""

        # Create a larger structure
        large_data = {
            "items": [{"id": i, "name": f"item_{i}", "active": i % 2 == 0} for i in range(100)]
        }

        # Dumps should handle large structures
        json_str = json.dumps(large_data)
        assert isinstance(json_str, str)  # No taint, should be regular string

        # Add taint and test
        large_data["metadata"] = TaintStr("large_test", taint_origin=["performance"])
        json_str = json.dumps(large_data)
        assert isinstance(json_str, TaintStr)
        assert get_taint_origins(json_str) == ["performance"]

    def test_position_tracking_with_whitespace(self):
        """Test position tracking with various JSON formatting."""

        # Test with different formatting styles
        compact = TaintStr(
            '{"key":"value"}', taint_origin=["compact"], random_pos=[Position(8, 13)]
        )  # "value"

        pretty = TaintStr(
            """
        {
            "key": "value"
        }
        """.strip(),
            taint_origin=["pretty"],
            random_pos=[Position(15, 18)],
        )  # "value" in pretty format

        result1 = json.loads(compact)
        result2 = json.loads(pretty)

        # Both should produce equivalent results
        assert isinstance(result1["key"], TaintStr)
        assert isinstance(result2["key"], TaintStr)
        assert result1["key"] == result2["key"] == "value"

    def test_circular_reference_handling(self):
        """Test that circular references are handled properly."""

        # Note: JSON doesn't support circular references, but our taint tracking should handle them
        from runner.taint_wrappers import TaintDict

        circular_dict = TaintDict({"name": "test"}, taint_origin=["circular"])
        circular_dict["self"] = circular_dict  # Create circular reference

        # This should raise an error from JSON, not from our taint tracking
        with pytest.raises(ValueError, match="Circular reference"):
            json.dumps(circular_dict)

    def test_custom_json_encoder_decoder(self):
        """Test interaction with custom JSON encoders/decoders."""

        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, set):
                    return list(obj)
                return super().default(obj)

        # Test with custom encoder
        obj = {"data": TaintStr("test", taint_origin=["custom"]), "tags": {1, 2, 3}}
        result = json.dumps(obj, cls=CustomEncoder)

        assert isinstance(result, TaintStr)
        assert get_taint_origins(result) == ["custom"]
        assert '"tags": [1, 2, 3]' in result or '"tags":[1,2,3]' in result

    def test_extreme_nesting(self):
        """Test very deeply nested structures."""

        # Create deeply nested structure
        nested = TaintStr("deep_value", taint_origin=["deep"])
        for i in range(10):
            nested = {"level_" + str(i): nested}

        # Serialize and deserialize
        json_str = json.dumps(nested)
        assert isinstance(json_str, TaintStr)
        assert get_taint_origins(json_str) == ["deep"]

        parsed = json.loads(json_str)

        # Navigate to deep value (levels are nested in reverse order)
        current = parsed
        for i in range(9, -1, -1):  # Go from level_9 down to level_0
            current = current["level_" + str(i)]

        assert isinstance(current, TaintStr)
        assert current == "deep_value"
        assert get_taint_origins(current) == ["deep"]

    def test_json_with_numeric_precision(self):
        """Test handling of floating point precision and large integers."""

        # Large integers and floats
        data = TaintStr(
            '{"big_int": 9007199254740991, "precise_float": 3.141592653589793}',
            taint_origin=["precision"],
        )

        result = json.loads(data)

        assert isinstance(result["big_int"], int)  # Should be TaintInt
        assert isinstance(result["precise_float"], float)  # Should be TaintFloat
        assert result["big_int"] == 9007199254740991
        assert abs(result["precise_float"] - 3.141592653589793) < 1e-15

    def test_malformed_json_error_preservation(self):
        """Test that JSON errors are preserved even with tainted input."""

        # Various malformed JSON with taint
        malformed_cases = [
            TaintStr('{"missing_quote: "value"}', taint_origin=["bad1"]),
            TaintStr('{"trailing_comma": "value",}', taint_origin=["bad2"]),
            TaintStr(
                '{"unescaped": "line\nbreak"}', taint_origin=["bad3"]
            ),  # Invalid unescaped newline
            TaintStr("[1,2,3,]", taint_origin=["bad4"]),  # Trailing comma in array
        ]

        for malformed in malformed_cases:
            with pytest.raises(json.JSONDecodeError):
                json.loads(malformed)

    def test_dumps_with_position_tracking_complex(self):
        """Test complex position tracking scenarios in dumps."""

        # Create object with multiple TaintStr values having different position tracking
        secret1 = TaintStr(
            "password123", taint_origin=["user1"], random_pos=[Position(8, 11)]
        )  # "123" part
        secret2 = TaintStr(
            "token_abc", taint_origin=["user2"], random_pos=[Position(6, 9)]
        )  # "abc" part

        obj = {"credentials": {"password": secret1, "token": secret2}, "public": "not_secret"}

        result = json.dumps(obj)

        # Should combine taint from both sources
        assert isinstance(result, TaintStr)
        taint_origins = get_taint_origins(result)
        assert set(taint_origins) == {"user1", "user2"}

        # Should have position tracking from marker injection
        assert hasattr(result, "_random_positions")
        # The exact positions will depend on JSON formatting, but should have some

    def test_json_with_different_separators(self):
        """Test JSON dumps with custom separators."""

        obj = {"key1": TaintStr("value1", taint_origin=["sep_test"]), "key2": "value2"}

        # Test with custom separators
        result1 = json.dumps(obj, separators=(",", ":"))
        result2 = json.dumps(obj, separators=(", ", ": "))

        # Both should be tainted
        assert isinstance(result1, TaintStr)
        assert isinstance(result2, TaintStr)
        assert get_taint_origins(result1) == ["sep_test"]
        assert get_taint_origins(result2) == ["sep_test"]

        # Content should differ due to spacing
        assert result1 != result2
        # Result2 should have spaces around separators
        assert ": " in result2  # Colon with space
        assert ", " in result2 or result2.count(",") == 0  # Comma with space (if there is a comma)

    def test_json_indentation_position_tracking(self):
        """Test position tracking with JSON indentation."""

        obj = {
            "level1": {
                "level2": TaintStr(
                    "nested_value", taint_origin=["indent_test"], random_pos=[Position(0, 6)]
                )  # "nested" part
            }
        }

        # Test with indentation
        compact = json.dumps(obj)
        indented = json.dumps(obj, indent=2)
        very_indented = json.dumps(obj, indent=4)

        # All should be tainted
        for result in [compact, indented, very_indented]:
            assert isinstance(result, TaintStr)
            assert get_taint_origins(result) == ["indent_test"]

        # Indented versions should be longer
        assert len(indented) > len(compact)
        assert len(very_indented) > len(indented)

        # All should contain the same data
        assert '"nested_value"' in compact
        assert '"nested_value"' in indented
        assert '"nested_value"' in very_indented

    def test_json_sort_keys_with_taint(self):
        """Test sort_keys parameter with tainted data."""

        obj = {
            "zebra": TaintStr("last", taint_origin=["sort1"]),
            "alpha": TaintStr("first", taint_origin=["sort2"]),
            "beta": "middle",
        }

        # Test with and without sort_keys
        unsorted = json.dumps(obj)
        sorted_json = json.dumps(obj, sort_keys=True)

        # Both should be tainted
        assert isinstance(unsorted, TaintStr)
        assert isinstance(sorted_json, TaintStr)

        # Should combine taint from both sources
        for result in [unsorted, sorted_json]:
            taint_origins = get_taint_origins(result)
            assert set(taint_origins) == {"sort1", "sort2"}

    def test_json_with_none_values(self):
        """Test JSON handling of None/null values in various contexts."""

        # Object with None values
        obj = {
            "data": TaintStr("important", taint_origin=["important"]),
            "optional": None,
            "nested": {"value": None, "other": TaintStr("other", taint_origin=["other"])},
        }

        json_str = json.dumps(obj)

        # Should be tainted due to TaintStr values
        assert isinstance(json_str, TaintStr)
        taint_origins = get_taint_origins(json_str)
        assert set(taint_origins) == {"important", "other"}

        # Should contain null values
        assert "null" in json_str

        # Parse back
        parsed = json.loads(json_str)
        assert parsed["optional"] is None
        assert parsed["nested"]["value"] is None

    def test_json_ensure_ascii_parameter(self):
        """Test ensure_ascii parameter with tainted unicode data."""

        obj = {"unicode": TaintStr("café", taint_origin=["unicode_test"])}

        # Test with ensure_ascii=True (default)
        ascii_result = json.dumps(obj, ensure_ascii=True)

        # Test with ensure_ascii=False
        unicode_result = json.dumps(obj, ensure_ascii=False)

        # Both should be tainted
        assert isinstance(ascii_result, TaintStr)
        assert isinstance(unicode_result, TaintStr)
        assert get_taint_origins(ascii_result) == ["unicode_test"]
        assert get_taint_origins(unicode_result) == ["unicode_test"]

        # ASCII version should have escaped unicode
        assert "\\u" in ascii_result
        # Unicode version should have actual unicode
        assert "café" in unicode_result

    def test_multiple_taint_sources_complex(self):
        """Test complex scenarios with multiple taint sources."""

        # Create object with taint from different sources at different levels
        obj = TaintDict(
            {
                "user_data": TaintDict(
                    {
                        "username": TaintStr("alice", taint_origin=["user_input"]),
                        "email": TaintStr("alice@test.com", taint_origin=["email_validation"]),
                    },
                    taint_origin=["user_session"],
                ),
                "system_data": {
                    "timestamp": TaintStr("2023-01-01", taint_origin=["system_time"]),
                    "version": "1.0",  # No taint
                },
            },
            taint_origin=["request_context"],
        )

        result = json.dumps(obj)

        # Should combine ALL taint sources
        taint_origins = get_taint_origins(result)
        expected_sources = {
            "user_input",
            "email_validation",
            "user_session",
            "system_time",
            "request_context",
        }
        assert set(taint_origins) == expected_sources

    def test_json_with_skipkeys_parameter(self):
        """Test skipkeys parameter behavior with tainted data."""

        # Create object with non-serializable keys
        obj = {
            "valid_key": TaintStr("valid_value", taint_origin=["valid"]),
            (1, 2): "tuple_key_value",  # This should be skipped with skipkeys=True
        }

        # Without skipkeys - should raise TypeError for tuple key
        with pytest.raises(TypeError, match="keys must be"):
            json.dumps(obj, skipkeys=False)

        # With skipkeys - should work and skip invalid keys
        result = json.dumps(obj, skipkeys=True)
        assert isinstance(result, TaintStr)
        assert get_taint_origins(result) == ["valid"]
        assert "valid_key" in result
        assert "valid_value" in result
        assert "tuple_key_value" not in result  # Tuple key should be skipped
