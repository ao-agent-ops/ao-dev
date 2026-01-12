import pytest
import json
from ao.server.taint_ops import add_to_taint_dict_and_return as taint, get_taint
from ....utils import with_ast_rewriting


class TestJsonLoads:
    """Test taint propagation through json.loads()."""

    @with_ast_rewriting
    def test_AST_loads_basic_taint_propagation(self):
        """Test that AST rewriting correctly wraps json.loads to propagate taint."""
        # Create tainted JSON string
        tainted_json = taint('{"name": "John", "age": 30}', ["user_input"])

        # Parse the JSON - this will be rewritten to use exec_func
        result = json.loads(tainted_json)

        # Check that result has taint
        assert get_taint(result) != []
        assert get_taint(result) == ["user_input"]

        # Check that string values are tainted
        assert get_taint(result["name"]) != []
        assert get_taint(result["name"]) == ["user_input"]

        # Check that non-string values preserve their types but have taint
        assert isinstance(result["age"], int)
        assert result["age"] == 30

    @with_ast_rewriting
    def test_loads_basic_taint_propagation(self):
        """Test that json.loads propagates taint from input string to result."""
        # Create tainted JSON string
        tainted_json = taint('{"name": "John", "age": 30}', ["user_input"])

        # Parse the JSON
        result = json.loads(tainted_json)

        # Check that result has taint
        assert get_taint(result) != []
        assert get_taint(result) == ["user_input"]

        # Check that string values are tainted
        assert get_taint(result["name"]) != []
        assert get_taint(result["name"]) == ["user_input"]

        # Check that non-string values preserve their types but have taint
        assert isinstance(result["age"], int)
        assert result["age"] == 30

    @with_ast_rewriting
    def test_loads_nested_objects(self):
        """Test taint propagation through nested JSON structures."""

        nested_json = taint(
            '{"user": {"name": "Alice", "details": {"city": "NYC", "age": 25}}, "items": ["book", "pen"]}',
            taint_origin=["api_response"],
        )

        result = json.loads(nested_json)

        # Check top level
        assert get_taint(result) != []
        assert get_taint(result) == ["api_response"]

        # Check nested dict
        assert get_taint(result["user"]) != []
        assert get_taint(result["user"]) == ["api_response"]

        # Check deeply nested dict
        assert get_taint(result["user"]["details"]) != []
        assert get_taint(result["user"]["details"]) == ["api_response"]

        # Check string values at all levels
        assert get_taint(result["user"]["name"]) != []
        assert get_taint(result["user"]["name"]) == ["api_response"]
        assert get_taint(result["user"]["details"]["city"]) != []
        assert get_taint(result["user"]["details"]["city"]) == ["api_response"]

        # Check list
        assert get_taint(result["items"]) != []
        assert get_taint(result["items"]) == ["api_response"]

        # Check list items
        assert get_taint(result["items"][0]) != []
        assert get_taint(result["items"][0]) == ["api_response"]

    @with_ast_rewriting
    def test_loads_with_untainted_input(self):
        """Test that untainted input produces untainted output."""

        clean_json = '{"name": "Bob", "score": 100}'
        result = json.loads(clean_json)

        # Should not be tainted
        assert get_taint(result) == []
        assert isinstance(result, dict)
        assert get_taint(result["name"]) == []
        assert isinstance(result["name"], str)

    @with_ast_rewriting
    def test_loads_empty_and_edge_cases(self):
        """Test edge cases like empty objects, null values, special characters."""

        # Empty object
        tainted_empty = taint("{}", ["test"])
        result = json.loads(tainted_empty)
        assert get_taint(result) != []
        assert get_taint(result) == ["test"]

        # Null values
        tainted_null = taint('{"value": null}', ["test"])
        result = json.loads(tainted_null)
        assert get_taint(result) != []
        assert result["value"] is None

        # Special characters
        tainted_special = taint('{"text": "Hello\\nWorld\\t!"}', ["test"])
        result = json.loads(tainted_special)
        assert get_taint(result["text"]) != []
        assert result["text"] == "Hello\nWorld\t!"
        assert get_taint(result["text"]) == ["test"]

    @with_ast_rewriting
    def test_loads_with_tainted_json(self):
        """Test that taint is preserved through json.loads."""

        # Create tainted string
        json_str = taint('{"secret": "password123"}', ["user"])
        result = json.loads(json_str)

        # Check that the secret value has taint
        assert get_taint(result["secret"]) != []
        assert get_taint(result["secret"]) == ["user"]


class TestJsonDumps:
    """Test taint propagation through json.dumps()."""

    @with_ast_rewriting
    def test_dumps_basic_taint_propagation(self):
        """Test that json.dumps propagates taint from object to JSON string."""

        # Create object with tainted strings
        obj = {"name": taint("Alice", ["user_input"]), "age": 30}

        result = json.dumps(obj)

        # Result should be tainted
        assert get_taint(result) != []
        assert get_taint(result) == ["user_input"]

        # Content should be valid JSON
        assert '"name": "Alice"' in result
        assert '"age": 30' in result

    @with_ast_rewriting
    def test_dumps_nested_tainted_objects(self):
        """Test taint propagation from nested tainted objects."""

        # Create nested structure with multiple taint sources
        obj = taint(
            {
                "user": taint(
                    {
                        "name": taint("Bob", ["source1"]),
                        "email": taint("bob@test.com", ["source2"]),
                    },
                    taint_origin=["source1"],
                ),
                "metadata": taint(
                    [
                        taint("tag1", ["source3"]),
                        taint("tag2", ["source3"]),
                    ],
                    taint_origin=["source3"],
                ),
            },
            taint_origin=["source1"],
        )

        result = json.dumps(obj)

        # Should combine all taint sources
        taint_origins = get_taint(result)
        expected_origins = {"source1", "source2", "source3"}
        assert set(taint_origins) == expected_origins

    @with_ast_rewriting
    def test_dumps_with_untainted_input(self):
        """Test that untainted input produces untainted output."""

        clean_obj = {"name": "Charlie", "values": [1, 2, 3]}
        result = json.dumps(clean_obj)

        # Should not be tainted
        assert get_taint(result) == []
        assert isinstance(result, str)

    @with_ast_rewriting
    def test_dumps_mixed_tainted_untainted(self):
        """Test objects with mix of tainted and untainted values."""

        mixed_obj = {
            "tainted": taint("secret", ["api"]),
            "clean": "public",
            "number": 42,
        }

        result = json.dumps(mixed_obj)

        # Should be tainted due to one tainted field
        assert get_taint(result) != []
        assert get_taint(result) == ["api"]

    @with_ast_rewriting
    def test_dumps_with_tainted_data(self):
        """Test that taint works through json.dumps."""

        # Create object with TaintStr that has taint
        obj = {"data": taint("sensitive123", ["user"])}

        result = json.dumps(obj)

        # Should have taint
        assert get_taint(result) != []
        assert get_taint(result) == ["user"]


class TestJsonRoundTrip:
    """Test round-trip operations (loads → dumps → loads)."""

    @with_ast_rewriting
    def test_roundtrip_preserves_taint(self):
        """Test that taint is preserved through loads→dumps→loads cycle."""

        # Start with tainted JSON
        original_json = taint('{"message": "hello world"}', ["original"])

        # loads: JSON string → object
        obj = json.loads(original_json)
        assert get_taint(obj) != []
        assert get_taint(obj["message"]) != []
        assert get_taint(obj["message"]) == ["original"]

        # dumps: object → JSON string
        json_str = json.dumps(obj)
        assert get_taint(json_str) != []
        assert get_taint(json_str) == ["original"]

        # loads again: JSON string → object
        final_obj = json.loads(json_str)
        assert get_taint(final_obj) != []
        assert get_taint(final_obj["message"]) != []
        assert get_taint(final_obj["message"]) == ["original"]

    @with_ast_rewriting
    def test_roundtrip_with_multiple_taint_sources(self):
        """Test round-trip with objects containing multiple taint sources."""

        # Create object with multiple taint sources
        obj = {
            "field1": taint("value1", ["source1"]),
            "field2": taint("value2", ["source2"]),
        }

        # dumps → loads
        json_str = json.dumps(obj)
        recovered_obj = json.loads(json_str)

        # Should preserve both taint sources
        assert get_taint(recovered_obj) != []
        field1_taint = get_taint(recovered_obj["field1"])
        field2_taint = get_taint(recovered_obj["field2"])

        # Both fields should have taint from the serialization process
        assert len(field1_taint) > 0
        assert len(field2_taint) > 0


class TestJsonEdgeCases:
    """Test edge cases and error conditions."""

    @with_ast_rewriting
    def test_loads_invalid_json(self):
        """Test that invalid JSON still raises appropriate errors."""

        tainted_invalid = taint('{"invalid": json}', ["test"])

        with pytest.raises(json.JSONDecodeError):
            json.loads(tainted_invalid)

    @with_ast_rewriting
    def test_dumps_non_serializable(self):
        """Test that non-serializable objects still raise appropriate errors."""

        class NonSerializable:
            pass

        obj = {"valid": "string", "invalid": NonSerializable()}

        with pytest.raises(TypeError):
            json.dumps(obj)

    @with_ast_rewriting
    def test_loads_with_custom_parameters(self):
        """Test that custom parameters still work with tainted inputs."""

        # Test with object_hook
        def custom_hook(d):
            return {"custom": "added", **d}

        tainted_json = taint('{"name": "test"}', ["hook_test"])
        result = json.loads(tainted_json, object_hook=custom_hook)

        # Should still apply taint even with custom hook
        assert get_taint(result) == ["hook_test"]
        assert "custom" in result
        assert get_taint(result["custom"]) != []  # Should be wrapped by taint_wrap
        assert result["custom"] == "added"

    @with_ast_rewriting
    def test_dumps_with_custom_parameters(self):
        """Test that custom parameters work with tainted objects."""

        obj = {"message": taint("hello", ["test"])}

        # Test with indent
        result = json.dumps(obj, indent=2)
        assert get_taint(result) != []
        assert get_taint(result) == ["test"]
        assert "  " in result  # Should have indentation

        # Test with sort_keys
        result2 = json.dumps(obj, sort_keys=True)
        assert get_taint(result2) != []
        assert get_taint(result2) == ["test"]


class TestJsonIntegrationWithOtherPatches:
    """Test interaction with other monkey patches like re_patch."""

    @with_ast_rewriting
    def test_json_with_re_patch_output(self):
        """Test JSON operations on strings that come from re module operations."""
        # This test ensures compatibility between different patches

        # Simulate getting tainted string from re operations
        tainted_from_re = taint("extracted_data", ["regex_result"])

        # Use in JSON operations
        obj = {"extracted": tainted_from_re}
        json_str = json.dumps(obj)

        assert get_taint(json_str) != []
        assert get_taint(json_str) == ["regex_result"]

        # Parse back
        parsed = json.loads(json_str)
        assert get_taint(parsed) != []
        assert get_taint(parsed["extracted"]) != []

    @with_ast_rewriting
    def test_json_boolean_handling(self):
        """Test that booleans are not tainted and remain as regular bool."""

        # Test loads with booleans - they should remain regular bool, not tainted
        tainted_json = taint('{"enabled": true, "disabled": false}', ["bool_test"])
        result = json.loads(tainted_json)

        assert get_taint(result) != []
        assert isinstance(result["enabled"], bool)  # Should be regular bool
        assert isinstance(result["disabled"], bool)  # Should be regular bool
        assert result["enabled"] is True
        assert result["disabled"] is False
        # The dict itself should have taint, but individual booleans should not
        assert get_taint(result) == ["bool_test"]

        # Test dumps with regular booleans
        obj = {"flag": True, "other": False}
        json_str = json.dumps(obj)

        # Should not be tainted since no TaintStr values
        assert isinstance(json_str, str)
        assert '"flag": true' in json_str or '"flag":true' in json_str


class TestJsonEdgeCasesExtended:
    """Extended edge case testing for JSON patches."""

    @with_ast_rewriting
    def test_empty_containers(self):
        """Test empty arrays, objects, and strings."""

        # Empty object
        tainted = taint("{}", ["empty"])
        result = json.loads(tainted)
        assert get_taint(result) != []
        assert len(result) == 0
        assert get_taint(result) == ["empty"]

        # Empty array
        tainted = taint("[]", ["empty_array"])
        result = json.loads(tainted)
        assert get_taint(result) != []
        assert len(result) == 0
        assert get_taint(result) == ["empty_array"]

        # Empty string value
        tainted = taint('{"empty": ""}', ["empty_str"])
        result = json.loads(tainted)
        assert get_taint(result["empty"]) != []
        assert result["empty"] == ""
        assert get_taint(result["empty"]) == ["empty_str"]

    @with_ast_rewriting
    def test_special_characters_and_escaping(self):
        """Test JSON with special characters, unicode, and escaping."""

        # Unicode and special characters
        unicode_json = taint(
            '{"unicode": "こんにちは", "emoji": "🌟", "newline": "line1\\nline2"}',
            taint_origin=["unicode"],
        )
        result = json.loads(unicode_json)

        assert get_taint(result["unicode"]) != []
        assert result["unicode"] == "こんにちは"
        assert get_taint(result["emoji"]) != []
        assert result["emoji"] == "🌟"
        assert get_taint(result["newline"]) != []
        assert result["newline"] == "line1\nline2"

        # All string values should have taint
        for value in result.values():
            if isinstance(value, str):
                assert get_taint(value) == ["unicode"]

    @with_ast_rewriting
    def test_nested_arrays_and_objects(self):
        """Test deeply nested structures."""

        complex_json = taint(
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
        assert get_taint(result) != []
        assert get_taint(result["users"]) != []
        assert get_taint(result["users"][0]) != []
        assert get_taint(result["users"][0]["name"]) != []
        assert get_taint(result["users"][0]["scores"]) != []
        assert isinstance(result["users"][0]["scores"][0], int)  # Numbers should be TaintInt

        # Check deeply nested object
        assert get_taint(result["metadata"]["settings"]) != []
        assert isinstance(result["metadata"]["settings"]["debug"], bool)
        assert result["metadata"]["settings"]["debug"] is True

    @with_ast_rewriting
    def test_null_values_and_mixed_types(self):
        """Test null values and arrays with mixed types."""

        mixed_json = taint(
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
        assert get_taint(mixed_arr) != []
        assert get_taint(mixed_arr[0]) != []  # "string"
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

    @with_ast_rewriting
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
        large_data["metadata"] = taint("large_test", ["performance"])
        json_str = json.dumps(large_data)
        assert get_taint(json_str) != []
        assert get_taint(json_str) == ["performance"]

    @with_ast_rewriting
    def test_taint_with_whitespace(self):
        """Test taint with various JSON formatting."""

        # Test with different formatting styles
        compact = taint('{"key":"value"}', ["compact"])

        pretty = taint(
            """
        {
            "key": "value"
        }
        """.strip(),
            taint_origin=["pretty"],
        )

        result1 = json.loads(compact)
        result2 = json.loads(pretty)

        # Both should produce equivalent results
        assert get_taint(result1["key"]) != []
        assert get_taint(result2["key"]) != []
        assert result1["key"] == result2["key"] == "value"

    @with_ast_rewriting
    def test_circular_reference_handling(self):
        """Test that circular references are handled properly."""

        # Note: JSON doesn't support circular references, but our taint tracking should handle them
        circular_dict = taint({"name": "test"}, ["circular"])
        circular_dict["self"] = circular_dict  # Create circular reference

        # This should raise an error from JSON, not from our taint tracking
        with pytest.raises(ValueError, match="Circular reference"):
            json.dumps(circular_dict)

    @with_ast_rewriting
    def test_custom_json_encoder_decoder(self):
        """Test interaction with custom JSON encoders/decoders."""

        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, set):
                    return list(obj)
                return super().default(obj)

        # Test with custom encoder
        obj = {"data": taint("test", ["custom"]), "tags": {1, 2, 3}}
        result = json.dumps(obj, cls=CustomEncoder)

        assert get_taint(result) != []
        assert get_taint(result) == ["custom"]
        assert '"tags": [1, 2, 3]' in result or '"tags":[1,2,3]' in result

    @with_ast_rewriting
    def test_extreme_nesting(self):
        """Test very deeply nested structures."""

        # Create deeply nested structure
        nested = taint("deep_value", ["deep"])
        for i in range(10):
            nested = {"level_" + str(i): nested}

        # Serialize and deserialize
        json_str = json.dumps(nested)
        assert get_taint(json_str) != []
        assert get_taint(json_str) == ["deep"]

        parsed = json.loads(json_str)

        # Navigate to deep value (levels are nested in reverse order)
        current = parsed
        for i in range(9, -1, -1):  # Go from level_9 down to level_0
            current = current["level_" + str(i)]

        assert get_taint(current) != []
        assert current == "deep_value"
        assert get_taint(current) == ["deep"]

    @with_ast_rewriting
    def test_json_with_numeric_precision(self):
        """Test handling of floating point precision and large integers."""

        # Large integers and floats
        data = taint(
            '{"big_int": 9007199254740991, "precise_float": 3.141592653589793}',
            taint_origin=["precision"],
        )

        result = json.loads(data)

        assert isinstance(result["big_int"], int)  # Should be TaintInt
        assert isinstance(result["precise_float"], float)  # Should be TaintFloat
        assert result["big_int"] == 9007199254740991
        assert abs(result["precise_float"] - 3.141592653589793) < 1e-15

    @with_ast_rewriting
    def test_malformed_json_error_preservation(self):
        """Test that JSON errors are preserved even with tainted input."""

        # Various malformed JSON with taint
        malformed_cases = [
            taint('{"missing_quote: "value"}', ["bad1"]),
            taint('{"trailing_comma": "value",}', ["bad2"]),
            taint('{"unescaped": "line\nbreak"}', ["bad3"]),  # Invalid unescaped newline
            taint("[1,2,3,]", ["bad4"]),  # Trailing comma in array
        ]

        for malformed in malformed_cases:
            with pytest.raises(json.JSONDecodeError):
                json.loads(malformed)

    @with_ast_rewriting
    def test_dumps_with_taint_complex(self):
        """Test complex taint scenarios in dumps."""

        # Create object with multiple TaintStr values having different taint
        secret1 = taint("password123", ["user1"])
        secret2 = taint("token_abc", ["user2"])

        obj = {"credentials": {"password": secret1, "token": secret2}, "public": "not_secret"}

        result = json.dumps(obj)

        # Should combine taint from both sources
        assert get_taint(result) != []
        taint_origins = get_taint(result)
        assert set(taint_origins) == {"user1", "user2"}

    @with_ast_rewriting
    def test_json_with_different_separators(self):
        """Test JSON dumps with custom separators."""

        obj = {"key1": taint("value1", ["sep_test"]), "key2": "value2"}

        # Test with custom separators
        result1 = json.dumps(obj, separators=(",", ":"))
        result2 = json.dumps(obj, separators=(", ", ": "))

        # Both should be tainted
        assert get_taint(result1) != []
        assert get_taint(result2) != []
        assert get_taint(result1) == ["sep_test"]
        assert get_taint(result2) == ["sep_test"]

        # Content should differ due to spacing
        assert result1 != result2
        # Result2 should have spaces around separators
        assert ": " in result2  # Colon with space
        assert ", " in result2 or result2.count(",") == 0  # Comma with space (if there is a comma)

    @with_ast_rewriting
    def test_json_indentation_taint(self):
        """Test taint with JSON indentation."""

        obj = {"level1": {"level2": taint("nested_value", ["indent_test"])}}

        # Test with indentation
        compact = json.dumps(obj)
        indented = json.dumps(obj, indent=2)
        very_indented = json.dumps(obj, indent=4)

        # All should be tainted
        for result in [compact, indented, very_indented]:
            assert get_taint(result) != []
            assert get_taint(result) == ["indent_test"]

        # Indented versions should be longer
        assert len(indented) > len(compact)
        assert len(very_indented) > len(indented)

        # All should contain the same data
        assert '"nested_value"' in compact
        assert '"nested_value"' in indented
        assert '"nested_value"' in very_indented

    @with_ast_rewriting
    def test_json_sort_keys_with_taint(self):
        """Test sort_keys parameter with tainted data."""

        obj = {
            "zebra": taint("last", ["sort1"]),
            "alpha": taint("first", ["sort2"]),
            "beta": "middle",
        }

        # Test with and without sort_keys
        unsorted = json.dumps(obj)
        sorted_json = json.dumps(obj, sort_keys=True)

        # Both should be tainted
        assert get_taint(unsorted) != []
        assert get_taint(sorted_json) != []

        # Should combine taint from both sources
        for result in [unsorted, sorted_json]:
            taint_origins = get_taint(result)
            assert set(taint_origins) == {"sort1", "sort2"}

    @with_ast_rewriting
    def test_json_with_none_values(self):
        """Test JSON handling of None/null values in various contexts."""

        # Object with None values
        obj = {
            "data": taint("important", ["important"]),
            "optional": None,
            "nested": {"value": None, "other": taint("other", ["other"])},
        }

        json_str = json.dumps(obj)

        # Should be tainted due to TaintStr values
        assert get_taint(json_str) != []
        taint_origins = get_taint(json_str)
        assert set(taint_origins) == {"important", "other"}

        # Should contain null values
        assert "null" in json_str

        # Parse back
        parsed = json.loads(json_str)
        assert parsed["optional"] is None
        assert parsed["nested"]["value"] is None

    @with_ast_rewriting
    def test_json_ensure_ascii_parameter(self):
        """Test ensure_ascii parameter with tainted unicode data."""

        obj = {"unicode": taint("café", ["unicode_test"])}

        # Test with ensure_ascii=True (default)
        ascii_result = json.dumps(obj, ensure_ascii=True)

        # Test with ensure_ascii=False
        unicode_result = json.dumps(obj, ensure_ascii=False)

        # Both should be tainted
        assert get_taint(ascii_result) != []
        assert get_taint(unicode_result) != []
        assert get_taint(ascii_result) == ["unicode_test"]
        assert get_taint(unicode_result) == ["unicode_test"]

        # ASCII version should have escaped unicode
        assert "\\u" in ascii_result
        # Unicode version should have actual unicode
        assert "café" in unicode_result

    @with_ast_rewriting
    def test_multiple_taint_sources_complex(self):
        """Test complex scenarios with multiple taint sources."""

        # Create object with taint from different sources at different levels
        obj = taint(
            {
                "user_data": taint(
                    {
                        "username": taint("alice", ["user_input"]),
                        "email": taint("alice@test.com", ["email_validation"]),
                    },
                    taint_origin=["user_session"],
                ),
                "system_data": {
                    "timestamp": taint("2023-01-01", ["system_time"]),
                    "version": "1.0",  # No taint
                },
            },
            taint_origin=["request_context"],
        )

        result = json.dumps(obj)

        # Should combine ALL taint sources
        taint_origins = get_taint(result)
        expected_sources = {
            "user_input",
            "email_validation",
            "user_session",
            "system_time",
            "request_context",
        }
        assert set(taint_origins) == expected_sources

    @with_ast_rewriting
    def test_json_with_skipkeys_parameter(self):
        """Test skipkeys parameter behavior with tainted data."""

        # Create object with non-serializable keys
        obj = {
            "valid_key": taint("valid_value", ["valid"]),
            (1, 2): "tuple_key_value",  # This should be skipped with skipkeys=True
        }

        # Without skipkeys - should raise TypeError for tuple key
        with pytest.raises(TypeError, match="keys must be"):
            json.dumps(obj, skipkeys=False)

        # With skipkeys - should work and skip invalid keys
        result = json.dumps(obj, skipkeys=True)
        assert get_taint(result) != []
        assert get_taint(result) == ["valid"]
        assert "valid_key" in result
        assert "valid_value" in result
        assert "tuple_key_value" not in result  # Tuple key should be skipped
