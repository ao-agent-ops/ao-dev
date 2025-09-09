"""
F-string and string formatting rewriter for taint tracking.

This module provides AST transformation capabilities to rewrite Python f-strings,
.format() calls, and % formatting operations to use taint-aware equivalents.
The transformations preserve taint information and position tracking through
string formatting operations.

Key Components:
- FStringTransformer: AST node transformer for rewriting string formatting
- taint_fstring_join: Taint-aware replacement for f-string concatenation
- taint_format_string: Taint-aware replacement for .format() calls
- taint_percent_format: Taint-aware replacement for % formatting

The rewriter uses marker injection to track which parts of formatted strings
come from tainted sources, preserving both taint origins and positional
information about tainted data within the resulting strings.
"""

import ast
from common.logger import logger
from runner.taint_wrappers import (
    TaintStr,
    get_taint_origins,
    inject_random_marker,
    remove_random_marker,
)


def taint_fstring_join(*args):
    """
    Taint-aware replacement for f-string concatenation.

    This function is used as a runtime replacement for f-string expressions.
    It joins the provided arguments into a single string while preserving
    taint information and tracking positional data from tainted sources.

    The function:
    1. Injects markers around tainted portions to track positions
    2. Joins all arguments into a single string
    3. Removes markers and extracts position information
    4. Collects taint origins from all arguments
    5. Returns a TaintStr if any taint or positions exist

    Args:
        *args: Variable number of arguments to join (values from f-string expressions)

    Returns:
        str or TaintStr: The joined string with taint information preserved

    Example:
        # Original: f"Hello {name}, you have {count} items"
        # Becomes: taint_fstring_join("Hello ", name, ", you have ", count, " items")
    """
    # Inject random markers into args to track position information
    args = inject_random_marker(args)
    result = "".join(str(a) for a in args)
    result, positions = remove_random_marker(result)
    all_origins = set()
    for a in args:
        all_origins.update(get_taint_origins(a))
    if all_origins or positions:
        return TaintStr(result, list(all_origins), random_pos=positions)
    return result


def taint_format_string(format_string, *args, **kwargs):
    """
    Taint-aware replacement for .format() string method calls.

    This function replaces calls to str.format() to preserve taint information
    through string formatting operations. It handles both positional and
    keyword arguments while tracking which parts of the result contain
    tainted data.

    The function:
    1. Injects markers around tainted arguments to track their positions
    2. Performs the string formatting operation
    3. Removes markers and extracts position information
    4. Collects taint origins from format string and all arguments
    5. Returns a TaintStr if any taint exists

    Args:
        format_string (str): The format string template
        *args: Positional arguments for formatting
        **kwargs: Keyword arguments for formatting

    Returns:
        str or TaintStr: The formatted string with taint information preserved

    Example:
        # Original: "Hello {}, you have {} items".format(name, count)
        # Becomes: taint_format_string("Hello {}, you have {} items", name, count)
    """
    args = inject_random_marker(args)
    kwargs = {key: inject_random_marker(value) for key, value in kwargs.items()}
    result = format_string.format(*args, **kwargs)
    result, positions = remove_random_marker(result)
    all_origins = set()
    for a in args:
        all_origins.update(get_taint_origins(a))
    for v in kwargs.values():
        all_origins.update(get_taint_origins(v))
    if all_origins or positions:
        return TaintStr(result, list(all_origins), random_pos=positions)
    return result


def taint_percent_format(format_string, values):
    """
    Taint-aware replacement for % string formatting operations.

    This function replaces Python's % formatting operator to preserve taint
    information through printf-style string formatting. It handles both
    single values and tuples/lists of values while tracking tainted content.

    The function:
    1. Injects markers around both format string and values if tainted
    2. Performs the % formatting operation
    3. Removes markers and extracts position information
    4. Collects taint origins from both format string and values
    5. Returns a TaintStr if any taint exists

    Args:
        format_string (str): The format string with % placeholders
        values: The values to format (single value, tuple, or list)

    Returns:
        str or TaintStr: The formatted string with taint information preserved

    Example:
        # Original: "Hello %s, you have %d items" % (name, count)
        # Becomes: taint_percent_format("Hello %s, you have %d items", (name, count))
    """
    # first we insert markers into the values that mark start/end of a random string
    marked_values = inject_random_marker(values)
    format_string = inject_random_marker(format_string)
    result = format_string % marked_values
    result, positions = remove_random_marker(result)
    all_origins = set(get_taint_origins(format_string))
    if isinstance(values, (tuple, list)):
        for v in values:
            all_origins.update(get_taint_origins(v))
    else:
        all_origins.update(get_taint_origins(values))
    if all_origins or positions:
        return TaintStr(result, list(all_origins), random_pos=positions)
    return result


class FStringTransformer(ast.NodeTransformer):
    """
    AST transformer that rewrites string formatting operations for taint tracking.

    This class extends ast.NodeTransformer to rewrite three types of string
    formatting operations in Python source code:

    1. F-strings (f"...{expr}...") -> taint_fstring_join calls
    2. .format() calls ("...{}...".format(args)) -> taint_format_string calls
    3. % formatting ("...%s..." % values) -> taint_percent_format calls

    The transformer preserves the original AST structure while replacing
    formatting operations with calls to taint-aware equivalents that track
    the flow of sensitive data through string operations.

    Usage:
        transformer = FStringTransformer()
        tree = ast.parse(source_code)
        new_tree = transformer.visit(tree)
        compiled_code = compile(new_tree, filename, 'exec')
    """

    def visit_JoinedStr(self, node):
        """
        Transform f-string literals into taint_fstring_join calls.

        Converts f-string expressions like f"Hello {name}!" into equivalent
        function calls that preserve taint information.

        Args:
            node (ast.JoinedStr): The f-string AST node to transform

        Returns:
            ast.Call: A call to taint_fstring_join with the f-string components as arguments
        """
        logger.debug(f"Transforming f-string at line {getattr(node, 'lineno', '?')}")
        # Replace f-string with a call to taint_fstring_join
        new_node = ast.Call(
            func=ast.Name(id="taint_fstring_join", ctx=ast.Load()),
            args=[value for value in node.values],
            keywords=[],
        )
        return ast.copy_location(new_node, node)

    def visit_Call(self, node):
        """
        Transform .format() method calls into taint_format_string calls.

        Detects string literal calls to the .format() method and converts them
        to equivalent taint_format_string calls that preserve taint information.

        Args:
            node (ast.Call): The method call AST node to potentially transform

        Returns:
            ast.Call or ast.Call: Either a transformed taint_format_string call
                                 or the original node (via generic_visit)
        """
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
        """
        Transform % formatting operations into taint_percent_format calls.

        Detects binary modulo operations where the left operand is a string
        literal and converts them to equivalent taint_percent_format calls
        that preserve taint information through printf-style formatting.

        Args:
            node (ast.BinOp): The binary operation AST node to potentially transform

        Returns:
            ast.Call or ast.BinOp: Either a transformed taint_percent_format call
                                  or the original node (via generic_visit)
        """
        # Add support for string % formatting
        if isinstance(node.op, ast.Mod) and (
            isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)
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
