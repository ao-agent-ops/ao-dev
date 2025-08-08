"""
Wrapper script templates for launching user code with AST patching and environment setup.
These templates use placeholders that will be replaced by develop_shim.py.
"""

# Template for running a script as a module (when user runs: develop script.py)
SCRIPT_WRAPPER_TEMPLATE = """import sys
import os
import runpy

# Force load sitecustomize.py for AST patching
runtime_tracing_dir = {runtime_tracing_dir}
if runtime_tracing_dir not in sys.path:
    sys.path.insert(0, runtime_tracing_dir)

# Add project root to path
project_root = {project_root}
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up AST rewriting
from runtime_tracing.fstring_rewriter import install_fstring_rewriter, set_user_py_files
from common.utils import scan_user_py_files_and_modules

# Scan and set up file mapping for the user's project root
user_py_files, file_to_module = scan_user_py_files_and_modules(project_root)
set_user_py_files(user_py_files, file_to_module)
install_fstring_rewriter()

# Set up argv and run the module
sys.argv = [{module_name}] + {script_args}
runpy.run_module({module_name}, run_name='__main__')
"""

# Template for running a module directly (when user runs: develop -m module)
MODULE_WRAPPER_TEMPLATE = """import sys
import os
import subprocess
import runpy

# Force load sitecustomize.py for AST patching
runtime_tracing_dir = {runtime_tracing_dir}
if runtime_tracing_dir not in sys.path:
    sys.path.insert(0, runtime_tracing_dir)

# Add project root to path
project_root = {project_root}
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up AST rewriting
from runtime_tracing.fstring_rewriter import install_fstring_rewriter, set_user_py_files
from common.utils import scan_user_py_files_and_modules

# Scan and set up file mapping for the user's project root
user_py_files, file_to_module = scan_user_py_files_and_modules(project_root)
set_user_py_files(user_py_files, file_to_module)
install_fstring_rewriter()

# Now run the module with proper resolution
module_name = {module_name}
sys.argv = [module_name] + {script_args}

# For files outside the project root, just use the module name as-is
# For files inside the project root, find the correct module name from the file mapping
if module_name and not module_name.startswith('..'):
    correct_module_name = None
    for file_path, mapped_name in file_to_module.items():
        if mapped_name == module_name:
            correct_module_name = mapped_name
            break
        # Also check if the module name is a suffix of the mapped name
        elif mapped_name.endswith('.' + module_name):
            correct_module_name = mapped_name
            break

    if correct_module_name:
        runpy.run_module(correct_module_name, run_name='__main__')
    else:
        runpy.run_module(module_name, run_name='__main__')
else:
    runpy.run_module(module_name, run_name='__main__')
""" 