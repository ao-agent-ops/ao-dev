import os
from typing import Optional
from supabase import create_client, Client
from common.logger import logger


class SupabaseClient:
    """Singleton Supabase client for telemetry operations."""

    _instance: Optional["SupabaseClient"] = None
    _client: Optional[Client] = None

    def __new__(cls) -> "SupabaseClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> Client:
        """Get or create the Supabase client."""
        if self._client is None:
            self._initialize_client()
        return self._client

    def _initialize_client(self) -> None:
        """Initialize the Supabase client with environment variables."""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")

        if not url or not key:
            logger.warning(
                "Supabase credentials not found. Set SUPABASE_URL and SUPABASE_ANON_KEY "
                "environment variables to enable telemetry."
            )
            # Create a mock client that fails gracefully
            self._client = None
            return

        try:
            self._client = create_client(url, key)
            print("Supabase client initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Supabase client: {e}")
            print(f"Error type: {type(e).__name__}")
            print(f"URL format: {url[:50]}..." if len(url) > 50 else f"URL: {url}")
            self._client = None

    def is_available(self) -> bool:
        """Check if Supabase client is available and ready."""
        if self._client is None:
            self._initialize_client()
        return self._client is not None


# Global instance
supabase_client = SupabaseClient()


if __name__ == "__main__":
    # Test the Supabase connection
    print("Testing Supabase connection...")

    # Check if supabase package is installed
    try:
        from supabase import create_client

        print("✅ Supabase package is installed")
    except ImportError as e:
        print(f"❌ Supabase package not installed: {e}")
        print("Run: pip install supabase")
        exit(1)

    # Check environment variables
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    print(f"URL: {url}")
    print(f"Key: {'Set (' + key[:20] + '...)' if key else 'Not set'}")

    if not url or not key:
        print("❌ Missing environment variables")
        exit(1)

    # Test connection manually to see the actual error
    print("\nTesting connection manually...")
    try:
        from supabase import create_client

        test_client = create_client(url, key)
        print("✅ Manual client creation successful!")

        # Test a simple operation
        try:
            response = test_client.table("code_snapshots").select("count", count="exact").execute()
            print(f"✅ Database connection verified!")
        except Exception as e:
            print(f"⚠️  Client created but database test failed: {e}")
            print("This is normal if you haven't created the tables yet")

    except Exception as e:
        print(f"❌ Manual client creation failed: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback

        print("Full traceback:")
        traceback.print_exc()

    # Also test our singleton
    print(f"\nOur singleton client available: {supabase_client.is_available()}")

    if not supabase_client.is_available():
        print("Debugging singleton issue...")
        print(f"Singleton _client value: {supabase_client._client}")
        # Force re-initialization
        supabase_client._client = None
        print("Forcing re-initialization...")
        test_available = supabase_client.is_available()
        print(f"After forced re-init: {test_available}")
