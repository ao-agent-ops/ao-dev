#!/usr/bin/env python3
"""
Comprehensive test for untaint_if_needed function to identify crashes and issues.
Tests various types including bound methods, functions, objects, enums, and edge cases.
"""

import sys
import os
import traceback
from enum import Enum, StrEnum, IntEnum
from dataclasses import dataclass
from typing import Any, Dict, List
import io
import re

from aco.runner.taint_wrappers import untaint_if_needed, TaintObject, TaintStr, TaintInt


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


class Status(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class Person:
    name: str
    age: int


class SimpleClass:
    def __init__(self, value):
        self.value = value

    def method(self):
        return f"method called with {self.value}"

    def bound_method_test(self, arg):
        return f"bound method with {arg}"


class ClassWithSlots:
    __slots__ = ["x", "y"]

    def __init__(self, x, y):
        self.x = x
        self.y = y


def standalone_function():
    return "standalone function"


def function_with_args(a, b):
    return a + b


class TestUntaintIfNeeded:
    """Test suite for untaint_if_needed function"""

    def __init__(self):
        self.test_results = []
        self.failed_tests = []

    def run_test(self, test_name: str, test_func):
        """Run a single test and record results"""
        try:
            print(f"\n🧪 Running {test_name}...")
            test_func()
            print(f"✅ {test_name} passed")
            self.test_results.append((test_name, "PASSED", None))
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            print(f"❌ {test_name} failed: {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
            self.test_results.append((test_name, "FAILED", error_msg))
            self.failed_tests.append((test_name, e, traceback.format_exc()))

    def test_primitives(self):
        """Test primitive types"""
        assert untaint_if_needed(42) == 42
        assert untaint_if_needed(3.14) == 3.14
        assert untaint_if_needed("hello") == "hello"
        assert untaint_if_needed(True) == True
        assert untaint_if_needed(None) == None

    def test_tainted_primitives(self):
        """Test tainted primitive types"""
        tainted_str = TaintStr("hello", ["test_origin"])
        result = untaint_if_needed(tainted_str)
        assert result == "hello"
        assert not hasattr(result, "_taint_origin")

        tainted_int = TaintInt(42, ["test_origin"])
        result = untaint_if_needed(tainted_int)
        assert result == 42
        assert not hasattr(result, "_taint_origin")

    def test_collections(self):
        """Test collection types"""
        # Lists
        result = untaint_if_needed([1, 2, 3])
        assert result == [1, 2, 3]

        # Tuples
        result = untaint_if_needed((1, 2, 3))
        assert result == (1, 2, 3)

        # Sets
        result = untaint_if_needed({1, 2, 3})
        assert result == {1, 2, 3}

        # Dicts
        result = untaint_if_needed({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_nested_collections(self):
        """Test nested collections"""
        nested = {"users": [{"name": "Alice", "scores": (90, 85, 88)}]}
        result = untaint_if_needed(nested)
        assert result == nested

    def test_enums(self):
        """Test enum types"""
        # Regular enum
        result = untaint_if_needed(Color.RED)
        assert result == Color.RED

        # StrEnum
        result = untaint_if_needed(Status.ACTIVE)
        assert result == Status.ACTIVE

        # IntEnum
        result = untaint_if_needed(Priority.HIGH)
        assert result == Priority.HIGH

    def test_functions(self):
        """Test function types"""
        # Standalone function
        result = untaint_if_needed(standalone_function)
        assert result == standalone_function

        # Function with args
        result = untaint_if_needed(function_with_args)
        assert result == function_with_args

        # Built-in function
        result = untaint_if_needed(len)
        assert result == len

        # Lambda
        lambda_func = lambda x: x * 2
        result = untaint_if_needed(lambda_func)
        assert result == lambda_func

    def test_functions_with_tainted_attributes(self):
        """Test functions with tainted attributes attached"""

        # Create a function with custom attributes
        def func_with_attrs():
            return "function result"

        # Add regular attributes
        func_with_attrs.custom_attr = "clean value"
        func_with_attrs.number = 42

        # Add tainted attributes
        func_with_attrs.tainted_str = TaintStr("tainted data", ["test_origin"])
        func_with_attrs.tainted_int = TaintInt(123, ["test_origin"])
        func_with_attrs.nested_taint = {
            "clean": "value",
            "tainted": TaintStr("nested taint", ["nested_origin"]),
        }

        # Test untainting
        result = untaint_if_needed(func_with_attrs)

        # Function should still be callable
        assert callable(result)
        assert result() == "function result"

        # Clean attributes should be preserved
        assert result.custom_attr == "clean value"
        assert result.number == 42

        # Tainted attributes should be untainted
        assert result.tainted_str == "tainted data"
        assert not hasattr(result.tainted_str, "_taint_origin")
        assert result.tainted_int == 123
        assert not hasattr(result.tainted_int, "_taint_origin")

        # Nested taint should be handled
        assert result.nested_taint["clean"] == "value"
        assert result.nested_taint["tainted"] == "nested taint"
        assert not hasattr(result.nested_taint["tainted"], "_taint_origin")

    def test_methods_with_tainted_attributes(self):
        """Test bound methods with tainted attributes in __dict__"""
        obj = SimpleClass("test")
        bound_method = obj.method

        # Add tainted attributes directly to the __dict__
        bound_method.__dict__["metadata"] = TaintStr("method metadata", ["method_origin"])
        bound_method.__dict__["config"] = {
            "setting": TaintInt(456, ["config_origin"]),
            "flag": True,
        }

        result = untaint_if_needed(bound_method)

        # Method should still work
        assert callable(result)
        assert result() == "method called with test"

        # Tainted attributes should be cleaned
        assert result.__dict__["metadata"] == "method metadata"
        assert not hasattr(result.__dict__["metadata"], "_taint_origin")
        assert result.__dict__["config"]["setting"] == 456
        assert not hasattr(result.__dict__["config"]["setting"], "_taint_origin")
        assert result.__dict__["config"]["flag"] == True

    def test_lambda_with_tainted_attributes(self):
        """Test lambda functions with tainted attributes"""
        lambda_func = lambda x: x * 3

        # Add tainted attributes to lambda
        lambda_func.multiplier = TaintInt(3, ["lambda_origin"])
        lambda_func.description = TaintStr("triple function", ["desc_origin"])

        result = untaint_if_needed(lambda_func)

        # Lambda should still work
        assert result(5) == 15

        # Attributes should be untainted
        assert result.multiplier == 3
        assert not hasattr(result.multiplier, "_taint_origin")
        assert result.description == "triple function"
        assert not hasattr(result.description, "_taint_origin")

    def test_function_circular_reference_with_taint(self):
        """Test function with circular references and taint"""

        def circular_func():
            return "circular"

        # Create circular reference with taint
        circular_func.self_ref = circular_func
        circular_func.tainted_data = TaintStr("circular taint", ["circular_origin"])

        result = untaint_if_needed(circular_func)

        # Should handle circular reference without infinite recursion
        assert result() == "circular"
        assert result.self_ref is result  # Circular reference preserved
        assert result.tainted_data == "circular taint"
        assert not hasattr(result.tainted_data, "_taint_origin")

    def test_builtin_function_edge_cases(self):
        """Test built-in functions that might have special handling"""
        # Built-ins typically can't have attributes added, but test anyway
        result = untaint_if_needed(len)
        assert result is len

        result = untaint_if_needed(print)
        assert result is print

        # Test method descriptors
        result = untaint_if_needed(str.upper)
        assert result is str.upper

        result = untaint_if_needed(list.append)
        assert result is list.append

    def test_bound_methods(self):
        """Test bound methods - this is where crashes occur"""
        obj = SimpleClass("test")

        # This should NOT crash
        bound_method = obj.method
        result = untaint_if_needed(bound_method)
        # Should return the method unchanged since it's a callable
        assert result == bound_method

        # Test calling the untainted method
        assert result() == "method called with test"

    def test_bound_methods_with_args(self):
        """Test bound methods with arguments"""
        obj = SimpleClass("test")
        bound_method = obj.bound_method_test
        result = untaint_if_needed(bound_method)
        assert result == bound_method

        # Test calling with args
        assert result("arg") == "bound method with arg"

    def test_simple_objects(self):
        """Test simple custom objects"""
        obj = SimpleClass("test_value")
        result = untaint_if_needed(obj)

        # Should create new object with same attributes
        assert result.value == "test_value"

    def test_dataclass_objects(self):
        """Test dataclass objects"""
        person = Person("Alice", 30)
        result = untaint_if_needed(person)

        assert result.name == "Alice"
        assert result.age == 30

    def test_objects_with_slots(self):
        """Test objects with __slots__"""
        obj = ClassWithSlots(10, 20)
        result = untaint_if_needed(obj)

        assert result.x == 10
        assert result.y == 20

    def test_taint_object_wrapper(self):
        """Test TaintObject wrapper"""
        original = SimpleClass("wrapped")
        tainted = TaintObject(original, ["test_origin"])

        result = untaint_if_needed(tainted)
        # Should extract the wrapped object
        assert result is original

    def test_circular_references(self):
        """Test circular references"""
        obj1 = SimpleClass("obj1")
        obj2 = SimpleClass("obj2")
        obj1.ref = obj2
        obj2.ref = obj1

        # Should not crash due to circular reference
        result = untaint_if_needed(obj1)
        assert result.value == "obj1"
        assert result.ref.value == "obj2"
        assert result.ref.ref.value == "obj1"

    def test_builtin_objects(self):
        """Test various built-in objects"""
        # Regex match object
        match = re.search(r"(\d+)", "hello 123 world")
        result = untaint_if_needed(match)
        assert result == match

        # File object
        with io.StringIO("test") as f:
            result = untaint_if_needed(f)
            assert result == f

    def test_complex_nested_structure(self):
        """Test complex nested structure"""
        obj = SimpleClass("root")
        obj.data = {
            "numbers": [1, 2, 3],
            "nested": {
                "person": Person("Bob", 25),
                "status": Status.ACTIVE,
                "callback": lambda x: x * 2,
            },
        }

        result = untaint_if_needed(obj)
        assert result.value == "root"
        assert result.data["numbers"] == [1, 2, 3]
        assert result.data["nested"]["person"].name == "Bob"
        assert result.data["nested"]["status"] == Status.ACTIVE

    def test_edge_cases(self):
        """Test edge cases that might cause crashes"""
        # Empty collections
        assert untaint_if_needed([]) == []
        assert untaint_if_needed({}) == {}
        assert untaint_if_needed(set()) == set()

        # Objects with unusual attributes
        obj = SimpleClass("test")
        obj._private = "private"
        obj.__dunder__ = "dunder"

        result = untaint_if_needed(obj)
        assert result.value == "test"
        assert result._private == "private"
        assert result.__dunder__ == "dunder"

    def test_objects_without_init(self):
        """Test objects that might not be constructible normally"""
        # Create object without calling __init__
        obj = SimpleClass.__new__(SimpleClass)
        obj.special_attr = "no init called"

        result = untaint_if_needed(obj)
        assert result.special_attr == "no init called"

    def test_class_objects(self):
        """Test class objects themselves"""
        result = untaint_if_needed(SimpleClass)
        assert result == SimpleClass

        result = untaint_if_needed(Color)
        assert result == Color

    def test_module_objects(self):
        """Test module objects"""
        import math

        result = untaint_if_needed(math)
        assert result == math

        result = untaint_if_needed(sys)
        assert result == sys

    def test_generator_objects(self):
        """Test generator objects"""

        def gen():
            yield 1
            yield 2
            yield 3

        generator = gen()
        result = untaint_if_needed(generator)
        assert result == generator

        # Should still work
        assert next(result) == 1

    def test_coroutine_objects(self):
        """Test coroutine objects"""
        import asyncio

        async def async_func():
            return "async result"

        coro = async_func()
        result = untaint_if_needed(coro)
        assert result == coro

        # Clean up
        coro.close()
        result.close()

    def test_method_descriptors(self):
        """Test method descriptors and unbound methods"""
        # Unbound method
        result = untaint_if_needed(SimpleClass.method)
        assert result == SimpleClass.method

        # Property objects
        class WithProperty:
            @property
            def prop(self):
                return "property value"

        result = untaint_if_needed(WithProperty.prop)
        assert result == WithProperty.prop

    def test_exception_objects(self):
        """Test exception objects"""
        try:
            raise ValueError("test error")
        except ValueError as e:
            result = untaint_if_needed(e)
            assert str(result) == "test error"
            assert isinstance(result, ValueError)

    def test_weakref_objects(self):
        """Test weakref objects"""
        import weakref

        obj = SimpleClass("weakref test")
        weak_ref = weakref.ref(obj)

        result = untaint_if_needed(weak_ref)
        assert result == weak_ref
        assert result() == obj

    def test_threading_objects(self):
        """Test threading primitives - should never be modified"""
        import threading

        # Test various threading objects
        lock = threading.Lock()
        rlock = threading.RLock()
        condition = threading.Condition()
        semaphore = threading.Semaphore()
        event = threading.Event()

        # All should be returned unchanged
        assert untaint_if_needed(lock) is lock
        assert untaint_if_needed(rlock) is rlock
        assert untaint_if_needed(condition) is condition
        assert untaint_if_needed(semaphore) is semaphore
        assert untaint_if_needed(event) is event

        # Test that locks still work after "untainting"
        untainted_lock = untaint_if_needed(lock)
        with untainted_lock:
            pass  # Should not raise any errors

        # Test with lock in a data structure
        data_with_lock = {"lock": lock, "data": "some data"}
        result = untaint_if_needed(data_with_lock)
        assert result["lock"] is lock  # Lock should be unchanged
        assert result["data"] == "some data"

    def run_all_tests(self):
        """Run all tests and report results"""
        print("🚀 Starting comprehensive untaint_if_needed tests...\n")

        test_methods = [
            ("Primitives", self.test_primitives),
            ("Tainted Primitives", self.test_tainted_primitives),
            ("Collections", self.test_collections),
            ("Nested Collections", self.test_nested_collections),
            ("Enums", self.test_enums),
            ("Functions", self.test_functions),
            ("Functions with Tainted Attributes", self.test_functions_with_tainted_attributes),
            ("Bound Method Attribute Restrictions", self.test_methods_with_tainted_attributes),
            ("Lambda with Tainted Attributes", self.test_lambda_with_tainted_attributes),
            (
                "Function Circular Reference with Taint",
                self.test_function_circular_reference_with_taint,
            ),
            ("Builtin Function Edge Cases", self.test_builtin_function_edge_cases),
            ("Bound Methods", self.test_bound_methods),
            ("Bound Methods with Args", self.test_bound_methods_with_args),
            ("Simple Objects", self.test_simple_objects),
            ("Dataclass Objects", self.test_dataclass_objects),
            ("Objects with Slots", self.test_objects_with_slots),
            ("TaintObject Wrapper", self.test_taint_object_wrapper),
            ("Circular References", self.test_circular_references),
            ("Builtin Objects", self.test_builtin_objects),
            ("Complex Nested Structure", self.test_complex_nested_structure),
            ("Edge Cases", self.test_edge_cases),
            ("Objects without Init", self.test_objects_without_init),
            ("Class Objects", self.test_class_objects),
            ("Module Objects", self.test_module_objects),
            ("Generator Objects", self.test_generator_objects),
            ("Coroutine Objects", self.test_coroutine_objects),
            ("Method Descriptors", self.test_method_descriptors),
            ("Exception Objects", self.test_exception_objects),
            ("Weakref Objects", self.test_weakref_objects),
            ("Threading Objects", self.test_threading_objects),
        ]

        for test_name, test_method in test_methods:
            self.run_test(test_name, test_method)

        # Report summary
        print(f"\n📊 Test Summary:")
        print(f"Total tests: {len(self.test_results)}")
        passed = len([r for r in self.test_results if r[1] == "PASSED"])
        failed = len([r for r in self.test_results if r[1] == "FAILED"])
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if self.failed_tests:
            print(f"\n❌ Failed tests details:")
            for test_name, exception, traceback_str in self.failed_tests:
                print(f"\n• {test_name}:")
                print(f"  Error: {type(exception).__name__}: {exception}")
                # Print first few lines of traceback for context
                lines = traceback_str.strip().split("\n")
                for line in lines[-5:]:  # Last 5 lines usually most relevant
                    print(f"  {line}")

        return len(self.failed_tests) == 0


if __name__ == "__main__":
    tester = TestUntaintIfNeeded()
    success = tester.run_all_tests()

    if not success:
        print(f"\n🔍 Issues found in untaint_if_needed function!")
        print("The function needs fixes to handle these types properly.")
    else:
        print(f"\n✨ All tests passed! The function works correctly.")
