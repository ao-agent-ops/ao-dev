"""Unit tests for TaintStr class."""

import pytest

from runner.taint_wrappers import TaintStr, get_taint_origins, is_tainted


class TestTaintStr:
    """Test suite for TaintStr class."""

    def test_creation(self):
        """Test TaintStr creation with various taint origins."""
        # Test with no taint
        s1 = TaintStr("hello")
        assert s1.get_raw() == "hello"
        assert s1._taint_origin == []
        assert not is_tainted(s1)

        # Test with single string taint
        s2 = TaintStr("world", taint_origin="source1")
        assert s2.get_raw() == "world"
        assert s2._taint_origin == ["source1"]
        assert is_tainted(s2)

        # Test with single int taint
        s3 = TaintStr("test", taint_origin=42)
        assert s3.get_raw() == "test"
        assert s3._taint_origin == [42]
        assert is_tainted(s3)

        # Test with list taint
        s4 = TaintStr("data", taint_origin=["source1", "source2"])
        assert s4.get_raw() == "data"
        assert s4._taint_origin == ["source1", "source2"]
        assert is_tainted(s4)

        # Test invalid taint origin type
        with pytest.raises(TypeError):
            TaintStr("invalid", taint_origin={})

    def test_addition(self):
        """Test string addition operations."""
        s1 = TaintStr("hello", taint_origin="source1")
        s2 = TaintStr(" world", taint_origin="source2")

        # TaintStr + TaintStr
        result = s1 + s2
        assert result.get_raw() == "hello world"
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # TaintStr + str
        result = s1 + " there"
        assert result.get_raw() == "hello there"
        assert get_taint_origins(result) == ["source1"]

        # str + TaintStr (radd)
        result = "Hi " + s2
        assert result.get_raw() == "Hi  world"
        assert get_taint_origins(result) == ["source2"]

    def test_format(self):
        """Test string formatting."""
        s = TaintStr("test", taint_origin="source1")

        # Test __format__
        result = format(s, ">10")
        assert result.get_raw() == "      test"
        assert get_taint_origins(result) == ["source1"]

    def test_getitem(self):
        """Test string indexing and slicing."""
        s = TaintStr("hello world", taint_origin="source1")

        # Single character
        result = s[0]
        assert result.get_raw() == "h"
        assert get_taint_origins(result) == ["source1"]

        # Slice
        result = s[0:5]
        assert result.get_raw() == "hello"
        assert get_taint_origins(result) == ["source1"]

        # Negative index
        result = s[-5:]
        assert result.get_raw() == "world"
        assert get_taint_origins(result) == ["source1"]

    def test_mod_operator(self):
        """Test % operator for string formatting."""
        s = TaintStr("Hello %s", taint_origin="template")

        # Single argument
        arg = TaintStr("World", taint_origin="arg1")
        result = s % arg
        assert result.get_raw() == "Hello World"
        assert set(get_taint_origins(result)) == {"template", "arg1"}

        # Multiple arguments (tuple)
        s2 = TaintStr("%s %s", taint_origin="template2")
        arg1 = TaintStr("Hello", taint_origin="arg1")
        arg2 = TaintStr("World", taint_origin="arg2")
        result = s2 % (arg1, arg2)
        assert result.get_raw() == "Hello World"
        assert set(get_taint_origins(result)) == {"template2", "arg1", "arg2"}

        # rmod
        template = "Hello %s"
        arg = TaintStr("World", taint_origin="arg1")
        result = template % arg
        assert result.get_raw() == "Hello World"
        assert get_taint_origins(result) == ["arg1"]

    def test_encode_decode(self):
        """Test encode and decode methods."""
        s = TaintStr("hello", taint_origin="source1")

        # Encode should return bytes (untainted)
        encoded = s.encode("utf-8")
        assert isinstance(encoded, bytes)
        assert encoded == b"hello"

    def test_join(self):
        """Test join method."""
        sep = TaintStr("-", taint_origin="separator")

        # Join normal strings
        result = sep.join(["a", "b", "c"])
        assert result.get_raw() == "a-b-c"
        assert get_taint_origins(result) == ["separator"]

        # Join tainted strings
        items = [TaintStr("x", taint_origin="item1"), TaintStr("y", taint_origin="item2"), "z"]
        result = sep.join(items)
        assert result.get_raw() == "x-y-z"
        assert set(get_taint_origins(result)) == {"separator", "item1", "item2"}

    def test_case_methods(self):
        """Test case conversion methods."""
        s = TaintStr("Hello World", taint_origin="source1")

        # upper
        result = s.upper()
        assert result.get_raw() == "HELLO WORLD"
        assert get_taint_origins(result) == ["source1"]

        # lower
        result = s.lower()
        assert result.get_raw() == "hello world"
        assert get_taint_origins(result) == ["source1"]

        # capitalize
        result = s.capitalize()
        assert result.get_raw() == "Hello world"
        assert get_taint_origins(result) == ["source1"]

        # title
        result = s.title()
        assert result.get_raw() == "Hello World"
        assert get_taint_origins(result) == ["source1"]

    def test_strip_methods(self):
        """Test strip, lstrip, rstrip methods."""
        s = TaintStr("  hello world  ", taint_origin="source1")

        # strip
        result = s.strip()
        assert result.get_raw() == "hello world"
        assert get_taint_origins(result) == ["source1"]

        # lstrip
        result = s.lstrip()
        assert result.get_raw() == "hello world  "
        assert get_taint_origins(result) == ["source1"]

        # rstrip
        result = s.rstrip()
        assert result.get_raw() == "  hello world"
        assert get_taint_origins(result) == ["source1"]

    def test_replace(self):
        """Test replace method."""
        s = TaintStr("hello world", taint_origin="source1")
        replacement = TaintStr("universe", taint_origin="source2")

        result = s.replace("world", replacement)
        assert result.get_raw() == "hello universe"
        assert set(get_taint_origins(result)) == {"source1", "source2"}

        # Replace with normal string
        result = s.replace("world", "there")
        assert result.get_raw() == "hello there"
        assert get_taint_origins(result) == ["source1"]

    def test_split(self):
        """Test split method."""
        s = TaintStr("hello-world-test", taint_origin="source1")

        result = s.split("-")
        assert len(result) == 3
        assert all(isinstance(part, TaintStr) for part in result)
        assert [part.get_raw() for part in result] == ["hello", "world", "test"]
        assert all(get_taint_origins(part) == ["source1"] for part in result)

    def test_search_methods(self):
        """Test startswith, endswith, find, index, count methods."""
        s = TaintStr("hello world", taint_origin="source1")

        # These should return bool/int (not tainted)
        assert s.startswith("hello") is True
        assert s.endswith("world") is True
        assert s.find("world") == 6
        assert s.index("world") == 6
        assert s.count("l") == 3

    def test_check_methods(self):
        """Test isdigit, isalpha, isalnum, etc."""
        s1 = TaintStr("123", taint_origin="source1")
        s2 = TaintStr("abc", taint_origin="source2")
        s3 = TaintStr("abc123", taint_origin="source3")
        s4 = TaintStr("   ", taint_origin="source4")

        assert s1.isdigit() is True
        assert s2.isalpha() is True
        assert s3.isalnum() is True
        assert s4.isspace() is True
        assert s1.isnumeric() is True
        assert s2.islower() is True
        assert TaintStr("ABC", "src").isupper() is True

    def test_hash(self):
        """Test that TaintStr is hashable."""
        s1 = TaintStr("hello", taint_origin="source1")
        s2 = TaintStr("hello", taint_origin="source2")
        s3 = "hello"

        # Same string should have same hash regardless of taint
        assert hash(s1) == hash(s2) == hash(s3)

        # Can be used in sets and dicts
        test_set = {s1, s2, s3}
        assert len(test_set) == 1  # All are considered equal

    def test_str_repr(self):
        """Test __str__ and __repr__ methods."""
        s = TaintStr("hello", taint_origin="source1")

        assert str(s) == "hello"
        assert repr(s) == "'hello'"

    def test_get_raw(self):
        """Test get_raw method."""
        s = TaintStr("hello", taint_origin="source1")
        raw = s.get_raw()
        assert raw == "hello"
        assert isinstance(raw, str)
        assert not isinstance(raw, TaintStr)
