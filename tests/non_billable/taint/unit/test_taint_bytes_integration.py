#!/usr/bin/env python3
"""Integration tests for tainted bytes with other taint types.

Tests the id-based taint tracking's handling of bytes objects.
"""

from ao.server.taint_ops import add_to_taint_dict_and_return as taint, get_taint
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintBytesIntegration:
    """Integration tests for tainted bytes."""

    def test_taint_bytes_with_taint():
        """Test that taint correctly handles bytes."""
        # Wrap plain bytes
        b = b"hello"
        tb = taint(b, ["source1"])
        assert tb == b"hello"
        assert get_taint(tb) == ["source1"]

        # Wrapping already tainted bytes returns the same object
        # (doesn't double-wrap, which is the expected behavior)
        tb2 = taint(tb, ["source2"])
        assert tb2 == tb  # Should be the same object

    def test_untaint_bytes():
        tb = taint(b"hello", ["source1"])
        raw = tb
        assert raw == b"hello"
        assert type(raw) == bytes
        assert not hasattr(raw, "_taint_origin")

    def test_taint_bytes_in_collections():
        """Test tainted bytes within lists and dicts."""
        # In list
        tb = taint(b"data", ["source1"])
        tl = taint([tb, b"other"], ["list_source"])

        assert len(tl) == 2
        assert tl[0] == b"data"
        # Check item's own taint is preserved
        assert "source1" in get_taint(tl[0])
        # Check list's own taint
        assert "list_source" in get_taint(tl)

        # In dict
        td = taint({"key": tb}, ["dict_source"])
        assert td["key"] == b"data"
        # Check item's own taint is preserved
        assert "source1" in get_taint(td["key"])
        # Check dict's own taint
        assert "dict_source" in get_taint(td)

    def test_mixed_taint_operations():
        """Test operations mixing tainted bytes with other taint types."""
        tb = taint(b"binary", ["bin_source"])
        ts = taint("text", ["str_source"])

        # Decode tainted bytes to tainted str
        decoded = tb.decode("utf-8")
        assert decoded == "binary"
        assert get_taint(decoded) == ["bin_source"]

        # Encode tainted str to bytes
        encoded = ts.encode("utf-8")
        assert encoded == b"text"

        # Mix in format operations
        fmt = taint("Data: %s", ["fmt_source"])
        result = fmt % decoded
        assert result == "Data: binary"
        assert set(get_taint(result)) == {"fmt_source", "bin_source"}

    def test_taint_bytes_with_io_operations():
        """Test tainted bytes behavior that could be used in I/O contexts."""
        # Simulate reading binary data
        data = b"\x00\x01\x02\xff"
        tb = taint(data, ["file_source"])

        # Hex representation (common for binary data display)
        hex_str = tb.hex()
        assert hex_str == "000102ff"
        assert get_taint(hex_str) == ["file_source"]

        # Slicing (common for parsing binary formats)
        header = tb[:2]
        payload = tb[2:]

        assert header == b"\x00\x01"
        assert payload == b"\x02\xff"
        assert get_taint(header) == ["file_source"]
        assert get_taint(payload) == ["file_source"]

    def test_taint_bytes_chaining():
        """Test that taint is preserved through multiple operations."""
        tb = taint(b"  HELLO WORLD  ", ["source1"])

        # Chain multiple operations
        result = tb.strip().lower().replace(b"world", b"python").center(20, b"*")

        assert result == b"****hello python****"
        assert "source1" in get_taint(result)

        # Convert to string and continue chaining
        str_result = result.decode("utf-8").upper().replace("*", "-")

        assert str_result == "----HELLO PYTHON----"
        assert "source1" in get_taint(str_result)

    def test_taint_bytes_edge_cases_with_system():
        """Test edge cases in the taint system with bytes."""
        # Empty bytes with taint
        empty = taint(b"", ["empty_source"])
        assert get_taint(empty) == ["empty_source"]
        assert empty == b""

        # Bytes with special characters
        special = taint(b"\x00\n\r\t\xff", ["special_source"])
        assert len(special) == 5
        assert get_taint(special) == ["special_source"]

        # Large bytes object
        large = taint(b"x" * 10000, ["large_source"])
        assert len(large) == 10000
        assert get_taint(large) == ["large_source"]

    def test_taint_bytes_format_operations():
        """Test formatting operations with tainted bytes."""
        # % formatting with bytes
        fmt = taint(b"File: %s Size: %d", ["fmt_source"])
        name = taint(b"data.bin", ["name_source"])
        size = 1024

        result = fmt % (name, size)
        assert result == b"File: data.bin Size: 1024"
        assert set(get_taint(result)) == {"fmt_source", "name_source"}

        # Join with tainted separator
        sep = taint(b" | ", ["sep_source"])
        parts = [
            taint(b"part1", ["p1"]),
            b"part2",
            taint(b"part3", ["p3"]),
        ]

        joined = sep.join(parts)
        assert joined == b"part1 | part2 | part3"
        origins = get_taint(joined)
        assert "sep_source" in origins
        assert "p1" in origins
        assert "p3" in origins
