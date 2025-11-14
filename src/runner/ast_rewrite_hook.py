"""
TODO
"""

import sys
import os
import marshal
from importlib.abc import MetaPathFinder, SourceLoader
from importlib.util import spec_from_loader
from aco.common.logger import logger
from aco.server.file_watcher import rewrite_source_to_code, get_pyc_path

_module_to_user_file = dict()


def set_module_to_user_file(module_to_user_file: dict):
    global _module_to_user_file
    _module_to_user_file = module_to_user_file


class ASTImportLoader(SourceLoader):
    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def source_to_code(self, data, path, *, _optimize=-1):
        try:
            pyc_path = get_pyc_path(path)
            file_mtime = os.path.getmtime(path)
            pyc_mtime = os.path.getmtime(pyc_path)
            # .pyc was created after file was modified
            if file_mtime < pyc_mtime:
                # pyc file is valid
                with open(pyc_path, "rb") as f:
                    _ = f.read(16)  # header
                    code_object = marshal.load(f)
                logger.debug(f"[ASTHook] Using cached {pyc_path}")
                return code_object
        except OSError as e:
            logger.debug(f"[ASTHook] Pulling .pyc failed: {e}")

        # .pyc is stale or not ready yet, manual AST transform...
        logger.debug(f"[ASTHook] Rewriting AST for {self.fullname} at {path}")
        code_object = rewrite_source_to_code(data, path, module_to_file=_module_to_user_file)
        return code_object


class ASTImportFinder(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        # Only handle modules that correspond to user files
        for mod_name, file_path in _module_to_user_file.items():
            if mod_name == fullname:
                return spec_from_loader(fullname, ASTImportLoader(fullname, file_path))
        return None


def install_patch_hook():
    """
    TODO
    """
    # put the AST re-write first to make sure we re-write the user-defined in
    # files/modules
    if not any(isinstance(f, ASTImportFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, ASTImportFinder())
