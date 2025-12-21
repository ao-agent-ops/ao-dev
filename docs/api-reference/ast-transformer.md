# AST Transformer Reference

The AST transformer rewrites Python source code to propagate taint information through all operations.

## Overview

The transformer handles:

1. **String formatting** - f-strings, `.format()`, and `%` formatting
2. **Third-party function calls** - Wraps external library calls with taint propagation

## Main Functions

### rewrite_source_to_code

Transform and compile Python source with AST rewrites:

::: aco.server.ast_transformer.rewrite_source_to_code
    options:
      show_root_heading: true
      show_source: true

### exec_func

Execute a function with taint propagation:

::: aco.server.ast_transformer.exec_func
    options:
      show_root_heading: true
      show_source: true

## String Formatting Functions

### taint_fstring_join

Taint-aware replacement for f-string concatenation:

::: aco.server.ast_transformer.taint_fstring_join
    options:
      show_root_heading: true
      show_source: true

### taint_format_string

Taint-aware replacement for `.format()` calls:

::: aco.server.ast_transformer.taint_format_string
    options:
      show_root_heading: true
      show_source: true

### taint_percent_format

Taint-aware replacement for `%` formatting:

::: aco.server.ast_transformer.taint_percent_format
    options:
      show_root_heading: true
      show_source: true

## Transformer Classes

### TaintPropagationTransformer

The main AST transformer class:

::: aco.server.ast_transformer.TaintPropagationTransformer
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - visit_JoinedStr
        - visit_Call
        - visit_BinOp

## Utility Functions

### is_pyc_rewritten

Check if a `.pyc` file was created by the AST transformer:

::: aco.server.ast_transformer.is_pyc_rewritten
    options:
      show_root_heading: true
      show_source: true
