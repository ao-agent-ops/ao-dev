"""Unit tests for TaintWrapper (list) functionality."""

import pytest

from ao.server.ast_helpers import taint_wrap, get_taint_origins, untaint_if_needed
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintList:
    """Test suite for TaintWrapper (list) functionality."""

    def test_creation(self):
        """Test TaintWrapper creation with various taint origins."""
        # Test with no taint
        l1 = [1, 2, 3]  # No wrapping for no taint
        assert list(l1) == [1, 2, 3]
        assert get_taint_origins(l1) == []

        # Test with single string taint
        l2 = taint_wrap(["a", "b"], taint_origin="source1")
        assert list(l2) == ["a", "b"]
        assert get_taint_origins(l2) == ["source1"]

        # Test with single int taint
        l3 = taint_wrap([10], taint_origin=999)
        assert list(l3) == [10]
        assert get_taint_origins(l3) == [999]

        # Test with list taint
        l4 = taint_wrap([], taint_origin=["source1", "source2"])
        assert list(l4) == []
        assert set(get_taint_origins(l4)) == {"source1", "source2"}

        # Test with tainted items - item taint is accessed via item
        tainted_str = taint_wrap("tainted", taint_origin="item_source")
        l5 = [tainted_str, "normal"]
        # List itself has no taint, but item does
        assert get_taint_origins(l5) == []
        assert get_taint_origins(l5[0]) == ["item_source"]

    def test_append(self):
        """Test append method."""
        l = taint_wrap([1, 2], taint_origin="original")

        # Append normal item
        l.append(3)
        assert list(l) == [1, 2, 3]
        assert get_taint_origins(l) == ["original"]

        # Append tainted item
        tainted = taint_wrap("tainted", taint_origin="new_item")
        l.append(tainted)
        assert list(l) == [1, 2, 3, "tainted"]
        # List keeps its own taint
        assert set(get_taint_origins(l)) == set(["original"])
        # Untainted items inherit parent's taint
        assert set(get_taint_origins(l[0])) == set(["original"])
        # Tainted items keep their own taint
        assert set(get_taint_origins(l[-1])) == set(["new_item"])

    # NOTE: This test fails due to the way tests are set up. SomeObj class
    # is not identified as user code but would be in normal operation.
    # def test_obj(self):
    #     class SomeObj:
    #         def __init__(self, x, y):
    #             self.list = [x, y]

    #         def add_to_list(self, z):
    #             self.list.append(z)

    #     tainted = taint_wrap(3, taint_origin="new_item")
    #     o = taint_wrap(SomeObj(1, 2))
    #     o.add_to_list(tainted)
    #     assert get_taint_origins(o.list[-1]) == ["new_item"], f"{get_taint_origins(o.list[-1])}"

    def test_extend(self):
        """Test extend method."""
        l = taint_wrap([1, 2], taint_origin="original")

        # Extend with normal items
        l.extend([3, 4])
        assert list(l) == [1, 2, 3, 4]
        assert get_taint_origins(l) == ["original"]

        # Extend with tainted items
        tainted1 = taint_wrap("t1", taint_origin="ext1")
        tainted2 = taint_wrap("t2", taint_origin="ext2")
        l.extend([tainted1, tainted2])
        assert list(l) == [1, 2, 3, 4, "t1", "t2"]
        # List keeps its own taint, items have their own taint
        assert get_taint_origins(l) == ["original"]
        assert get_taint_origins(l[-2]) == ["ext1"]
        assert get_taint_origins(l[-1]) == ["ext2"]

    def test_setitem(self):
        """Test __setitem__ method."""
        l = taint_wrap([1, 2, 3, 4], taint_origin="original")

        # Set single item (normal)
        l[0] = 10
        assert list(l) == [10, 2, 3, 4]
        assert get_taint_origins(l) == ["original"]

        # Set single item (tainted)
        tainted = taint_wrap("tainted", taint_origin="new_item")
        l[1] = tainted
        assert list(l) == [10, "tainted", 3, 4]
        # List keeps its own taint, item has its own taint
        assert get_taint_origins(l) == ["original"]
        assert get_taint_origins(l[1]) == ["new_item"]

        # Set slice
        l[2:4] = [30, 40]
        assert list(l) == [10, "tainted", 30, 40]
        assert get_taint_origins(l) == ["original"]

        # Set slice with tainted items
        tainted1 = taint_wrap("s1", "slice1")
        tainted2 = taint_wrap("s2", "slice2")
        l[0:2] = [tainted1, tainted2]
        assert list(l) == ["s1", "s2", 30, 40]
        assert get_taint_origins(l) == ["original"]
        assert get_taint_origins(l[0]) == ["slice1"]
        assert get_taint_origins(l[1]) == ["slice2"]

    def test_delitem(self):
        """Test __delitem__ method."""
        tainted1 = taint_wrap("t1", taint_origin="item1")
        tainted2 = taint_wrap("t2", taint_origin="item2")
        l = taint_wrap([tainted1, "normal", tainted2], taint_origin="original")

        # Delete single item
        del l[1]  # Remove "normal"
        assert list(l) == ["t1", "t2"]
        # List keeps its own taint
        assert get_taint_origins(l) == ["original"]
        # Items still have their taint
        assert get_taint_origins(l[0]) == ["item1"]
        assert get_taint_origins(l[1]) == ["item2"]

        # Delete slice
        l = taint_wrap([1, tainted1, 3, tainted2, 5], taint_origin="original")
        del l[1:4]  # Remove indices 1,2,3 (tainted1, 3, tainted2)
        assert list(l) == [1, 5]
        # List keeps its own taint
        assert get_taint_origins(l) == ["original"]

    def test_insert(self):
        """Test insert method."""
        l = taint_wrap([1, 3], taint_origin="original")

        # Insert normal item
        l.insert(1, 2)
        assert list(l) == [1, 2, 3]
        assert get_taint_origins(l) == ["original"]

        # Insert tainted item
        tainted = taint_wrap("inserted", taint_origin="inserted_item")
        l.insert(0, tainted)
        assert list(l) == ["inserted", 1, 2, 3]
        # List keeps its own taint, item has its own taint
        assert get_taint_origins(l) == ["original"]
        assert get_taint_origins(l[0]) == ["inserted_item"]

    def test_pop(self):
        """Test pop method."""
        tainted1 = taint_wrap("t1", taint_origin="item1")
        tainted2 = taint_wrap("t2", taint_origin="item2")
        l = taint_wrap([tainted1, "normal", tainted2], taint_origin="original")

        # Pop last item - popped item retains its taint
        popped = l.pop()
        assert popped == "t2"
        assert get_taint_origins(popped) == ["item2"]
        assert list(l) == ["t1", "normal"]
        # List keeps its own taint
        assert get_taint_origins(l) == ["original"]

        # Pop specific index
        popped = l.pop(0)
        assert popped == "t1"
        assert get_taint_origins(popped) == ["item1"]
        assert list(l) == ["normal"]
        # List keeps its own taint
        assert get_taint_origins(l) == ["original"]

    def test_remove(self):
        """Test remove method."""
        tainted1 = taint_wrap("t1", taint_origin="item1")
        tainted2 = taint_wrap("t2", taint_origin="item2")
        l = taint_wrap([tainted1, "normal", tainted2, tainted1], taint_origin="original")

        # Remove first occurrence of tainted1
        l.remove("t1")  # Use the unwrapped value for comparison
        assert list(l) == ["normal", "t2", "t1"]
        # List keeps its own taint
        assert get_taint_origins(l) == ["original"]

    def test_clear(self):
        """Test clear method."""
        tainted = taint_wrap("tainted", taint_origin="item")
        l = taint_wrap([1, tainted, 3], taint_origin="original")

        l.clear()
        assert list(l) == []
        # Still retains the original list taint
        assert get_taint_origins(l) == ["original"]

    def test_iadd(self):
        """Test += operator."""
        l = taint_wrap([1, 2], taint_origin="original")

        # += with normal list
        l += [3, 4]
        assert list(l) == [1, 2, 3, 4]
        assert get_taint_origins(l) == ["original"]

        # += with tainted items
        tainted = taint_wrap("tainted", taint_origin="added")
        l += [tainted]
        assert list(l) == [1, 2, 3, 4, "tainted"]
        # List keeps its own taint, item has its own taint
        assert get_taint_origins(l) == ["original"]
        assert get_taint_origins(l[-1]) == ["added"]

        # Verify it returns self
        result = l
        l += [5]
        assert l is result

    def test_imul(self):
        """Test *= operator."""
        tainted = taint_wrap("t", taint_origin="item")
        l = taint_wrap([1, tainted], taint_origin="original")

        l *= 3
        expected = [1, "t", 1, "t", 1, "t"]
        assert list(l) == expected
        # List keeps its own taint
        assert get_taint_origins(l) == ["original"]
        # Items retain their taint
        assert get_taint_origins(l[1]) == ["item"]

        # Verify it returns self
        result = l
        l *= 1
        assert l is result

    def test_get_raw(self):
        """Test getting raw object using untaint_if_needed."""
        tainted = taint_wrap("tainted", taint_origin="item")
        l = taint_wrap([1, tainted, 3], taint_origin="original")

        raw = untaint_if_needed(l)
        assert raw == [1, "tainted", 3]  # Returns fully unwrapped list
        assert isinstance(raw, list)

    def test_list_methods(self):
        """Test standard list methods work correctly."""
        tainted = taint_wrap("tainted", taint_origin="item")
        l = taint_wrap([1, tainted, 3, tainted], taint_origin="original")

        # count - use unwrapped value for comparison
        assert l.count("tainted") == 2
        assert l.count(1) == 1
        assert l.count("missing") == 0

        # index - use unwrapped value for comparison
        assert l.index("tainted") == 1
        assert l.index(3) == 2

        # reverse
        l.reverse()
        expected = ["tainted", 3, "tainted", 1]
        assert list(l) == expected
        # List keeps its own taint
        assert get_taint_origins(l) == ["original"]

        # sort (if items are comparable)
        l2 = taint_wrap([3, 1, 2], taint_origin="sortable")
        l2.sort()
        assert list(l2) == [1, 2, 3]
        assert get_taint_origins(l2) == ["sortable"]

    def test_list_operations(self):
        """Test list-like operations."""
        tainted1 = taint_wrap("t1", taint_origin="item1")
        tainted2 = taint_wrap("t2", taint_origin="item2")
        l = taint_wrap([1, tainted1, 3], taint_origin="original")

        # len
        assert len(l) == 3

        # in operator - use unwrapped value for comparison
        assert 1 in l
        assert "t1" in l
        assert "missing" not in l

        # iter
        items = []
        for item in l:
            items.append(item)
        assert items == [1, "t1", 3]

        # bool
        assert bool(l) is True
        empty = taint_wrap([], taint_origin="empty")
        assert bool(empty) is False

    def test_nested_taint_propagation(self):
        """Test taint propagation with nested structures."""
        # Create nested tainted items
        inner_list = taint_wrap([1, 2], taint_origin="inner")
        tainted_str = taint_wrap("nested", taint_origin="string")

        outer = taint_wrap([inner_list, tainted_str], taint_origin="outer")

        # Outer list has its own taint
        assert get_taint_origins(outer) == ["outer"]
        # Items have their own taint
        assert get_taint_origins(outer[0]) == ["inner"]
        assert get_taint_origins(outer[1]) == ["string"]

        # Modify inner list
        inner_list.append(taint_wrap("new", taint_origin="added"))

        # Inner list's new item has its taint
        assert get_taint_origins(inner_list[-1]) == ["added"]

    def test_comparison_with_regular_lists(self):
        """Test that TaintWrapper behaves like regular list in comparisons."""
        l1 = taint_wrap([1, 2, 3], taint_origin="source1")
        l2 = [1, 2, 3]
        l3 = taint_wrap([1, 2, 3], taint_origin="source2")

        # Should be equal regardless of taint
        assert l1 == l2
        assert l1 == l3
        assert l2 == l3

        # Different contents should not be equal
        l4 = taint_wrap([1, 2, 4], taint_origin="source1")
        assert l1 != l4
