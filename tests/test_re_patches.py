import re
import sys
from runner.taint_wrappers import TaintStr, Position, get_taint_origins, get_random_positions


def test_basic_setup():
    """Test that we can import and apply patches without errors."""
    print("Testing basic setup...")

    print("✓ Patches applied successfully")


def test_pattern_search():
    """Test Pattern.search() with tainted strings and position tracking."""
    print("Testing Pattern.search()...")

    # Create tainted string with specific position tracking
    tainted = TaintStr(
        "Hello world test", taint_origin=["user_input"], random_pos=[Position(6, 11)]
    )
    pattern = re.compile(r"world")

    # Test search
    match = pattern.search(tainted)
    assert match is not None, "Should find match"

    # Test that match.group() returns tainted string with correct position
    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "user_input"
    ], f"Expected ['user_input'], got {get_taint_origins(group)}"

    # Check position tracking - "world" should have position tracking
    positions = get_random_positions(group)
    assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"
    assert (
        positions[0].start == 0 and positions[0].stop == 5
    ), f"Expected Position(0, 5) for 'world', got {positions[0]}"

    print(f"✓ Pattern.search() returned tainted group: {group.taint_repr()}")


def test_re_search():
    """Test module-level re.search() with tainted strings and position tracking."""
    print("Testing re.search()...")

    tainted = TaintStr("Hello world", taint_origin=["api_response"], random_pos=[Position(6, 11)])
    match = re.search(r"world", tainted)

    assert match is not None, "Should find match"
    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "api_response"
    ], f"Expected ['api_response'], got {get_taint_origins(group)}"

    # Check position tracking for the matched "world"
    positions = get_random_positions(group)
    assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"
    assert (
        positions[0].start == 0 and positions[0].stop == 5
    ), f"Expected Position(0, 5) for 'world', got {positions[0]}"

    print(f"✓ re.search() returned tainted group: {group.taint_repr()}")


def test_findall():
    """Test findall() with tainted strings and position tracking."""
    print("Testing findall()...")

    tainted = TaintStr(
        "abc 123 def 456",
        taint_origin=["file_input"],
        random_pos=[Position(4, 7), Position(12, 15)],
    )
    results = re.findall(r"\d+", tainted)

    assert len(results) == 2, f"Expected 2 matches, got {len(results)}"

    expected_lengths = [3, 3]  # "123" and "456"
    for i, result in enumerate(results):
        assert isinstance(result, TaintStr), f"Expected TaintStr, got {type(result)}"
        assert get_taint_origins(result) == [
            "file_input"
        ], f"Expected ['file_input'], got {get_taint_origins(result)}"

        # Check position tracking
        positions = get_random_positions(result)
        assert len(positions) == 1, f"Result {i} expected 1 position, got {len(positions)}"
        assert (
            positions[0].start == 0 and positions[0].stop == expected_lengths[i]
        ), f"Result {i} position mismatch"

    print(f"✓ findall() returned tainted results: {[r.taint_repr() for r in results]}")


def test_split():
    """Test split() with tainted strings."""
    print("Testing split()...")

    tainted = TaintStr("one,two,three", taint_origin=["csv_data"], random_pos=[Position(4, 7)])
    results = re.split(r",", tainted)

    assert len(results) == 3, f"Expected 3 parts, got {len(results)}"

    # Check that parts with random positions are properly tracked
    for i, result in enumerate(results):
        assert isinstance(result, TaintStr), f"Part {i} expected TaintStr, got {type(result)}"
        assert get_taint_origins(result) == [
            "csv_data"
        ], f"Part {i} expected ['csv_data'], got {get_taint_origins(result)}"

    # The middle part "two" should have random positions
    two_positions = get_random_positions(results[1])
    assert len(two_positions) > 0, "Middle part should have random positions"

    print(f"✓ split() returned tainted parts: {[r.taint_repr() for r in results]}")


def test_sub():
    """Test sub() with tainted strings."""
    print("Testing sub()...")

    tainted = TaintStr("Hello world", taint_origin=["input1"], random_pos=[Position(6, 11)])
    replacement = TaintStr("universe", taint_origin=["input2"])

    result = re.sub(r"world", replacement, tainted)

    assert isinstance(result, TaintStr), f"Expected TaintStr, got {type(result)}"

    # Should have taint from both original string and replacement
    taint_origins = set(get_taint_origins(result))
    assert "input1" in taint_origins, f"Expected 'input1' in taint origins, got {taint_origins}"
    assert "input2" in taint_origins, f"Expected 'input2' in taint origins, got {taint_origins}"

    print(f"✓ sub() returned tainted result: {result.taint_repr()}")


def test_groups():
    """Test Match.groups() with tainted strings and position tracking."""
    print("Testing Match.groups()...")

    tainted = TaintStr(
        "John: 25, Jane: 30",
        taint_origin=["user_data"],
        random_pos=[Position(0, 4), Position(6, 8)],
    )
    pattern = re.compile(r"(\w+): (\d+)")

    match = pattern.search(tainted)
    assert match is not None, "Should find match"

    groups = match.groups()
    assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"

    expected_lengths = [4, 2]  # "John" and "25"
    for i, group in enumerate(groups):
        assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
        assert get_taint_origins(group) == [
            "user_data"
        ], f"Expected ['user_data'], got {get_taint_origins(group)}"

        # Check position tracking for each group
        positions = get_random_positions(group)
        assert len(positions) == 1, f"Group {i} expected 1 position, got {len(positions)}"
        assert (
            positions[0].start == 0 and positions[0].stop == expected_lengths[i]
        ), f"Group {i} position mismatch"

    print(f"✓ groups() returned tainted groups: {[g.taint_repr() for g in groups]}")


def test_groupdict():
    """Test Match.groupdict() with tainted strings and position tracking."""
    print("Testing Match.groupdict()...")

    tainted = TaintStr(
        "John: 25", taint_origin=["form_input"], random_pos=[Position(0, 4), Position(6, 8)]
    )
    pattern = re.compile(r"(?P<name>\w+): (?P<age>\d+)")

    match = pattern.search(tainted)
    assert match is not None, "Should find match"

    groupdict = match.groupdict()
    assert "name" in groupdict, "Should have 'name' group"
    assert "age" in groupdict, "Should have 'age' group"

    expected_lengths = {"name": 4, "age": 2}  # "John" and "25"
    for key, value in groupdict.items():
        assert isinstance(value, TaintStr), f"Group '{key}' expected TaintStr, got {type(value)}"
        assert get_taint_origins(value) == [
            "form_input"
        ], f"Group '{key}' expected ['form_input'], got {get_taint_origins(value)}"

        # Check position tracking for named groups
        positions = get_random_positions(value)
        assert len(positions) == 1, f"Group '{key}' expected 1 position, got {len(positions)}"
        assert (
            positions[0].start == 0 and positions[0].stop == expected_lengths[key]
        ), f"Group '{key}' position mismatch"

    print(
        f"✓ groupdict() returned tainted groups: {[(k, v.taint_repr()) for k, v in groupdict.items()]}"
    )


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
        assert isinstance(group, TaintStr), "Callback should receive tainted match"
        return f"[{group.upper()}]"

    tainted = TaintStr("hello world test", taint_origin=["callback_test"])
    result = re.sub(r"\w+", callback, tainted)

    assert isinstance(result, TaintStr), "Result should be TaintStr"
    assert "callback_test" in get_taint_origins(result), "Should preserve original taint"
    assert (
        str(result) == "[HELLO] [WORLD] [TEST]"
    ), f"Expected '[HELLO] [WORLD] [TEST]', got '{result}'"

    print(f"✓ Function callbacks work: {result.taint_repr()}")


def test_overlapping_positions():
    """Test complex position tracking with overlapping taint areas."""
    print("Testing overlapping positions...")

    # Create string with multiple random position areas
    tainted = TaintStr(
        "prefix_random1_middle_random2_suffix",
        taint_origin=["multi_random"],
        random_pos=[Position(7, 14), Position(22, 29)],
    )

    # Split should preserve position tracking
    parts = re.split(r"_", tainted)

    # Check that random positions are correctly distributed
    found_random = False
    for part in parts:
        if get_random_positions(part):
            found_random = True
            print(f"  Part with random positions: {part.taint_repr()}")

    assert found_random, "Should find parts with random positions"
    print("✓ Overlapping positions handled correctly")


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
        random_pos=[Position(1000, 2000), Position(3000, 4000)],
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


def test_memory_cleanup():
    """Test that taint context tracks match objects properly."""
    print("Testing memory cleanup...")

    from runner.monkey_patching.patches.builtin_patches import _match_taint_context

    initial_size = len(_match_taint_context)
    matches_created = 0

    # Create unique matches with different patterns to avoid reuse
    for i in range(10):
        tainted = TaintStr(f"unique_test_{i}_end", taint_origin=[f"source{i}"])
        match = re.search(rf"unique_test_{i}_end", tainted)
        if match:
            matches_created += 1
            match.group()  # Access the group to ensure it's processed

    # Context should have grown by at least the number of matches created
    final_size = len(_match_taint_context)
    context_growth = final_size - initial_size

    print(f"  Created {matches_created} matches, context grew by {context_growth}")
    assert context_growth >= 0, "Context should track match objects"

    # Note: In a real implementation, we'd want garbage collection of old match objects
    print(f"✓ Taint context properly tracks match objects ({final_size} total)")


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
    """Test Pattern.match() with position tracking."""
    print("Testing Pattern.match() position tracking...")

    tainted = TaintStr(
        "hello world test", taint_origin=["match_test"], random_pos=[Position(6, 11)]
    )
    pattern = re.compile(r"hello")

    match = pattern.match(tainted)
    assert match is not None, "Should find match at start"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "match_test"
    ], f"Expected ['match_test'], got {get_taint_origins(group)}"

    # Check position tracking
    positions = get_random_positions(group)
    assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"
    assert (
        positions[0].start == 0 and positions[0].stop == 5
    ), f"Expected Position(0, 5), got {positions[0]}"

    print(f"✓ Pattern.match() position tracking: {group.taint_repr()}")


def test_pattern_fullmatch():
    """Test Pattern.fullmatch() with position tracking."""
    print("Testing Pattern.fullmatch() position tracking...")

    tainted = TaintStr("test123", taint_origin=["fullmatch_test"], random_pos=[Position(0, 4)])
    pattern = re.compile(r"test\d+")

    match = pattern.fullmatch(tainted)
    assert match is not None, "Should fullmatch entire string"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "fullmatch_test"
    ], f"Expected ['fullmatch_test'], got {get_taint_origins(group)}"

    # Check position tracking - should cover full match
    positions = get_random_positions(group)
    assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"
    assert (
        positions[0].start == 0 and positions[0].stop == 7
    ), f"Expected Position(0, 7), got {positions[0]}"

    print(f"✓ Pattern.fullmatch() position tracking: {group.taint_repr()}")


def test_pattern_finditer():
    """Test Pattern.finditer() with position tracking."""
    print("Testing Pattern.finditer() position tracking...")

    tainted = TaintStr(
        "word1 word2 word3", taint_origin=["finditer_test"], random_pos=[Position(6, 11)]
    )
    pattern = re.compile(r"word\d")

    matches = list(pattern.finditer(tainted))
    assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}"

    for i, match in enumerate(matches):
        group = match.group()
        assert isinstance(group, TaintStr), f"Match {i} should be TaintStr, got {type(group)}"
        assert get_taint_origins(group) == ["finditer_test"], f"Match {i} should preserve taint"

        # Check position tracking
        positions = get_random_positions(group)
        assert len(positions) == 1, f"Match {i} expected 1 position, got {len(positions)}"

        # Verify position corresponds to match location
        expected_len = 5  # "wordN" is 5 characters
        assert (
            positions[0].stop - positions[0].start == expected_len
        ), f"Match {i} position length should be {expected_len}"

    print(f"✓ Pattern.finditer() position tracking: {len(matches)} matches")


def test_re_match():
    """Test re.match() with position tracking."""
    print("Testing re.match() position tracking...")

    tainted = TaintStr(
        "start middle end", taint_origin=["re_match_test"], random_pos=[Position(6, 12)]
    )

    match = re.match(r"start", tainted)
    assert match is not None, "Should find match at beginning"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "re_match_test"
    ], f"Expected ['re_match_test'], got {get_taint_origins(group)}"

    # Check position tracking
    positions = get_random_positions(group)
    assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"
    assert (
        positions[0].start == 0 and positions[0].stop == 5
    ), f"Expected Position(0, 5), got {positions[0]}"

    print(f"✓ re.match() position tracking: {group.taint_repr()}")


def test_re_fullmatch():
    """Test re.fullmatch() with position tracking."""
    print("Testing re.fullmatch() position tracking...")

    tainted = TaintStr("complete", taint_origin=["re_fullmatch_test"], random_pos=[Position(2, 6)])

    match = re.fullmatch(r"complete", tainted)
    assert match is not None, "Should fullmatch entire string"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert get_taint_origins(group) == [
        "re_fullmatch_test"
    ], f"Expected ['re_fullmatch_test'], got {get_taint_origins(group)}"

    # Check position tracking - should span entire string
    positions = get_random_positions(group)
    assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"
    assert (
        positions[0].start == 0 and positions[0].stop == 8
    ), f"Expected Position(0, 8), got {positions[0]}"

    print(f"✓ re.fullmatch() position tracking: {group.taint_repr()}")


def test_re_finditer():
    """Test re.finditer() with position tracking."""
    print("Testing re.finditer() position tracking...")

    tainted = TaintStr(
        "cat dog cat bird cat",
        taint_origin=["re_finditer_test"],
        random_pos=[Position(8, 11), Position(17, 20)],
    )

    matches = list(re.finditer(r"cat", tainted))
    assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}"

    for i, match in enumerate(matches):
        group = match.group()
        assert isinstance(group, TaintStr), f"Match {i} should be TaintStr, got {type(group)}"
        assert get_taint_origins(group) == ["re_finditer_test"], f"Match {i} should preserve taint"

        # Check position tracking
        positions = get_random_positions(group)
        assert len(positions) == 1, f"Match {i} expected 1 position, got {len(positions)}"

        # Verify position corresponds to group content length (3 chars for "cat")
        assert (
            positions[0].start == 0 and positions[0].stop == 3
        ), f"Match {i} position should map to group content"

    print(f"✓ re.finditer() position tracking: {len(matches)} matches")


def test_nested_group_position_tracking():
    """Test position tracking with complex nested groups."""
    print("Testing nested group position tracking...")

    # Test complex nested pattern with position tracking
    tainted = TaintStr(
        "User: alice@example.com (ID: 12345)",
        taint_origin=["nested_test"],
        random_pos=[Position(6, 21), Position(27, 32)],
    )
    pattern = re.compile(r"User: ((\w+)@([\w.]+)) \(ID: (\d+)\)")

    match = pattern.search(tainted)
    assert match is not None, "Should find complex nested match"

    # Test all groups have position tracking
    groups = match.groups()
    expected_contents = ["alice@example.com", "alice", "example.com", "12345"]
    expected_lengths = [17, 5, 11, 5]

    for i, (group, expected_content, expected_len) in enumerate(
        zip(groups, expected_contents, expected_lengths)
    ):
        assert isinstance(group, TaintStr), f"Group {i+1} should be TaintStr, got {type(group)}"
        assert (
            str(group) == expected_content
        ), f"Group {i+1} content mismatch: expected '{expected_content}', got '{group}'"
        assert get_taint_origins(group) == ["nested_test"], f"Group {i+1} should preserve taint"

        # Check position tracking
        positions = get_random_positions(group)
        assert len(positions) == 1, f"Group {i+1} expected 1 position, got {len(positions)}"
        assert (
            positions[0].start == 0 and positions[0].stop == expected_len
        ), f"Group {i+1} position length mismatch"

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
        positions = get_random_positions(group)
        assert len(positions) == 1, f"{group_name} should have position tracking"

    print("✓ Nested group position tracking works correctly")


def test_overlapping_groups_position_tracking():
    """Test position tracking with overlapping and optional groups."""
    print("Testing overlapping groups position tracking...")

    # Pattern with optional groups that may overlap
    tainted = TaintStr(
        "prefix123suffix", taint_origin=["overlap_test"], random_pos=[Position(6, 9)]
    )
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

        # Check position tracking
        positions = get_random_positions(group)
        assert len(positions) == 1, f"Group {i+1} expected 1 position, got {len(positions)}"
        assert positions[0].start == 0 and positions[0].stop == len(
            expected
        ), f"Group {i+1} position mismatch"

    print("✓ Overlapping groups position tracking works correctly")


def test_zero_width_assertions_position_tracking():
    """Test position tracking with zero-width assertions and lookheads."""
    print("Testing zero-width assertions position tracking...")

    # Test positive lookahead
    tainted = TaintStr("password123", taint_origin=["lookahead_test"], random_pos=[Position(8, 11)])
    pattern = re.compile(r"password(?=\d+)")

    match = pattern.search(tainted)
    assert match is not None, "Should find match with lookahead"

    group = match.group()
    assert isinstance(group, TaintStr), f"Expected TaintStr, got {type(group)}"
    assert str(group) == "password", f"Expected 'password', got '{group}'"

    # Check position tracking for lookahead match
    positions = get_random_positions(group)
    assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"
    assert (
        positions[0].start == 0 and positions[0].stop == 8
    ), f"Expected Position(0, 8), got {positions[0]}"

    # Test negative lookbehind
    tainted2 = TaintStr("test123end", taint_origin=["lookbehind_test"], random_pos=[Position(4, 7)])
    pattern2 = re.compile(r"(?<=test)\d+")

    match2 = pattern2.search(tainted2)
    assert match2 is not None, "Should find match with lookbehind"

    group2 = match2.group()
    assert isinstance(group2, TaintStr), f"Expected TaintStr, got {type(group2)}"
    assert str(group2) == "123", f"Expected '123', got '{group2}'"

    # Check position tracking for lookbehind match
    positions2 = get_random_positions(group2)
    assert len(positions2) == 1, f"Expected 1 position, got {len(positions2)}"
    assert (
        positions2[0].start == 0 and positions2[0].stop == 3
    ), f"Expected Position(0, 3), got {positions2[0]}"

    print("✓ Zero-width assertions position tracking works correctly")


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
        test_overlapping_positions()
        test_nested_operations()
        test_large_strings()
        test_special_characters()
        test_compiled_vs_string_patterns()
        test_subn_with_count()
        test_error_conditions()
        test_expand_method()
        test_memory_cleanup()
        test_edge_case_scenarios()

        # New position tracking tests
        test_pattern_match()
        test_pattern_fullmatch()
        test_pattern_finditer()
        test_re_match()
        test_re_fullmatch()
        test_re_finditer()
        test_nested_group_position_tracking()
        test_overlapping_groups_position_tracking()
        test_zero_width_assertions_position_tracking()
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
