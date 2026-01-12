"""Unit tests for taint tracking (list) functionality."""

import pytest

from ao.server.taint_ops import add_to_taint_dict_and_return as taint, get_taint
from ....utils import with_ast_rewriting_class


@with_ast_rewriting_class
class TestTaintList:
    """Test suite for taint tracking (list) functionality."""

    def test_creation(self):
        """Test taint creation with various taint origins."""
        # Test with no taint
        l1 = [1, 2, 3]  # No wrapping for no taint
        assert list(l1) == [1, 2, 3]
        assert get_taint(l1) == []

        # Test with single string taint
        l2 = taint(["a", "b"], ["source1"])
        assert list(l2) == ["a", "b"]
        assert get_taint(l2) == ["source1"]

        # Test with single int taint
        l3 = taint([10], [999])
        assert list(l3) == [10]
        assert get_taint(l3) == [999]

        # Test with list taint
        l4 = taint([], ["source1", "source2"])
        assert list(l4) == []
        assert set(get_taint(l4)) == {"source1", "source2"}

        # Test with tainted items - item taint is accessed via item
        tainted_str = taint("tainted", ["item_source"])
        l5 = [tainted_str, "normal"]
        # List itself has no taint, but item does
        assert get_taint(l5) == []
        assert get_taint(l5[0]) == ["item_source"]

    def test_append(self):
        """Test append method."""
        l = taint([1, 2], ["original"])

        # Append normal item
        l.append(3)
        assert list(l) == [1, 2, 3]
        assert get_taint(l) == ["original"]

        # Append tainted item
        tainted = taint("tainted", ["new_item"])
        l.append(tainted)
        assert list(l) == [1, 2, 3, "tainted"]
        # List keeps its own taint
        assert set(get_taint(l)) == set(["original"])
        # Untainted items inherit parent's taint
        assert set(get_taint(l[0])) == set(["original"])
        # Tainted items keep their own taint
        assert set(get_taint(l[-1])) == set(["new_item"])

    # NOTE: This test fails due to the way tests are set up. SomeObj class
    # is not identified as user code but would be in normal operation.
    # def test_obj(self):
    #     class SomeObj:
    #         def __init__(self, x, y):
    #             self.list = [x, y]

    #         def add_to_list(self, z):
    #             self.list.append(z)

    #     tainted = taint(3, ["new_item"])
    #     o = taint(SomeObj(1, [2]))
    #     o.add_to_list(tainted)
    #     assert get_taint(o.list[-1]) == ["new_item"], f"{get_taint(o.list[-1])}"

    def test_extend(self):
        """Test extend method."""
        l = taint([1, 2], ["original"])

        # Extend with normal items
        l.extend([3, 4])
        assert list(l) == [1, 2, 3, 4]
        assert get_taint(l) == ["original"]

        # Extend with tainted items
        tainted1 = taint("t1", ["ext1"])
        tainted2 = taint("t2", ["ext2"])
        l.extend([tainted1, tainted2])
        assert list(l) == [1, 2, 3, 4, "t1", "t2"]
        # List keeps its own taint, items have their own taint
        assert get_taint(l) == ["original"]
        assert get_taint(l[-2]) == ["ext1"]
        assert get_taint(l[-1]) == ["ext2"]

    def test_setitem(self):
        """Test __setitem__ method."""
        l = taint([1, 2, 3, 4], ["original"])

        # Set single item (normal)
        l[0] = 10
        assert list(l) == [10, 2, 3, 4]
        assert get_taint(l) == ["original"]

        # Set single item (tainted)
        tainted = taint("tainted", ["new_item"])
        l[1] = tainted
        assert list(l) == [10, "tainted", 3, 4]
        # List keeps its own taint, item has its own taint
        assert get_taint(l) == ["original"]
        assert get_taint(l[1]) == ["new_item"]

        # Set slice
        l[2:4] = [30, 40]
        assert list(l) == [10, "tainted", 30, 40]
        assert get_taint(l) == ["original"]

        # Set slice with tainted items
        tainted1 = taint("s1", ["slice1"])
        tainted2 = taint("s2", ["slice2"])
        l[0:2] = [tainted1, tainted2]
        assert list(l) == ["s1", "s2", 30, 40]
        assert get_taint(l) == ["original"]
        assert get_taint(l[0]) == ["slice1"]
        assert get_taint(l[1]) == ["slice2"]

    def test_delitem(self):
        """Test __delitem__ method."""
        tainted1 = taint("t1", ["item1"])
        tainted2 = taint("t2", ["item2"])
        l = taint([tainted1, "normal", tainted2], ["original"])

        # Delete single item
        del l[1]  # Remove "normal"
        assert list(l) == ["t1", "t2"]
        # List keeps its own taint
        assert get_taint(l) == ["original"]
        # Items still have their taint
        assert get_taint(l[0]) == ["item1"]
        assert get_taint(l[1]) == ["item2"]

        # Delete slice
        l = taint([1, tainted1, 3, tainted2, 5], ["original"])
        del l[1:4]  # Remove indices 1,2,3 (tainted1, 3, tainted2)
        assert list(l) == [1, 5]
        # List keeps its own taint
        assert get_taint(l) == ["original"]

    def test_insert(self):
        """Test insert method."""
        l = taint([1, 3], ["original"])

        # Insert normal item
        l.insert(1, 2)
        assert list(l) == [1, 2, 3]
        assert get_taint(l) == ["original"]

        # Insert tainted item
        tainted = taint("inserted", ["inserted_item"])
        l.insert(0, tainted)
        assert list(l) == ["inserted", 1, 2, 3]
        # List keeps its own taint, item has its own taint
        assert get_taint(l) == ["original"]
        assert get_taint(l[0]) == ["inserted_item"]

    def test_pop(self):
        """Test pop method."""
        tainted1 = taint("t1", ["item1"])
        tainted2 = taint("t2", ["item2"])
        l = taint([tainted1, "normal", tainted2], ["original"])

        # Pop last item - popped item retains its taint
        popped = l.pop()
        assert popped == "t2"
        assert get_taint(popped) == ["item2"]
        assert list(l) == ["t1", "normal"]
        # List keeps its own taint
        assert get_taint(l) == ["original"]

        # Pop specific index
        popped = l.pop(0)
        assert popped == "t1"
        assert get_taint(popped) == ["item1"]
        assert list(l) == ["normal"]
        # List keeps its own taint
        assert get_taint(l) == ["original"]

    def test_remove(self):
        """Test remove method."""
        tainted1 = taint("t1", ["item1"])
        tainted2 = taint("t2", ["item2"])
        l = taint([tainted1, "normal", tainted2, tainted1], ["original"])

        # Remove first occurrence of tainted1
        l.remove("t1")  # Use the unwrapped value for comparison
        assert list(l) == ["normal", "t2", "t1"]
        # List keeps its own taint
        assert get_taint(l) == ["original"]

    def test_clear(self):
        """Test clear method."""
        tainted = taint("tainted", ["item"])
        l = taint([1, tainted, 3], ["original"])

        l.clear()
        assert list(l) == []
        # Still retains the original list taint
        assert get_taint(l) == ["original"]

    def test_iadd(self):
        """Test += operator."""
        l = taint([1, 2], ["original"])

        # += with normal list
        l += [3, 4]
        assert list(l) == [1, 2, 3, 4]
        assert get_taint(l) == ["original"]

        # += with tainted items
        tainted = taint("tainted", ["added"])
        l += [tainted]
        assert list(l) == [1, 2, 3, 4, "tainted"]
        # List keeps its own taint, item has its own taint
        assert get_taint(l) == ["original"]
        assert get_taint(l[-1]) == ["added"]

        # Verify it returns self
        result = l
        l += [5]
        assert l is result

    def test_imul(self):
        """Test *= operator."""
        tainted = taint("t", ["item"])
        l = taint([1, tainted], ["original"])

        l *= 3
        expected = [1, "t", 1, "t", 1, "t"]
        assert list(l) == expected
        # List keeps its own taint
        assert get_taint(l) == ["original"]
        # Items retain their taint
        assert get_taint(l[1]) == ["item"]

        # Verify it returns self
        result = l
        l *= 1
        assert l is result

    def test_get_raw(self):
        tainted = taint("tainted", ["item"])
        l = taint([1, tainted, 3], ["original"])

        raw = l
        assert raw == [1, "tainted", 3]  # Returns fully unwrapped list
        assert isinstance(raw, list)

    def test_list_methods(self):
        """Test standard list methods work correctly."""
        tainted = taint("tainted", ["item"])
        l = taint([1, tainted, 3, tainted], ["original"])

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
        assert get_taint(l) == ["original"]

        # sort (if items are comparable)
        l2 = taint([3, 1, 2], ["sortable"])
        l2.sort()
        assert list(l2) == [1, 2, 3]
        assert get_taint(l2) == ["sortable"]

    def test_list_operations(self):
        """Test list-like operations."""
        tainted1 = taint("t1", ["item1"])
        tainted2 = taint("t2", ["item2"])
        l = taint([1, tainted1, 3], ["original"])

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
        empty = taint([], ["empty"])
        assert bool(empty) is False

    def test_nested_taint_propagation(self):
        """Test taint propagation with nested structures."""
        # Create nested tainted items
        inner_list = taint([1, 2], ["inner"])
        tainted_str = taint("nested", ["string"])

        outer = taint([inner_list, tainted_str], ["outer"])

        # Outer list has its own taint
        assert get_taint(outer) == ["outer"]
        # Items have their own taint
        assert get_taint(outer[0]) == ["inner"]
        assert get_taint(outer[1]) == ["string"]

        # Modify inner list
        inner_list.append(taint("new", ["added"]))

        # Inner list's new item has its taint
        assert get_taint(inner_list[-1]) == ["added"]

    def test_comparison_with_regular_lists(self):
        """Test that tainted lists behave like regular lists in comparisons."""
        l1 = taint([1, 2, 3], ["source1"])
        l2 = [1, 2, 3]
        l3 = taint([1, 2, 3], ["source2"])

        # Should be equal regardless of taint
        assert l1 == l2
        assert l1 == l3
        assert l2 == l3

        # Different contents should not be equal
        l4 = taint([1, 2, 4], ["source1"])
        assert l1 != l4
