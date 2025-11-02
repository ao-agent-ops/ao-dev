from typing import Optional
from aco.common.constants import COLLECT_TELEMETRY, TELEMETRY_KEY, TELEMETRY_URL
from aco.common.logger import logger

try:
    from supabase import create_client

    SUPABASE_AVAILABLE = True
except ImportError:
    if COLLECT_TELEMETRY:
        raise ImportError(
            "Supabase is required for telemetry but not installed. "
            "Install with: pip install supabase"
        )
    else:
        logger.info("Supabase not available, but telemetry disabled anyways.")
    SUPABASE_AVAILABLE = False


class SupabaseClient:
    """Singleton Supabase client for telemetry operations."""

    _instance: Optional["SupabaseClient"] = None
    _client: Optional["Client"] = None

    def __new__(cls) -> "SupabaseClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> "Client":
        """Get or create the Supabase client."""
        if self._client is None:
            self._initialize_client()
        return self._client

    def _initialize_client(self) -> None:
        """Initialize the Supabase client with config values."""
        if not SUPABASE_AVAILABLE:
            logger.debug("Supabase not available, telemetry client disabled.")
            self._client = None
            return

        url = TELEMETRY_URL
        key = TELEMETRY_KEY

        if not COLLECT_TELEMETRY or not url or not key:
            logger.debug(
                "Telemetry URL or key not configured. " "Run 'aco config' to set up telemetry."
            )
            self._client = None
            return

        try:
            self._client = create_client(url, key)
        except Exception:
            self._client = None

    def is_available(self) -> bool:
        """Check if Supabase client is available and ready."""
        if self._client is None:
            self._initialize_client()
        return self._client is not None


# Global instance
supabase_client = SupabaseClient()
