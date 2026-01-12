#!/usr/bin/env python3
"""Test taint tracking (bytes) functionality."""

import pytest
from ao.server.taint_ops import add_to_taint_dict_and_return as taint, get_taint
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintBytes:
    """Test suite for taint tracking (bytes) functionality."""

    def test_basic_creation(self):
        """Test basic taint creation with bytes."""
        # Create from bytes
        tb1 = taint(b"hello", ["source1"])
        assert tb1 == b"hello", f"{tb1}"
        assert get_taint(tb1) == ["source1"]

        # Create from bytearray
        tb2 = taint(bytearray(b"world"), ["source2", "source3"])
        assert tb2 == b"world"
        assert set(get_taint(tb2)) == {"source2", "source3"}

    def test_arithmetic_operations(self):
        """Test arithmetic operations."""
        tb1 = taint(b"hello", ["source1"])
        tb2 = taint(b" world", ["source2"])

        # Addition
        tb3 = tb1 + tb2
        assert tb3 == b"hello world"
        assert set(get_taint(tb3)) == {"source1", "source2"}

        # Reverse addition
        tb4 = b"prefix " + tb1
        assert tb4 == b"prefix hello"
        assert "source1" in get_taint(tb4)

        # Multiplication
        tb5 = tb1 * 2
        assert tb5 == b"hellohello"
        assert get_taint(tb5) == ["source1"]

        # Reverse multiplication
        tb6 = 3 * tb1
        assert tb6 == b"hellohellohello"
        assert get_taint(tb6) == ["source1"]

    def test_modulo_formatting(self):
        """Test % formatting with bytes."""
        tb = taint(b"Hello %s", ["fmt_source"])

        # Format with single value
        result = tb % b"World"
        assert result == b"Hello World"
        assert "fmt_source" in get_taint(result)

        # Format with tainted value
        tb_val = taint(b"Python", ["val_source"])
        result2 = tb % tb_val
        assert result2 == b"Hello Python"
        assert set(get_taint(result2)) == {"fmt_source", "val_source"}

    def test_slicing():
        """Test slicing operations."""
        tb = taint(b"hello world", ["source1"])

        # Slice
        tb_slice = tb[0:5]
        assert tb_slice == b"hello"
        assert get_taint(tb_slice) == ["source1"]

        # Single index (returns int)
        val = tb[0]
        assert val == ord(b"h")
        assert isinstance(val, int)

        # Negative indexing
        assert tb[-1] == ord(b"d")

        # Step slicing
        tb_step = tb[::2]
        assert tb_step == b"hlowrd"

    def test_case_methods():
        """Test case conversion methods."""
        tb = taint(b"Hello World", ["source1"])

        # Upper
        upper = tb.upper()
        assert upper == b"HELLO WORLD"
        assert get_taint(upper) == ["source1"]

        # Lower
        lower = tb.lower()
        assert lower == b"hello world"
        assert get_taint(lower) == ["source1"]

        # Title
        title = tb.title()
        assert title == b"Hello World"
        assert get_taint(title) == ["source1"]

        # Capitalize
        cap = tb.lower().capitalize()
        assert cap == b"Hello world"
        assert get_taint(cap) == ["source1"]

        # Swapcase
        swap = tb.swapcase()
        assert swap == b"hELLO wORLD"
        assert get_taint(swap) == ["source1"]

    def test_strip_methods():
        """Test strip methods."""
        tb = taint(b"  hello  ", ["source1"])

        # Strip
        stripped = tb.strip()
        assert stripped == b"hello"
        assert get_taint(stripped) == ["source1"]

        # Lstrip
        lstripped = tb.lstrip()
        assert lstripped == b"hello  "
        assert get_taint(lstripped) == ["source1"]

        # Rstrip
        rstripped = tb.rstrip()
        assert rstripped == b"  hello"
        assert get_taint(rstripped) == ["source1"]

    def test_padding_methods():
        """Test padding and justification methods."""
        tb = taint(b"hello", ["source1"])

        # Center
        centered = tb.center(10)
        assert centered == b"  hello   "
        assert len(centered) == 10
        assert get_taint(centered) == ["source1"]

        # Ljust
        ljusted = tb.ljust(10, b"*")
        assert ljusted == b"hello*****"
        assert get_taint(ljusted) == ["source1"]

        # Rjust
        rjusted = tb.rjust(10, b"-")
        assert rjusted == b"-----hello"
        assert get_taint(rjusted) == ["source1"]

        # Zfill
        tb_num = taint(b"42", ["num_source"])
        zfilled = tb_num.zfill(5)
        assert zfilled == b"00042"
        assert get_taint(zfilled) == ["num_source"]

    def test_replace():
        """Test replace method."""
        tb = taint(b"Hello World", ["source1"])

        # Simple replace
        tb2 = tb.replace(b"World", b"Python")
        assert tb2 == b"Hello Python"
        assert "source1" in get_taint(tb2)

        # Replace with tainted value
        tb_new = taint(b"Universe", ["new_source"])
        tb3 = tb.replace(b"World", tb_new)
        assert tb3 == b"Hello Universe"
        assert set(get_taint(tb3)) == {"source1", "new_source"}

        # Replace with count
        tb4 = taint(b"aaa", ["source2"])
        tb5 = tb4.replace(b"a", b"b", 2)
        assert tb5 == b"bba"

    def test_split_methods():
        """Test split methods."""
        tb = taint(b"one,two,three", ["source1"])

        # Split
        parts = tb.split(b",")
        assert len(parts) == 3
        assert parts[0] == b"one"
        assert parts[1] == b"two"
        assert parts[2] == b"three"
        assert all(get_taint(p) == ["source1"] for p in parts)

        # Rsplit
        rparts = tb.rsplit(b",", 1)
        assert len(rparts) == 2
        assert rparts[0] == b"one,two"
        assert rparts[1] == b"three"

        # Splitlines
        tb_lines = taint(b"line1\nline2\rline3", ["lines_source"])
        lines = tb_lines.splitlines()
        assert len(lines) == 3

    def test_partition_methods():
        """Test partition methods."""
        tb = taint(b"one,two,three", ["source1"])

        # Partition
        before, sep, after = tb.partition(b",")
        assert before == b"one"
        assert sep == b","
        assert after == b"two,three"
        assert all(get_taint(p) == ["source1"] for p in [before, sep, after])

        # Rpartition
        before2, sep2, after2 = tb.rpartition(b",")
        assert before2 == b"one,two"
        assert sep2 == b","
        assert after2 == b"three"

    def test_prefix_suffix():
        """Test removeprefix and removesuffix methods."""
        tb = taint(b"HelloWorld", ["source1"])

        # Remove prefix
        tb2 = tb.removeprefix(b"Hello")
        assert tb2 == b"World"
        assert get_taint(tb2) == ["source1"]

        # Remove suffix
        tb3 = tb.removesuffix(b"World")
        assert tb3 == b"Hello"
        assert get_taint(tb3) == ["source1"]

    def test_find_index_methods():
        """Test find and index methods."""
        tb = taint(b"hello world", ["source1"])

        # Find
        assert tb.find(b"world") == 6
        assert tb.find(b"xyz") == -1
        assert tb.rfind(b"o") == 7

        # Index
        assert tb.index(b"world") == 6
        assert tb.rindex(b"o") == 7

        # Index with non-existent substring should raise
        with pytest.raises(ValueError):
            tb.index(b"xyz")

    def test_count():
        """Test count method."""
        tb = taint(b"hello world", ["source1"])

        assert tb.count(b"l") == 3
        assert tb.count(b"o") == 2
        assert tb.count(b"xyz") == 0

    def test_boolean_check_methods():
        """Test boolean checking methods."""
        # Test isalnum
        assert b"hello123".isalnum() == True
        assert b"hello 123".isalnum() == False

        # Test isalpha
        assert b"hello".isalpha() == True
        assert b"hello123".isalpha() == False

        # Test isdigit
        assert b"123".isdigit() == True
        assert b"123abc".isdigit() == False

        # Test isspace
        assert b"   ".isspace() == True
        assert b"  a ".isspace() == False

        # Test islower
        assert b"hello".islower() == True
        assert b"Hello".islower() == False

        # Test isupper
        assert b"HELLO".isupper() == True
        assert b"Hello".isupper() == False

        # Test istitle
        assert b"Hello World".istitle() == True
        assert b"hello world".istitle() == False

        # Test isascii
        assert b"hello".isascii() == True

    def test_decode_encode():
        """Test decode to TaintWrapper."""
        tb = taint(b"hello", ["source1"])

        # Decode to TaintWrapper
        ts = tb.decode("utf-8")
        assert ts == "hello"
        assert get_taint(ts) == ["source1"]

        # Decode with errors parameter
        tb_invalid = taint(b"\xff\xfe", ["invalid_source"])
        ts_replaced = tb_invalid.decode("utf-8", errors="replace")
        assert get_taint(ts_replaced) == ["invalid_source"]

    def test_hex_methods():
        """Test hex conversion methods."""
        tb = taint(b"hello", ["source1"])

        # To hex
        hex_str = tb.hex()
        assert hex_str == "68656c6c6f"
        assert get_taint(hex_str) == ["source1"]

        # To hex with separator
        hex_sep = tb.hex("-", 2)
        assert hex_sep == "68-656c-6c6f"  # bytes grouped by 2 hex chars (1 byte)

    def test_join():
        """Test join method."""
        separator = taint(b",", ["sep_source"])
        items = [
            taint(b"one", ["source1"]),
            taint(b"two", ["source2"]),
            b"three",  # Regular bytes
        ]

        result = separator.join(items)
        assert result == b"one,two,three"
        origins = set(get_taint(result))
        assert "sep_source" in origins
        assert "source1" in origins
        assert "source2" in origins

    def test_translate():
        """Test translate method."""
        tb = taint(b"hello", ["source1"])

        # Create translation table
        table = bytes.maketrans(b"el", b"ip")

        # Translate
        translated = tb.translate(table)
        assert translated == b"hippo"
        assert get_taint(translated) == ["source1"]

    def test_expandtabs():
        """Test expandtabs method."""
        tb = taint(b"a\tb\tc", ["source1"])

        expanded = tb.expandtabs(4)
        assert expanded == b"a   b   c"
        assert get_taint(expanded) == ["source1"]

    def test_comparison_methods():
        """Test comparison methods."""
        tb1 = taint(b"hello", ["source1"])
        tb2 = taint(b"hello", ["source2"])
        tb3 = taint(b"world", ["source3"])

        # Equality
        assert tb1 == tb2
        assert tb1 == b"hello"
        assert tb1 != tb3
        assert tb1 != b"world"

        # Ordering
        assert tb1 < tb3
        assert tb1 < b"world"
        assert tb3 > tb1
        assert tb3 > b"hello"
        assert tb1 <= tb2
        assert tb1 >= tb2

        # Contains
        assert b"ell" in tb1
        assert b"xyz" not in tb1

        # Startswith/endswith
        assert tb1.startswith(b"hel")
        assert tb1.startswith(b"hel", 0, 3)
        assert tb1.endswith(b"llo")
        assert tb1.endswith(b"llo", 2)

    def test_utility_methods():
        """Test utility methods."""
        tb = taint(b"hello", ["source1"])

        # get_raw
        raw = tb
        assert raw == b"hello"
        assert type(raw) == bytes

        # len
        assert len(tb) == 5

        # bool
        assert bool(tb) == True
        assert bool(b"") == False

        # hash
        assert hash(tb) == hash(b"hello")

        # repr and str
        assert repr(tb) == repr(b"hello")
        assert str(tb) == str(b"hello")

        # iter
        for i, byte_val in enumerate(tb):
            assert isinstance(byte_val, int)
            assert byte_val == b"hello"[i]

    def test_edge_cases():
        """Test edge cases and corner scenarios."""
        # Empty bytes
        tb_empty = taint(b"", ["empty_source"])
        assert tb_empty == b""
        assert len(tb_empty) == 0
        assert bool(tb_empty) == False
        assert get_taint(tb_empty) == ["empty_source"]

        # None taint origin - no wrapping for no taint
        tb_none = b"test"
        assert tb_none == b"test"
        assert get_taint(tb_none) == []

        # Multiple operations preserving taint
        tb1 = taint(b"hello", ["source1"])
        tb2 = tb1.upper().replace(b"L", b"X").strip()
        assert tb2 == b"HEXXO"
        assert "source1" in get_taint(tb2)
