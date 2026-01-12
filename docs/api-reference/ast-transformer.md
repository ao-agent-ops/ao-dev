# AST Transformer Reference

The AST transformer rewrites Python source code to propagate taint information through all operations.

## Overview

The transformer handles:

1. **String formatting** - f-strings, `.format()`, and `%` formatting
2. **Third-party function calls** - Wraps external library calls with taint propagation

## Main Functions

### rewrite_source_to_code

Transform and compile Python source with AST rewrites:

::: ao.server.file_watcher.rewrite_source_to_code
    options:
      show_root_heading: true
      show_source: true

### exec_func

Execute a function with taint propagation:

::: ao.server.taint_ops.exec_func
    options:
      show_root_heading: true
      show_source: true

## String Formatting Functions

### taint_fstring_join

Taint-aware replacement for f-string concatenation:

::: ao.server.taint_ops.taint_fstring_join
    options:
      show_root_heading: true
      show_source: true

### taint_format_string

Taint-aware replacement for `.format()` calls:

::: ao.server.taint_ops.taint_format_string
    options:
      show_root_heading: true
      show_source: true

### taint_percent_format

Taint-aware replacement for `%` formatting:

::: ao.server.taint_ops.taint_percent_format
    options:
      show_root_heading: true
      show_source: true

## Transformer Classes

### TaintPropagationTransformer

The main AST transformer class:

::: ao.server.ast_transformer.TaintPropagationTransformer
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - visit_JoinedStr
        - visit_Call
        - visit_BinOp

