"""
ALEX -- Permission System (Phase 3)
Three-tier permission enforcement for action execution.

Tiers:
  SAFE      -- Execute immediately, no prompt
  MODERATE  -- Log warning, execute (can be promoted to DANGEROUS)
  DANGEROUS -- Require explicit "yes" confirmation + double-logged
"""

from enum import Enum
import config
from utils.helpers import get_logger

logger = get_logger()


class PermissionTier(Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"
    UNKNOWN = "unknown"


class PermissionSystem:
    """
    Manages permission checks for function execution.
    Tiers are defined in config.py and can be overridden via user preferences.
    """

    def __init__(self, memory_db=None):
        self._memory = memory_db
        self._tier_map: dict[str, PermissionTier] = {}
        self._build_tier_map()

    def _build_tier_map(self):
        """Build the function -> tier mapping from config."""
        for func_name in config.PERMISSION_TIERS.get("SAFE", []):
            self._tier_map[func_name] = PermissionTier.SAFE

        for func_name in config.PERMISSION_TIERS.get("MODERATE", []):
            self._tier_map[func_name] = PermissionTier.MODERATE

        for func_name in config.PERMISSION_TIERS.get("DANGEROUS", []):
            self._tier_map[func_name] = PermissionTier.DANGEROUS

        # Apply user preference overrides
        if self._memory:
            self._apply_overrides()

    def _apply_overrides(self):
        """Apply user preference overrides for permission tiers."""
        prefs = self._memory.get_all_preferences()
        for key, value in prefs.items():
            if key.startswith("permission_"):
                func_name = key.replace("permission_", "")
                tier_str = value.lower()
                if tier_str in ("safe", "moderate", "dangerous"):
                    tier = PermissionTier(tier_str)
                    self._tier_map[func_name] = tier
                    logger.debug(
                        f"Permission override: {func_name} -> {tier.value}"
                    )

    def check(self, function_name: str) -> PermissionTier:
        """Get the permission tier for a function."""
        return self._tier_map.get(function_name, PermissionTier.SAFE)

    def requires_confirmation(self, function_name: str) -> bool:
        """Check if a function requires user confirmation."""
        return self.check(function_name) == PermissionTier.DANGEROUS

    def is_moderate(self, function_name: str) -> bool:
        """Check if a function is in the moderate tier."""
        return self.check(function_name) == PermissionTier.MODERATE

    def get_tier_summary(self) -> dict[str, list[str]]:
        """Get a summary of all tier assignments."""
        summary = {"safe": [], "moderate": [], "dangerous": [], "unknown": []}
        for func, tier in sorted(self._tier_map.items()):
            summary[tier.value].append(func)
        return summary
