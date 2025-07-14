import ast
import importlib.abc
import importlib.util
import sys
import os
from common.logging_config import setup_logging

logger = setup_logging()

_user_py_files = set()
_user_file_to_module = dict()

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

def taint_format_string(format_string, *args, **kwargs):
    from runtime_tracing.taint_wrappers import TaintStr, get_origin_nodes
    result = format_string.format(*args, **kwargs)
    all_origins = set()
    for a in args:
        all_origins.update(get_origin_nodes(a))
    for v in kwargs.values():
        all_origins.update(get_origin_nodes(v))
    if all_origins:
        return TaintStr(result, {'origin_nodes': list(all_origins)})
    return result

class FStringTransformer(ast.NodeTransformer):
    def visit_JoinedStr(self, node):
        logger.debug(f"Transforming f-string at line {getattr(node, 'lineno', '?')}")
        # Replace f-string with a call to taint_fstring_join
        new_node = ast.Call(
            func=ast.Name(id='taint_fstring_join', ctx=ast.Load()),
            args=[value for value in node.values],
            keywords=[]
        )
        return ast.copy_location(new_node, node)
    
    def visit_Call(self, node):
        # Check if this is a .format() call
        if (isinstance(node.func, ast.Attribute) and 
            isinstance(node.func.value, ast.Constant) and 
            isinstance(node.func.value.value, str) and
            node.func.attr == 'format'):
            
            logger.debug(f"Transforming .format() call at line {getattr(node, 'lineno', '?')}")
            
            # Extract the format string and arguments
            format_string = node.func.value.value
            format_args = node.args
            format_kwargs = node.keywords
            
            # Create a call to taint_format_string
            new_node = ast.Call(
                func=ast.Name(id='taint_format_string', ctx=ast.Load()),
                args=[ast.Constant(value=format_string)] + format_args,
                keywords=format_kwargs
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
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def source_to_code(self, data, path, *, _optimize=-1):
        logger.debug(f"Rewriting AST for {self.fullname} at {path}")
        tree = ast.parse(data, filename=path)
        tree = FStringTransformer().visit(tree)
        ast.fix_missing_locations(tree)
        return compile(tree, path, 'exec')

class FStringImportFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):        
        # Only handle modules that correspond to user files
        for file_path, mod_name in _user_file_to_module.items():
            if mod_name == fullname:
                logger.debug(f"Will rewrite: {fullname} from {file_path}")
                return importlib.util.spec_from_loader(fullname, FStringImportLoader(fullname, file_path))
        logger.debug(f"No match found for: {fullname}")
        return None

def install_fstring_rewriter():
    if not any(isinstance(f, FStringImportFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, FStringImportFinder())
    # Make taint functions globally available
    import builtins
    builtins.taint_fstring_join = taint_fstring_join
    builtins.taint_format_string = taint_format_string 