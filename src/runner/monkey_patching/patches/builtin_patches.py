import re
from forbiddenfruit import curse, patchable_builtin
from runner.taint_wrappers import (
    TaintStr,
    get_taint_origins,
    shift_position_taints,
    get_random_positions,
    inject_random_marker,
    remove_random_marker,
    Position,
)


def str_patch():
    """Patches related to inbuilt str class."""
    curse(str, "join", _cursed_join)


def re_patch():
    """Patches related to re module for taint propagation."""
    # Store original methods first to avoid recursion
    _store_original_methods()

    # Patch Match object methods
    curse(re.Match, "group", _cursed_match_group)
    curse(re.Match, "groups", _cursed_match_groups)
    curse(re.Match, "groupdict", _cursed_match_groupdict)
    curse(re.Match, "expand", _cursed_match_expand)

    # Patch Pattern object methods
    curse(re.Pattern, "search", _cursed_pattern_search)
    curse(re.Pattern, "match", _cursed_pattern_match)
    curse(re.Pattern, "fullmatch", _cursed_pattern_fullmatch)
    curse(re.Pattern, "split", _cursed_pattern_split)
    curse(re.Pattern, "findall", _cursed_pattern_findall)
    curse(re.Pattern, "finditer", _cursed_pattern_finditer)
    curse(re.Pattern, "sub", _cursed_pattern_sub)
    curse(re.Pattern, "subn", _cursed_pattern_subn)

    # Replace module-level functions directly
    re.search = _cursed_re_search
    re.match = _cursed_re_match
    re.fullmatch = _cursed_re_fullmatch
    re.split = _cursed_re_split
    re.findall = _cursed_re_findall
    re.finditer = _cursed_re_finditer
    re.sub = _cursed_re_sub
    re.subn = _cursed_re_subn


# Global variable to store taint context for Match objects
_match_taint_context = {}

# Store original methods to avoid recursion
_original_methods = {}


def _store_original_methods():
    """Store original methods before patching to avoid recursion."""
    if not _original_methods:
        _original_methods.update(
            {
                "match_group": patchable_builtin(re.Match)["group"],
                "match_groups": patchable_builtin(re.Match)["groups"],
                "match_groupdict": patchable_builtin(re.Match)["groupdict"],
                "match_expand": patchable_builtin(re.Match)["expand"],
                "pattern_search": patchable_builtin(re.Pattern)["search"],
                "pattern_match": patchable_builtin(re.Pattern)["match"],
                "pattern_fullmatch": patchable_builtin(re.Pattern)["fullmatch"],
                "pattern_split": patchable_builtin(re.Pattern)["split"],
                "pattern_findall": patchable_builtin(re.Pattern)["findall"],
                "pattern_finditer": patchable_builtin(re.Pattern)["finditer"],
                "pattern_sub": patchable_builtin(re.Pattern)["sub"],
                "pattern_subn": patchable_builtin(re.Pattern)["subn"],
                "re_search": re.search,
                "re_match": re.match,
                "re_fullmatch": re.fullmatch,
                "re_split": re.split,
                "re_findall": re.findall,
                "re_finditer": re.finditer,
                "re_sub": re.sub,
                "re_subn": re.subn,
            }
        )


# Match object method patches
def _cursed_match_group(self, *args):
    """Tainted version of Match.group()."""
    original_method = _original_methods["match_group"]
    # original_method = patchable_builtin(re.Match)["_c_group"]
    result = original_method(self, *args)

    # Get taint context for this match object
    match_id = id(self)
    if match_id in _match_taint_context:
        taint_origins = _match_taint_context[match_id]
        if isinstance(result, str) and taint_origins:
            # Calculate position within original string for this group
            start_pos = self.start() if not args or args[0] == 0 else self.start(args[0])
            end_pos = self.end() if not args or args[0] == 0 else self.end(args[0])
            positions = [Position(0, len(result))] if start_pos != -1 else []
            return TaintStr(result, taint_origin=taint_origins, random_pos=positions)

    return result


def _cursed_match_groups(self, default=None):
    """Tainted version of Match.groups()."""
    original_method = _original_methods["match_groups"]
    result = original_method(self, default)

    match_id = id(self)
    if match_id in _match_taint_context:
        taint_origins = _match_taint_context[match_id]
        if taint_origins:
            tainted_groups = []
            for i, group in enumerate(result):
                if group is not None and isinstance(group, str):
                    try:
                        start_pos = self.start(i + 1)
                        end_pos = self.end(i + 1)
                        positions = [Position(0, len(group))] if start_pos != -1 else []
                        tainted_groups.append(
                            TaintStr(group, taint_origin=taint_origins, random_pos=positions)
                        )
                    except:
                        tainted_groups.append(group)
                else:
                    tainted_groups.append(group)
            return tuple(tainted_groups)

    return result


def _cursed_match_groupdict(self, default=None):
    """Tainted version of Match.groupdict()."""
    original_method = _original_methods["match_groupdict"]
    result = original_method(self, default)

    match_id = id(self)
    if match_id in _match_taint_context:
        taint_origins = _match_taint_context[match_id]
        if taint_origins:
            tainted_dict = {}
            for name, group in result.items():
                if group is not None and isinstance(group, str):
                    try:
                        start_pos = self.start(name)
                        end_pos = self.end(name)
                        positions = [Position(0, len(group))] if start_pos != -1 else []
                        tainted_dict[name] = TaintStr(
                            group, taint_origin=taint_origins, random_pos=positions
                        )
                    except:
                        tainted_dict[name] = group
                else:
                    tainted_dict[name] = group
            return tainted_dict

    return result


def _cursed_match_expand(self, template):
    """Tainted version of Match.expand()."""
    original_method = _original_methods["match_expand"]

    # Use marker injection for template expansion
    marked_template = (
        inject_random_marker(template) if isinstance(template, (str, TaintStr)) else template
    )
    result = original_method(self, marked_template)

    # Extract positions and combine taint origins
    result, positions = remove_random_marker(result)

    match_id = id(self)
    taint_origins = set()
    if match_id in _match_taint_context:
        taint_origins.update(_match_taint_context[match_id])
    taint_origins.update(get_taint_origins(template))

    if taint_origins:
        return TaintStr(result, taint_origin=list(taint_origins), random_pos=positions)
    return result


# Pattern object method patches
def _cursed_pattern_search(self, string, pos=0, endpos=None):
    """Tainted version of Pattern.search()."""
    original_method = _original_methods["pattern_search"]
    if endpos is None:
        result = original_method(self, string, pos)
    else:
        result = original_method(self, string, pos, endpos)

    if result is not None:
        # Store taint context for this match object
        _match_taint_context[id(result)] = get_taint_origins(string)

    return result


def _cursed_pattern_match(self, string, pos=0, endpos=None):
    """Tainted version of Pattern.match()."""
    original_method = _original_methods["pattern_match"]
    if endpos is None:
        result = original_method(self, string, pos)
    else:
        result = original_method(self, string, pos, endpos)

    if result is not None:
        _match_taint_context[id(result)] = get_taint_origins(string)

    return result


def _cursed_pattern_fullmatch(self, string, pos=0, endpos=None):
    """Tainted version of Pattern.fullmatch()."""
    original_method = _original_methods["pattern_fullmatch"]
    if endpos is None:
        result = original_method(self, string, pos)
    else:
        result = original_method(self, string, pos, endpos)

    if result is not None:
        _match_taint_context[id(result)] = get_taint_origins(string)

    return result


def _cursed_pattern_split(self, string, maxsplit=0):
    """Tainted version of Pattern.split()."""
    original_method = _original_methods["pattern_split"]

    # Use marker injection to track positions through split
    marked_string = inject_random_marker(string, level="char")
    result = original_method(self, marked_string, maxsplit=maxsplit)

    taint_origins = get_taint_origins(string)
    if not taint_origins:
        return result

    # Process each split part
    tainted_result = []
    for part in result:
        if isinstance(part, str):
            clean_part, positions = remove_random_marker(part, level="char")
            if positions or taint_origins:
                tainted_result.append(
                    TaintStr(clean_part, taint_origin=taint_origins, random_pos=positions)
                )
            else:
                tainted_result.append(clean_part)
        else:
            tainted_result.append(part)

    return tainted_result


def _cursed_pattern_findall(self, string, pos=0, endpos=None):
    """Tainted version of Pattern.findall()."""
    original_method = _original_methods["pattern_findall"]
    if endpos is None:
        result = original_method(self, string, pos)
    else:
        result = original_method(self, string, pos, endpos)

    taint_origins = get_taint_origins(string)
    if not taint_origins:
        return result

    # Taint all found strings
    tainted_result = []
    for item in result:
        if isinstance(item, str):
            tainted_result.append(
                TaintStr(item, taint_origin=taint_origins, random_pos=[Position(0, len(item))])
            )
        elif isinstance(item, tuple):
            # Multiple groups case
            tainted_groups = []
            for group in item:
                if isinstance(group, str):
                    tainted_groups.append(
                        TaintStr(
                            group, taint_origin=taint_origins, random_pos=[Position(0, len(group))]
                        )
                    )
                else:
                    tainted_groups.append(group)
            tainted_result.append(tuple(tainted_groups))
        else:
            tainted_result.append(item)

    return tainted_result


def _cursed_pattern_finditer(self, string, pos=0, endpos=None):
    """Tainted version of Pattern.finditer()."""
    original_method = _original_methods["pattern_finditer"]
    if endpos is None:
        iterator = original_method(self, string, pos)
    else:
        iterator = original_method(self, string, pos, endpos)

    taint_origins = get_taint_origins(string)

    # Store taint context for each match as we iterate
    for match in iterator:
        if taint_origins:
            _match_taint_context[id(match)] = taint_origins
        yield match


def _cursed_pattern_sub(self, repl, string, count=0):
    """Tainted version of Pattern.sub()."""
    original_method = _original_methods["pattern_sub"]

    if callable(repl):
        # Handle function callbacks - need to wrap the callback to ensure match objects are tainted
        def wrapped_callback(match):
            # Store taint context for this match before calling user function
            _match_taint_context[id(match)] = get_taint_origins(string)
            return repl(match)

        result = original_method(self, wrapped_callback, string, count)

        # Combine taint from string and callback result
        taint_origins = set(get_taint_origins(string))
        if taint_origins:
            return TaintStr(result, taint_origin=list(taint_origins))
        return result
    else:
        # Use marker injection to track position changes for string replacements
        marked_string = inject_random_marker(string)
        marked_repl = inject_random_marker(repl) if isinstance(repl, (str, TaintStr)) else repl

        result = original_method(self, marked_repl, marked_string, count)
        result, positions = remove_random_marker(result)

        # Combine taint origins from string and replacement
        taint_origins = set(get_taint_origins(string))
        taint_origins.update(get_taint_origins(repl))

        if taint_origins:
            return TaintStr(result, taint_origin=list(taint_origins), random_pos=positions)
        return result


def _cursed_pattern_subn(self, repl, string, count=0):
    """Tainted version of Pattern.subn()."""
    original_method = _original_methods["pattern_subn"]

    if callable(repl):
        # Handle function callbacks
        def wrapped_callback(match):
            _match_taint_context[id(match)] = get_taint_origins(string)
            return repl(match)

        result, num_subs = original_method(self, wrapped_callback, string, count)

        # Combine taint from string
        taint_origins = set(get_taint_origins(string))
        if taint_origins:
            return TaintStr(result, taint_origin=list(taint_origins)), num_subs
        return result, num_subs
    else:
        # Use marker injection to track position changes for string replacements
        marked_string = inject_random_marker(string)
        marked_repl = inject_random_marker(repl) if isinstance(repl, (str, TaintStr)) else repl

        result, num_subs = original_method(self, marked_repl, marked_string, count)
        result, positions = remove_random_marker(result)

        # Combine taint origins from string and replacement
        taint_origins = set(get_taint_origins(string))
        taint_origins.update(get_taint_origins(repl))

        if taint_origins:
            return (
                TaintStr(result, taint_origin=list(taint_origins), random_pos=positions),
                num_subs,
            )
        return result, num_subs


# Module-level function patches
def _cursed_re_search(pattern, string, flags=0):
    """Tainted version of re.search()."""
    original_func = _original_methods["re_search"]
    result = original_func(pattern, string, flags)

    if result is not None:
        _match_taint_context[id(result)] = get_taint_origins(string)

    return result


def _cursed_re_match(pattern, string, flags=0):
    """Tainted version of re.match()."""
    original_func = _original_methods["re_match"]
    result = original_func(pattern, string, flags)

    if result is not None:
        _match_taint_context[id(result)] = get_taint_origins(string)

    return result


def _cursed_re_fullmatch(pattern, string, flags=0):
    """Tainted version of re.fullmatch()."""
    original_func = _original_methods["re_fullmatch"]
    result = original_func(pattern, string, flags)

    if result is not None:
        _match_taint_context[id(result)] = get_taint_origins(string)

    return result


def _cursed_re_split(pattern, string, maxsplit=0, flags=0):
    """Tainted version of re.split()."""
    original_func = _original_methods["re_split"]

    marked_string = inject_random_marker(string, level="char")
    result = original_func(pattern, marked_string, maxsplit=maxsplit, flags=flags)

    taint_origins = get_taint_origins(string)
    if not taint_origins:
        return result

    tainted_result = []
    for part in result:
        if isinstance(part, str):
            clean_part, positions = remove_random_marker(part, level="char")
            if positions or taint_origins:
                tainted_result.append(
                    TaintStr(clean_part, taint_origin=taint_origins, random_pos=positions)
                )
            else:
                tainted_result.append(clean_part)
        else:
            tainted_result.append(part)

    return tainted_result


def _cursed_re_findall(pattern, string, flags=0):
    """Tainted version of re.findall()."""
    original_func = _original_methods["re_findall"]
    result = original_func(pattern, string, flags)

    taint_origins = get_taint_origins(string)
    if not taint_origins:
        return result

    tainted_result = []
    for item in result:
        if isinstance(item, str):
            tainted_result.append(
                TaintStr(item, taint_origin=taint_origins, random_pos=[Position(0, len(item))])
            )
        elif isinstance(item, tuple):
            tainted_groups = []
            for group in item:
                if isinstance(group, str):
                    tainted_groups.append(
                        TaintStr(
                            group, taint_origin=taint_origins, random_pos=[Position(0, len(group))]
                        )
                    )
                else:
                    tainted_groups.append(group)
            tainted_result.append(tuple(tainted_groups))
        else:
            tainted_result.append(item)

    return tainted_result


def _cursed_re_finditer(pattern, string, flags=0):
    """Tainted version of re.finditer()."""
    original_func = _original_methods["re_finditer"]
    iterator = original_func(pattern, string, flags=flags)

    taint_origins = get_taint_origins(string)

    for match in iterator:
        if taint_origins:
            _match_taint_context[id(match)] = taint_origins
        yield match


def _cursed_re_sub(pattern, repl, string, count=0, flags=0):
    """Tainted version of re.sub()."""
    original_func = _original_methods["re_sub"]

    if callable(repl):
        # Handle function callbacks
        def wrapped_callback(match):
            _match_taint_context[id(match)] = get_taint_origins(string)
            return repl(match)

        result = original_func(pattern, wrapped_callback, string, count=count, flags=flags)

        # Combine taint from string
        taint_origins = set(get_taint_origins(string))
        if taint_origins:
            return TaintStr(result, taint_origin=list(taint_origins))
        return result
    else:
        # Use marker injection for string replacements
        marked_string = inject_random_marker(string)
        marked_repl = inject_random_marker(repl) if isinstance(repl, (str, TaintStr)) else repl

        result = original_func(pattern, marked_repl, marked_string, count=count, flags=flags)
        result, positions = remove_random_marker(result)

        taint_origins = set(get_taint_origins(string))
        taint_origins.update(get_taint_origins(repl))

        if taint_origins:
            return TaintStr(result, taint_origin=list(taint_origins), random_pos=positions)
        return result


def _cursed_re_subn(pattern, repl, string, count=0, flags=0):
    """Tainted version of re.subn()."""
    original_func = _original_methods["re_subn"]

    if callable(repl):
        # Handle function callbacks
        def wrapped_callback(match):
            _match_taint_context[id(match)] = get_taint_origins(string)
            return repl(match)

        result, num_subs = original_func(
            pattern, wrapped_callback, string, count=count, flags=flags
        )

        # Combine taint from string
        taint_origins = set(get_taint_origins(string))
        if taint_origins:
            return TaintStr(result, taint_origin=list(taint_origins)), num_subs
        return result, num_subs
    else:
        # Use marker injection for string replacements
        marked_string = inject_random_marker(string)
        marked_repl = inject_random_marker(repl) if isinstance(repl, (str, TaintStr)) else repl

        result, num_subs = original_func(
            pattern, marked_repl, marked_string, count=count, flags=flags
        )
        result, positions = remove_random_marker(result)

        taint_origins = set(get_taint_origins(string))
        taint_origins.update(get_taint_origins(repl))

        if taint_origins:
            return (
                TaintStr(result, taint_origin=list(taint_origins), random_pos=positions),
                num_subs,
            )
        return result, num_subs


def _cursed_join(sep: str, elements: list[str]) -> str:
    """
    Join string elements with a separator while preserving taint tracking.

    This function joins a list of strings with a separator, similar to str.join(),
    but maintains taint information and random position tracking throughout the
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
    curr_offs = 0
    random_positions = []
    for value in elements:
        shift_position_taints(value, curr_offs)
        curr_offs += len(value) + len(sep)
        random_positions.extend(get_random_positions(value))
        nodes.update(get_taint_origins(value))

    if len(nodes) > 0:
        return TaintStr(final_string, taint_origin=nodes, random_pos=random_positions)
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
