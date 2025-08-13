#!/usr/bin/env python3
"""
AST Transformer for LLM Call Simplification

Transforms complex LLM API patterns into simple function calls that Pyre can
analyze effectively for taint flow detection.
"""

import libcst as cst
from typing import Dict, List, Any, Union, Optional
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
    """

    # Request position metadata so we can keep the replacement's vertical size
    # identical to the original call (avoids shifting later line numbers).
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, llm_patterns: Dict[str, List[str]]):
        super().__init__()
        self.llm_patterns = llm_patterns
        self.member_variables = {}  # Track member variables for simplification
        self.current_class = None
        self.current_function = None
        self.call_llm_vars = set()  # Track variables that store call_llm results
        self.transformation_count = 0
        self.methods_with_llm_calls = set()  # Track methods that contain LLM calls
        self.db_tainted_vars = set()  # Track variables that contain database results

        # Compile pattern regexes for efficiency
        self.compiled_patterns = {}
        for provider, patterns in llm_patterns.items():
            self.compiled_patterns[provider] = [
                re.compile(pattern.replace(".", r"\.").replace("*", ".*")) for pattern in patterns
            ]

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

        Also track variables that store call_llm results and database results for better flow detection.
        """
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

        # Track variables that store call_llm results or database results
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
                        self.call_llm_vars.add(var_name)

                    # Check if it's a database fetch operation
                    elif self._is_database_fetch_operation(updated_node.value):
                        # Mark as tainted regardless - database operations should preserve taint
                        self.call_llm_vars.add(var_name)
                        self.db_tainted_vars.add(var_name)

                # Check if the value is a variable that contains call_llm result or database result
                elif isinstance(updated_node.value, cst.Name):
                    source_var = updated_node.value.value
                    if source_var in self.call_llm_vars:
                        self.call_llm_vars.add(var_name)

                # Check for database access patterns like cursor.fetchone()[0]
                elif isinstance(updated_node.value, cst.Subscript):
                    if self._is_database_access_pattern(updated_node.value):
                        # Mark as tainted if the base operation is a database fetch
                        self.call_llm_vars.add(var_name)
                        self.db_tainted_vars.add(var_name)

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

        # Handle database operations first
        if self._is_database_operation(updated_node):
            return self._handle_database_operation(updated_node)

        # Get the function call chain
        call_chain = self._extract_call_chain(updated_node.func)

        if call_chain:
            # Check if this matches any LLM pattern
            provider = self._match_llm_pattern(call_chain)

            if provider:
                # Transform to call_llm function
                self.transformation_count += 1
                # Track that this function contains LLM calls
                if self.current_function:
                    self.methods_with_llm_calls.add(self.current_function)
                return self._create_call_llm(updated_node, provider)

        # Also check for method calls that might be LLM-related
        if isinstance(updated_node.func, cst.Attribute):
            if self._is_llm_method_call(updated_node):
                self.transformation_count += 1
                # Track that this function contains LLM calls
                if self.current_function:
                    self.methods_with_llm_calls.add(self.current_function)
                return self._create_call_llm(updated_node, "generic")

        # Check for direct llm() function calls and ensure they're converted to call_llm()
        if isinstance(updated_node.func, cst.Name):
            if updated_node.func.value == "llm":
                self.transformation_count += 1
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

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> Union[cst.Attribute, cst.Name]:
        """
        Transform member variable access.

        Convert: self.client -> client
        Also handle: self.openai -> openai_client for better clarity
        """
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
        # Check for LLMRequest objects or similar
        if isinstance(arg.value, cst.Call):
            if isinstance(arg.value.func, cst.Name):
                if (
                    "llm" in arg.value.func.value.lower()
                    or "request" in arg.value.func.value.lower()
                ):
                    return True

        # Check for variables that store call_llm results
        elif isinstance(arg.value, cst.Name):
            if arg.value.value in self.call_llm_vars:
                return True

        return False

    def _is_database_operation(self, call_node: cst.Call) -> bool:
        """Check if this is a database operation (execute, fetchall, fetchone, etc.)"""
        if isinstance(call_node.func, cst.Attribute):
            method_name = call_node.func.attr.value
            database_methods = [
                "execute",
                "executemany",
                "executescript",
                "fetchall",
                "fetchone",
                "fetchmany",
                "commit",
                "rollback",
            ]
            return method_name in database_methods
        return False

    def _is_database_fetch_operation(self, call_node: cst.Call) -> bool:
        """Check if this is specifically a database fetch operation"""
        if isinstance(call_node.func, cst.Attribute):
            method_name = call_node.func.attr.value
            fetch_methods = ["fetchall", "fetchone", "fetchmany"]
            return method_name in fetch_methods
        return False

    def _handle_database_operation(self, call_node: cst.Call) -> cst.Call:
        """
        Handle database operations to preserve taint flows.
        Convert database operations to preserve taint through transformations.
        """
        if isinstance(call_node.func, cst.Attribute):
            method_name = call_node.func.attr.value

            # For fetch operations, completely replace with call_llm
            if method_name in ["fetchall", "fetchone", "fetchmany"]:
                # Replace with call_llm - this creates a clean taint source
                self.transformation_count += 1
                print(f"🔧 Converting database {method_name}() to call_llm for taint preservation")
                return cst.Call(
                    func=cst.Name("call_llm"),
                    args=[
                        cst.Arg(value=cst.SimpleString('"database"')),
                        cst.Arg(value=cst.SimpleString(f'"db_{method_name}_result"')),
                    ],
                )

            # For execute operations, preserve the operation but track taint
            elif method_name in ["execute", "executemany"]:
                # Check if any arguments are tainted
                if self._call_contains_tainted_vars(call_node):
                    # Mark this as a tainted database operation
                    # But return the original call since execute doesn't return data directly
                    pass

        return call_node

    def _call_contains_tainted_vars(self, call_node: cst.Call) -> bool:
        """Check if any arguments in the call contain tainted variables"""
        for arg in call_node.args:
            if self._arg_contains_tainted_vars(arg):
                return True
        return False

    def _arg_contains_tainted_vars(self, arg: cst.Arg) -> bool:
        """Check if an argument contains tainted variables"""
        # Check for direct variable references
        if isinstance(arg.value, cst.Name):
            return arg.value.value in self.call_llm_vars

        # Check for attribute access (like rows.something)
        elif isinstance(arg.value, cst.Attribute):
            base_var = self._extract_base_variable(arg.value)
            return base_var and base_var in self.call_llm_vars

        # Check for subscript access (like rows[0])
        elif isinstance(arg.value, cst.Subscript):
            base_var = self._extract_base_variable(arg.value)
            return base_var and base_var in self.call_llm_vars

        return False

    def _is_database_access_pattern(self, subscript_node: cst.Subscript) -> bool:
        """Check if this is a database access pattern like cursor.fetchone()[0]"""
        if isinstance(subscript_node.value, cst.Call):
            if isinstance(subscript_node.value.func, cst.Attribute):
                method_name = subscript_node.value.func.attr.value
                return method_name in ["fetchone", "fetchall", "fetchmany"]
        return False

    def _extract_base_variable(self, node: cst.BaseExpression) -> Optional[str]:
        """Extract the base variable name from complex expressions"""
        if isinstance(node, cst.Name):
            return node.value
        elif isinstance(node, cst.Attribute):
            return self._extract_base_variable(node.value)
        elif isinstance(node, cst.Subscript):
            return self._extract_base_variable(node.value)
        elif isinstance(node, cst.Call):
            if isinstance(node.func, cst.Attribute):
                return self._extract_base_variable(node.func.value)
        return None

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
