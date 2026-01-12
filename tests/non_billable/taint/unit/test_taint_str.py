"""Unit tests for taint tracking (string) functionality."""

import pytest

from ao.server.taint_ops import add_to_taint_dict_and_return as taint, get_taint
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintStr:
    """Test suite for taint tracking (string) functionality."""

    def test_creation(self):
        """Test taint_wrap creation with various taint origins."""
        # Test with no taint
        s1 = "hello"  # Plain string, not wrapped
        assert s1 == "hello"
        assert get_taint(s1) == []

        # Test with single string taint
        s2 = taint("world", ["source1"])
        assert s2 == "world"
        assert get_taint(s2) == ["source1"]

        # Test with single int taint
        s3 = taint("test", [42])
        assert s3 == "test"
        assert get_taint(s3) == [42]

        # Test with list taint
        s4 = taint("data", ["source1", "source2"])
        assert s4 == "data"
        assert set(get_taint(s4)) == {"source1", "source2"}

    def test_addition(self):
        """Test string addition operations."""
        s1 = taint("hello", ["source1"])
        s2 = taint(" world", ["source2"])

        # tainted string + tainted string
        result = s1 + s2
        assert str(result) == "hello world"
        assert set(get_taint(result)) == {"source1", "source2"}

        # tainted string + str
        result = s1 + " there"
        assert str(result) == "hello there"
        assert get_taint(result) == ["source1"]

        # str + tainted string (radd)
        result = "Hi " + s2
        assert str(result) == "Hi  world"
        assert get_taint(result) == ["source2"]

    def test_format(self):
        """Test string formatting."""
        s = taint("test", ["source1"])

        # Test __format__
        result = format(s, ">10")
        assert str(result) == "      test"
        assert get_taint(result) == ["source1"]

    def test_getitem(self):
        """Test string indexing and slicing."""
        s = taint("hello world", ["source1"])

        # Single character
        result = s[0]
        assert str(result) == "h"
        assert get_taint(result) == ["source1"]

        # Slice
        result = s[0:5]
        assert str(result) == "hello"
        assert get_taint(result) == ["source1"]

        # Negative index
        result = s[-5:]
        assert str(result) == "world"
        assert get_taint(result) == ["source1"]

    def test_mod_operator(self):
        """Test % operator for string formatting.

        Uses unique result strings to avoid Python string interning,
        which would cause false taint sharing with id-based tracking.
        """
        s = taint("Greetings %s", ["template"])

        # Single argument
        arg = taint("Universe", ["arg1"])
        result = s % arg
        assert str(result) == "Greetings Universe"
        assert set(get_taint(result)) == {"template", "arg1"}

        # Multiple arguments (tuple)
        s2 = taint("%s to %s", ["template2"])
        arg1 = taint("Welcome", ["arg1"])
        arg2 = taint("Earth", ["arg2"])
        result = s2 % (arg1, arg2)
        assert str(result) == "Welcome to Earth"
        assert set(get_taint(result)) == {"template2", "arg1", "arg2"}

        # rmod - untainted template with tainted argument
        template = "Salutations %s"
        arg = taint("Planet", ["arg_only"])
        result = template % arg
        assert str(result) == "Salutations Planet"
        assert get_taint(result) == ["arg_only"]

    def test_encode_decode(self):
        """Test encode and decode methods."""
        s = taint("hello", ["source1"])

        # Encode should return bytes (untainted)
        encoded = s.encode("utf-8")
        assert isinstance(encoded, bytes)
        assert encoded == b"hello"

    def test_join(self):
        """Test join method."""
        sep = taint("-", ["separator"])

        # Join normal strings
        result = sep.join(["a", "b", "c"])
        assert str(result) == "a-b-c"
        assert get_taint(result) == ["separator"]

        # Join tainted strings
        items = [taint("x", ["item1"]), taint("y", ["item2"]), "z"]
        result = sep.join(items)
        assert str(result) == "x-y-z"
        assert set(get_taint(result)) == {"separator", "item1", "item2"}

    def test_case_methods(self):
        """Test case conversion methods."""
        s = taint("Hello World", ["source1"])

        # upper
        result = s.upper()
        assert str(result) == "HELLO WORLD"
        assert get_taint(result) == ["source1"]

        # lower
        result = s.lower()
        assert str(result) == "hello world"
        assert get_taint(result) == ["source1"]

        # capitalize
        result = s.capitalize()
        assert str(result) == "Hello world"
        assert get_taint(result) == ["source1"]

        # title
        result = s.title()
        assert str(result) == "Hello World"
        assert get_taint(result) == ["source1"]

    def test_strip_methods(self):
        """Test strip, lstrip, rstrip methods."""
        s = taint("  hello world  ", ["source1"])

        # strip
        result = s.strip()
        assert str(result) == "hello world"
        assert get_taint(result) == ["source1"]

        # lstrip
        result = s.lstrip()
        assert str(result) == "hello world  "
        assert get_taint(result) == ["source1"]

        # rstrip
        result = s.rstrip()
        assert str(result) == "  hello world"
        assert get_taint(result) == ["source1"]

    def test_replace(self):
        """Test replace method."""
        s = taint("hello world", ["source1"])
        replacement = taint("universe", ["source2"])

        result = s.replace("world", replacement)
        assert str(result) == "hello universe"
        assert set(get_taint(result)) == {"source1", "source2"}

        # Replace with normal string
        result = s.replace("world", "there")
        assert str(result) == "hello there"
        assert get_taint(result) == ["source1"]

    def test_split(self):
        """Test split method.

        Uses unique strings to avoid Python string interning,
        which would cause false taint sharing with id-based tracking.
        """
        s = taint("alpha7-beta8-gamma9", ["split_src"])

        result = s.split("-")
        assert len(result) == 3
        assert [str(part) for part in result] == ["alpha7", "beta8", "gamma9"]
        assert all(get_taint(part) == ["split_src"] for part in result), f"result: {result}"

    def test_search_methods(self):
        """Test startswith, endswith, find, index, count methods."""
        s = taint("hello world", ["source1"])

        # These should return bool/int (not tainted)
        assert s.startswith("hello") is True
        assert s.endswith("world") is True
        assert s.find("world") == 6
        assert s.index("world") == 6
        assert s.count("l") == 3

    def test_check_methods(self):
        """Test isdigit, isalpha, isalnum, etc."""
        s1 = taint("123", ["source1"])
        s2 = taint("abc", ["source2"])
        s3 = taint("abc123", ["source3"])
        s4 = taint("   ", ["source4"])

        assert s1.isdigit() is True
        assert s2.isalpha() is True
        assert s3.isalnum() is True
        assert s4.isspace() is True
        assert s1.isnumeric() is True
        assert s2.islower() is True
        assert taint("ABC", ["src"]).isupper() is True

    def test_hash(self):
        """Test that tainted values are hashable."""
        s1 = taint("hello", ["source1"])
        s2 = taint("world", ["source2"])
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
        s = taint("hello", ["source1"])

        assert str(s) == "hello"
        # repr returns the string's repr
        assert "hello" in repr(s)

    def test_get_raw(self):
        s = taint("hello", ["source1"])
        raw = s
        assert raw == "hello"
        assert isinstance(raw, str)
