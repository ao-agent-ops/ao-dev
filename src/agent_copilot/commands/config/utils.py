from typing import Callable, Any
import os
import pathlib
import readline


def complete_path(text, state):
    incomplete_path = pathlib.Path(text)
    if incomplete_path.is_dir():
        completions = [p.as_posix() for p in incomplete_path.iterdir()]
    elif incomplete_path.exists():
        completions = [incomplete_path]
    else:
        exists_parts = pathlib.Path(".")
        for part in incomplete_path.parts:
            test_next_part = exists_parts / part
            if test_next_part.exists():
                exists_parts = test_next_part

        completions = []
        for p in exists_parts.iterdir():
            p_str = p.as_posix()
            if p_str.startswith(text):
                completions.append(p_str)
    return completions[state]


def _ask_field(
    input_text: str,
    convert_value: Callable[[Any], Any] | None = None,
    default: Any | None = None,
    error_message: str | None = None,
):
    # we want to treat '/' as part of a word, so override the delimiters
    readline.set_completer_delims(" \t\n;")
    readline.parse_and_bind("tab: complete")
    readline.set_completer(complete_path)
    ask_again = True
    while ask_again:
        result = input(input_text)
        try:
            if default is not None and len(result) == 0:
                return default
            return convert_value(result) if convert_value is not None else result
        except Exception:
            if error_message is not None:
                print(error_message)


def _convert_yes_no_to_bool(value: str) -> bool:
    return {"yes": True, "no": False}[value.lower()]


def _convert_to_valid_path(value: str) -> str:
    value = os.path.abspath(value)
    if os.path.isdir(value):
        return value
    raise ValueError("Invalid path.")
