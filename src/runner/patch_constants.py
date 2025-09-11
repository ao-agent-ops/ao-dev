"""
Constants for controlling taint tracking import hook behavior.

This module defines lists of modules and attributes that should be handled
specially during the taint tracking patching process to avoid conflicts,
circular imports, and other issues.
"""

# CPython modules that need special handling for taint tracking
# These modules have C extensions or special behavior that requires
# custom taint propagation through the obj_id_to_taint_origin mapping
CPYTHON_MODS = ["re"]

# Modules that are explicitly patched for taint tracking
# These modules are reloaded after the import hook is installed to
# ensure they are properly patched with taint wrappers
MODULE_WHITELIST = ["json", "re"]

# Specific module attributes that should NOT be patched
# Format: "module_name.attribute_name"
# These are typically internal functions that could cause issues if wrapped
MODULE_ATTR_BLACKLIST = [
    "json.load",
    "json.dump",
    "json.encoder",
    "json.decoder",
    "json.detect_encoding",
]

# Specific class methods that should NOT be patched
# Format: "ClassName.method_name"
# These are typically core methods that could break functionality if wrapped
CLS_ATTR_BLACKLIST = [
    "JSONEncoder.default",
    "JSONEncoder.decode",
    "JSONDecoder.raw_decode",
    "JSONEncoder.encode",
    "JSONEncoder.iterencode",
    "JSONDecodeError.add_note",
    "JSONDecodeError.with_traceback",
    "JSONDecoder.decode",
]
