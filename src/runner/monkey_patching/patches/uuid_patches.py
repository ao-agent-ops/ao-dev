from typing import Any
from functools import wraps
from uuid import UUID
from runner.taint_wrappers import TaintStr


class RandomObject:
    def __init__(self, obj: Any):
        self.obj = obj


def uuid_patch():
    setattr(UUID, "hex", property(hex))
    setattr(UUID, "bytes", property(bytes_prop))
    setattr(UUID, "bytes_le", property(bytes_le))
    setattr(UUID, "urn", property(urn))
    setattr(UUID, "__str__", uuid_str)
    setattr(UUID, "__repr__", uuid_repr)


def hex(self: UUID):
    hex_str = "%032x" % self.int
    return TaintStr(hex_str, taint_origin=f"[random]{str([0,len(hex_str)])}")


def bytes_prop(self: UUID):
    bytes_data = self.int.to_bytes(16)  # big endian
    return TaintStr(bytes_data, taint_origin=f"[random]{str([0,len(bytes_data)])}")


def bytes_le(self: UUID):
    bytes_data = self.int.to_bytes(16)  # big endian first
    bytes_le_data = (
        bytes_data[4 - 1 :: -1]
        + bytes_data[6 - 1 : 4 - 1 : -1]
        + bytes_data[8 - 1 : 6 - 1 : -1]
        + bytes_data[8:]
    )
    return TaintStr(bytes_le_data, taint_origin=f"[random]{str([0,len(bytes_le_data)])}")


def urn(self: UUID):
    uuid_str = "%032x" % self.int
    formatted_uuid = "%s-%s-%s-%s-%s" % (
        uuid_str[:8],
        uuid_str[8:12],
        uuid_str[12:16],
        uuid_str[16:20],
        uuid_str[20:],
    )
    urn_str = "urn:uuid:" + formatted_uuid
    return TaintStr(
        urn_str, taint_origin=f"[random]{str([9,len(urn_str)])}"
    )  # taint starts after 'urn:uuid:'


def uuid_str(self: UUID):
    hex_str = "%032x" % self.int
    formatted_uuid = "%s-%s-%s-%s-%s" % (
        hex_str[:8],
        hex_str[8:12],
        hex_str[12:16],
        hex_str[16:20],
        hex_str[20:],
    )
    return TaintStr(formatted_uuid, taint_origin=f"[random]{str([0,len(formatted_uuid)])}")


def uuid_repr(self: UUID):
    str_repr = uuid_str(self)  # Get the tainted string representation
    repr_str = f"{self.__class__.__name__}('{str_repr}')"
    return TaintStr(
        repr_str, taint_origin=f"[random]{str([6,len(repr_str)-2])}"
    )  # taint the UUID part only


if __name__ == "__main__":
    uuid_patch()
    from uuid import uuid4

    # Test the new properties
    print("\n=== Testing UUID properties ===")
    test_uuid = uuid4()

    # Test bytes property
    uuid_bytes = test_uuid.bytes
    print(f"bytes result: {uuid_bytes}")
    print(f"bytes type: {type(uuid_bytes)}")
    print(f"bytes taint origins: {uuid_bytes._taint_origin}")

    # Test bytes_le property
    uuid_bytes_le = test_uuid.bytes_le
    print(f"bytes_le result: {uuid_bytes_le}")
    print(f"bytes_le type: {type(uuid_bytes_le)}")
    print(f"bytes_le taint origins: {uuid_bytes_le._taint_origin}")

    # Test urn property
    uuid_urn = test_uuid.urn
    print(f"urn result: {uuid_urn}")
    print(f"urn type: {type(uuid_urn)}")
    print(f"urn taint origins: {uuid_urn._taint_origin}")

    # Test __str__ method
    uuid_str_result = str(test_uuid)
    print(f"str result: {uuid_str_result}")
    print(f"str type: {type(uuid_str_result)}")
    print(f"str taint origins: {uuid_str_result._taint_origin}")

    # Test __repr__ method
    uuid_repr_result = repr(test_uuid)
    print(f"repr result: {uuid_repr_result}")
    print(f"repr type: {type(uuid_repr_result)}")
    print(f"repr taint origins: {uuid_repr_result._taint_origin}")

    # Test case for __format__ method
    print("\n=== Testing __format__ with tainted UUID ===")
    uuid_hex = uuid4().hex

    # Using string formatting - this triggers __format__
    formatted = f"UUID: {uuid_hex}"
    print(f"Formatted result: {formatted}")
    print(f"Formatted type: {type(formatted)}")
    print(f"Formatted taint origins: {formatted._taint_origin}")

    # Using format method with format spec
    formatted_upper = "{:>40}".format(uuid_hex)  # Right-align in 40 chars
    print(f"Formatted upper result: '{formatted_upper}'")
    print(f"Formatted upper type: {type(formatted_upper)}")
    print(f"Formatted upper taint origins: {formatted_upper._taint_origin}")

    # Test left-align format
    formatted_left = "{:<40}".format(uuid_hex)  # Left-align in 40 chars
    print(f"Formatted left result: '{formatted_left}'")
    print(f"Formatted left type: {type(formatted_left)}")
    print(f"Formatted left taint origins: {formatted_left._taint_origin}")

    # Test center format
    formatted_center = "{:^40}".format(uuid_hex)  # Center in 40 chars
    print(f"Formatted center result: '{formatted_center}'")
    print(f"Formatted center type: {type(formatted_center)}")
    print(f"Formatted center taint origins: {formatted_center._taint_origin}")

    # Test with padding character
    formatted_padded = "{:*^40}".format(uuid_hex)  # Center with * padding
    print(f"Formatted padded result: '{formatted_padded}'")
    print(f"Formatted padded type: {type(formatted_padded)}")
    print(f"Formatted padded taint origins: {formatted_padded._taint_origin}")

    # Test multiple arguments
    uuid2 = uuid4().hex
    formatted_multi = "UUID1: {} UUID2: {}".format(uuid_hex, uuid2)
    print(f"Formatted multi result: {formatted_multi}")
    print(f"Formatted multi type: {type(formatted_multi)}")
    print(f"Formatted multi taint origins: {formatted_multi._taint_origin}")

    # Test with non-tainted mixed in
    formatted_mixed = "Prefix: {}, Suffix: {}".format(uuid_hex, "not-tainted")
    print(f"Formatted mixed result: {formatted_mixed}")
    print(f"Formatted mixed type: {type(formatted_mixed)}")
    print(f"Formatted mixed taint origins: {formatted_mixed._taint_origin}")

    print("\n=== EDGE CASES AND HARDER TESTS ===")

    # Edge case 1: Same UUID appearing multiple times
    uuid3 = uuid4().hex
    duplicate_uuid = "First: {}, Second: {}, Third: {}".format(uuid3, uuid3, uuid3)
    print(f"Duplicate UUID result: {duplicate_uuid}")
    print(f"Duplicate UUID taint origins: {duplicate_uuid._taint_origin}")

    # Edge case 2: Substring matching issue - UUID that's a substring of another
    short_uuid = uuid4().hex[:8]  # Take first 8 chars
    long_text = "aa" + short_uuid + "bb"  # Embed it in a longer string
    tricky_format = "Text: {}, Short: {}".format(long_text, short_uuid)
    print(f"Substring matching result: {tricky_format}")
    print(f"Substring matching taint origins: {tricky_format._taint_origin}")

    # Edge case 3: Empty format result
    empty_format = "{}".format("")
    print(f"Empty format result: '{empty_format}'")
    print(f"Empty format type: {type(empty_format)}")

    # Edge case 4: UUID with special characters that might affect find()
    special_uuid = TaintStr("special-uuid-with-dashes", taint_origin="[random][0,25]")
    special_format = "Special: {}".format(special_uuid)
    print(f"Special UUID result: {special_format}")
    print(f"Special UUID taint origins: {special_format._taint_origin}")

    # Edge case 5: Very long format strings with many placeholders
    many_args = "A:{} B:{} C:{} D:{} E:{}".format(
        uuid3[:4], uuid3[4:8], uuid3[8:12], uuid3[12:16], uuid3[16:20]
    )
    print(f"Many args result: {many_args}")
    print(f"Many args taint origins: {many_args._taint_origin}")

    # Edge case 6: Nested format-like strings (shouldn't break our parser)
    nested_format = "Outer: {{{}}}, Inner: {}".format("middle", uuid3[:6])
    print(f"Nested format result: {nested_format}")
    print(f"Nested format type: {type(nested_format)}")
    if hasattr(nested_format, "_taint_origin"):
        print(f"Nested format taint origins: {nested_format._taint_origin}")
    else:
        print("Nested format has no taint origins")

    # Edge case 7: Format with width shorter than UUID (should truncate)
    truncated = "{:.10}".format(uuid3)  # Only first 10 chars
    print(f"Truncated result: '{truncated}'")
    print(f"Truncated taint origins: {truncated._taint_origin}")

    # Edge case 8: Format with zero padding
    uuid_as_int = int(uuid3[:8], 16)  # Convert first 8 hex chars to int
    tainted_int = TaintStr(str(uuid_as_int), taint_origin="[random][0,10]")
    zero_padded = "{:010}".format(tainted_int)
    print(f"Zero padded result: '{zero_padded}'")
    print(f"Zero padded taint origins: {zero_padded._taint_origin}")

    # Edge case 9: Same string content but different taint origins
    uuid_copy1 = TaintStr(uuid3, taint_origin="[random][5,15]")
    uuid_copy2 = TaintStr(uuid3, taint_origin="[random][20,30]")
    same_content = "Copy1: {}, Copy2: {}".format(uuid_copy1, uuid_copy2)
    print(f"Same content result: {same_content}")
    print(f"Same content taint origins: {same_content._taint_origin}")

    # Additional test: Three identical UUIDs to test multiple occurrence handling
    print("\n=== Testing multiple identical UUIDs ===")
    uuid_triple1 = TaintStr(uuid3, taint_origin="[random][100,132]")
    uuid_triple2 = TaintStr(uuid3, taint_origin="[random][200,232]")
    uuid_triple3 = TaintStr(uuid3, taint_origin="[random][300,332]")
    triple_format = "A:{}, B:{}, C:{}".format(uuid_triple1, uuid_triple2, uuid_triple3)
    print(f"Triple format result: {triple_format}")
    print(f"Triple format taint origins: {triple_format._taint_origin}")
    print(f"Number of taint origins: {len(triple_format._taint_origin)}")

    # Edge case 10: Format that results in the UUID not being found (transformed)
    try:
        upper_format = "{:UPPER CASE NOT SUPPORTED}".format(uuid3)  # This will fail
        print(f"Upper format attempt: {upper_format}")
        print(f"Upper format taint origins: {upper_format._taint_origin}")
    except ValueError as e:
        print(f"Upper format failed as expected: {e}")
    except Exception as e:
        print(f"Upper format failed with unexpected error: {e}")
