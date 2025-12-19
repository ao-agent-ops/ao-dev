#!/usr/bin/env python3
"""Test the TaintBytes implementation."""

import pytest
from aco.runner.taint_wrappers import TaintBytes, TaintStr, get_taint_origins


def test_basic_creation():
    """Test basic TaintBytes creation."""
    # Create from bytes
    tb1 = TaintBytes(b"hello", taint_origin="source1")
    assert tb1 == b"hello"
    assert get_taint_origins(tb1) == ["source1"]

    # Create from bytearray
    tb2 = TaintBytes(bytearray(b"world"), taint_origin=["source2", "source3"])
    assert tb2 == b"world"
    assert set(get_taint_origins(tb2)) == {"source2", "source3"}


def test_arithmetic_operations():
    """Test arithmetic operations."""
    tb1 = TaintBytes(b"hello", taint_origin="source1")
    tb2 = TaintBytes(b" world", taint_origin="source2")

    # Addition
    tb3 = tb1 + tb2
    assert tb3 == b"hello world"
    assert set(get_taint_origins(tb3)) == {"source1", "source2"}

    # Reverse addition
    tb4 = b"prefix " + tb1
    assert tb4 == b"prefix hello"
    assert isinstance(tb4, TaintBytes)
    assert "source1" in get_taint_origins(tb4)

    # Multiplication
    tb5 = tb1 * 2
    assert tb5 == b"hellohello"
    assert get_taint_origins(tb5) == ["source1"]

    # Reverse multiplication
    tb6 = 3 * tb1
    assert tb6 == b"hellohellohello"
    assert get_taint_origins(tb6) == ["source1"]


def test_modulo_formatting():
    """Test % formatting with bytes."""
    tb = TaintBytes(b"Hello %s", taint_origin="fmt_source")

    # Format with single value
    result = tb % b"World"
    assert result == b"Hello World"
    assert isinstance(result, TaintBytes)
    assert "fmt_source" in get_taint_origins(result)

    # Format with tainted value
    tb_val = TaintBytes(b"Python", taint_origin="val_source")
    result2 = tb % tb_val
    assert result2 == b"Hello Python"
    assert set(get_taint_origins(result2)) == {"fmt_source", "val_source"}


def test_slicing():
    """Test slicing operations."""
    tb = TaintBytes(b"hello world", taint_origin="source1")

    # Slice
    tb_slice = tb[0:5]
    assert tb_slice == b"hello"
    assert isinstance(tb_slice, TaintBytes)
    assert get_taint_origins(tb_slice) == ["source1"]

    # Single index (returns int)
    val = tb[0]
    assert val == ord(b"h")
    assert isinstance(val, int)

    # Negative indexing
    assert tb[-1] == ord(b"d")

    # Step slicing
    tb_step = tb[::2]
    assert tb_step == b"hlowrd"
    assert isinstance(tb_step, TaintBytes)


def test_case_methods():
    """Test case conversion methods."""
    tb = TaintBytes(b"Hello World", taint_origin="source1")

    # Upper
    upper = tb.upper()
    assert upper == b"HELLO WORLD"
    assert isinstance(upper, TaintBytes)
    assert get_taint_origins(upper) == ["source1"]

    # Lower
    lower = tb.lower()
    assert lower == b"hello world"
    assert get_taint_origins(lower) == ["source1"]

    # Title
    title = tb.title()
    assert title == b"Hello World"
    assert get_taint_origins(title) == ["source1"]

    # Capitalize
    cap = tb.lower().capitalize()
    assert cap == b"Hello world"
    assert get_taint_origins(cap) == ["source1"]

    # Swapcase
    swap = tb.swapcase()
    assert swap == b"hELLO wORLD"
    assert get_taint_origins(swap) == ["source1"]


def test_strip_methods():
    """Test strip methods."""
    tb = TaintBytes(b"  hello  ", taint_origin="source1")

    # Strip
    stripped = tb.strip()
    assert stripped == b"hello"
    assert get_taint_origins(stripped) == ["source1"]

    # Lstrip
    lstripped = tb.lstrip()
    assert lstripped == b"hello  "
    assert get_taint_origins(lstripped) == ["source1"]

    # Rstrip
    rstripped = tb.rstrip()
    assert rstripped == b"  hello"
    assert get_taint_origins(rstripped) == ["source1"]


def test_padding_methods():
    """Test padding and justification methods."""
    tb = TaintBytes(b"hello", taint_origin="source1")

    # Center
    centered = tb.center(10)
    assert centered == b"  hello   "
    assert len(centered) == 10
    assert get_taint_origins(centered) == ["source1"]

    # Ljust
    ljusted = tb.ljust(10, b"*")
    assert ljusted == b"hello*****"
    assert get_taint_origins(ljusted) == ["source1"]

    # Rjust
    rjusted = tb.rjust(10, b"-")
    assert rjusted == b"-----hello"
    assert get_taint_origins(rjusted) == ["source1"]

    # Zfill
    tb_num = TaintBytes(b"42", taint_origin="num_source")
    zfilled = tb_num.zfill(5)
    assert zfilled == b"00042"
    assert get_taint_origins(zfilled) == ["num_source"]


def test_replace():
    """Test replace method."""
    tb = TaintBytes(b"Hello World", taint_origin="source1")

    # Simple replace
    tb2 = tb.replace(b"World", b"Python")
    assert tb2 == b"Hello Python"
    assert "source1" in get_taint_origins(tb2)

    # Replace with tainted value
    tb_new = TaintBytes(b"Universe", taint_origin="new_source")
    tb3 = tb.replace(b"World", tb_new)
    assert tb3 == b"Hello Universe"
    assert set(get_taint_origins(tb3)) == {"source1", "new_source"}

    # Replace with count
    tb4 = TaintBytes(b"aaa", taint_origin="source2")
    tb5 = tb4.replace(b"a", b"b", 2)
    assert tb5 == b"bba"


def test_split_methods():
    """Test split methods."""
    tb = TaintBytes(b"one,two,three", taint_origin="source1")

    # Split
    parts = tb.split(b",")
    assert len(parts) == 3
    assert parts[0] == b"one"
    assert parts[1] == b"two"
    assert parts[2] == b"three"
    assert all(isinstance(p, TaintBytes) for p in parts)
    assert all(get_taint_origins(p) == ["source1"] for p in parts)

    # Rsplit
    rparts = tb.rsplit(b",", 1)
    assert len(rparts) == 2
    assert rparts[0] == b"one,two"
    assert rparts[1] == b"three"

    # Splitlines
    tb_lines = TaintBytes(b"line1\nline2\rline3", taint_origin="lines_source")
    lines = tb_lines.splitlines()
    assert len(lines) == 3
    assert all(isinstance(l, TaintBytes) for l in lines)


def test_partition_methods():
    """Test partition methods."""
    tb = TaintBytes(b"one,two,three", taint_origin="source1")

    # Partition
    before, sep, after = tb.partition(b",")
    assert before == b"one"
    assert sep == b","
    assert after == b"two,three"
    assert all(isinstance(p, TaintBytes) for p in [before, sep, after])
    assert all(get_taint_origins(p) == ["source1"] for p in [before, sep, after])

    # Rpartition
    before2, sep2, after2 = tb.rpartition(b",")
    assert before2 == b"one,two"
    assert sep2 == b","
    assert after2 == b"three"


def test_prefix_suffix():
    """Test removeprefix and removesuffix methods."""
    tb = TaintBytes(b"HelloWorld", taint_origin="source1")

    # Remove prefix
    tb2 = tb.removeprefix(b"Hello")
    assert tb2 == b"World"
    assert get_taint_origins(tb2) == ["source1"]

    # Remove suffix
    tb3 = tb.removesuffix(b"World")
    assert tb3 == b"Hello"
    assert get_taint_origins(tb3) == ["source1"]


def test_find_index_methods():
    """Test find and index methods."""
    tb = TaintBytes(b"hello world", taint_origin="source1")

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
    tb = TaintBytes(b"hello world", taint_origin="source1")

    assert tb.count(b"l") == 3
    assert tb.count(b"o") == 2
    assert tb.count(b"xyz") == 0


def test_boolean_check_methods():
    """Test boolean checking methods."""
    # Test isalnum
    assert TaintBytes(b"hello123").isalnum() == True
    assert TaintBytes(b"hello 123").isalnum() == False

    # Test isalpha
    assert TaintBytes(b"hello").isalpha() == True
    assert TaintBytes(b"hello123").isalpha() == False

    # Test isdigit
    assert TaintBytes(b"123").isdigit() == True
    assert TaintBytes(b"123abc").isdigit() == False

    # Test isspace
    assert TaintBytes(b"   ").isspace() == True
    assert TaintBytes(b"  a ").isspace() == False

    # Test islower
    assert TaintBytes(b"hello").islower() == True
    assert TaintBytes(b"Hello").islower() == False

    # Test isupper
    assert TaintBytes(b"HELLO").isupper() == True
    assert TaintBytes(b"Hello").isupper() == False

    # Test istitle
    assert TaintBytes(b"Hello World").istitle() == True
    assert TaintBytes(b"hello world").istitle() == False

    # Test isascii
    assert TaintBytes(b"hello").isascii() == True


def test_decode_encode():
    """Test decode to TaintStr."""
    tb = TaintBytes(b"hello", taint_origin="source1")

    # Decode to TaintStr
    ts = tb.decode("utf-8")
    assert ts == "hello"
    assert isinstance(ts, TaintStr)
    assert get_taint_origins(ts) == ["source1"]

    # Decode with errors parameter
    tb_invalid = TaintBytes(b"\xff\xfe", taint_origin="invalid_source")
    ts_replaced = tb_invalid.decode("utf-8", errors="replace")
    assert isinstance(ts_replaced, TaintStr)
    assert get_taint_origins(ts_replaced) == ["invalid_source"]


def test_hex_methods():
    """Test hex conversion methods."""
    tb = TaintBytes(b"hello", taint_origin="source1")

    # To hex
    hex_str = tb.hex()
    assert hex_str == "68656c6c6f"
    assert isinstance(hex_str, TaintStr)
    assert get_taint_origins(hex_str) == ["source1"]

    # To hex with separator
    hex_sep = tb.hex("-", 2)
    assert hex_sep == "68-656c-6c6f"  # bytes grouped by 2 hex chars (1 byte)
    assert isinstance(hex_sep, TaintStr)

    # From hex (class method)
    tb_from_hex = TaintBytes.fromhex("68656c6c6f")
    assert tb_from_hex == b"hello"
    assert isinstance(tb_from_hex, bytes)  # Note: fromhex returns plain bytes


def test_join():
    """Test join method."""
    separator = TaintBytes(b",", taint_origin="sep_source")
    items = [
        TaintBytes(b"one", taint_origin="source1"),
        TaintBytes(b"two", taint_origin="source2"),
        b"three",  # Regular bytes
    ]

    result = separator.join(items)
    assert result == b"one,two,three"
    assert isinstance(result, TaintBytes)
    origins = set(get_taint_origins(result))
    assert "sep_source" in origins
    assert "source1" in origins
    assert "source2" in origins


def test_translate():
    """Test translate method."""
    tb = TaintBytes(b"hello", taint_origin="source1")

    # Create translation table
    table = bytes.maketrans(b"el", b"ip")

    # Translate
    translated = tb.translate(table)
    assert translated == b"hippo"
    assert isinstance(translated, TaintBytes)
    assert get_taint_origins(translated) == ["source1"]


def test_expandtabs():
    """Test expandtabs method."""
    tb = TaintBytes(b"a\tb\tc", taint_origin="source1")

    expanded = tb.expandtabs(4)
    assert expanded == b"a   b   c"
    assert isinstance(expanded, TaintBytes)
    assert get_taint_origins(expanded) == ["source1"]


def test_comparison_methods():
    """Test comparison methods."""
    tb1 = TaintBytes(b"hello", taint_origin="source1")
    tb2 = TaintBytes(b"hello", taint_origin="source2")
    tb3 = TaintBytes(b"world", taint_origin="source3")

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
    tb = TaintBytes(b"hello", taint_origin="source1")

    # get_raw
    raw = tb.get_raw()
    assert raw == b"hello"
    assert type(raw) == bytes

    # len
    assert len(tb) == 5

    # bool
    assert bool(tb) == True
    assert bool(TaintBytes(b"")) == False

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
    tb_empty = TaintBytes(b"", taint_origin="empty_source")
    assert tb_empty == b""
    assert len(tb_empty) == 0
    assert bool(tb_empty) == False
    assert get_taint_origins(tb_empty) == ["empty_source"]

    # None taint origin
    tb_none = TaintBytes(b"test")
    assert tb_none == b"test"
    assert get_taint_origins(tb_none) == []

    # Multiple operations preserving taint
    tb1 = TaintBytes(b"hello", taint_origin="source1")
    tb2 = tb1.upper().replace(b"L", b"X").strip()
    assert tb2 == b"HEXXO"
    assert "source1" in get_taint_origins(tb2)
