from collections import OrderedDict
import typing as t



def _parse_block(output: str, tag: str, langs: t.List[str] = [], tolerate_unclosed_tags: bool = True):
    """Parse code between <tag attrs> and </tag>"""
    start_tag = f"<{tag}"
    end_tag = f"</{tag}>"
    start = output.find(start_tag)
    end = output.find(end_tag)
    if end == -1 and tolerate_unclosed_tags:
        end = len(output)
    if start == -1 or end == -1:
        return None
    # Parse attributes: attr1=value1 attr2=value2
    attrs_start = start + len(start_tag)
    attrs_end = output.find(">", attrs_start)
    attrs = output[attrs_start:attrs_end]
    attrs = attrs.split(" ")
    attrs = {a.split("=")[0]: a.split("=")[1] for a in attrs if "=" in a}
    # Parse content
    start_block = attrs_end + 1
    end_block = output.find(end_tag, start_block)
    block = output[start_block:end_block]
    if block.startswith("\n"):
        block = block[1:]
    if block.endswith("\n"):
        block = block[:-1]
    # Remove possible surroundings. Keep this order.
    block = block.strip()
    lines = block.split("\n")
    # Only remove the surroundings from the first and last line (after strip)
    first_line = lines[0]
    last_line = lines[-1]
    possible_surroundings = ["```toml", "```json", "```diff", "```python", "```py", "```md", "```\n", "\n```"]
    for lang in langs:
        possible_surroundings = [f"```{lang}"] + possible_surroundings
    for surrounding in possible_surroundings:
        first_line = first_line.replace(surrounding, "```")
        last_line = last_line.replace(surrounding, "```")
    first_line = first_line.replace("```", "")
    last_line = last_line.replace("```", "")
    lines[0] = first_line
    lines[-1] = last_line
    block = "\n".join(lines)
    return block, attrs, attrs_end


def parse_standard_response(
    response: str,
    reason_tag: str = "reason",
    code_tag: str = "patch", # TODO: I think we can delete this.
    code_langs: t.List[str]|str = [],
    tolerate_unclosed_tags: bool = True,
    repeated_tags: bool = False, # Multiple blocks with the same tag may exist and are parsed together.
):
    """Parse a standard LLM response."""
    if isinstance(code_langs, str):
        code_langs = [code_langs]
    reasons = {}
    codes = OrderedDict()
    attrs = {}
    i = -1
    while True:
        if i == -1:
            # Parse overall explanation/code.
            curr_reason_tag = reason_tag
            curr_code_tag = code_tag
        else:
            # Parse individual explanations/code
            if not repeated_tags:
                # Names are indexed.
                curr_reason_tag = f"{reason_tag}{i}"
                curr_code_tag = f"{code_tag}{i}"
        res = _parse_block(response, curr_reason_tag, langs=["md"])
        if res is not None:
            explanation, attr, block_end = res
            if not repeated_tags:
                reasons[curr_reason_tag] = explanation
                if len(attr) > 0:
                    attrs[curr_reason_tag] = attr
            else:
                reasons.setdefault(curr_reason_tag, []).append(explanation)
                if len(attr) > 0:
                    attrs.setdefault(curr_reason_tag, []).append(attr)
                response = response[block_end:]
        res = _parse_block(response, curr_code_tag, langs=code_langs, tolerate_unclosed_tags=tolerate_unclosed_tags)
        if res is not None:
            codeblock, attr, block_end = res
            if not repeated_tags:
                codes[curr_code_tag] = codeblock
                if len(attr) > 0:
                    attrs[curr_code_tag] = attr
            else:
                codes.setdefault(curr_code_tag, []).append(codeblock)
                if len(attr) > 0:
                    attrs.setdefault(curr_code_tag, []).append(attr)
                response = response[block_end:]
        else:
            if i >= 0:
                break
        i += 1
    return reasons, codes, attrs


def parse_out_tag(response, tag):
        _, code_update, _ = parse_standard_response(response, code_tag=tag)
        return code_update[tag].strip()

