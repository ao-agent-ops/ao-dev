from forbiddenfruit import curse
from aco.runner.taint_wrappers import TaintStr, get_taint_origins


def str_patch():
    """Patches related to inbuilt str class."""
    curse(str, "join", _cursed_join)


def _cursed_join(sep: str, elements: list[str]) -> str:
    """
    Join string elements with a separator while preserving taint tracking.

    This function joins a list of strings with a separator, similar to str.join(),
    but maintains taint information throughout the
    operation. It uses byte-level joining for performance and handles taint
    propagation from both the separator and all elements.

    Args:
        sep (str): The separator string to join elements with
        elements (list[str]): List of string elements to join

    Returns:
        str | TaintStr: The joined string, returned as TaintStr if any element
                        or separator has taint information, otherwise regular str
    """
    joined_bytes = _bytes_join(sep.encode(), [elem.encode() for elem in elements])
    final_string = joined_bytes.decode()

    nodes = set(get_taint_origins(sep))

    if len(nodes) > 0:
        return TaintStr(final_string, taint_origin=nodes)
    return final_string


def _bytes_join(sep: bytes, elements: list[bytes]) -> bytes:
    """
    Efficiently join byte sequences with a separator using a pre-allocated buffer.

    This function performs byte-level joining of elements with a separator,
    providing better performance than repeated concatenation by pre-allocating
    a buffer of the exact required size and copying data directly.

    Args:
        sep (bytes): The separator bytes to join elements with
        elements (list[bytes]): List of byte sequences to join

    Returns:
        bytes: The joined byte sequence, or empty bytes if total length is 0 or negative
    """
    # create a mutable buffer that is long enough to hold the result
    total_length = sum(len(elem) for elem in elements)
    total_length += (len(elements) - 1) * len(sep)
    if total_length <= 0:
        return bytearray(0)
    result = bytearray(total_length)
    # copy all characters from the inputs to the result
    insert_idx = 0
    for elem in elements:
        result[insert_idx : insert_idx + len(elem)] = elem
        insert_idx += len(elem)
        if insert_idx < total_length:
            result[insert_idx : insert_idx + len(sep)] = sep
            insert_idx += len(sep)
    return bytes(result)
