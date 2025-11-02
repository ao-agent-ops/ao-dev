"""
Taint tracking import hook system.

This module implements a comprehensive taint tracking system using Python's import
machinery. It intercepts module loading and dynamically patches functions, methods,
and callables to propagate taint information through the application.

Key Components:
- TaintImportHook: Custom import hook that intercepts module loading
- TaintModuleLoader/TaintBuiltinLoader: Custom loaders that apply patching
- create_taint_wrapper: Creates taint-aware wrappers for functions and methods
- patch_module_callables: Recursively patches all callables in a module

The system handles both synchronous and asynchronous functions, avoids circular
imports, and respects blacklists to prevent patching system-critical modules.
"""

from types import ModuleType
import os
import random
import sys
import ast
import inspect
import functools
from importlib import reload, import_module
from importlib.abc import MetaPathFinder, SourceLoader
from importlib.machinery import (
    PathFinder,
    SourceFileLoader,
    BuiltinImporter,
)
from importlib.util import spec_from_loader
from forbiddenfruit import curse
from aco.runner.taint_wrappers import (
    get_taint_origins,
    taint_wrap,
    untaint_if_needed,
)
from aco.runner.fstring_rewriter import (
    FStringTransformer,
    taint_fstring_join,
    taint_format_string,
    taint_percent_format,
)
from aco.common.logger import logger
import threading
from contextlib import contextmanager
from .patch_constants import (
    MODULE_WHITELIST,
    MODULE_ATTR_BLACKLIST,
    CLS_ATTR_BLACKLIST,
)


# Thread-local storage for taint propagation control
_thread_local = threading.local()

# Cache of original functions to avoid re-wrapping
_user_py_files = set()
_user_file_to_module = dict()
_module_to_user_file = dict()
_original_functions = dict()


def set_user_py_files(py_files, file_to_module=None):
    global _user_py_files, _user_file_to_module
    _user_py_files = py_files
    if file_to_module is not None:
        _user_file_to_module = file_to_module


def set_module_to_user_file(module_to_user_file: dict):
    global _module_to_user_file
    _module_to_user_file = module_to_user_file


@contextmanager
def disable_taint_propagation():
    """
    Context manager to temporarily disable taint propagation.

    This is used during module patching to prevent circular import issues
    when the patched import functions are called during the patching process.

    Yields:
        None: Context where taint propagation is disabled
    """
    old_value = getattr(_thread_local, "disable_taint", False)
    _thread_local.disable_taint = True
    try:
        yield
    finally:
        _thread_local.disable_taint = old_value


def _is_taint_disabled():
    """
    Check if taint propagation is currently disabled.

    Returns:
        bool: True if taint propagation is disabled, False otherwise
    """
    return getattr(_thread_local, "disable_taint", False)


def get_all_taint(*args, **kwargs):
    """
    Extract all taint origins from function arguments.

    Recursively analyzes the provided arguments and keyword arguments
    to collect all taint origin information.

    Args:
        *args: Positional arguments to analyze for taint
        **kwargs: Keyword arguments to analyze for taint

    Returns:
        set: Set of all taint origins found in the arguments
    """
    try:
        args_taint_origins = get_taint_origins(args)
        kwargs_taint_origins = get_taint_origins(kwargs)
        taints = set(args_taint_origins) | set(kwargs_taint_origins)
    except Exception:
        logger.debug(f"Failed to get taint for args, kwargs {args} {kwargs}")
        taints = set()
    return taints


def remove_taint(*args, **kwargs):
    """
    Remove taint information from arguments, returning clean versions.

    Args:
        *args: Positional arguments to untaint
        **kwargs: Keyword arguments to untaint

    Returns:
        tuple: (untainted_args, untainted_kwargs)
    """
    args = untaint_if_needed(args)
    kwargs = untaint_if_needed(kwargs)
    return args, kwargs


def apply_taint(output, taint_origin: set):
    """
    Apply taint information to an output value.

    Args:
        output: The value to taint
        taint_origin (set): Set of taint origins to apply

    Returns:
        The tainted version of the output
    """
    if taint_origin:
        return taint_wrap(output, taint_origin=taint_origin)
    return output


def create_taint_wrapper(original_func):
    """
    Create a taint-aware wrapper for a function or method.

    This function creates a wrapper that:
    - Extracts taint from input arguments
    - Calls the original function (with proper async handling)
    - Applies collected taint to the output
    - Handles both synchronous and asynchronous functions

    Args:
        original_func: The function to wrap with taint tracking

    Returns:
        callable: A taint-aware wrapper function that preserves the original's signature
    """
    # Don't patch generator functions - they have special semantics that need to be preserved
    if inspect.isgeneratorfunction(original_func):
        return original_func

    if getattr(original_func, "_is_taint_wrapped", False):
        return original_func

    key = id(original_func)

    if key in _original_functions:
        return _original_functions[key]

    # Check if the original function is async
    if inspect.iscoroutinefunction(original_func):

        @functools.wraps(original_func)
        async def async_patched_function(*args, **kwargs):
            if _is_taint_disabled():
                return await original_func(*args, **kwargs)

            with disable_taint_propagation():
                taint = get_all_taint(*args, **kwargs)
                output = await original_func(*args, **kwargs)
                # it could be that the returned function is also patched. this can lead to unforeseen side-effects
                # so we recursively unwrap it
                if hasattr(output, "__name__") and output.__name__ == "patched_function":
                    output = inspect.unwrap(output)
                tainted_output = apply_taint(output, taint)
                return tainted_output

        async_patched_function._is_taint_wrapped = True
        _original_functions[key] = async_patched_function
        return async_patched_function
    else:

        @functools.wraps(original_func)
        def patched_function(*args, **kwargs):
            if _is_taint_disabled():
                return original_func(*args, **kwargs)

            with disable_taint_propagation():
                # TODO, the orig func could also return taint. if that is the case,
                # we should ignore the high-level taint because the sub-func is more precise
                taint = get_all_taint(*args, **kwargs)
                output = original_func(*args, **kwargs)
                # it could be that the returned function is also patched. this can lead to unforeseen side-effects
                # so we recursively unwrap it
                if hasattr(output, "__name__") and output.__name__ == "patched_function":
                    output = inspect.unwrap(output)
                tainted_output = apply_taint(output, taint)
                return tainted_output

        patched_function._is_taint_wrapped = True
        _original_functions[key] = patched_function
        return patched_function


def has_lazy_imports(module) -> bool:
    """
    Check if module uses lazy imports that could interfere with taint tracking.

    Detects common third-party lazy import patterns that can cause
    "dictionary changed size during iteration" errors.

    Args:
        module: The module to check

    Returns:
        bool: True if lazy imports are detected, False otherwise
    """
    if not hasattr(module, "__dict__"):
        return False

    # Check for common lazy import function names that actually exist
    lazy_import_indicators = {
        "lazy_import",  # websockets and other libraries use this
        "__lazy_import__",
        "_lazy_import",
    }

    try:
        # Use list() to create a snapshot and avoid "dictionary changed size during iteration"
        items = list(module.__dict__.items())
    except RuntimeError:
        # If we can't even create a snapshot, this module is definitely problematic
        return True

    for name, value in items:
        # Direct function name match
        if name in lazy_import_indicators:
            return True
        # Check if it's a callable with lazy_import in the name
        if callable(value) and hasattr(value, "__name__"):
            try:
                if value.__name__ in lazy_import_indicators:
                    return True
            except TypeError:  # value.__name__ might not be hashable
                return False

    return False


def patch_module_callables(module, visited=None):
    """
    Recursively patch all callables in a module with taint tracking.

    This function traverses a module and its attributes, applying taint wrappers to:
    - Functions and methods
    - Class methods (static, class, and instance methods)
    - Callable objects (with special handling for __call__ method)
    - Submodules (recursively)

    It respects blacklists and handles special cases like:
    - Modules with lazy imports
    - Partially loaded modules
    - Built-in functions and methods
    - Objects that may cause circular imports

    Args:
        module: The module to patch (ModuleType or other object)
        visited (set, optional): Set of already visited module IDs to prevent cycles
    """
    # Skip patching modules with lazy imports to avoid runtime dictionary modification issues
    if has_lazy_imports(module):
        logger.debug(
            f"Skipping patching for module {getattr(module, '__name__', 'unknown')} - uses lazy imports"
        )
        return

    if isinstance(module, ModuleType):
        module_name = module.__name__
        parent_name = module_name.lstrip(".").split(".")[0]
        if not parent_name in MODULE_WHITELIST:
            return

    if visited is None:
        visited = set()

    if id(module) in visited:
        return
    visited.add(id(module))

    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue

        if f"{module_name}.{attr_name}" in MODULE_ATTR_BLACKLIST:
            logger.info(f"{module_name}.{attr_name} in MODULE_ATTR_BLACKLIST. Skipped.")
            continue

        # Safely get attribute, avoiding lazy import triggers during patching
        try:
            # First try to get it directly from __dict__ to avoid __getattr__
            if hasattr(module, "__dict__") and attr_name in module.__dict__:
                attr = module.__dict__[attr_name]
            else:
                # If not in __dict__, try normal getattr but be prepared for circular imports
                attr = getattr(module, attr_name)
        except (AttributeError, ImportError) as e:
            # Skip attributes that cause circular imports or don't exist
            logger.warning(f"Skipping {module_name}.{attr_name} due to: {e}")
            continue
        except Exception as e:
            logger.warning(f"Unexpected error accessing {module_name}.{attr_name}: {e}")
            continue

        if inspect.isfunction(attr):
            # Patch functions
            if hasattr(attr, "__wrapped__"):  # already patched
                continue

            logger.info(f"Patched {module_name}.{attr_name}")
            setattr(module, attr_name, create_taint_wrapper(attr))
        elif inspect.isclass(attr):
            # Patch class methods
            patch_class_methods(attr)
        elif inspect.ismodule(attr):
            # Recurse into submodules
            patch_module_callables(attr, visited)
        elif callable(attr):
            if attr.__class__.__name__ == "builtin_function_or_method":
                setattr(module, attr_name, create_taint_wrapper(attr))
                continue

            try:
                setattr(attr, "__call__", create_taint_wrapper(attr.__call__))
            except AttributeError:
                pass


def patch_class_methods(cls):
    """
    Patch all methods of a class with taint tracking.

    Handles different types of methods:
    - Regular instance methods
    - Static methods (@staticmethod)
    - Class methods (@classmethod)

    Uses forbiddenfruit.curse to safely monkey-patch class methods
    while preserving their descriptor types.

    Args:
        cls: The class whose methods should be patched
    """
    if not cls.__class__.__name__ == "type":
        return

    for method_name in dir(cls):
        if method_name.startswith("_"):
            continue
        try:
            # Check the original descriptor type in __dict__
            original_descriptor = None
            if hasattr(cls, "__dict__") and method_name in cls.__dict__:
                original_descriptor = cls.__dict__[method_name]

            method = getattr(cls, method_name)
        except AttributeError:
            continue

        if inspect.ismethod(method) or inspect.isfunction(method):
            if f"{cls.__name__}.{method_name}" in CLS_ATTR_BLACKLIST:
                continue

            # Get the unbound function for special method types
            if isinstance(original_descriptor, staticmethod):
                # For staticmethod, get the wrapped function
                unbound_func = original_descriptor.__func__
                wrapped_method = create_taint_wrapper(unbound_func)
                curse(cls, method_name, staticmethod(wrapped_method))
            elif isinstance(original_descriptor, classmethod):
                # For classmethod, get the wrapped function
                unbound_func = original_descriptor.__func__
                wrapped_method = create_taint_wrapper(unbound_func)
                curse(cls, method_name, classmethod(wrapped_method))
            else:
                # Regular instance method
                wrapped_method = create_taint_wrapper(method)
                curse(cls, method_name, wrapped_method)

        elif callable(method):
            try:
                setattr(method, "__call__", create_taint_wrapper(method.__call__))
            except Exception:
                # callable, could be CPython
                wrapped_method = create_taint_wrapper(method)
                curse(cls, method_name, wrapped_method)


class TaintModuleLoader(SourceFileLoader):
    """
    Custom module loader that applies taint tracking after module execution.

    Extends SourceFileLoader to automatically patch all callables in a module
    after it has been loaded and executed.
    """

    def exec_module(self, module):
        """
        Execute the module and apply taint tracking patches.

        Args:
            module: The module to execute and patch
        """
        super().exec_module(module)
        patch_module_callables(module=module)


class TaintBuiltinLoader(BuiltinImporter):
    """
    Custom builtin module loader that applies taint tracking after module loading.

    Extends BuiltinImporter to automatically patch all callables in builtin
    modules after they have been loaded.
    """

    def exec_module(self, module):
        """
        Execute the builtin module and apply taint tracking patches.

        Args:
            module: The builtin module to execute and patch
        """
        super().exec_module(module)
        patch_module_callables(module=module)


class FStringImportLoader(SourceLoader):
    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def exec_module(self, module):
        super().exec_module(module)
        # NOTE This does not even get triggered!!
        # We are not patching functions in the user-code...
        patch_module_callables(module=module)

    def source_to_code(self, data, path, *, _optimize=-1):
        logger.debug(f"Rewriting AST for {self.fullname} at {path}")
        tree = ast.parse(data, filename=path)
        tree = FStringTransformer().visit(tree)
        ast.fix_missing_locations(tree)
        return compile(tree, path, "exec")


class TaintImportHook:
    """
    Custom import hook that intercepts module loading for taint tracking.

    This hook is inserted into sys.meta_path to intercept all module imports
    and ensure they use our custom loaders that apply taint tracking patches.

    Handles both source modules (Python files) and builtin modules (C extensions).
    """

    def find_spec(self, fullname: str, path, target=None):
        """
        Find the module specification and return one with our custom loader.

        This method intercepts module loading and replaces the standard loaders
        with our taint-aware versions.

        Args:
            fullname (str): The fully qualified name of the module
            path: The search path for the module
            target: The module object (unused)

        Returns:
            ModuleSpec or None: A module spec with our custom loader, or None
                               to let other finders handle the module
        """
        if fullname.startswith("_"):
            return None

        if path is None:
            path = sys.path

        # Try builtin modules first
        builtin_importer = BuiltinImporter()
        spec = builtin_importer.find_spec(fullname=fullname)
        if spec and spec.origin:
            return spec_from_loader(fullname, TaintBuiltinLoader())

        # Try source modules
        finder = PathFinder()
        spec = finder.find_spec(fullname, path=path)
        if spec and spec.origin and isinstance(spec.loader, SourceFileLoader):
            return spec_from_loader(fullname, TaintModuleLoader(fullname, spec.origin))
        return None


class FStringImportFinder(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        # Only handle modules that correspond to user files
        for mod_name, file_path in _module_to_user_file.items():
            if mod_name == fullname:
                logger.debug(f"Will rewrite: {fullname} from {file_path}")
                return spec_from_loader(fullname, FStringImportLoader(fullname, file_path))
        return None


def install_patch_hook():
    """
    Install the taint tracking import hook into the Python import system.

    This function:
    1. Inserts our TaintImportHook at the beginning of sys.meta_path
    2. Reloads whitelisted modules to ensure they get properly patched

    Should be called once at application startup to enable taint tracking.
    """
    if not any(isinstance(mod, TaintImportHook) for mod in sys.meta_path):
        sys.meta_path.insert(0, TaintImportHook())

    # put the f-string re-write first to make sure we re-write the f-strings in
    # the files/modules we want to
    if not any(isinstance(f, FStringImportFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, FStringImportFinder())

    for module_name in MODULE_WHITELIST:
        mod = import_module(module_name)
        reload(mod)

    # Set random seeds
    aco_random_seed = os.environ.get("ACO_SEED", None)
    if not aco_random_seed:
        raise Exception("ACO random seed not set.")
    else:
        try:
            aco_random_seed = int(aco_random_seed)
        except:
            raise Exception("Error converting ACO_SEED to int.")

    logger.debug(f"ACO_SEED was set to {aco_random_seed}")

    try:
        from numpy.random import seed

        seed(aco_random_seed)
    except:
        logger.debug("Failed to set the numpy seed")

    try:
        from torch import manual_seed

        manual_seed(aco_random_seed)
    except:
        logger.debug("Failed to set the torch seed")

    random.seed(aco_random_seed)

    # Make taint functions available in bultins
    import builtins

    builtins.taint_fstring_join = taint_fstring_join
    builtins.taint_format_string = taint_format_string
    builtins.taint_percent_format = taint_percent_format
