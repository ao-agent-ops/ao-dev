#!/usr/bin/env python3
"""Integration tests for tainted bytes with other taint types.

Tests the unified TaintWrapper's handling of bytes objects.
"""

from aco.runner.taint_wrappers import (
    get_taint_origins,
    untaint_if_needed,
    taint_wrap,
)
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintBytesIntegration:
    """Integration tests for tainted bytes."""

    def test_taint_bytes_with_taint_wrap():
        """Test that taint_wrap correctly handles bytes."""
        # Wrap plain bytes
        b = b"hello"
        tb = taint_wrap(b, taint_origin="source1")
        assert tb == b"hello"
        assert get_taint_origins(tb) == ["source1"]

        # Wrapping already tainted bytes returns the same object
        # (doesn't double-wrap, which is the expected behavior)
        tb2 = taint_wrap(tb, taint_origin="source2")
        assert tb2 == tb  # Should be the same object

    def test_untaint_bytes():
        """Test that untaint_if_needed works with tainted bytes."""
        tb = taint_wrap(b"hello", taint_origin="source1")

        # Untaint should return plain bytes
        raw = untaint_if_needed(tb)
        assert raw == b"hello"
        assert type(raw) == bytes
        assert not hasattr(raw, "_taint_origin")

    def test_taint_bytes_in_collections():
        """Test tainted bytes within lists and dicts."""
        # In list
        tb = taint_wrap(b"data", taint_origin="source1")
        tl = taint_wrap([tb, b"other"], taint_origin="list_source")

        assert len(tl) == 2
        assert tl[0] == b"data"
        # Check item's own taint is preserved
        assert "source1" in get_taint_origins(tl[0])
        # Check list's own taint
        assert "list_source" in get_taint_origins(tl)

        # In dict
        td = taint_wrap({"key": tb}, taint_origin="dict_source")
        assert td["key"] == b"data"
        # Check item's own taint is preserved
        assert "source1" in get_taint_origins(td["key"])
        # Check dict's own taint
        assert "dict_source" in get_taint_origins(td)

    def test_mixed_taint_operations():
        """Test operations mixing tainted bytes with other taint types."""
        tb = taint_wrap(b"binary", taint_origin="bin_source")
        ts = taint_wrap("text", taint_origin="str_source")

        # Decode tainted bytes to tainted str
        decoded = tb.decode("utf-8")
        assert decoded == "binary"
        assert get_taint_origins(decoded) == ["bin_source"]

        # Encode tainted str to bytes
        encoded = ts.encode("utf-8")
        assert encoded == b"text"

        # Mix in format operations
        fmt = taint_wrap("Data: %s", taint_origin="fmt_source")
        result = fmt % decoded
        assert result == "Data: binary"
        assert set(get_taint_origins(result)) == {"fmt_source", "bin_source"}

    def test_taint_bytes_with_io_operations():
        """Test tainted bytes behavior that could be used in I/O contexts."""
        # Simulate reading binary data
        data = b"\x00\x01\x02\xff"
        tb = taint_wrap(data, taint_origin="file_source")

        # Hex representation (common for binary data display)
        hex_str = tb.hex()
        assert hex_str == "000102ff"
        assert get_taint_origins(hex_str) == ["file_source"]

        # Slicing (common for parsing binary formats)
        header = tb[:2]
        payload = tb[2:]

        assert header == b"\x00\x01"
        assert payload == b"\x02\xff"
        assert get_taint_origins(header) == ["file_source"]
        assert get_taint_origins(payload) == ["file_source"]

    def test_taint_bytes_chaining():
        """Test that taint is preserved through multiple operations."""
        tb = taint_wrap(b"  HELLO WORLD  ", taint_origin="source1")

        # Chain multiple operations
        result = tb.strip().lower().replace(b"world", b"python").center(20, b"*")

        assert result == b"****hello python****"
        assert "source1" in get_taint_origins(result)

        # Convert to string and continue chaining
        str_result = result.decode("utf-8").upper().replace("*", "-")

        assert str_result == "----HELLO PYTHON----"
        assert "source1" in get_taint_origins(str_result)

    def test_taint_bytes_edge_cases_with_system():
        """Test edge cases in the taint system with bytes."""
        # Empty bytes with taint
        empty = taint_wrap(b"", taint_origin="empty_source")
        assert get_taint_origins(empty) == ["empty_source"]
        assert untaint_if_needed(empty) == b""

        # Bytes with special characters
        special = taint_wrap(b"\x00\n\r\t\xff", taint_origin="special_source")
        assert len(special) == 5
        assert get_taint_origins(special) == ["special_source"]

        # Large bytes object
        large = taint_wrap(b"x" * 10000, taint_origin="large_source")
        assert len(large) == 10000
        assert get_taint_origins(large) == ["large_source"]

    def test_taint_bytes_format_operations():
        """Test formatting operations with tainted bytes."""
        # % formatting with bytes
        fmt = taint_wrap(b"File: %s Size: %d", taint_origin="fmt_source")
        name = taint_wrap(b"data.bin", taint_origin="name_source")
        size = 1024

        result = fmt % (name, size)
        assert result == b"File: data.bin Size: 1024"
        assert set(get_taint_origins(result)) == {"fmt_source", "name_source"}

        # Join with tainted separator
        sep = taint_wrap(b" | ", taint_origin="sep_source")
        parts = [
            taint_wrap(b"part1", taint_origin="p1"),
            b"part2",
            taint_wrap(b"part3", taint_origin="p3"),
        ]

        joined = sep.join(parts)
        assert joined == b"part1 | part2 | part3"
        origins = get_taint_origins(joined)
        assert "sep_source" in origins
        assert "p1" in origins
        assert "p3" in origins
