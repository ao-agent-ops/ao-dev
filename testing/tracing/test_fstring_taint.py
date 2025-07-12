import ast
import traceback

# Load user's script from disk
user_script_path = "user_script.py"
with open(user_script_path, "r") as f:
    user_code = f.read()

# Taint runtime helpers
taint_runtime_code = """
class TaintedString(str):
    def __new__(cls, value, taint=False):
        obj = str.__new__(cls, value)
        obj.taint = taint
        return obj

    def is_tainted(self):
        return getattr(self, 'taint', False)

def taint_concat(format_str, *args):
    result = format_str.format(*[str(arg) for arg in args])
    tainted = any(getattr(arg, 'is_tainted', False) for arg in args)
    return TaintedString(result, tainted)
"""

# AST Transformer to replace f-strings with taint_concat calls
class FstringToTaintConcat(ast.NodeTransformer):
    def visit_JoinedStr(self, node):
        format_str = ""
        args = []

        for part in node.values:
            if isinstance(part, ast.Constant):
                format_str += part.value
            elif isinstance(part, ast.FormattedValue):
                format_str += "{}"
                args.append(part.value)

        new_node = ast.Call(
            func=ast.Name(id="taint_concat", ctx=ast.Load()),
            args=[ast.Constant(value=format_str)] + args,
            keywords=[]
        )
        ast.copy_location(new_node, node)
        return new_node

# Parse and transform user's code
parsed_user_ast = ast.parse(user_code, filename=user_script_path)
transformed_user_ast = FstringToTaintConcat().visit(parsed_user_ast)
ast.fix_missing_locations(transformed_user_ast)

# Combine runtime and user code
runtime_ast = ast.parse(taint_runtime_code, filename="taint_runtime.py")
runtime_ast.body.extend(transformed_user_ast.body)

# Compile and execute with filename pointing to actual user file
try:
    code = compile(runtime_ast, filename=user_script_path, mode="exec")
    exec(code, {})
except Exception:
    traceback.print_exc()
