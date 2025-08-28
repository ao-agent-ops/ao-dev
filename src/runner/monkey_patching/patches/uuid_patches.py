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
