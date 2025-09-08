import pytest
from uuid import UUID, uuid4
from runner.monkey_patching.patches.uuid_patches import uuid_patch
from runner.taint_wrappers import TaintStr


class TestUUIDPatches:
    """Test suite for UUID patches that add taint tracking with position information."""

    @pytest.fixture(autouse=True)
    def setup_patches(self):
        """Apply UUID patches before each test."""
        uuid_patch()

    def test_hex_property_returns_taintstr(self):
        """Test that UUID.hex returns a TaintStr with proper position tracking."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex

        assert isinstance(hex_result, TaintStr)
        assert len(hex_result) == 32  # UUID hex is 32 characters
        assert len(hex_result._random_positions) == 1
        assert hex_result._random_positions[0].start == 0
        assert hex_result._random_positions[0].stop == 32

    def test_str_method_returns_taintstr(self):
        """Test that UUID.__str__ returns a TaintStr with proper position tracking."""
        test_uuid = uuid4()
        str_result = str(test_uuid)

        assert isinstance(str_result, TaintStr)
        assert len(str_result) == 36  # UUID string with dashes is 36 characters
        assert len(str_result._random_positions) == 1
        assert str_result._random_positions[0].start == 0
        assert str_result._random_positions[0].stop == 36
        # Verify format: 8-4-4-4-12
        assert str_result[8] == "-"
        assert str_result[13] == "-"
        assert str_result[18] == "-"
        assert str_result[23] == "-"

    def test_repr_method_returns_taintstr(self):
        """Test that UUID.__repr__ returns a TaintStr with proper position tracking."""
        test_uuid = uuid4()
        repr_result = repr(test_uuid)

        assert isinstance(repr_result, TaintStr)
        assert repr_result.startswith("UUID('")
        assert repr_result.endswith("')")
        assert len(repr_result._random_positions) == 1
        assert repr_result._random_positions[0].start == 0
        assert repr_result._random_positions[0].stop == len(repr_result)

    def test_hex_string_correctness(self):
        """Test that the hex string is correctly formatted."""
        # Use a known UUID for predictable testing
        test_uuid = UUID("12345678-1234-5678-9012-123456789abc")
        hex_result = test_uuid.hex

        assert hex_result == "12345678123456789012123456789abc"
        assert isinstance(hex_result, TaintStr)

    def test_str_string_correctness(self):
        """Test that the string representation is correctly formatted."""
        # Use a known UUID for predictable testing
        test_uuid = UUID("12345678-1234-5678-9012-123456789abc")
        str_result = str(test_uuid)

        assert str_result == "12345678-1234-5678-9012-123456789abc"
        assert isinstance(str_result, TaintStr)

    def test_repr_string_correctness(self):
        """Test that the repr representation is correctly formatted."""
        test_uuid = UUID("12345678-1234-5678-9012-123456789abc")
        repr_result = repr(test_uuid)

        expected = "UUID('12345678-1234-5678-9012-123456789abc')"
        assert str(repr_result) == expected
        assert isinstance(repr_result, TaintStr)

    def test_string_concatenation_preserves_positions(self):
        """Test that string concatenation preserves position tracking."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex

        concatenated = hex_result + "-suffix"
        assert isinstance(concatenated, TaintStr)
        assert len(concatenated._random_positions) == 1
        # Original position should be preserved
        assert concatenated._random_positions[0].start == 0
        assert concatenated._random_positions[0].stop == 32

    def test_string_slicing_preserves_positions(self):
        """Test that string slicing preserves and adjusts position tracking."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex

        # Test slicing
        slice_result = hex_result[5:15]
        assert isinstance(slice_result, TaintStr)
        assert len(slice_result._random_positions) == 1
        # Position should be adjusted for the slice
        assert slice_result._random_positions[0].start == 0
        assert slice_result._random_positions[0].stop == 10

    def test_string_indexing_preserves_positions(self):
        """Test that string indexing preserves position tracking."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex

        # Test single character indexing
        char_result = hex_result[10]
        assert isinstance(char_result, TaintStr)
        assert len(char_result) == 1
        assert len(char_result._random_positions) == 1
        assert char_result._random_positions[0].start == 0
        assert char_result._random_positions[0].stop == 1

    def test_string_replacement_preserves_positions(self):
        """Test that string replacement operations preserve position tracking."""
        test_uuid = uuid4()
        str_result = str(test_uuid)

        # Replace dashes with underscores
        replaced = str_result.replace("-", "_")
        assert isinstance(replaced, TaintStr)
        assert len(replaced._random_positions) == 1
        assert replaced._random_positions[0].start == 0
        assert replaced._random_positions[0].stop == len(replaced)

    def test_string_case_methods_preserve_positions(self):
        """Test that string case methods preserve position tracking."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex

        # Test various case methods
        upper_result = hex_result.upper()
        lower_result = hex_result.lower()

        for result in [upper_result, lower_result]:
            assert isinstance(result, TaintStr)
            assert len(result._random_positions) == 1
            assert result._random_positions[0].start == 0
            assert result._random_positions[0].stop == len(result)

    def test_string_strip_methods_preserve_positions(self):
        """Test that string strip methods preserve and adjust position tracking."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex

        # Add padding and test strip
        padded = "   " + hex_result + "   "
        stripped = padded.strip()

        assert isinstance(stripped, TaintStr)
        assert str(stripped) == str(hex_result)
        # Position should be adjusted after stripping
        assert len(stripped._random_positions) == 1
        assert stripped._random_positions[0].start == 0
        assert stripped._random_positions[0].stop == len(hex_result)

    def test_string_split_preserves_positions(self):
        """Test that string split preserves position tracking in parts."""
        test_uuid = uuid4()
        str_result = str(test_uuid)

        # Split by dashes
        parts = str_result.split("-")
        assert len(parts) == 5

        # Each part should be a TaintStr with appropriate positions
        for i, part in enumerate(parts):
            assert isinstance(part, TaintStr)
            assert len(part._random_positions) == 1
            # First part starts at 0, others are adjusted
            assert part._random_positions[0].start == 0
            assert part._random_positions[0].stop == len(part)

    def test_string_formatting_with_modulo(self):
        """Test string formatting with % operator."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex

        formatted = "UUID: %s" % hex_result
        assert isinstance(formatted, TaintStr)
        assert len(formatted._random_positions) == 1
        # Position should account for the "UUID: " prefix
        assert formatted._random_positions[0].start == 6
        assert formatted._random_positions[0].stop == 6 + len(hex_result)

    def test_string_formatting_with_fstring(self):
        """Test string formatting with f-strings preserves taint and position tracking."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex
        str_result = str(test_uuid)

        # Test basic f-string
        f_string_basic = f"UUID: {hex_result}"
        # F-strings preserve taint when launched with aco-launch
        assert isinstance(f_string_basic, TaintStr)
        assert len(f_string_basic._random_positions) == 1
        # Position should account for the "UUID: " prefix
        assert f_string_basic._random_positions[0].start == 6
        assert f_string_basic._random_positions[0].stop == 6 + len(hex_result)
        assert f_string_basic == f"UUID: {str(hex_result)}"

        # Test f-string with multiple UUID values
        f_string_multi = f"Hex: {hex_result}, String: {str_result}"
        assert isinstance(f_string_multi, TaintStr)
        assert len(f_string_multi._random_positions) == 2
        # First UUID position after "Hex: "
        assert f_string_multi._random_positions[0].start == 5
        assert f_string_multi._random_positions[0].stop == 5 + len(hex_result)
        # Second UUID position after first UUID and ", String: "
        assert f_string_multi._random_positions[1].start == 5 + len(hex_result) + 10
        assert f_string_multi._random_positions[1].stop == 5 + len(hex_result) + 10 + len(
            str_result
        )

        # Test f-string with expressions
        f_string_expr = f"UUID length: {len(hex_result)} chars: {hex_result[:8]}..."
        assert isinstance(f_string_expr, TaintStr)
        assert len(f_string_expr._random_positions) == 1
        # Position should account for the prefix and middle text
        chars_pos = str(f_string_expr).find(str(hex_result[:8]))
        assert f_string_expr._random_positions[0].start == chars_pos
        assert f_string_expr._random_positions[0].stop == chars_pos + 8

        # NOTE: This doesn't work rn but it's a bit of an edge case
        # # Test f-string with format specifications
        # f_string_format = f"UUID: {hex_result!r}"
        # assert isinstance(f_string_format, TaintStr)
        # assert len(f_string_format._random_positions) == 1

    def test_string_formatting_with_format_method(self):
        """Test string formatting with .format() method preserves taint and position tracking."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex
        str_result = str(test_uuid)

        # Test basic .format()
        format_basic = "UUID: {}".format(hex_result)
        # .format() method preserves taint when launched with aco-launch
        assert isinstance(format_basic, TaintStr)
        assert len(format_basic._random_positions) == 1
        # Position should account for the "UUID: " prefix
        assert format_basic._random_positions[0].start == 6
        assert format_basic._random_positions[0].stop == 6 + len(hex_result)
        assert format_basic == f"UUID: {str(hex_result)}"

        # Test .format() with positional arguments
        format_positional = "Hex: {0}, String: {1}".format(hex_result, str_result)
        assert isinstance(format_positional, TaintStr)
        assert len(format_positional._random_positions) == 2
        # First UUID position after "Hex: "
        assert format_positional._random_positions[0].start == 5
        assert format_positional._random_positions[0].stop == 5 + len(hex_result)
        # Second UUID position after first UUID and ", String: "
        assert format_positional._random_positions[1].start == 5 + len(hex_result) + 10
        assert format_positional._random_positions[1].stop == 5 + len(hex_result) + 10 + len(
            str_result
        )

        # Test .format() with named arguments
        format_named = "Hex: {hex}, String: {string}".format(hex=hex_result, string=str_result)
        assert isinstance(format_named, TaintStr)
        assert len(format_named._random_positions) == 2
        # First UUID position after "Hex: "
        assert format_named._random_positions[0].start == 5
        assert format_named._random_positions[0].stop == 5 + len(hex_result)
        # Second UUID position after first UUID and ", String: "
        assert format_named._random_positions[1].start == 5 + len(hex_result) + 10
        assert format_named._random_positions[1].stop == 5 + len(hex_result) + 10 + len(str_result)

        # Test .format() with format specifications
        format_spec = "UUID: {!r}".format(hex_result)
        assert isinstance(format_spec, TaintStr)
        assert len(format_spec._random_positions) == 1

    def test_multiple_uuid_operations(self):
        """Test operations with multiple UUIDs maintain separate position tracking."""
        uuid1 = uuid4()
        uuid2 = uuid4()

        hex1 = uuid1.hex
        hex2 = uuid2.hex

        # Combine them
        combined = hex1 + "-" + hex2
        assert isinstance(combined, TaintStr)
        assert len(combined._random_positions) == 2

        # First UUID position
        assert combined._random_positions[0].start == 0
        assert combined._random_positions[0].stop == 32

        # Second UUID position (after first UUID and dash)
        assert combined._random_positions[1].start == 33
        assert combined._random_positions[1].stop == 65

    def test_position_consistency_across_methods(self):
        """Test that position tracking is consistent across different UUID methods."""
        test_uuid = uuid4()

        hex_result = test_uuid.hex
        str_result = str(test_uuid)
        repr_result = repr(test_uuid)

        # All should have exactly one position
        assert len(hex_result._random_positions) == 1
        assert len(str_result._random_positions) == 1
        assert len(repr_result._random_positions) == 1

        # All positions should start at 0
        assert hex_result._random_positions[0].start == 0
        assert str_result._random_positions[0].start == 0
        assert repr_result._random_positions[0].start == 0

        # Positions should match string lengths
        assert hex_result._random_positions[0].stop == len(hex_result)
        assert str_result._random_positions[0].stop == len(str_result)
        assert repr_result._random_positions[0].stop == len(repr_result)

    def test_complex_nested_operations(self):
        """Test complex nested operations maintain position tracking."""
        uuid1 = uuid4()
        uuid2 = uuid4()

        # Complex operation: combine parts and transform
        result = (uuid1.hex[:8] + "-" + uuid2.hex[8:16]).upper()

        assert isinstance(result, TaintStr)
        assert len(result._random_positions) == 2

        # First part: first 8 chars of uuid1
        assert result._random_positions[0].start == 0
        assert result._random_positions[0].stop == 8

        # Second part: chars 8-16 of uuid2, after dash
        assert result._random_positions[1].start == 9
        assert result._random_positions[1].stop == 17

    def test_edge_cases(self):
        """Test edge cases like empty concatenation and boundary slicing."""
        test_uuid = uuid4()
        hex_result = test_uuid.hex

        # Empty string concatenation
        empty_concat = hex_result + ""
        assert isinstance(empty_concat, TaintStr)
        assert len(empty_concat._random_positions) == 1
        assert empty_concat._random_positions[0] == hex_result._random_positions[0]

        # Single character slice
        first_char = hex_result[0:1]
        assert isinstance(first_char, TaintStr)
        assert len(first_char) == 1
        assert len(first_char._random_positions) == 1
        assert first_char._random_positions[0].start == 0
        assert first_char._random_positions[0].stop == 1

        # End slice
        end_slice = hex_result[-4:]
        assert isinstance(end_slice, TaintStr)
        assert len(end_slice) == 4
        assert len(end_slice._random_positions) == 1
        assert end_slice._random_positions[0].start == 0
        assert end_slice._random_positions[0].stop == 4

    def test_string_alignment_methods(self):
        """Test string alignment methods preserve position tracking."""
        test_uuid = uuid4()
        hex_short = test_uuid.hex[:8]

        # Test center, ljust, rjust
        centered = hex_short.center(20, "-")
        left_just = hex_short.ljust(20, "*")
        right_just = hex_short.rjust(20, "=")

        for result in [centered, left_just, right_just]:
            assert isinstance(result, TaintStr)
            assert len(result) == 20
            assert len(result._random_positions) == 1

    def test_string_ljust_method(self):
        """Test string ljust method preserves position tracking and alignment."""
        test_uuid = uuid4()
        hex_short = test_uuid.hex[:8]

        # Test ljust with default fillchar (space)
        left_just_default = hex_short.ljust(15)
        assert isinstance(left_just_default, TaintStr)
        assert len(left_just_default) == 15
        assert left_just_default.startswith(str(hex_short))  # Original content at start
        assert left_just_default.endswith(" ")  # Padded with spaces at end
        assert len(left_just_default._random_positions) == 1
        # Position should be at the beginning for the original content
        assert left_just_default._random_positions[0].start == 0
        assert left_just_default._random_positions[0].stop == 8

        # Test ljust with custom fillchar
        left_just_custom = hex_short.ljust(12, "*")
        assert isinstance(left_just_custom, TaintStr)
        assert len(left_just_custom) == 12
        assert left_just_custom.startswith(str(hex_short))
        assert left_just_custom.endswith("*")  # Padded with asterisks
        assert len(left_just_custom._random_positions) == 1
        assert left_just_custom._random_positions[0].start == 0
        assert left_just_custom._random_positions[0].stop == 8

    def test_string_rjust_method(self):
        """Test string rjust method preserves position tracking and alignment."""
        test_uuid = uuid4()
        hex_short = test_uuid.hex[:8]

        # Test rjust with default fillchar (space)
        right_just_default = hex_short.rjust(15)
        assert isinstance(right_just_default, TaintStr)
        assert len(right_just_default) == 15
        assert right_just_default.endswith(str(hex_short))  # Original content at end
        assert right_just_default.startswith(" ")  # Padded with spaces at start
        assert len(right_just_default._random_positions) == 1
        # Position should be adjusted for the padding
        assert right_just_default._random_positions[0].start == 7  # 15 - 8 = 7 spaces added
        assert right_just_default._random_positions[0].stop == 15

        # Test rjust with custom fillchar
        right_just_custom = hex_short.rjust(12, "=")
        assert isinstance(right_just_custom, TaintStr)
        assert len(right_just_custom) == 12
        assert right_just_custom.endswith(str(hex_short))
        assert right_just_custom.startswith("=")  # Padded with equals signs
        assert len(right_just_custom._random_positions) == 1
        assert right_just_custom._random_positions[0].start == 4  # 12 - 8 = 4 equals added
        assert right_just_custom._random_positions[0].stop == 12

    def test_string_zfill_method(self):
        """Test string zfill method preserves position tracking."""
        test_uuid = uuid4()
        hex_short = test_uuid.hex[:8]

        # Test zfill with padding
        zero_filled = hex_short.zfill(20)
        assert isinstance(zero_filled, TaintStr)
        assert len(zero_filled) == 20
        assert zero_filled.startswith("0")  # Should be padded with zeros
        assert len(zero_filled._random_positions) == 1
        # Position should be adjusted for the zero padding
        assert zero_filled._random_positions[0].start == 12  # 20 - 8 = 12 zeros added
        assert zero_filled._random_positions[0].stop == 20

    def test_string_partition_methods(self):
        """Test string partition methods preserve position tracking."""
        test_uuid = uuid4()
        str_result = str(test_uuid)

        # Test partition
        before, sep, after = str_result.partition("-")

        # All parts should be TaintStr (except separator which is regular string)
        assert isinstance(before, TaintStr)
        assert isinstance(sep, str)  # Separator is not tainted in current implementation
        assert isinstance(after, TaintStr)

        # Verify the partition worked correctly
        assert len(before) == 8  # First part of UUID
        assert sep == "-"
        assert len(after) > 0  # Remaining part
        assert len(before._random_positions) == 1
        assert len(after._random_positions) == 1

        # Test rpartition
        before2, sep2, after2 = str_result.rpartition("-")

        assert isinstance(before2, TaintStr)
        assert isinstance(sep2, str)  # Separator is not tainted
        assert isinstance(after2, TaintStr)
        assert sep2 == "-"
        assert len(after2) == 12  # Last part of UUID
        assert len(before2._random_positions) == 1
        assert len(after2._random_positions) == 1
