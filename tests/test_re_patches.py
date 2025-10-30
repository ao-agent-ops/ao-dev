import re
import sys
from aco.runner.taint_wrappers import TaintStr, get_taint_origins


def test_basic_setup():
    """Test that we can import and apply patches without errors."""
    print("Testing basic setup...")

    print("✓ Patches applied successfully")


def test_pattern_search():
    """Test Pattern.search() with tainted strings."""
    print("Testing Pattern.search()...")

    # Create tainted string
    tainted = TaintStr("Hello world test", taint_origin=["user_input"])
    pattern = re.compile(r"world")

    # Test search
    match = pattern.search(tainted)
    assert match is not None, "Should find match"

    # Test that match.group() returns tainted string
    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "user_input"
    ], f"Expected ['user_input'], got {get_taint_origins(group)}"

    print(f"✓ Pattern.search() returned tainted group: {group}")


def test_re_search():
    """Test module-level re.search() with tainted strings."""
    print("Testing re.search()...")

    tainted = TaintStr("Hello world", taint_origin=["api_response"])
    match = re.search(r"world", tainted)

    assert match is not None, "Should find match"
    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "api_response"
    ], f"Expected ['api_response'], got {get_taint_origins(group)}"

    print(f"✓ re.search() returned tainted group: {group}")


def test_findall():
    """Test findall() with tainted strings."""
    print("Testing findall()...")

    tainted = TaintStr(
        "abc 123 def 456",
        taint_origin=["file_input"],
    )
    results = re.findall(r"\d+", tainted)

    assert len(results) == 2, f"Expected 2 matches, got {len(results)}"

    for i, result in enumerate(results):
        assert isinstance(result, TaintStr), f"Expected TaintStr, got {type(result)}"
        assert get_taint_origins(result) == [
            "file_input"
        ], f"Expected ['file_input'], got {get_taint_origins(result)}"

    print(f"✓ findall() returned tainted results: {results}")


def test_split():
    """Test split() with tainted strings."""
    print("Testing split()...")

    tainted = TaintStr("one,two,three", taint_origin=["csv_data"])
    results = re.split(r",", tainted)

    assert len(results) == 3, f"Expected 3 parts, got {len(results)}"

    # Check that parts preserve taint
    for i, result in enumerate(results):
        assert isinstance(result, TaintStr), f"Part {i} expected TaintStr, got {type(result)}"
        assert get_taint_origins(result) == [
            "csv_data"
        ], f"Part {i} expected ['csv_data'], got {get_taint_origins(result)}"

    print(f"✓ split() returned tainted parts: {results}")


def test_sub():
    """Test sub() with tainted strings."""
    print("Testing sub()...")

    tainted = TaintStr("Hello world", taint_origin=["input1"])
    replacement = TaintStr("universe", taint_origin=["input2"])

    result = re.sub(r"world", replacement, tainted)

    assert isinstance(result, TaintStr), f"Expected TaintStr, got {type(result)}"

    # Should have taint from both original string and replacement
    taint_origins = set(get_taint_origins(result))
    assert "input1" in taint_origins, f"Expected 'input1' in taint origins, got {taint_origins}"
    assert "input2" in taint_origins, f"Expected 'input2' in taint origins, got {taint_origins}"

    print(f"✓ sub() returned tainted result: {result}")


def test_groups():
    """Test Match.groups() with tainted strings."""
    print("Testing Match.groups()...")

    tainted = TaintStr(
        "John: 25, Jane: 30",
        taint_origin=["user_data"],
    )
    pattern = re.compile(r"(\w+): (\d+)")

    match = pattern.search(tainted)
    assert match is not None, "Should find match"

    groups = match.groups()
    assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"

    for i, group in enumerate(groups):
        assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
        assert get_taint_origins(group) == [
            "user_data"
        ], f"Expected ['user_data'], got {get_taint_origins(group)}"

    print(f"✓ groups() returned tainted groups: {groups}")


def test_groupdict():
    """Test Match.groupdict() with tainted strings."""
    print("Testing Match.groupdict()...")

    tainted = TaintStr("John: 25", taint_origin=["form_input"])
    pattern = re.compile(r"(?P<name>\w+): (?P<age>\d+)")

    match = pattern.search(tainted)
    assert match is not None, "Should find match"

    groupdict = match.groupdict()
    assert "name" in groupdict, "Should have 'name' group"
    assert "age" in groupdict, "Should have 'age' group"

    for key, value in groupdict.items():
        assert isinstance(value, TaintStr), f"Group '{key}' expected TaintStr, got {type(value)}"
        assert get_taint_origins(value) == [
            "form_input"
        ], f"Group '{key}' expected ['form_input'], got {get_taint_origins(value)}"

    print(f"✓ groupdict() returned tainted groups: {[(k, v) for k, v in groupdict.items()]}")


def test_isinstance_compatibility():
    """Test that Match objects still pass isinstance checks."""
    print("Testing isinstance compatibility...")

    tainted = TaintStr("test string", taint_origin=["test"])
    match = re.search(r"test", tainted)

    assert match is not None, "Should find match"
    assert isinstance(
        match, re.Match
    ), f"Match object should be isinstance of re.Match, got {type(match)}"

    print("✓ Match objects preserve isinstance compatibility")


def test_complex_patterns():
    """Test complex regex patterns with multiple nested groups."""
    print("Testing complex patterns...")

    # Test nested groups
    tainted = TaintStr(
        "Email: john.doe@example.com, Phone: 555-1234", taint_origin=["contact_data"]
    )
    pattern = re.compile(r"Email: ((\w+)\.(\w+)@(\w+\.\w+)), Phone: ((\d{3})-(\d{4}))")

    match = pattern.search(tainted)
    assert match is not None, "Should find complex match"

    # Test all groups are tainted
    all_groups = match.groups()
    assert len(all_groups) == 7, f"Expected 7 groups, got {len(all_groups)}"

    for i, group in enumerate(all_groups):
        if group is not None:
            assert isinstance(group, TaintStr), f"Group {i} should be TaintStr, got {type(group)}"
            assert get_taint_origins(group) == [
                "contact_data"
            ], f"Group {i} should have contact_data taint"

    print(f"✓ Complex pattern with {len(all_groups)} groups all properly tainted")


def test_empty_and_none_cases():
    """Test edge cases with empty matches and None values."""
    print("Testing empty and None cases...")

    # Test no match case
    tainted = TaintStr("hello", taint_origin=["test"])
    result = re.search(r"xyz", tainted)
    assert result is None, "Should return None for no match"

    # Test empty string match
    empty_tainted = TaintStr("", taint_origin=["empty_data"])
    result = re.search(r".*", empty_tainted)
    assert result is not None, "Should match empty string"
    group = result.group()
    assert isinstance(group, TaintStr), "Empty match should be TaintStr"
    assert get_taint_origins(group) == ["empty_data"], "Empty match should preserve taint"

    # Test optional groups that might be None
    tainted = TaintStr("abc", taint_origin=["test"])
    pattern = re.compile(r"(a)(b)?(c)?(d)?")
    match = pattern.search(tainted)
    groups = match.groups()

    # Should have some None values for optional groups
    assert groups[0] == "a", "First group should match"
    assert groups[1] == "b", "Second group should match"
    assert groups[2] == "c", "Third group should match"
    assert groups[3] is None, "Fourth group should be None"

    print("✓ Empty and None cases handled correctly")


def test_function_callbacks():
    """Test sub/subn with function callbacks."""
    print("Testing function callbacks...")

    def callback(match):
        # Function should receive tainted match object
        group = match.group()
        return f"[{group.upper()}]"

    tainted = TaintStr("hello world test", taint_origin=["callback_test"])
    result = re.sub(r"\w+", callback, tainted)

    assert isinstance(result, TaintStr), "Result should be TaintStr"
    assert "callback_test" in get_taint_origins(result), "Should preserve original taint"
    assert (
        str(result) == "[HELLO] [WORLD] [TEST]"
    ), f"Expected '[HELLO] [WORLD] [TEST]', got '{result}'"

    print(f"✓ Function callbacks work: {result.taint_repr()}")


def test_overlapping_taint():
    """Test complex taint with overlapping areas."""
    print("Testing overlapping taint...")

    # Create string with taint
    tainted = TaintStr(
        "prefix_random1_middle_random2_suffix",
        taint_origin=["multi_random"],
    )

    # Split should preserve taint
    parts = re.split(r"_", tainted)

    # Check that all parts have taint
    for part in parts:
        assert isinstance(part, TaintStr), "All parts should be tainted"
        assert get_taint_origins(part) == ["multi_random"]

    print("✓ Overlapping taint handled correctly")


def test_nested_operations():
    """Test nested regex operations on already-tainted results."""
    print("Testing nested operations...")

    # First operation
    tainted = TaintStr("name=john;age=25;city=ny", taint_origin=["config_data"])
    pairs = re.split(r";", tainted)

    # Second operation on results of first
    results = {}
    for pair in pairs:
        assert isinstance(pair, TaintStr), "Split result should be TaintStr"
        match = re.search(r"(\w+)=(\w+)", pair)
        if match:
            key = match.group(1)
            value = match.group(2)
            assert isinstance(key, TaintStr), "Key should be TaintStr"
            assert isinstance(value, TaintStr), "Value should be TaintStr"
            assert get_taint_origins(key) == ["config_data"], "Key should preserve taint"
            assert get_taint_origins(value) == ["config_data"], "Value should preserve taint"
            results[str(key)] = str(value)

    expected = {"name": "john", "age": "25", "city": "ny"}
    assert results == expected, f"Expected {expected}, got {results}"
    print("✓ Nested operations preserve taint correctly")


def test_large_strings():
    """Test performance with large strings."""
    print("Testing large strings...")

    # Create large tainted string
    large_content = "word " * 10000  # 50k characters
    tainted = TaintStr(
        large_content,
        taint_origin=["large_data"],
    )

    # Test findall on large string
    matches = re.findall(r"word", tainted)
    assert len(matches) == 10000, f"Expected 10000 matches, got {len(matches)}"

    # Check first and last matches are tainted
    assert isinstance(matches[0], TaintStr), "First match should be TaintStr"
    assert isinstance(matches[-1], TaintStr), "Last match should be TaintStr"
    assert get_taint_origins(matches[0]) == ["large_data"], "Should preserve taint"

    print(f"✓ Large string with {len(matches)} matches processed correctly")


def test_special_characters():
    """Test regex with special characters and unicode."""
    print("Testing special characters...")

    # Test unicode characters
    tainted = TaintStr("Hello 世界! Price: $50.99 🎉", taint_origin=["unicode_data"])

    # Test unicode word matching
    matches = re.findall(r"\w+", tainted)
    for match in matches:
        assert isinstance(match, TaintStr), f"Unicode match should be TaintStr: {match}"
        assert get_taint_origins(match) == ["unicode_data"], "Should preserve taint"

    # Test special character replacement
    result = re.sub(r"[🎉$]", "X", tainted)
    assert isinstance(result, TaintStr), "Result should be TaintStr"
    assert "X50.99" in str(result), "Should replace special characters"

    print("✓ Special characters and unicode handled correctly")


def test_compiled_vs_string_patterns():
    """Test both compiled patterns and string patterns."""
    print("Testing compiled vs string patterns...")

    tainted = TaintStr("test123", taint_origin=["pattern_test"])

    # Test string pattern
    match1 = re.search(r"\d+", tainted)
    group1 = match1.group()

    # Test compiled pattern
    compiled_pattern = re.compile(r"\d+")
    match2 = compiled_pattern.search(tainted)
    group2 = match2.group()

    # Both should produce tainted results
    assert isinstance(group1, TaintStr), "String pattern result should be TaintStr"
    assert isinstance(group2, TaintStr), "Compiled pattern result should be TaintStr"
    assert get_taint_origins(group1) == ["pattern_test"], "String pattern should preserve taint"
    assert get_taint_origins(group2) == ["pattern_test"], "Compiled pattern should preserve taint"

    print("✓ Both string and compiled patterns work correctly")


def test_subn_with_count():
    """Test subn function that returns count of substitutions."""
    print("Testing subn with count...")

    tainted = TaintStr("foo bar foo baz foo", taint_origin=["subn_test"])
    replacement = TaintStr("FOO", taint_origin=["replacement"])

    # Test unlimited substitutions
    result, count = re.subn(r"foo", replacement, tainted)
    assert isinstance(result, TaintStr), "Result should be TaintStr"
    assert count == 3, f"Expected 3 substitutions, got {count}"
    assert "subn_test" in get_taint_origins(result), "Should preserve original taint"
    assert "replacement" in get_taint_origins(result), "Should include replacement taint"

    # Test limited substitutions
    result2, count2 = re.subn(r"FOO", "foo", result, count=2)
    assert count2 == 2, f"Expected 2 substitutions, got {count2}"
    assert isinstance(result2, TaintStr), "Limited subn result should be TaintStr"

    print(f"✓ subn with count works: {count} substitutions, result={result.taint_repr()}")


def test_error_conditions():
    """Test error conditions and malformed inputs."""
    print("Testing error conditions...")

    try:
        # Test invalid regex
        re.search("[", "test")
        assert False, "Should raise error for invalid regex"
    except re.error:
        pass  # Expected

    # Test with non-string input
    try:
        tainted = TaintStr("123", taint_origin=["num_test"])
        result = re.search(r"\d+", tainted)
        group = result.group()
        assert isinstance(group, TaintStr), "Should handle normal case"
    except Exception as e:
        assert False, f"Normal case should not raise error: {e}"

    print("✓ Error conditions handled appropriately")


def test_expand_method():
    """Test Match.expand() method with templates."""
    print("Testing Match.expand()...")

    tainted = TaintStr("Name: John, Age: 25", taint_origin=["template_data"])
    template = TaintStr("Hello \\1, you are \\2 years old", taint_origin=["template"])

    pattern = re.compile(r"Name: (\w+), Age: (\d+)")
    match = pattern.search(tainted)

    expanded = match.expand(template)
    assert isinstance(expanded, TaintStr), "Expanded result should be TaintStr"

    # Should have taint from both original string and template
    taint_origins = set(get_taint_origins(expanded))
    assert "template_data" in taint_origins, "Should preserve original string taint"
    assert "template" in taint_origins, "Should preserve template taint"

    expected = "Hello John, you are 25 years old"
    assert str(expanded) == expected, f"Expected '{expected}', got '{expanded}'"

    print(f"✓ expand() works: {expanded.taint_repr()}")


def test_edge_case_scenarios():
    """Test various edge cases and corner scenarios."""
    print("Testing edge case scenarios...")

    # Test 1: Zero-length matches
    tainted = TaintStr("abc", taint_origin=["zero_test"])
    matches = re.findall(r"(?=.)", tainted)  # Lookahead creates zero-length matches
    assert len(matches) == 3, f"Expected 3 zero-length matches, got {len(matches)}"
    for match in matches:
        assert isinstance(match, TaintStr), "Zero-length match should be TaintStr"

    # Test 2: Backreferences in replacement
    tainted = TaintStr("hello world", taint_origin=["backref_test"])
    result = re.sub(r"(\w+) (\w+)", r"\2 \1", tainted)
    assert isinstance(result, TaintStr), "Backreference result should be TaintStr"
    assert str(result) == "world hello", f"Expected 'world hello', got '{result}'"
    assert get_taint_origins(result) == ["backref_test"], "Should preserve taint"

    # Test 3: Multiple taint sources in complex substitution
    tainted1 = TaintStr("prefix", taint_origin=["source1"])
    tainted2 = TaintStr("middle", taint_origin=["source2"])
    combined = tainted1 + " " + tainted2 + " suffix"
    result = re.sub(r"(\w+) (\w+) (\w+)", r"\3-\2-\1", combined)

    taint_origins = set(get_taint_origins(result))
    assert "source1" in taint_origins, "Should preserve source1 taint"
    assert "source2" in taint_origins, "Should preserve source2 taint"
    assert str(result) == "suffix-middle-prefix", f"Expected 'suffix-middle-prefix', got '{result}'"

    # Test 4: Regex flags
    tainted = TaintStr("Hello WORLD", taint_origin=["flags_test"])
    match = re.search(r"world", tainted, re.IGNORECASE)
    assert match is not None, "Should match with IGNORECASE flag"
    group = match.group()
    assert isinstance(group, TaintStr), "Flag-based match should be TaintStr"
    assert str(group) == "WORLD", f"Expected 'WORLD', got '{group}'"

    # Test 5: Empty replacement
    tainted = TaintStr("remove this text", taint_origin=["remove_test"])
    result = re.sub(r" this", "", tainted)
    assert isinstance(result, TaintStr), "Empty replacement result should be TaintStr"
    assert str(result) == "remove text", f"Expected 'remove text', got '{result}'"

    # Test 6: Group indexing edge cases
    tainted = TaintStr("a1b2c3", taint_origin=["index_test"])
    pattern = re.compile(r"([a-z])(\d)([a-z])(\d)([a-z])(\d)")
    match = pattern.search(tainted)

    # Test accessing specific groups
    group0 = match.group(0)  # Full match
    group1 = match.group(1)  # First group
    group6 = match.group(6)  # Last group

    assert all(
        isinstance(g, TaintStr) for g in [group0, group1, group6]
    ), "All groups should be TaintStr"
    assert all(
        get_taint_origins(g) == ["index_test"] for g in [group0, group1, group6]
    ), "All should preserve taint"

    print("✓ Edge case scenarios handled correctly")


def test_pattern_match():
    """Test Pattern.match() with taint tracking."""
    print("Testing Pattern.match() taint tracking...")

    tainted = TaintStr("hello world test", taint_origin=["match_test"])
    pattern = re.compile(r"hello")

    match = pattern.match(tainted)
    assert match is not None, "Should find match at start"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "match_test"
    ], f"Expected ['match_test'], got {get_taint_origins(group)}"

    print(f"✓ Pattern.match() taint tracking: {group}")


def test_pattern_fullmatch():
    """Test Pattern.fullmatch() with taint tracking."""
    print("Testing Pattern.fullmatch() taint tracking...")

    tainted = TaintStr("test123", taint_origin=["fullmatch_test"])
    pattern = re.compile(r"test\d+")

    match = pattern.fullmatch(tainted)
    assert match is not None, "Should fullmatch entire string"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "fullmatch_test"
    ], f"Expected ['fullmatch_test'], got {get_taint_origins(group)}"

    print(f"✓ Pattern.fullmatch() taint tracking: {group}")


# TODO Generic patching of functions that return generators is not supported yet
# def test_pattern_finditer():
#     """Test Pattern.finditer() with taint tracking."""
#     print("Testing Pattern.finditer() taint tracking...")

#     tainted = TaintStr(
#         "word1 word2 word3", taint_origin=["finditer_test"]
#     )
#     pattern = re.compile(r"word\d")

#     matches = list(pattern.finditer(tainted))
#     assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}"

#     for i, match in enumerate(matches):
#         group = match.group()
#         assert isinstance(group, TaintStr), f"Match {i} should be TaintStr, got {type(group)}"
#         assert get_taint_origins(group) == ["finditer_test"], f"Match {i} should preserve taint"

#     print(f"✓ Pattern.finditer() taint tracking: {len(matches)} matches")


def test_re_match():
    """Test re.match() with taint tracking."""
    print("Testing re.match() taint tracking...")

    tainted = TaintStr("start middle end", taint_origin=["re_match_test"])

    match = re.match(r"start", tainted)
    assert match is not None, "Should find match at beginning"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "re_match_test"
    ], f"Expected ['re_match_test'], got {get_taint_origins(group)}"

    print(f"✓ re.match() taint tracking: {group}")


def test_re_fullmatch():
    """Test re.fullmatch() with taint tracking."""
    print("Testing re.fullmatch() taint tracking...")

    tainted = TaintStr("complete", taint_origin=["re_fullmatch_test"])

    match = re.fullmatch(r"complete", tainted)
    assert match is not None, "Should fullmatch entire string"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "re_fullmatch_test"
    ], f"Expected ['re_fullmatch_test'], got {get_taint_origins(group)}"

    print(f"✓ re.fullmatch() taint tracking: {group}")


# TODO Generic patching of functions that return generators is not supported yet
# def test_re_finditer():
#     """Test re.finditer() with taint tracking."""
#     print("Testing re.finditer() taint tracking...")

#     tainted = TaintStr(
#         "cat dog cat bird cat",
#         taint_origin=["re_finditer_test"],
#     )

#     matches = list(re.finditer(r"cat", tainted))
#     assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}"

#     for i, match in enumerate(matches):
#         group = match.group()
#         assert isinstance(group, TaintStr), f"Match {i} should be TaintStr, got {type(group)}"
#         assert get_taint_origins(group) == ["re_finditer_test"], f"Match {i} should preserve taint"

#     print(f"✓ re.finditer() taint tracking: {len(matches)} matches")


def test_nested_group_taint_tracking():
    """Test taint tracking with complex nested groups."""
    print("Testing nested group taint tracking...")

    # Test complex nested pattern with taint tracking
    tainted = TaintStr(
        "User: alice@example.com (ID: 12345)",
        taint_origin=["nested_test"],
    )
    pattern = re.compile(r"User: ((\w+)@([\w.]+)) \(ID: (\d+)\)")

    match = pattern.search(tainted)
    assert match is not None, "Should find complex nested match"

    # Test all groups have taint tracking
    groups = match.groups()
    expected_contents = ["alice@example.com", "alice", "example.com", "12345"]

    for i, (group, expected_content) in enumerate(zip(groups, expected_contents)):
        assert isinstance(group, TaintStr), f"Group {i+1} should be TaintStr, got {type(group)}"
        assert (
            str(group) == expected_content
        ), f"Group {i+1} content mismatch: expected '{expected_content}', got '{group}'"
        assert get_taint_origins(group) == ["nested_test"], f"Group {i+1} should preserve taint"

    # Test accessing specific groups by index
    full_email = match.group(1)  # alice@example.com
    username = match.group(2)  # alice
    domain = match.group(3)  # example.com
    user_id = match.group(4)  # 12345

    for group_name, group in [
        ("email", full_email),
        ("username", username),
        ("domain", domain),
        ("id", user_id),
    ]:
        assert isinstance(group, TaintStr), f"{group_name} should be TaintStr"
        assert get_taint_origins(group) == ["nested_test"], f"{group_name} should preserve taint"

    print("✓ Nested group taint tracking works correctly")


def test_overlapping_groups_taint_tracking():
    """Test taint tracking with overlapping and optional groups."""
    print("Testing overlapping groups taint tracking...")

    # Pattern with optional groups that may overlap
    tainted = TaintStr("prefix123suffix", taint_origin=["overlap_test"])
    pattern = re.compile(r"(prefix)?(\d+)(suffix)?")

    match = pattern.search(tainted)
    assert match is not None, "Should find match with optional groups"

    groups = match.groups()
    assert len(groups) == 3, f"Expected 3 groups, got {len(groups)}"

    # All groups should be present in this case
    expected_groups = ["prefix", "123", "suffix"]
    for i, (group, expected) in enumerate(zip(groups, expected_groups)):
        assert group is not None, f"Group {i+1} should not be None"
        assert isinstance(group, TaintStr), f"Group {i+1} should be TaintStr"
        assert str(group) == expected, f"Group {i+1} content mismatch"
        assert get_taint_origins(group) == ["overlap_test"], f"Group {i+1} should preserve taint"

    print("✓ Overlapping groups taint tracking works correctly")


def test_zero_width_assertions_taint_tracking():
    """Test taint tracking with zero-width assertions and lookheads."""
    print("Testing zero-width assertions taint tracking...")

    # Test positive lookahead
    tainted = TaintStr("password123", taint_origin=["lookahead_test"])
    pattern = re.compile(r"password(?=\d+)")

    match = pattern.search(tainted)
    assert match is not None, "Should find match with lookahead"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert str(group) == "password", f"Expected 'password', got '{group}'"
    assert get_taint_origins(group) == ["lookahead_test"], "Should preserve taint"

    # Test negative lookbehind
    tainted2 = TaintStr("test123end", taint_origin=["lookbehind_test"])
    pattern2 = re.compile(r"(?<=test)\d+")

    match2 = pattern2.search(tainted2)
    assert match2 is not None, "Should find match with lookbehind"

    group2 = match2.group()
    assert isinstance(group2, TaintStr), f"Expected TaintStr, got {type(group2)}"
    assert str(group2) == "123", f"Expected '123', got '{group2}'"
    assert get_taint_origins(group2) == ["lookbehind_test"], "Should preserve taint"

    print("✓ Zero-width assertions taint tracking works correctly")


def test_multiple_patch_calls():
    """Test that calling  multiple times doesn't break anything."""
    print("Testing multiple patch calls...")

    # Apply patches multiple times

    # Should still work correctly
    tainted = TaintStr("test multiple patches", taint_origin=["multi_patch_test"])
    match = re.search(r"multiple", tainted)
    assert match is not None, "Should still find matches after multiple patches"

    group = match.group()
    assert isinstance(group, TaintStr), "Should still return TaintStr"
    assert get_taint_origins(group) == ["multi_patch_test"], "Should still preserve taint"

    print("✓ Multiple patch calls handled correctly")


def run_all_tests():
    """Run all tests."""
    print("Running comprehensive re module taint propagation tests...\n")

    try:
        test_basic_setup()
        test_pattern_search()
        test_re_search()
        test_findall()
        test_split()
        test_sub()
        test_groups()
        test_groupdict()
        test_isinstance_compatibility()

        # Extended tests
        test_complex_patterns()
        test_empty_and_none_cases()
        test_function_callbacks()
        test_overlapping_taint()
        test_nested_operations()
        test_large_strings()
        test_special_characters()
        test_compiled_vs_string_patterns()
        test_subn_with_count()
        test_error_conditions()
        test_expand_method()
        test_edge_case_scenarios()

        # New position tracking tests
        test_pattern_match()
        test_pattern_fullmatch()
        test_re_match()
        test_re_fullmatch()
        test_nested_group_taint_tracking()
        test_overlapping_groups_taint_tracking()
        test_zero_width_assertions_taint_tracking()
        test_multiple_patch_calls()

        print("\n🎉 All comprehensive tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
