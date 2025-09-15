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

import uuid
import random
from uuid import UUID


def uuid_patch():
    """
    Apply taint tracking patches to the UUID class and uuid4 function.

    Modifies the UUID class to return TaintStr objects instead of regular strings
    for hex, str, and repr operations. Also patches the uuid4 function to use
    Python's random.getrandbits instead of os.urandom for reproducible randomness.
    """
    setattr(uuid, "uuid4", uuid4)


def uuid4():
    """Generate a random UUID using Python's random.getrandbits instead of os.urandom.

    This allows for reproducible UUIDs when a random seed is set, which is useful
    for testing and debugging purposes.

    Returns:
        UUID: A new UUID4 object generated using random.getrandbits(128)
    """
    # Generate a random 128-bit integer using Python's random module
    generated_uuid = UUID(int=random.getrandbits(128), version=4)
    return generated_uuid
