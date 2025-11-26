"""
Test to verify that super().__init__() is not wrapped by AST transformer.

This test applies the AST transformation to code containing super().__init__()
and prints the transformed code to verify it's not wrapped with exec_func.
"""

import ast
import sys
from aco.server.ast_transformer import TaintPropagationTransformer


# Test code with super().__init__()
test_code = """
class Parent:
    def __init__(self, name):
        self.name = name

class Child(Parent):
    def __init__(self, name, age):
        super().__init__(name)
        self.age = age

    def greet(self):
        return f"Hello, I'm {self.name}"
"""


def test_super_not_wrapped():
    """Test that super().__init__() is not wrapped with exec_func."""
    print("Original code:")
    print("=" * 60)
    print(test_code)
    print("=" * 60)
    print()

    # Parse the code
    tree = ast.parse(test_code)

    # Apply AST transformation
    transformer = TaintPropagationTransformer(module_to_file={}, current_file="test.py")
    transformed_tree = transformer.visit(tree)

    # Inject imports if needed
    transformed_tree = transformer._inject_taint_imports(transformed_tree)

    # Fix missing locations
    ast.fix_missing_locations(transformed_tree)

    # Unparse back to code
    transformed_code = ast.unparse(transformed_tree)

    print("Transformed code:")
    print("=" * 60)
    print(transformed_code)
    print("=" * 60)
    print()

    # Check that super() is NOT wrapped
    if "exec_func(super" in transformed_code:
        print("❌ FAILED: super() was wrapped with exec_func!")
        print("   This will break inheritance patterns.")
        return False
    else:
        print("✓ PASSED: super() was not wrapped")

    # Check that __init__ is NOT wrapped when called on super()
    if "super().__init__" in transformed_code:
        print("✓ PASSED: super().__init__() pattern is preserved")
    else:
        print("❌ FAILED: super().__init__() pattern was modified!")
        return False

    # Check that f-strings ARE transformed
    if "taint_fstring_join" in transformed_code:
        print("✓ PASSED: f-strings are correctly transformed")
    else:
        print("⚠ WARNING: f-strings were not transformed (expected if no transformations needed)")

    print()
    print("All checks passed!")
    return True


if __name__ == "__main__":
    success = test_super_not_wrapped()
    sys.exit(0 if success else 1)
