import ast
import importlib.abc
import importlib.util
import sys
import os

_user_py_files = set()
_user_file_to_module = dict()

# Called from sitecustomize.py
# py_files: set of absolute file paths
# file_to_module: dict mapping file path to module name

def set_user_py_files(py_files, file_to_module=None):
    global _user_py_files, _user_file_to_module
    _user_py_files = py_files
    if file_to_module is not None:
        _user_file_to_module = file_to_module


def taint_fstring_join(*args):
    from runtime_tracing.taint_wrappers import TaintStr, get_origin_nodes
    result = ''.join(str(a) for a in args)
    all_origins = set()
    for a in args:
        all_origins.update(get_origin_nodes(a))
    if all_origins:
        return TaintStr(result, {'origin_nodes': list(all_origins)})
    return result

class FStringTransformer(ast.NodeTransformer):
    def visit_JoinedStr(self, node):
        # Replace f-string with a call to taint_fstring_join
        new_node = ast.Call(
            func=ast.Name(id='taint_fstring_join', ctx=ast.Load()),
            args=[value for value in node.values],
            keywords=[]
        )
        return ast.copy_location(new_node, node)

class FStringImportLoader(importlib.abc.SourceLoader):
    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def source_to_code(self, data, path, *, _optimize=-1):
        tree = ast.parse(data, filename=path)
        tree = FStringTransformer().visit(tree)
        ast.fix_missing_locations(tree)
        return compile(tree, path, 'exec')

class FStringImportFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        # Only handle modules that correspond to user files
        # Try to resolve the file path for this module name
        for file_path, mod_name in _user_file_to_module.items():
            if mod_name == fullname:
                return importlib.util.spec_from_loader(fullname, FStringImportLoader(fullname, file_path))
        return None

def install_fstring_rewriter():
    if not any(isinstance(f, FStringImportFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, FStringImportFinder())
    # Make taint_fstring_join globally available
    import builtins
    builtins.taint_fstring_join = taint_fstring_join 