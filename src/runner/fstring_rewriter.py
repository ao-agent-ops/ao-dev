import ast
import importlib.abc
import importlib.util
import sys
import re
from common.logger import logger
from runner.taint_wrappers import (
    TaintStr,
    get_taint_origins,
    increase_position_taints,
    set_position_taints,
)


_user_py_files = set()
_user_file_to_module = dict()
_module_to_user_file = dict()


def set_user_py_files(py_files, file_to_module=None):
    global _user_py_files, _user_file_to_module
    _user_py_files = py_files
    if file_to_module is not None:
        _user_file_to_module = file_to_module


def set_module_to_user_file(module_to_user_file: dict):
    global _module_to_user_file
    _module_to_user_file = module_to_user_file


def taint_fstring_join(*args):
    result = "".join(str(a) for a in args)
    all_origins = set()
    offs = 0
    for a in args:
        updated_taint_origins = increase_position_taints(a, offs)
        all_origins.update(updated_taint_origins)
        offs += len(a)
    if all_origins:
        return TaintStr(result, list(all_origins))
    return result


def taint_format_string(format_string, *args, **kwargs):
    result = format_string.format(*args, **kwargs)
    all_origins = set()
    used_positions = set()  # Track (start, end) tuples to avoid duplicates

    # Parse the format string to extract individual format specs
    import string

    formatter = string.Formatter()
    format_specs = list(formatter.parse(format_string))

    # For each tainted argument, format it individually and find where it appears
    arg_index = 0
    for literal_text, field_name, format_spec, conversion in format_specs:
        if field_name is not None:  # This is a placeholder
            # Determine if this is a positional or keyword argument
            if field_name.isdigit():
                # Positional argument with explicit index
                idx = int(field_name)
                if idx < len(args):
                    arg = args[idx]
                else:
                    continue
            elif field_name == "":
                # Auto-numbered positional argument
                if arg_index < len(args):
                    arg = args[arg_index]
                    arg_index += 1
                else:
                    continue
            elif field_name in kwargs:
                # Keyword argument
                arg = kwargs[field_name]
            else:
                continue

            # Only process tainted arguments
            if get_taint_origins(arg):
                # Format this argument individually to see how it gets transformed
                try:
                    # Create format spec for just this argument
                    individual_format_spec = format_spec if format_spec else ""
                    if conversion:
                        # Handle conversion (!s, !r, !a)
                        if conversion == "s":
                            converted_arg = str(arg)
                        elif conversion == "r":
                            converted_arg = repr(arg)
                        elif conversion == "a":
                            converted_arg = ascii(arg)
                        else:
                            converted_arg = arg
                        formatted_arg = format(converted_arg, individual_format_spec)
                    else:
                        formatted_arg = format(arg, individual_format_spec)

                    # Find where this formatted argument appears in the final result
                    for match in re.finditer(re.escape(formatted_arg), result):
                        formatted_field_start = match.start()
                        formatted_field_end = match.end()

                        # Skip if this position is already used
                        if (formatted_field_start, formatted_field_end) not in used_positions:
                            used_positions.add((formatted_field_start, formatted_field_end))

                            # Find where the actual content appears within the formatted field
                            original_content = str(arg)
                            content_pos_in_field = formatted_arg.find(original_content)

                            if content_pos_in_field != -1:
                                # Calculate the actual content position in the final result
                                content_start = formatted_field_start + content_pos_in_field
                                content_end = content_start + len(original_content)

                                # Set position taints based on where the actual content ended up
                                position_taints = set_position_taints(
                                    arg, content_start, content_end
                                )
                                all_origins.update(position_taints)
                            else:
                                # Fallback: if we can't find original content in formatted field,
                                # track the entire formatted field (this handles cases like conversions)
                                position_taints = set_position_taints(
                                    arg, formatted_field_start, formatted_field_end
                                )
                                all_origins.update(position_taints)
                            break  # Use only the first unused occurrence for this argument
                    else:
                        # Fallback: add original taints if formatted version not found
                        all_origins.update(get_taint_origins(arg))

                except (ValueError, AttributeError, TypeError) as e:
                    # Format failed - fallback to original taints
                    all_origins.update(get_taint_origins(arg))
            else:
                # Non-tainted argument - still increment counter for auto-numbered args
                if field_name == "":
                    arg_index += 1

    # Handle any remaining positional args that weren't covered by format specs
    # (This shouldn't normally happen with well-formed format strings)
    for i in range(arg_index, len(args)):
        arg = args[i]
        if get_taint_origins(arg):
            all_origins.update(get_taint_origins(arg))

    # Handle any remaining kwargs that weren't covered
    for key, value in kwargs.items():
        if get_taint_origins(value):
            # Check if this kwarg was already processed
            was_processed = any(
                field_name == key for _, field_name, _, _ in format_specs if field_name
            )
            if not was_processed:
                all_origins.update(get_taint_origins(value))

    if all_origins:
        return TaintStr(result, list(all_origins))
    return result


def taint_percent_format(format_string, values):
    try:
        result = format_string % values
    except Exception:
        return format_string % values  # fallback, may raise
    all_origins = set(get_taint_origins(format_string))
    if isinstance(values, (tuple, list)):
        for v in values:
            all_origins.update(get_taint_origins(v))
    else:
        all_origins.update(get_taint_origins(values))
    if all_origins:
        return TaintStr(result, list(all_origins))
    return result


class FStringTransformer(ast.NodeTransformer):
    def visit_JoinedStr(self, node):
        logger.debug(f"Transforming f-string at line {getattr(node, 'lineno', '?')}")
        # Replace f-string with a call to taint_fstring_join
        new_node = ast.Call(
            func=ast.Name(id="taint_fstring_join", ctx=ast.Load()),
            args=[value for value in node.values],
            keywords=[],
        )
        return ast.copy_location(new_node, node)

    def visit_Call(self, node):
        # Check if this is a .format() call
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Constant)
            and isinstance(node.func.value.value, str)
            and node.func.attr == "format"
        ):

            logger.debug(f"Transforming .format() call at line {getattr(node, 'lineno', '?')}")

            # Extract the format string and arguments
            format_string = node.func.value.value
            format_args = node.args
            format_kwargs = node.keywords

            # Create a call to taint_format_string
            new_node = ast.Call(
                func=ast.Name(id="taint_format_string", ctx=ast.Load()),
                args=[ast.Constant(value=format_string)] + format_args,
                keywords=format_kwargs,
            )
            return ast.copy_location(new_node, node)

        return self.generic_visit(node)

    def visit_BinOp(self, node):
        # Add support for string % formatting
        if isinstance(node.op, ast.Mod) and (
            (isinstance(node.left, ast.Constant) and isinstance(node.left.value, str))
            or (isinstance(node.left, ast.Str))
        ):
            logger.debug(f"Transforming % formatting at line {getattr(node, 'lineno', '?')}")
            # Replace with taint_percent_format(format_string, right)
            new_node = ast.Call(
                func=ast.Name(id="taint_percent_format", ctx=ast.Load()),
                args=[node.left, node.right],
                keywords=[],
            )
            return ast.copy_location(new_node, node)
        return self.generic_visit(node)


class FStringImportLoader(importlib.abc.SourceLoader):
    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def source_to_code(self, data, path, *, _optimize=-1):
        logger.debug(f"Rewriting AST for {self.fullname} at {path}")
        tree = ast.parse(data, filename=path)
        tree = FStringTransformer().visit(tree)
        ast.fix_missing_locations(tree)
        return compile(tree, path, "exec")


class FStringImportFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        # Only handle modules that correspond to user files
        for mod_name, file_path in _module_to_user_file.items():
            if mod_name == fullname:
                logger.debug(f"Will rewrite: {fullname} from {file_path}")
                return importlib.util.spec_from_loader(
                    fullname, FStringImportLoader(fullname, file_path)
                )
        return None


def install_fstring_rewriter():
    if not any(isinstance(f, FStringImportFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, FStringImportFinder())
    # Make taint functions globally available
    import builtins

    builtins.taint_fstring_join = taint_fstring_join
    builtins.taint_format_string = taint_format_string
    builtins.taint_percent_format = taint_percent_format
