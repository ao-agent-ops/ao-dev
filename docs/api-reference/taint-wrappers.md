# Taint Wrappers Reference

Taint wrappers are the core data types that enable AO to track data provenance through your Python code.

## Overview

When an LLM produces output, AO wraps that output in a taint-aware type. As the data flows through your program, the taint information propagates, allowing AO to build the dataflow graph.

## Taint-Aware Types

### TaintStr

A string that tracks its origins:

::: ao.runner.taint_wrappers.TaintStr
    options:
      show_root_heading: true
      show_source: false
      members:
        - __new__
        - __add__
        - join
        - split
        - get_raw

### TaintInt

An integer that tracks its origins:

::: ao.runner.taint_wrappers.TaintInt
    options:
      show_root_heading: true
      show_source: false
      members:
        - __new__
        - get_raw

### TaintFloat

A float that tracks its origins:

::: ao.runner.taint_wrappers.TaintFloat
    options:
      show_root_heading: true
      show_source: false
      members:
        - __new__
        - get_raw

### TaintList

A list that tracks taint from its elements:

::: ao.runner.taint_wrappers.TaintList
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - append
        - extend
        - get_raw

### TaintDict

A dictionary that tracks taint from its values:

::: ao.runner.taint_wrappers.TaintDict
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - update
        - get_raw

### TaintObject

A generic wrapper for objects that don't fit the basic types:

::: ao.runner.taint_wrappers.TaintObject
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - __getattr__
        - __call__
        - get_raw

## Utility Functions

### get_taint_origins

Extract taint origins from any value:

::: ao.runner.taint_wrappers.get_taint_origins
    options:
      show_root_heading: true
      show_source: true

### untaint_if_needed

Remove taint wrapper and return the raw value:

::: ao.runner.taint_wrappers.untaint_if_needed
    options:
      show_root_heading: true
      show_source: true

### is_tainted

Check if a value has taint information:

::: ao.runner.taint_wrappers.is_tainted
    options:
      show_root_heading: true
      show_source: true

### taint_wrap

Wrap a value with taint information:

::: ao.runner.taint_wrappers.taint_wrap
    options:
      show_root_heading: true
      show_source: true
