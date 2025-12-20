"""Unit tests for TaintWrapper (string) functionality."""

import pytest

from aco.runner.taint_wrappers import taint_wrap, TaintWrapper, get_taint_origins, untaint_if_needed
from ....utils import with_ast_rewriting, with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintStr:
    """Test suite for TaintWrapper (string) functionality."""

    def test_creation(self):
        """Test taint_wrap creation with various taint origins."""
        # Test with no taint
        s1 = "hello"  # Plain string, not wrapped
        assert s1 == "hello"
        assert get_taint_origins(s1) == []

        # Test with single string taint
        s2 = taint_wrap("world", taint_origin="source1")
        assert s2 == "world"
        assert get_taint_origins(s2) == ["source1"]

        # Test with single int taint
        s3 = taint_wrap("test", taint_origin=42)
        assert s3 == "test"
        assert get_taint_origins(s3) == [42]

        # Test with list taint
        s4 = taint_wrap("data", taint_origin=["source1", "source2"])
        assert s4 == "data"
        assert set(get_taint_origins(s4)) == {"source1", "source2"}

    def test_addition(self):
        """Test string addition operations."""
        s1 = taint_wrap("hello", taint_origin="source1")
        s2 = taint_wrap(" world", taint_origin="source2")

        # TaintWrapper + TaintWrapper
        result = s1 + s2
        assert str(result) == "hello world"
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # TaintWrapper + str
        result = s1 + " there"
        assert str(result) == "hello there"
        assert get_taint_origins(result) == ["source1"]

        # str + TaintWrapper (radd)
        result = "Hi " + s2
        assert str(result) == "Hi  world"
        assert get_taint_origins(result) == ["source2"]

    def test_format(self):
        """Test string formatting."""
        s = taint_wrap("test", taint_origin="source1")

        # Test __format__
        result = format(s, ">10")
        assert str(result) == "      test"
        assert get_taint_origins(result) == ["source1"]

    def test_getitem(self):
        """Test string indexing and slicing."""
        s = taint_wrap("hello world", taint_origin="source1")

        # Single character
        result = s[0]
        assert str(result) == "h"
        assert get_taint_origins(result) == ["source1"]

        # Slice
        result = s[0:5]
        assert str(result) == "hello"
        assert get_taint_origins(result) == ["source1"]

        # Negative index
        result = s[-5:]
        assert str(result) == "world"
        assert get_taint_origins(result) == ["source1"]

    def test_mod_operator(self):
        """Test % operator for string formatting."""
        s = taint_wrap("Hello %s", taint_origin="template")

        # Single argument
        arg = taint_wrap("World", taint_origin="arg1")
        result = s % arg
        assert str(result) == "Hello World"
        assert set(get_taint_origins(result)) == {"template", "arg1"}

        # Multiple arguments (tuple)
        s2 = taint_wrap("%s %s", taint_origin="template2")
        arg1 = taint_wrap("Hello", taint_origin="arg1")
        arg2 = taint_wrap("World", taint_origin="arg2")
        result = s2 % (arg1, arg2)
        assert str(result) == "Hello World"
        assert set(get_taint_origins(result)) == {"template2", "arg1", "arg2"}

        # rmod
        template = "Hello %s"
        arg = taint_wrap("World", taint_origin="arg1")
        result = template % arg
        assert str(result) == "Hello World"
        assert get_taint_origins(result) == ["arg1"]

    def test_encode_decode(self):
        """Test encode and decode methods."""
        s = taint_wrap("hello", taint_origin="source1")

        # Encode should return bytes (untainted)
        encoded = s.encode("utf-8")
        assert isinstance(encoded, bytes)
        assert encoded == b"hello"

    def test_join(self):
        """Test join method."""
        sep = taint_wrap("-", taint_origin="separator")

        # Join normal strings
        result = sep.join(["a", "b", "c"])
        assert str(result) == "a-b-c"
        assert get_taint_origins(result) == ["separator"]

        # Join tainted strings
        items = [taint_wrap("x", taint_origin="item1"), taint_wrap("y", taint_origin="item2"), "z"]
        result = sep.join(items)
        assert str(result) == "x-y-z"
        assert set(get_taint_origins(result)) == {"separator", "item1", "item2"}

    def test_case_methods(self):
        """Test case conversion methods."""
        s = taint_wrap("Hello World", taint_origin="source1")

        # upper
        result = s.upper()
        assert str(result) == "HELLO WORLD"
        assert get_taint_origins(result) == ["source1"]

        # lower
        result = s.lower()
        assert str(result) == "hello world"
        assert get_taint_origins(result) == ["source1"]

        # capitalize
        result = s.capitalize()
        assert str(result) == "Hello world"
        assert get_taint_origins(result) == ["source1"]

        # title
        result = s.title()
        assert str(result) == "Hello World"
        assert get_taint_origins(result) == ["source1"]

    def test_strip_methods(self):
        """Test strip, lstrip, rstrip methods."""
        s = taint_wrap("  hello world  ", taint_origin="source1")

        # strip
        result = s.strip()
        assert str(result) == "hello world"
        assert get_taint_origins(result) == ["source1"]

        # lstrip
        result = s.lstrip()
        assert str(result) == "hello world  "
        assert get_taint_origins(result) == ["source1"]

        # rstrip
        result = s.rstrip()
        assert str(result) == "  hello world"
        assert get_taint_origins(result) == ["source1"]

    def test_replace(self):
        """Test replace method."""
        s = taint_wrap("hello world", taint_origin="source1")
        replacement = taint_wrap("universe", taint_origin="source2")

        result = s.replace("world", replacement)
        assert str(result) == "hello universe"
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Replace with normal string
        result = s.replace("world", "there")
        assert str(result) == "hello there"
        assert get_taint_origins(result) == ["source1"]

    def test_split(self):
        """Test split method."""
        s = taint_wrap("hello-world-test", taint_origin="source1")

        result = s.split("-")
        assert len(result) == 3
        assert [str(part) for part in result] == ["hello", "world", "test"]
        assert all(get_taint_origins(part) == ["source1"] for part in result), f"result: {result}"

    def test_search_methods(self):
        """Test startswith, endswith, find, index, count methods."""
        s = taint_wrap("hello world", taint_origin="source1")

        # These should return bool/int (not tainted)
        assert s.startswith("hello") is True
        assert s.endswith("world") is True
        assert s.find("world") == 6
        assert s.index("world") == 6
        assert s.count("l") == 3

    def test_check_methods(self):
        """Test isdigit, isalpha, isalnum, etc."""
        s1 = taint_wrap("123", taint_origin="source1")
        s2 = taint_wrap("abc", taint_origin="source2")
        s3 = taint_wrap("abc123", taint_origin="source3")
        s4 = taint_wrap("   ", taint_origin="source4")

        assert s1.isdigit() is True
        assert s2.isalpha() is True
        assert s3.isalnum() is True
        assert s4.isspace() is True
        assert s1.isnumeric() is True
        assert s2.islower() is True
        assert taint_wrap("ABC", "src").isupper() is True

    def test_hash(self):
        """Test that tainted values are hashable."""
        s1 = taint_wrap("hello", taint_origin="source1")
        s2 = taint_wrap("world", taint_origin="source2")
        s3 = "hello"

        # Tainted values hash like their underlying values
        # (hash() calls are AST-rewritten and unwrap the value)
        assert hash(s1) == hash(s3)  # Both hash to hash("hello")
        assert hash(s1) != hash(s2)  # Different underlying values

        # Can be used in sets and dicts (based on underlying value)
        test_set = {s1, s2}
        assert len(test_set) == 2  # Different underlying values

    def test_str_repr(self):
        """Test __str__ and __repr__ methods."""
        s = taint_wrap("hello", taint_origin="source1")

        assert str(s) == "hello"
        # repr returns TaintWrapper repr
        assert "hello" in repr(s)

    def test_get_raw(self):
        """Test getting raw object using untaint_if_needed."""
        s = taint_wrap("hello", taint_origin="source1")
        raw = untaint_if_needed(s)
        assert raw == "hello"
        assert isinstance(raw, str)
        assert not isinstance(raw, TaintWrapper)
