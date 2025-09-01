"""
UUID monkey patches for taint tracking.

This module provides patches for Python's UUID class to enable taint tracking
for UUID operations. When applied, UUID methods will return TaintStr objects
with position tracking information for security analysis.

The patches modify the following UUID methods:
- hex: Returns the UUID as a 32-character hexadecimal TaintStr
- __str__: Returns the UUID as a formatted string with dashes as TaintStr
- __repr__: Returns the UUID's repr as TaintStr

All returned strings include Position objects that track the entire string
as containing random/sensitive data for security analysis purposes.
"""

from uuid import UUID
from runner.taint_wrappers import TaintStr, Position


def uuid_patch():
    """
    Apply taint tracking patches to the UUID class.

    Modifies the UUID class to return TaintStr objects instead of regular strings
    for hex, str, and repr operations. This enables tracking of UUID data through
    security analysis pipelines.
    """
    setattr(UUID, "hex", property(hex))
    setattr(UUID, "__str__", uuid_str)
    setattr(UUID, "__repr__", uuid_repr)


def hex(self: UUID):
    """
    Return the UUID as a 32-character hexadecimal TaintStr.

    Args:
        self (UUID): The UUID instance

    Returns:
        TaintStr: 32-character lowercase hexadecimal representation with position tracking
    """
    hex_str = "%032x" % self.int
    return TaintStr(hex_str, random_pos=Position(0, len(hex_str)))


def uuid_str(self: UUID):
    """
    Return the UUID as a formatted string with dashes as TaintStr.

    Returns the standard UUID string representation in the format:
    xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    Args:
        self (UUID): The UUID instance

    Returns:
        TaintStr: 36-character UUID string with dashes and position tracking
    """
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
    """
    Return the UUID's repr as TaintStr.

    Returns a string representation suitable for debugging in the format:
    UUID('xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx')

    Args:
        self (UUID): The UUID instance

    Returns:
        TaintStr: String representation with UUID constructor format and position tracking
    """
    repr_str = "%s(%r)" % (self.__class__.__name__, str(self))
    return TaintStr(repr_str, random_pos=Position(0, len(repr_str)))
