from typing import Any
from uuid import UUID
from runner.taint_wrappers import TaintStr, Position


class RandomObject:
    def __init__(self, obj: Any):
        self.obj = obj


def uuid_patch():
    setattr(UUID, "hex", property(hex))
    setattr(UUID, "__str__", uuid_str)
    setattr(UUID, "__repr__", uuid_repr)


def hex(self: UUID):
    hex_str = "%032x" % self.int
    return TaintStr(hex_str, random_pos=Position(0, len(hex_str)))


def uuid_str(self: UUID):
    hex_str = "%032x" % self.int
    formatted_uuid = "%s-%s-%s-%s-%s" % (
        hex_str[:8],
        hex_str[8:12],
        hex_str[12:16],
        hex_str[16:20],
        hex_str[20:],
    )
    return TaintStr(formatted_uuid, random_pos=Position(0, len(formatted_uuid)))


def uuid_repr(self: UUID):
    repr_str = "%s(%r)" % (self.__class__.__name__, str(self))
    return TaintStr(repr_str, random_pos=Position(0, len(repr_str)))


if __name__ == "__main__":
    uuid_patch()
    from uuid import uuid4

    print("=== Testing Position tracking in UUID patches ===")
    test_uuid = uuid4()

    # Test 1: Basic hex property with Position
    print("\nTest 1 - hex property:")
    uuid_hex = test_uuid.hex
    print("  hex result: " + repr(uuid_hex))
    print("  hex type: " + str(type(uuid_hex)))
    print("  hex random positions: " + str(uuid_hex._random_positions))

    # Test 2: str method with Position
    print("\nTest 2 - __str__ method:")
    uuid_str_result = str(test_uuid)
    print("  str result: " + repr(uuid_str_result))
    print("  str type: " + str(type(uuid_str_result)))
    print("  str random positions: " + str(uuid_str_result._random_positions))

    # Test 3: repr method with Position
    print("\nTest 3 - __repr__ method:")
    uuid_repr_result = repr(test_uuid)
    print("  repr result: " + repr(uuid_repr_result))
    print("  repr type: " + str(type(uuid_repr_result)))
    print("  repr random positions: " + str(uuid_repr_result._random_positions))

    # Test 4: String concatenation with Position tracking
    print("\nTest 4 - String concatenation:")
    uuid_hex = test_uuid.hex
    added_string = uuid_hex + "hello"
    print("  Original hex: " + repr(uuid_hex))
    print("  Original positions: " + str(uuid_hex._random_positions))
    print("  After adding 'hello': " + repr(added_string))
    print("  Concatenated positions: " + str(added_string._random_positions))

    # Test 5: Position object inspection
    print("\nTest 5 - Position object details:")
    first_pos = uuid_hex._random_positions[0]
    print("  Position object: " + repr(first_pos))
    print("  Start: " + str(first_pos.start))
    print("  Stop: " + str(first_pos.stop))

    # Test 6: Multiple UUID operations
    print("\nTest 6 - Multiple UUID operations:")
    uuid1 = uuid4().hex
    uuid2 = uuid4().hex
    combined = uuid1 + "-" + uuid2
    print("  UUID1: " + repr(uuid1))
    print("  UUID2: " + repr(uuid2))
    print("  Combined: " + repr(combined))
    print("  Combined positions: " + str(combined._random_positions))

    # Test 7: String slicing and indexing with Position tracking
    print("\nTest 7 - String slicing and indexing:")
    uuid_hex = test_uuid.hex
    slice_result = uuid_hex[5:15]
    single_char = uuid_hex[10]
    print("  Original UUID hex: " + repr(uuid_hex))
    print("  Original positions: " + str(uuid_hex._random_positions))
    print("  Slice [5:15]: " + repr(slice_result))
    print("  Slice positions: " + str(slice_result._random_positions))
    print("  Single char [10]: " + repr(single_char))
    print("  Single char positions: " + str(single_char._random_positions))

    # Test 8: String replacement operations
    print("\nTest 8 - String replacement:")
    uuid_str = str(test_uuid)
    replaced = uuid_str.replace("-", "_")
    print("  Original UUID str: " + repr(uuid_str))
    print("  Original positions: " + str(uuid_str._random_positions))
    print("  After replace('-', '_'): " + repr(replaced))
    print("  Replaced positions: " + str(replaced._random_positions))

    # Test 9: String formatting with UUID
    print("\nTest 9 - String formatting:")
    uuid_hex = test_uuid.hex
    formatted = "UUID: " + uuid_hex + " (length: " + str(len(uuid_hex)) + ")"
    print("  Formatted string: " + repr(formatted))
    print("  Formatted positions: " + str(formatted._random_positions))

    # Test 10: Multiple concatenations with position shifts
    print("\nTest 10 - Multiple concatenations:")
    prefix = "prefix-"
    uuid_part = uuid4().hex[:8]
    suffix = "-suffix"
    result = prefix + uuid_part + suffix
    print("  Prefix: " + repr(prefix))
    print("  UUID part: " + repr(uuid_part))
    print("  UUID part positions: " + str(uuid_part._random_positions))
    print("  Suffix: " + repr(suffix))
    print("  Final result: " + repr(result))
    print("  Final positions: " + str(result._random_positions))

    # Test 11: Position object manipulation
    print("\nTest 11 - Position object manipulation:")
    uuid_hex = test_uuid.hex
    pos = uuid_hex._random_positions[0]
    print("  Original position: " + repr(pos))
    print("  Position start: " + str(pos.start))
    print("  Position stop: " + str(pos.stop))

    # Create a copy and shift it
    from runner.taint_wrappers import Position

    pos_copy = Position(pos.start, pos.stop)
    pos_copy.shift(10)
    print("  After shift(10): " + repr(pos_copy))

    # Test 12: Edge cases with empty strings and boundaries
    print("\nTest 12 - Edge cases:")
    uuid_hex = test_uuid.hex
    empty_concat = uuid_hex + ""
    boundary_slice = uuid_hex[0:1]
    end_slice = uuid_hex[-4:]
    print("  UUID + empty string: " + repr(empty_concat))
    print("  Empty concat positions: " + str(empty_concat._random_positions))
    print("  First character [0:1]: " + repr(boundary_slice))
    print("  First char positions: " + str(boundary_slice._random_positions))
    print("  Last 4 chars [-4:]: " + repr(end_slice))
    print("  Last 4 positions: " + str(end_slice._random_positions))

    # Test 13: Complex nested operations
    print("\nTest 13 - Complex nested operations:")
    uuid1 = uuid4().hex
    uuid2 = uuid4().hex
    complex_result = (uuid1[:8] + "-" + uuid2[8:16]).upper()
    print("  UUID1: " + repr(uuid1))
    print("  UUID2: " + repr(uuid2))
    print("  Complex result: " + repr(complex_result))
    print("  Complex positions: " + str(complex_result._random_positions))

    # Test 14: Testing all UUID methods together
    print("\nTest 14 - All UUID methods:")
    test_uuid2 = uuid4()
    hex_val = test_uuid2.hex
    str_val = str(test_uuid2)
    repr_val = repr(test_uuid2)

    print("  hex: " + repr(hex_val) + " positions: " + str(hex_val._random_positions))
    print("  str: " + repr(str_val) + " positions: " + str(str_val._random_positions))
    print("  repr: " + repr(repr_val) + " positions: " + str(repr_val._random_positions))

    # Verify position consistency
    hex_len = len(hex_val)
    str_len = len(str_val)
    print(
        "  hex length vs position: "
        + str(hex_len)
        + " vs "
        + str(hex_val._random_positions[0].stop)
    )
    print(
        "  str length vs position: "
        + str(str_len)
        + " vs "
        + str(str_val._random_positions[0].stop)
    )

    # Test 15: F-string formatting
    print("\nTest 15 - F-string formatting:")
    uuid_hex = test_uuid.hex
    f_string_result = f"UUID is {uuid_hex} with length {len(uuid_hex)}"
    print("  UUID hex: " + repr(uuid_hex))
    print("  UUID positions: " + str(uuid_hex._random_positions))
    print("  F-string result: " + repr(f_string_result))
    print("  F-string type: " + str(type(f_string_result)))
    if hasattr(f_string_result, "_random_positions"):
        print("  F-string positions: " + str(f_string_result._random_positions))
    else:
        print("  F-string positions: None (not a TaintStr)")

    # Test 16: String modulo formatting (__mod__ and __rmod__)
    print("\nTest 16 - String modulo formatting:")
    uuid_hex = test_uuid.hex
    mod_result1 = "UUID: %s" % uuid_hex
    mod_result2 = "UUID: %s, Length: %d" % (uuid_hex, len(uuid_hex))
    print("  Single %s: " + repr(mod_result1))
    print("  Single %s positions: " + str(mod_result1._random_positions))
    print("  Multiple %s: " + repr(mod_result2))
    print("  Multiple %s positions: " + str(mod_result2._random_positions))

    # Test reverse modulo
    template = TaintStr("Template: %s")
    rmod_result = template % uuid_hex
    print("  Reverse mod template: " + repr(template))
    print("  Reverse mod result: " + repr(rmod_result))
    print("  Reverse mod positions: " + str(rmod_result._random_positions))

    # Test 17: String methods that return strings
    print("\nTest 17 - String methods returning strings:")
    uuid_str = str(test_uuid)

    # Test strip methods
    padded_uuid = "   " + uuid_str + "   "
    stripped = padded_uuid.strip()
    lstripped = padded_uuid.lstrip()
    rstripped = padded_uuid.rstrip()
    print("  Padded UUID: " + repr(padded_uuid))
    print("  Padded positions: " + str(padded_uuid._random_positions))
    print("  strip(): " + repr(stripped))
    print("  strip() positions: " + str(stripped._random_positions))
    print("  lstrip(): " + repr(lstripped))
    print("  lstrip() positions: " + str(lstripped._random_positions))
    print("  rstrip(): " + repr(rstripped))
    print("  rstrip() positions: " + str(rstripped._random_positions))

    # Test 18: Split method
    print("\nTest 18 - Split method:")
    uuid_str = str(test_uuid)
    split_result = uuid_str.split("-")
    print("  Original UUID: " + repr(uuid_str))
    print("  Original positions: " + str(uuid_str._random_positions))
    print("  Split result: " + str([repr(s) for s in split_result]))
    print("  Split types: " + str([type(s).__name__ for s in split_result]))
    print("  First part positions: " + str(split_result[0]._random_positions))
    print("  Second part positions: " + str(split_result[1]._random_positions))

    # Test 19: Title and capitalize methods
    print("\nTest 19 - Title and capitalize methods:")
    uuid_lower = uuid_hex.lower()
    titled = uuid_lower.title()
    capitalized = uuid_lower.capitalize()
    print("  Lowercase UUID: " + repr(uuid_lower))
    print("  Lowercase positions: " + str(uuid_lower._random_positions))
    print("  title(): " + repr(titled))
    print("  title() positions: " + str(titled._random_positions))
    print("  capitalize(): " + repr(capitalized))
    print("  capitalize() positions: " + str(capitalized._random_positions))

    # Test 20: Encode and decode methods
    print("\nTest 20 - Encode and decode methods:")
    uuid_hex = test_uuid.hex
    encoded = uuid_hex.encode("utf-8")
    decoded = encoded.decode("utf-8")
    print("  Original UUID: " + repr(uuid_hex))
    print("  Original positions: " + str(uuid_hex._random_positions))
    print("  Encoded: " + repr(encoded))
    print("  Encoded type: " + str(type(encoded)))
    print("  Decoded: " + repr(decoded))
    print("  Decoded type: " + str(type(decoded)))
    # Note: encode/decode don't preserve taint in current implementation

    # Test 21: Complex f-string with multiple UUIDs
    print("\nTest 21 - Complex f-string with multiple UUIDs:")
    uuid1 = uuid4().hex
    uuid2 = uuid4().hex
    complex_f_string = f"First: {uuid1[:8]}, Second: {uuid2[8:16]}, Combined: {uuid1 + uuid2}"
    print("  UUID1: " + repr(uuid1))
    print("  UUID2: " + repr(uuid2))
    print("  Complex f-string: " + repr(complex_f_string))
    print("  F-string type: " + str(type(complex_f_string)))

    # Test 22: String formatting with format method
    print("\nTest 22 - String format method:")
    uuid_hex = test_uuid.hex
    format_result = "UUID: {} length: {}".format(uuid_hex, len(uuid_hex))
    print("  Format result: " + repr(format_result))
    print("  Format type: " + str(type(format_result)))
    if hasattr(format_result, "_random_positions"):
        print("  Format positions: " + str(format_result._random_positions))

    # Test 23: String case methods
    print("\nTest 23 - String case methods:")
    uuid_hex = test_uuid.hex
    upper_result = uuid_hex.upper()
    lower_result = uuid_hex.lower()
    swapcase_result = uuid_hex.swapcase()
    casefold_result = uuid_hex.casefold()
    print("  Original: " + repr(uuid_hex))
    print("  Original positions: " + str(uuid_hex._random_positions))
    print("  upper(): " + repr(upper_result))
    print("  upper() positions: " + str(upper_result._random_positions))
    print("  lower(): " + repr(lower_result))
    print("  lower() positions: " + str(lower_result._random_positions))
    print("  swapcase(): " + repr(swapcase_result))
    print("  swapcase() positions: " + str(swapcase_result._random_positions))
    print("  casefold(): " + repr(casefold_result))
    print("  casefold() positions: " + str(casefold_result._random_positions))

    # Test 24: String alignment methods
    print("\nTest 24 - String alignment methods:")
    uuid_short = uuid_hex[:8]
    centered = uuid_short.center(20, "-")
    left_just = uuid_short.ljust(20, "*")
    right_just = uuid_short.rjust(20, "=")
    zero_filled = uuid_short.zfill(20)
    print("  Short UUID: " + repr(uuid_short))
    print("  Short positions: " + str(uuid_short._random_positions))
    print("  center(20, '-'): " + repr(centered))
    print("  center positions: " + str(centered._random_positions))
    print("  ljust(20, '*'): " + repr(left_just))
    print("  ljust positions: " + str(left_just._random_positions))
    print("  rjust(20, '='): " + repr(right_just))
    print("  rjust positions: " + str(right_just._random_positions))
    print("  zfill(20): " + repr(zero_filled))
    print("  zfill positions: " + str(zero_filled._random_positions))

    # Test 25: String partition methods
    print("\nTest 25 - String partition methods:")
    uuid_str = str(test_uuid)
    partition_result = uuid_str.partition("-")
    rpartition_result = uuid_str.rpartition("-")
    print("  UUID: " + repr(uuid_str))
    print("  UUID positions: " + str(uuid_str._random_positions))
    print("  partition('-'): " + str([repr(s) for s in partition_result]))
    print("  partition types: " + str([type(s).__name__ for s in partition_result]))
    print("  rpartition('-'): " + str([repr(s) for s in rpartition_result]))
    print("  rpartition types: " + str([type(s).__name__ for s in rpartition_result]))

    # Test 26: String split variations
    print("\nTest 26 - String split variations:")
    uuid_str = str(test_uuid)
    rsplit_result = uuid_str.rsplit("-", 1)
    splitlines_test = uuid_str + "\nSecond line\nThird line"
    splitlines_result = splitlines_test.splitlines()
    print("  rsplit('-', 1): " + str([repr(s) for s in rsplit_result]))
    print("  rsplit types: " + str([type(s).__name__ for s in rsplit_result]))
    print("  splitlines test: " + repr(splitlines_test))
    print("  splitlines(): " + str([repr(s) for s in splitlines_result]))
    print("  splitlines types: " + str([type(s).__name__ for s in splitlines_result]))

    # Test 27: String join method
    print("\nTest 27 - String join method:")
    uuid_parts = [uuid4().hex[:4] for _ in range(3)]
    separator = TaintStr("-", random_pos=Position(0, 1))
    joined_result = separator.join(uuid_parts)
    print("  UUID parts: " + str([repr(p) for p in uuid_parts]))
    print("  Separator: " + repr(separator))
    print("  Separator positions: " + str(separator._random_positions))
    print("  Joined result: " + repr(joined_result))
    print("  Joined positions: " + str(joined_result._random_positions))

    # Test 28: String prefix/suffix methods (boolean return)
    print("\nTest 28 - String prefix/suffix methods:")
    uuid_hex = test_uuid.hex
    starts_with_result = uuid_hex.startswith(uuid_hex[:4])
    ends_with_result = uuid_hex.endswith(uuid_hex[-4:])
    print("  UUID: " + repr(uuid_hex))
    print("  startswith(first_4): " + str(starts_with_result))
    print("  endswith(last_4): " + str(ends_with_result))

    # Test 29: String search methods (return indices)
    print("\nTest 29 - String search methods:")
    uuid_str = str(test_uuid)
    find_result = uuid_str.find("-")
    rfind_result = uuid_str.rfind("-")
    index_result = uuid_str.index("-")
    rindex_result = uuid_str.rindex("-")
    count_result = uuid_str.count("-")
    print("  UUID: " + repr(uuid_str))
    print("  find('-'): " + str(find_result))
    print("  rfind('-'): " + str(rfind_result))
    print("  index('-'): " + str(index_result))
    print("  rindex('-'): " + str(rindex_result))
    print("  count('-'): " + str(count_result))

    # Test 30: String translation methods
    print("\nTest 30 - String translation methods:")
    uuid_hex = test_uuid.hex
    # Create a simple translation table
    trans_table = str.maketrans("abcdef", "123456")
    translated = uuid_hex.translate(trans_table)
    print("  Original: " + repr(uuid_hex))
    print("  Original positions: " + str(uuid_hex._random_positions))
    print("  Translated (a-f -> 1-6): " + repr(translated))
    print("  Translated positions: " + str(translated._random_positions))

    # Test 31: String expandtabs method
    print("\nTest 31 - String expandtabs method:")
    tab_string = TaintStr("UUID:\t" + uuid_hex, random_pos=Position(6, 6 + len(uuid_hex)))
    expanded = tab_string.expandtabs(8)
    print("  With tabs: " + repr(tab_string))
    print("  Tab string positions: " + str(tab_string._random_positions))
    print("  expandtabs(8): " + repr(expanded))
    print("  Expanded positions: " + str(expanded._random_positions))

    # Test 32: String format_map method
    print("\nTest 32 - String format_map method:")
    template = "UUID: {uuid}, Length: {length}"
    format_map_result = template.format_map({"uuid": uuid_hex, "length": len(uuid_hex)})
    print("  Template: " + repr(template))
    print("  format_map result: " + repr(format_map_result))
    print("  format_map type: " + str(type(format_map_result)))

    # Test 33: String classification methods (return boolean)
    print("\nTest 33 - String classification methods:")
    uuid_hex = test_uuid.hex
    test_strings = [uuid_hex, "123456", "abcdef", "ABC123", "   ", ""]
    methods = [
        "isalnum",
        "isalpha",
        "isascii",
        "isdecimal",
        "isdigit",
        "isidentifier",
        "islower",
        "isnumeric",
        "isprintable",
        "isspace",
        "istitle",
        "isupper",
    ]

    for test_str in test_strings[:2]:  # Test first two strings to keep output manageable
        print("  Testing: " + repr(test_str))
        for method in methods:
            if hasattr(test_str, method):
                result = getattr(test_str, method)()
                print("    " + method + "(): " + str(result))

    # Test 34: String removeprefix and removesuffix (Python 3.9+)
    print("\nTest 34 - String removeprefix/removesuffix:")
    uuid_with_prefix = "prefix_" + uuid_hex
    uuid_with_suffix = uuid_hex + "_suffix"
    try:
        removed_prefix = uuid_with_prefix.removeprefix("prefix_")
        removed_suffix = uuid_with_suffix.removesuffix("_suffix")
        print("  With prefix: " + repr(uuid_with_prefix))
        print("  removeprefix: " + repr(removed_prefix))
        print("  removeprefix positions: " + str(removed_prefix._random_positions))
        print("  With suffix: " + repr(uuid_with_suffix))
        print("  removesuffix: " + repr(removed_suffix))
        print("  removesuffix positions: " + str(removed_suffix._random_positions))
    except AttributeError:
        print("  removeprefix/removesuffix not available (Python < 3.9)")

    print("\n=== All tests completed ===")
