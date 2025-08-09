#!/usr/bin/env python3
"""
Test script to verify that the monkey patches work with optional dependencies.
This script simulates a user environment where not all API packages (openai, 
anthropic, google, ...) are installed. I don't want our install to overwrite 
the user's installation of the APIs because they change all the time.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_import_without_api_dependencies():
    """Test that modules can be imported without API dependencies."""
    print("Testing import without API dependencies...")
    
    # Remove API modules from sys.modules to simulate them not being installed
    modules_to_remove = [mod for mod in sys.modules if any(api in mod for api in ['openai', 'anthropic', 'google'])]
    original_modules = {}
    
    for mod in modules_to_remove:
        if mod in sys.modules:
            original_modules[mod] = sys.modules[mod]
            del sys.modules[mod]
    
    # Mock the imports to raise ImportError
    class MockImportError:
        def __getattr__(self, name):
            raise ImportError(f'No module named {name}')
    
    sys.modules['openai'] = MockImportError()
    sys.modules['anthropic'] = MockImportError()
    sys.modules['google'] = MockImportError()
    
    try:
        # Test importing monkey patches
        from runtime_tracing.monkey_patches import CUSTOM_PATCH_FUNCTIONS
        print(f"✓ Successfully imported monkey_patches with {len(CUSTOM_PATCH_FUNCTIONS)} patch functions")
        
        # Test calling patch functions
        class MockServerConn:
            def sendall(self, data):
                pass
        
        server_conn = MockServerConn()
        
        for patch_func in CUSTOM_PATCH_FUNCTIONS:
            try:
                patch_func(server_conn)
                print(f"✓ {patch_func.__name__} handled missing dependency gracefully")
            except Exception as e:
                print(f"✗ {patch_func.__name__} failed: {e}")
                return False
                
        print("✓ All tests passed! Users don't need all API packages installed.")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Restore original modules
        for mod, original in original_modules.items():
            sys.modules[mod] = original
        # Remove mock modules
        for mock_mod in ['openai', 'anthropic', 'google']:
            if mock_mod in sys.modules and isinstance(sys.modules[mock_mod], MockImportError):
                del sys.modules[mock_mod]

def test_import_with_api_dependencies():
    """Test that modules work correctly when API dependencies are available."""
    print("\nTesting import with API dependencies...")
    
    try:
        from runtime_tracing.monkey_patches import CUSTOM_PATCH_FUNCTIONS
        
        class MockServerConn:
            def sendall(self, data):
                pass
        
        server_conn = MockServerConn()
        
        for patch_func in CUSTOM_PATCH_FUNCTIONS:
            try:
                patch_func(server_conn)
                print(f"✓ {patch_func.__name__} succeeded")
            except Exception as e:
                print(f"✗ {patch_func.__name__} failed: {e}")
                return False
                
        print("✓ All tests passed with dependencies available!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_import_without_api_dependencies()
    success2 = test_import_with_api_dependencies()
    
    if success1 and success2:
        print("\n✅ The monkey patches support optional dependencies.")
        sys.exit(0)
    else:
        print("\n❌ The monkey patches do not support optional dependencies.")
        sys.exit(1) 