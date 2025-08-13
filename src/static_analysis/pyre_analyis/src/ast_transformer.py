#!/usr/bin/env python3
"""
AST Transformer for LLM Call Simplification

Transforms complex LLM API patterns into simple function calls that Pyre can
analyze effectively for taint flow detection.
"""

import libcst as cst
from typing import Dict, List, Any, Union, Optional, Tuple
import re
from libcst.metadata import PositionProvider


class LLMCallTransformer(cst.CSTTransformer):
    """
    Transforms LLM API calls and related patterns to simplify Pyre analysis.

    Key transformations:
    1. Convert LLM API calls to simple call_llm() functions
    2. Simplify member variable patterns
    3. Handle dictionary operations (Pyre handles these by default)
    4. Handle database operations to preserve taint flows
    5. Preserve line numbers for result mapping
    6. Sanitize operations on sanitized values to eliminate false positives
    """

    # Request position metadata so we can keep the replacement's vertical size
    # identical to the original call (avoids shifting later line numbers).
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, llm_patterns: Dict[str, List[str]], source_file_path: str = ""):
        super().__init__()
        self.llm_patterns = llm_patterns
        self.source_file_path = source_file_path
        self.member_variables = {}  # Track member variables for simplification
        self.current_class = None
        self.current_function = None
        self.call_llm_vars = set()  # Track variables that store call_llm results
        self.transformation_count = 0
        self.methods_with_llm_calls = set()  # Track methods that contain LLM calls
        self.sanitized_vars = (
            set()
        )  # Track variables that contain sanitized values (None, empty tuples, etc.)
        self.sanitized_calls_in_current_assign = (
            False  # Track if current assignment RHS was sanitized
        )

        # Line number mapping: transformed_line -> original_line
        self.line_mapping: Dict[int, int] = {}
        self.transformation_locations: List[Tuple[int, str, str]] = (
            []
        )  # (line, original_pattern, transformed_pattern)

        # Compile pattern regexes for efficiency
        self.compiled_patterns = {}
        for provider, patterns in llm_patterns.items():
            self.compiled_patterns[provider] = [
                re.compile(pattern.replace(".", r"\.").replace("*", ".*")) for pattern in patterns
            ]

    def _get_original_line(self, node: cst.CSTNode) -> int:
        """Get the original line number for a node."""
        try:
            position = self.get_metadata(PositionProvider, node)
            if position and position.start:
                return position.start.line
        except Exception:
            pass
        return 0

    def _record_transformation(
        self, node: cst.CSTNode, original_pattern: str, transformed_pattern: str
    ):
        """Record a transformation for line number mapping."""
        line_num = self._get_original_line(node)
        if line_num > 0:
            self.transformation_locations.append((line_num, original_pattern, transformed_pattern))

    def get_line_mapping(self) -> Dict[int, int]:
        """Return the line number mapping for this transformation."""
        return self.line_mapping

    def get_transformation_locations(self) -> List[Tuple[int, str, str]]:
        """Return all transformation locations."""
        return self.transformation_locations

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        """Track current class for member variable transformation"""
        self.current_class = node.name.value
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        """Track current function for LLM call detection"""
        self.current_function = (
            f"{self.current_class}.{node.name.value}" if self.current_class else node.name.value
        )
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        """Reset class tracking"""
        self.current_class = None
        return updated_node

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        """
        Transform member variable assignments and track call_llm variables.

        Convert: self.client = LLMClient()
        To: client = LLMClient()  (module-level)

        Also track variables that store call_llm results, database results, and sanitized values for better flow detection.
        """
        # First check if this assignment contains a sanitized call on the RHS
        if self.sanitized_calls_in_current_assign:
            # Mark all target variables as sanitized
            for target in updated_node.targets:
                self._mark_assignment_targets_as_sanitized(target.target)
            # Reset the flag
            self.sanitized_calls_in_current_assign = False
            return updated_node

        if self.current_class and len(updated_node.targets) == 1:
            target = updated_node.targets[0]

            # Check for self.variable = value pattern
            if isinstance(target.target, cst.Attribute):
                attr = target.target
                if isinstance(attr.value, cst.Name) and attr.value.value == "self":

                    attr_name = attr.attr.value

                    # Check if this is LLM-related or contains common LLM patterns
                    if self._is_llm_related_assignment(updated_node.value) or any(
                        pattern in attr_name.lower()
                        for pattern in ["openai", "anthropic", "client", "llm", "ai"]
                    ):

                        # Transform to module-level variable with better naming
                        if attr_name.lower() in ["openai", "anthropic"] and not attr_name.endswith(
                            "_client"
                        ):
                            var_name = f"{attr_name}_client"
                        else:
                            var_name = attr_name

                        self.member_variables[attr_name] = True

                        # Create new assignment without self.
                        new_target = cst.AssignTarget(target=cst.Name(var_name))
                        return updated_node.with_changes(targets=[new_target])

        # Track variables that store call_llm results, database results, or sanitized values
        if len(updated_node.targets) == 1:
            target = updated_node.targets[0]
            if isinstance(target.target, cst.Name):
                var_name = target.target.value

                # Check if the value is a call_llm call or llm() call
                if isinstance(updated_node.value, cst.Call):
                    func_name = None
                    if isinstance(updated_node.value.func, cst.Name):
                        func_name = updated_node.value.func.value

                    # Track call_llm and llm function calls
                    if func_name in ["call_llm", "llm"]:
                        self._mark_var_as_tainted(var_name)

                    # Check if it's a database fetch operation
                    elif self._is_database_fetch_operation(updated_node.value):
                        # Mark as tainted regardless - database operations should preserve taint
                        self._mark_var_as_tainted(var_name)

                # Check if the value is a sanitized constant (None, empty tuple, empty dict)
                elif self._is_sanitized_value(updated_node.value):
                    self.sanitized_vars.add(var_name)

                # Check if the value is a variable that contains call_llm result or database result
                elif isinstance(updated_node.value, cst.Name):
                    source_var = updated_node.value.value
                    if source_var in self.call_llm_vars:
                        self._mark_var_as_tainted(var_name)
                    elif source_var in self.sanitized_vars:
                        self.sanitized_vars.add(var_name)

                # Check for attribute access on sanitized variables
                elif isinstance(updated_node.value, cst.Attribute):
                    if self._is_sanitized_attribute(updated_node.value):
                        self.sanitized_vars.add(var_name)

        # Handle dictionary key assignment like y["key"] = tainted_value
        if len(updated_node.targets) == 1 and isinstance(
            updated_node.targets[0].target, cst.Subscript
        ):
            target = updated_node.targets[0]
            sub = target.target
            # Only handle simple string key subscripts: y["key"]
            if isinstance(sub.slice, cst.Index) and isinstance(sub.slice.value, cst.SimpleString):
                key_str = sub.slice.value.value.strip("'\"")
                # Build new variable name y_key (or just key if value is Name y)
                base_name = None
                if isinstance(sub.value, cst.Name):
                    base_name = sub.value.value
                if base_name:
                    new_var_name = f"{base_name}_{key_str}"
                    # Replace assignment target with new variable
                    new_target = cst.AssignTarget(target=cst.Name(new_var_name))
                    self._record_transformation(
                        original_node, f"{base_name}['{key_str}']", new_var_name
                    )
                    self.transformation_count += 1

                    # Also if RHS is a Name and tainted, propagate taint tracking set
                    if isinstance(updated_node.value, cst.Name):
                        source_var = updated_node.value.value
                        if source_var in self.call_llm_vars:
                            self._mark_var_as_tainted(new_var_name)

                    # Mark base dictionary variable as tainted too
                    if source_var in self.call_llm_vars:
                        self._mark_var_as_tainted(base_name)
                    if source_var in self.sanitized_vars:
                        self.sanitized_vars.add(base_name)

                    updated_node = updated_node.with_changes(targets=[new_target])

        # If RHS is a Call that contains tainted args, mark LHS tainted (pass-through wrappers)
        elif isinstance(updated_node.value, cst.Call):
            if self._call_contains_tainted_vars(updated_node.value):
                for target in updated_node.targets:
                    if isinstance(target.target, cst.Name):
                        var_name = target.target.value
                        self._mark_var_as_tainted(var_name)

        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """
        Transform LLM API calls into simple call_llm() functions and handle database operations.

        Convert patterns like:
        - openai.chat.completions.create(...)
        - client.messages.create(...)
        - anthropic.messages.create(...)
        - cursor.execute(...) / cursor.fetchall() (database operations)

        To: call_llm(provider="openai", content=...)
        Or: preserve taint for database operations
        """

        # --- Disabled: special database handling (obscure functionality removed) ---
        # if self._is_database_operation(updated_node):
        #     return self._handle_database_operation(updated_node)
        # --------------------------------------------------------------------------

        # Get the function call chain
        call_chain = self._extract_call_chain(updated_node.func)

        # --- Special handling: LanguageModel.parse_standard_response --------------------
        # This helper extracts structured content from an LLM response. It should
        # propagate taint (TITO) but must NOT be considered an LLM sink. We convert it
        # into a lightweight stub `extract_llm_response(...)` that will later be
        # modelled as `TaintInTaintOut` inside the generated .pysa models.
        if (
            call_chain
            and call_chain.endswith(".parse_standard_response")
            and any(prefix in call_chain for prefix in ["LANGUAGE_MODEL", "LanguageModel"])
        ):
            self.transformation_count += 1
            self._record_transformation(original_node, call_chain, "extract_llm_response")

            # Preserve original argument list to avoid shifting line numbers or
            # breaking positional/keyword semantics.
            return cst.Call(func=cst.Name("extract_llm_response"), args=updated_node.args)
        # -----------------------------------------------------------------------------

        # JSON/TOML/YAML helpers that should be TITO
        passthrough_funcs = [
            "json.loads",
            "json.dumps",
            "tomli.loads",
            "tomli_w.dumps",
            "yaml.safe_load",
        ]

        if call_chain and any(call_chain.endswith(func) for func in passthrough_funcs):
            self.transformation_count += 1
            self._record_transformation(original_node, call_chain, "extract_llm_response")
            return cst.Call(func=cst.Name("extract_llm_response"), args=updated_node.args)

        if call_chain:
            # Check if this matches any LLM pattern
            provider = self._match_llm_pattern(call_chain)

            if provider:
                # Transform to call_llm function
                self.transformation_count += 1
                # Record the transformation
                self._record_transformation(original_node, call_chain, f"call_llm({provider})")
                # Track that this function contains LLM calls
                if self.current_function:
                    self.methods_with_llm_calls.add(self.current_function)
                return self._create_call_llm(updated_node, provider)

        # Also check for method calls that might be LLM-related
        if isinstance(updated_node.func, cst.Attribute):
            if self._is_llm_method_call(updated_node):
                self.transformation_count += 1
                # Record the transformation
                method_name = updated_node.func.attr.value
                self._record_transformation(
                    original_node, f"method.{method_name}", "call_llm(generic)"
                )
                # Track that this function contains LLM calls
                if self.current_function:
                    self.methods_with_llm_calls.add(self.current_function)
                return self._create_call_llm(updated_node, "generic")

        # Check for direct llm() function calls and ensure they're converted to call_llm()
        if isinstance(updated_node.func, cst.Name):
            if updated_node.func.value == "llm":
                self.transformation_count += 1
                # Record the transformation
                self._record_transformation(original_node, "llm()", "call_llm(generic)")
                # Track that this function contains LLM calls
                if self.current_function:
                    self.methods_with_llm_calls.add(self.current_function)
                # Convert llm() to call_llm()
                content_arg = (
                    updated_node.args[0].value
                    if updated_node.args
                    else cst.SimpleString('"default"')
                )
                return cst.Call(
                    func=cst.Name("call_llm"),
                    args=[cst.Arg(value=cst.SimpleString('"generic"')), cst.Arg(value=content_arg)],
                )

        # Custom wrapper: LanguageModel.invoke -> treat as LLM call
        if (
            call_chain
            and call_chain.endswith(".invoke")
            and any(prefix in call_chain for prefix in ["LANGUAGE_MODEL", "LanguageModel"])
        ):
            # Treat this wrapper as an LLM call (both source and sink)
            self.transformation_count += 1
            # Record the transformation
            self._record_transformation(original_node, call_chain, "call_llm(generic)")
            if self.current_function:
                self.methods_with_llm_calls.add(self.current_function)
            return self._create_call_llm(updated_node, "generic")

        # Custom wrapper: LanguageModel.load_tomli_str -> sanitize taint (returns a safe empty dict).
        if (
            call_chain
            and call_chain.endswith(".load_tomli_str")
            and any(prefix in call_chain for prefix in ["LANGUAGE_MODEL", "LanguageModel"])
        ):
            self.transformation_count += 1
            self._record_transformation(original_node, call_chain, "sanitize_tomli")
            # Mark that this assignment contains a sanitized call
            self.sanitized_calls_in_current_assign = True

            empty_dict = cst.Dict([])

            return empty_dict

        return updated_node

    def leave_Subscript(
        self, original_node: cst.Subscript, updated_node: cst.Subscript
    ) -> Union[cst.Subscript, cst.Name]:
        """
        Sanitize subscript access on sanitized variables to prevent false positive taint flows.

        Convert: sanitized_var[0] -> None
        """
        if isinstance(updated_node.value, cst.Name):
            var_name = updated_node.value.value
            if var_name in self.sanitized_vars:
                # Replace subscript access on sanitized variables with None
                self.transformation_count += 1
                self._record_transformation(original_node, f"{var_name}[...]", "None")
                return cst.Name("None")

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> Union[cst.Attribute, cst.Name]:
        """
        Transform member variable access and sanitize attribute access on sanitized variables.

        Convert: self.client -> client
        Also handle: self.openai -> openai_client for better clarity
        And sanitize: sanitized_var.attr -> None
        """
        # First check if this is attribute access on a sanitized variable
        if isinstance(updated_node.value, cst.Name):
            var_name = updated_node.value.value
            if var_name in self.sanitized_vars:
                # Replace attribute access on sanitized variables with None
                self.transformation_count += 1
                self._record_transformation(
                    original_node, f"{var_name}.{updated_node.attr.value}", "None"
                )
                return cst.Name("None")

        # Handle self.attribute patterns
        if isinstance(updated_node.value, cst.Name) and updated_node.value.value == "self":

            attr_name = updated_node.attr.value

            # Check if this is a tracked member variable
            if attr_name in self.member_variables:
                return cst.Name(attr_name)

            # Handle common LLM client attribute patterns
            llm_client_attrs = ["openai", "anthropic", "client", "llm_client", "ai_client"]
            if any(attr_name.lower().startswith(pattern) for pattern in llm_client_attrs):
                # Convert to module-level variable name
                client_name = (
                    f"{attr_name}_client" if not attr_name.endswith("client") else attr_name
                )
                self.member_variables[attr_name] = True
                return cst.Name(client_name)

        return updated_node

    def _extract_call_chain(self, func_node: cst.BaseExpression) -> Optional[str]:
        """Extract the full call chain from a function call"""
        parts = []
        current = func_node

        while isinstance(current, cst.Attribute):
            parts.append(current.attr.value)
            current = current.value

        if isinstance(current, cst.Name):
            parts.append(current.value)
            parts.reverse()
            return ".".join(parts)

        return None

    def _match_llm_pattern(self, call_chain: str) -> Optional[str]:
        """Check if call chain matches any LLM pattern and return provider"""
        for provider, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(call_chain):
                    return provider
        return None

    def _create_call_llm(self, original_call: cst.Call, provider: str) -> cst.Call:
        """Return a new Call node that replaces the full attribute chain with
        `call_llm` but **preserves all original parentheses, commas, whitespace
        and comments** so that the vertical footprint (line numbers) stays
        identical to the original code.
        """

        # Build the new first argument: "provider"
        provider_arg = cst.Arg(value=cst.SimpleString(f'"{provider}"'))

        # Clone original args so we don't mutate the CST tuple
        original_args = list(original_call.args)

        # Try to select a taint-carrying expression to pass explicitly as the second
        # positional argument. We *also* keep the original argument in place to
        # preserve vertical footprint, so line numbers stay intact.

        def _extract_taint_expr(node: cst.CSTNode) -> Optional[cst.BaseExpression]:
            """Recursively find the first Name/Subscript/Attribute inside *node* that
            could carry user data (e.g. `x` inside messages=[{"content": x}])."""
            if isinstance(node, cst.Name):
                return node
            for field in node.children:
                if isinstance(field, cst.CSTNode):
                    found = _extract_taint_expr(field)
                    if found is not None:
                        return found
            return None

        content_expr: Optional[cst.BaseExpression] = None

        # 1) Prefer keywords like input=..., messages=..., prompt=...
        content_keywords = {"input", "messages", "content", "prompt", "text"}
        for arg in original_args:
            if arg.keyword and arg.keyword.value in content_keywords:
                content_expr = _extract_taint_expr(arg.value)
                if content_expr is None:
                    # fallback: use the full value
                    content_expr = arg.value
                break

        # 2) Else, take the last positional argument (common in some APIs)
        if content_expr is None:
            for arg in reversed(original_args):
                if arg.keyword is None:
                    content_expr = arg.value
                    break

        # If we could not detect a relevant content expression, don't transform –
        # returning the original call avoids injecting placeholders that could
        # break flow accuracy.
        if content_expr is None:
            return original_call

        content_arg = cst.Arg(value=content_expr)

        # Assemble new argument list: provider, explicit content, followed by *all* original args
        new_args = [provider_arg, content_arg] + original_args

        new_call = original_call.with_changes(
            func=cst.Name("call_llm"),
            args=new_args,
        )

        return new_call

    def _is_llm_related_assignment(self, value_node: cst.BaseExpression) -> bool:
        """Check if assignment value is LLM-related"""
        if isinstance(value_node, cst.Call):
            call_chain = self._extract_call_chain(value_node.func)
            if call_chain:
                # Check for common LLM client patterns
                llm_keywords = [
                    "client",
                    "openai",
                    "anthropic",
                    "llm",
                    "ai",
                    "gpt",
                    "claude",
                    "chat",
                    "completion",
                ]
                return any(keyword.lower() in call_chain.lower() for keyword in llm_keywords)
        return False

    def _is_llm_method_call(self, call_node: cst.Call) -> bool:
        """Check if this is an LLM-related method call that should be transformed"""
        if isinstance(call_node.func, cst.Attribute):
            method_name = call_node.func.attr.value

            # Database operations that can transfer taint
            database_methods = ["execute", "fetchall", "fetchone", "fetchmany"]

            # LLM processing methods
            llm_method_patterns = [
                "process_request",
                "make_call",
                "create",
                "query",
                "call",
                "process",
                "run",
                "invoke",
                "request",
            ]

            # Check if this is a database operation that could carry taint
            if method_name in database_methods:
                # Database operations should preserve taint but not be converted to call_llm
                return False

            # Check if method name suggests LLM processing
            if any(pattern in method_name.lower() for pattern in llm_method_patterns):
                # Check if any arguments contain LLM-related content
                for arg in call_node.args:
                    if self._arg_contains_llm_content(arg):
                        return True
        return False

    def _arg_contains_llm_content(self, arg: cst.Arg) -> bool:
        """Check if argument contains LLM-related content or variables"""
        # Check for variables that store call_llm results
        if isinstance(arg.value, cst.Name):
            var_name = arg.value.value
            # Exclude sanitized variables - they should not be considered LLM content
            if var_name in self.sanitized_vars:
                return False
            if var_name in self.call_llm_vars:
                return True

        # Check for LLMRequest objects or similar
        elif isinstance(arg.value, cst.Call):
            if isinstance(arg.value.func, cst.Name):
                if (
                    "llm" in arg.value.func.value.lower()
                    or "request" in arg.value.func.value.lower()
                ):
                    return True

        return False

    def _is_database_fetch_operation(self, call_node: cst.Call) -> bool:
        """Check if this is specifically a database fetch operation"""
        if isinstance(call_node.func, cst.Attribute):
            method_name = call_node.func.attr.value
            fetch_methods = ["fetchall", "fetchone", "fetchmany"]
            return method_name in fetch_methods
        return False

    def _is_sanitized_value(self, value_node: cst.BaseExpression) -> bool:
        """Check if the value is a sanitized constant (None, empty tuple, empty dict)"""
        # Single None value (from generic parsing sanitization)
        if isinstance(value_node, cst.Name) and value_node.value == "None":
            return True
        # Tuple of None values (from parse_standard_response sanitization)
        elif isinstance(value_node, cst.Tuple):
            return all(
                isinstance(element, cst.Element)
                and isinstance(element.value, cst.Name)
                and element.value.value == "None"
                for element in value_node.elements
            )
        # Empty dict (from load_tomli_str sanitization)
        elif isinstance(value_node, cst.Dict):
            return not value_node.elements
        return False

    def _is_sanitized_subscript(self, subscript_node: cst.Subscript) -> bool:
        """Check if this is a sanitized subscript accessing a sanitized variable"""
        if isinstance(subscript_node.value, cst.Name):
            return subscript_node.value.value in self.sanitized_vars
        return False

    def _is_sanitized_attribute(self, attribute_node: cst.Attribute) -> bool:
        """Check if this is a sanitized attribute accessing a sanitized variable"""
        if isinstance(attribute_node.value, cst.Name):
            return attribute_node.value.value in self.sanitized_vars
        return False

    def _mark_assignment_targets_as_sanitized(self, target: cst.BaseAssignTargetExpression) -> None:
        """Recursively mark assignment targets as sanitized to handle tuple unpacking"""
        if isinstance(target, cst.Name):
            # Single variable assignment: var = sanitized_call()
            self.sanitized_vars.add(target.value)
        elif isinstance(target, cst.Tuple):
            # Tuple unpacking: a, b, c = sanitized_call()
            for element in target.elements:
                if isinstance(element, cst.Element):
                    self._mark_assignment_targets_as_sanitized(element.value)
        elif isinstance(target, cst.List):
            # List unpacking: [a, b, c] = sanitized_call()
            for element in target.elements:
                if isinstance(element, cst.Element):
                    self._mark_assignment_targets_as_sanitized(element.value)
        elif isinstance(target, cst.Subscript):
            # Subscript assignment: obj[key] = sanitized_call()
            # Mark the base object as potentially containing sanitized data
            if isinstance(target.value, cst.Name):
                self.sanitized_vars.add(target.value.value)
        elif isinstance(target, cst.Attribute):
            # Attribute assignment: obj.attr = sanitized_call()
            # Mark the base object as potentially containing sanitized data
            if isinstance(target.value, cst.Name):
                self.sanitized_vars.add(target.value.value)

    def _expr_contains_tainted_var(self, expr: cst.CSTNode) -> bool:
        """Return True if *expr* (recursively) references a variable in self.call_llm_vars
        that is not sanitised. This is used to detect simple pass-through wrappers
        such as `foo(bar)` where *bar* already holds data returned from a previous
        LLM call and *foo()* just forwards it somewhere else.
        """
        # Direct name
        if isinstance(expr, cst.Name):
            name = expr.value
            return (name in self.call_llm_vars) and (name not in self.sanitized_vars)

        # Attribute or subscript – check the base object
        if isinstance(expr, (cst.Attribute, cst.Subscript)):
            base = expr.value if isinstance(expr, (cst.Attribute, cst.Subscript)) else None
            if isinstance(base, cst.Name):
                name = base.value
                if (name in self.call_llm_vars) and (name not in self.sanitized_vars):
                    return True

        # Recurse into children (covers tuples, lists, dicts, nested calls, etc.)
        for child in expr.children:
            if isinstance(child, cst.CSTNode) and self._expr_contains_tainted_var(child):
                return True

        return False

    def _call_contains_tainted_vars(self, call_node: cst.Call) -> bool:
        """Return True if any argument of *call_node* contains a value originating
        from a previous call_llm result (i.e. a variable in self.call_llm_vars) and
        that variable has not been sanitised. This allows us to propagate the
        taint through simple wrapper functions that immediately forward the value.
        """
        for arg in call_node.args:
            if self._expr_contains_tainted_var(arg.value):
                return True
        return False

    def _mark_var_as_tainted(self, var_name: str) -> None:
        """Record *var_name* as holding LLM-tainted data and ensure it is *not*
        considered sanitised any longer (the latter can happen when a variable
        that previously stored a placeholder/empty value is later overwritten
        with a fresh LLM reply)."""
        self.call_llm_vars.add(var_name)
        # If the variable was previously flagged as sanitised, revoke that flag.
        self.sanitized_vars.discard(var_name)

    def transform(self, source_code: str) -> str:
        """
        Main transformation method.

        Args:
            source_code: Original Python source code

        Returns:
            Transformed Python source code
        """
        try:
            # Parse the source code and wrap with metadata so we can query positions
            module = cst.parse_module(source_code)
            wrapper = cst.MetadataWrapper(module)
            transformed_tree = wrapper.visit(self)

            # Check if we have call_llm calls and add function definition if needed
            transformed_code = transformed_tree.code
            if "call_llm(" in transformed_code and "def call_llm(" not in transformed_code:
                # Define stub function content
                call_llm_definition = '''
def call_llm(provider, content):
    """Stub function for LLM API calls - used for taint analysis."""
    # This is a placeholder function for Pyre taint analysis
    # In real code, this would make actual LLM API calls
    return content
'''

                # Append definition to end to avoid mutating line numbers of existing code
                if not transformed_code.endswith("\n"):
                    transformed_code += "\n"
                transformed_code = transformed_code + "\n" + call_llm_definition.strip("\n") + "\n"

            if self.transformation_count > 0:
                print(f"🔧 Applied {self.transformation_count} LLM call transformations")
                print(f"📊 Tracked {len(self.call_llm_vars)} variables with call_llm results")
                if self.sanitized_vars:
                    print(
                        f"🧼 Sanitized {len(self.sanitized_vars)} variables to eliminate false positives"
                    )

            # Inject stub for extract_llm_response if needed (TITO helper)
            if (
                "extract_llm_response(" in transformed_code
                and "def extract_llm_response(" not in transformed_code
            ):
                extract_def = '''
def extract_llm_response(data):
    """Stub that simply returns *data* while preserving taint information.\n    This models a pure extraction helper and is treated as TITO in Pyre models."""
    return data
'''
                if not transformed_code.endswith("\n"):
                    transformed_code += "\n"
                transformed_code = transformed_code + "\n" + extract_def.strip("\n") + "\n"

            return transformed_code

        except Exception as e:
            print(f"⚠️  AST transformation error: {e}")
            # Return original code if transformation fails
            return source_code


# Helper functions for standalone usage
def transform_code_for_pyre(
    source_code: str, llm_patterns: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    Convenience function to transform code for Pyre analysis.

    Args:
        source_code: Original Python source code
        llm_patterns: Optional custom LLM patterns

    Returns:
        Transformed Python source code
    """
    if llm_patterns is None:
        # Default patterns
        llm_patterns = {
            "openai": [
                "openai.chat.completions.create",
                "openai.Completion.create",
                "openai.completions.create",
                "openai.responses.create",
                "client.chat.completions.create",
                "client.completions.create",
                "client.responses.create",
            ],
            "anthropic": ["anthropic.messages.create", "client.messages.create"],
        }

    transformer = LLMCallTransformer(llm_patterns)
    return transformer.transform(source_code)


def analyze_transformations(source_code: str) -> Dict[str, Any]:
    """
    Analyze what transformations would be applied to source code.

    Returns:
        Dictionary with transformation details
    """

    class AnalysisTransformer(LLMCallTransformer):
        def __init__(self, llm_patterns):
            super().__init__(llm_patterns)
            self.transformations = []

        def leave_Call(self, original_node, updated_node):
            result = super().leave_Call(original_node, updated_node)
            if result != updated_node:
                self.transformations.append(
                    {
                        "type": "LLM_CALL",
                        "original": self._extract_call_chain(original_node.func),
                        "transformed": "call_llm",
                    }
                )
            return result

        def leave_Assign(self, original_node, updated_node):
            result = super().leave_Assign(original_node, updated_node)
            if result != updated_node:
                self.transformations.append(
                    {
                        "type": "MEMBER_VARIABLE",
                        "details": "Converted self.variable to module-level variable",
                    }
                )
            return result

    # Default patterns for analysis
    patterns = {
        "openai": [
            "openai.chat.completions.create",
            "client.chat.completions.create",
            "openai.responses.create",
            "client.responses.create",
        ],
        "anthropic": ["anthropic.messages.create", "client.messages.create"],
    }

    analyzer = AnalysisTransformer(patterns)

    try:
        tree = cst.parse_module(source_code)
        tree.visit(analyzer)

        return {
            "transformations": analyzer.transformations,
            "count": len(analyzer.transformations),
            "success": True,
        }
    except Exception as e:
        return {"transformations": [], "count": 0, "success": False, "error": str(e)}


if __name__ == "__main__":
    # Example usage for testing
    test_code = """
import openai
import anthropic

class LLMHandler:
    def __init__(self):
        self.openai_client = openai.OpenAI()
        self.anthropic_client = anthropic.Anthropic()
    
    def process(self, user_input):
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": user_input}]
        )
        
        result = self.anthropic_client.messages.create(
            model="claude-3",
            messages=[{"role": "user", "content": response}]
        )
        
        return result

# Direct calls
x = openai.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": "hello"}])
y = anthropic.messages.create(model="claude-3", messages=[{"role": "user", "content": x}])
"""

    print("Original code:")
    print(test_code)
    print("\n" + "=" * 50 + "\n")

    transformed = transform_code_for_pyre(test_code)
    print("Transformed code:")
    print(transformed)

    print("\n" + "=" * 50 + "\n")

    analysis = analyze_transformations(test_code)
    print("Analysis:")
    print(f"Transformations applied: {analysis['count']}")
    for t in analysis["transformations"]:
        print(
            f"- {t['type']}: {t.get('original', '')} -> {t.get('transformed', t.get('details', ''))}"
        )
