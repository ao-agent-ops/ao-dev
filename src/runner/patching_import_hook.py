from types import ModuleType
import sys
import inspect
import functools
from importlib import reload, import_module
from importlib.machinery import (
    FileFinder,
    PathFinder,
    SourceFileLoader,
    BuiltinImporter,
    SOURCE_SUFFIXES,
)
from importlib.util import spec_from_loader
from common.logger import logger
from forbiddenfruit import curse


MODULE_WHITELIST = ["json", "re", "uuid"]

MODULE_BLACKLIST = [
    "os",
    "sys",
    "runpy",
    "importlib",
    "_io",
    "collections",
    "inspect",
    "multiprocessing",
    "functools",
    "tempfile",
    "types",
    "typing",
]

ATTR_BLACKLIST = [
    "aiter",
    "anext",
    "acii",
    "breakpoint",
    "callable",
    "chr",
    "compile",
    "copyright",
    "credits",
    "delattr",
    "dir",
    "eval",
    "exec",
    "execfile",
    "getattr",
    "globals",
    "hasattr",
    "isinstance",
    "issubclass",
    "iter",
    "locals",
    "next",
    "oct",
    "open",
    "runfile",
    "setattr",
]

_original_functions = {}


def get_all_taint(*args, **kwargs):
    return ""


def remove_taint(*args, **kwargs):
    pass


def apply_taint(output, taint):
    return output


def create_taint_wrapper(original_func):
    key = id(original_func)
    if key in _original_functions:
        logger.info(f"{key} already in _original_functions. returning...")
        return _original_functions[key]

    _original_functions[key] = original_func

    @functools.wraps(original_func)
    def patched_function(*args, **kwargs):
        taint = get_all_taint(*args, **kwargs)
        remove_taint(*args, **kwargs)
        output = _original_functions[key](*args, **kwargs)
        return apply_taint(output, taint)

    return patched_function


def patch_module_callables(module, visited=None):
    if isinstance(module, ModuleType):
        module_name = module.__name__
        parent_name = module_name.rpartition(".")[0] if "." in module_name else module_name
        if parent_name in MODULE_BLACKLIST:
            return

    if visited is None:
        visited = set()

    if id(module) in visited:
        return
    visited.add(id(module))

    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue

        if attr_name in ATTR_BLACKLIST:
            continue

        attr = getattr(module, attr_name)

        if inspect.isfunction(attr):
            # Patch functions
            logger.info(f"Patched {module}.{attr_name}")
            setattr(module, attr_name, create_taint_wrapper(attr))
        elif inspect.isclass(attr):
            # Patch class methods
            patch_class_methods(attr)
        elif inspect.ismodule(attr):
            # Recurse into submodules
            patch_module_callables(attr, visited)
        elif callable(attr):
            # Other callables
            logger.info(f"Patched {module}.{attr_name}")
            setattr(module, attr_name, create_taint_wrapper(attr))


def patch_class_methods(cls):
    for method_name in dir(cls):
        if method_name.startswith("_"):
            continue
        try:
            method = getattr(cls, method_name)
        except AttributeError:
            continue

        if callable(method):
            logger.info(f"Patched {cls}.{method_name}")
            curse(cls, method_name, create_taint_wrapper(method))


class TaintModuleLoader(SourceFileLoader):
    def exec_module(self, module):
        """Execute the module."""
        super().exec_module(module)
        patch_module_callables(module=module)


class TaintBuiltinLoader(BuiltinImporter):
    def exec_module(self, module):
        """Execute the module."""
        super().exec_module(module)
        patch_module_callables(module=module)


class TaintImportHook:
    def find_spec(self, fullname, path, target=None):

        if "_" == fullname[:1]:
            logger.debug(f"Skipping attaching TaintImportHook to: {fullname}")
            return None

        if path is None:
            path = sys.path

        for search_path in path:
            # Create a FileFinder for this directory
            finder = FileFinder(search_path, (SourceFileLoader, SOURCE_SUFFIXES))

            # Try to find the module in this directory
            spec = finder.find_spec(fullname)
            # return spec
            if spec and spec.origin and isinstance(spec.loader, SourceFileLoader):
                return spec_from_loader(fullname, TaintModuleLoader(fullname, spec.origin))

        finder = PathFinder()
        # Try to find the module in this directory
        spec = finder.find_spec(fullname)
        # return spec
        if spec and spec.origin and isinstance(spec.loader, SourceFileLoader):
            return spec_from_loader(fullname, TaintModuleLoader(fullname, spec.origin))

        builtin_importer = BuiltinImporter()
        spec = builtin_importer.find_spec(fullname=fullname)
        if spec and spec.origin:
            return spec_from_loader(fullname, TaintBuiltinLoader())

        return None


# How do integrate the f-string re-writer:
# install the FStringFinder at first position in meta sys
# let it find only for modules in project root
# re-write the AST etc.
# execute the module and then patch the module


def install_patch_hook():
    if not any(isinstance(mod, TaintImportHook) for mod in sys.meta_path):
        sys.meta_path.insert(0, TaintImportHook())

    for module_name in MODULE_WHITELIST:
        mod = import_module(module_name)
        reload(mod)
