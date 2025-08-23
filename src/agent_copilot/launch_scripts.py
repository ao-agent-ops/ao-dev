# Wrapper script templates for launching user code with AST patching and environment setup.
# These templates use placeholders that will be replaced by develop_shim.py.


_SETUP_TRACING_SETUP = """import os
import sys
import runpy

project_root = {project_root}
packages_in_project_root = {packages_in_project_root}

# Add project root to path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force load sitecustomize.py for AST patching
runtime_tracing_dir = {runtime_tracing_dir}
if runtime_tracing_dir not in sys.path:
    sys.path.insert(0, runtime_tracing_dir)

# Set up AST rewriting
from runtime_tracing.sitecustomize import setup_tracing
from runtime_tracing.fstring_rewriter import install_fstring_rewriter, set_module_to_user_file
from common.utils import scan_user_py_files_and_modules

_, _, module_to_file = scan_user_py_files_and_modules(project_root)
for additional_package in packages_in_project_root:
    _, _, additional_package_module_to_file = scan_user_py_files_and_modules(additional_package)
    module_to_file = {{**module_to_file, **additional_package_module_to_file}}

set_module_to_user_file(module_to_file)
install_fstring_rewriter()

setup_tracing()
"""


# Template for running a script as a module (when user runs: develop script.py)
SCRIPT_WRAPPER_TEMPLATE = (
    _SETUP_TRACING_SETUP
    + """
# Set up argv and run the module
module_name = os.path.abspath({module_name})
sys.argv = [{module_name}] + {script_args}
runpy.run_module({module_name}, run_name='__main__')
"""
)

# Template for running a module directly (when user runs: develop -m module)
MODULE_WRAPPER_TEMPLATE = (
    _SETUP_TRACING_SETUP
    + """
# Now run the module with proper resolution
sys.argv = [{module_name}] + {script_args}
runpy.run_module({module_name}, run_name='__main__')
"""
)
