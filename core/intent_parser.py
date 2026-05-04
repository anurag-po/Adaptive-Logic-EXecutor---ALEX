"""
ALEX — Intent Parser
Validates JSON responses from the LLM against the expected schema
and cross-checks function names against the registry.
"""

from dataclasses import dataclass, field
import config
from core.registry_validator import RegistryValidator
from utils.helpers import get_logger

logger = get_logger()


@dataclass
class ActionItem:
    """A single function call extracted from LLM output."""
    function: str
    args: dict = field(default_factory=dict)


@dataclass
class ParsedIntent:
    """Fully validated intent ready for routing."""
    intent: str
    funcnum: str              # "single" or "multi"
    actions: list[ActionItem] = field(default_factory=list)
    confidence: float = 0.0
    sensitive: bool = False
    raw: dict = field(default_factory=dict)


class IntentParser:
    """
    Validates LLM JSON output:
      1. Schema correctness (required keys present)
      2. Function existence in registry
      3. Confidence threshold check
    """

    def __init__(self, registry: RegistryValidator):
        self._registry = registry

    def parse(self, data: dict) -> ParsedIntent | str:
        """
        Parse and validate LLM output dict.
        Returns ParsedIntent on success, or an error string on failure.
        """
        # ── Step 1: Basic schema validation ──────────────────────
        intent = data.get("intent", "")
        funcnum = data.get("funcnum", "")
        confidence = data.get("confidence", 0.0)

        if not intent:
            return "Missing 'intent' field in LLM response."

        if funcnum not in ("single", "multi"):
            return f"Invalid funcnum '{funcnum}'. Must be 'single' or 'multi'."

        # ── Step 2: Confidence check ─────────────────────────────
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0

        if confidence < config.CONFIDENCE_THRESHOLD:
            return (
                f"Confidence too low ({confidence:.2f} < "
                f"{config.CONFIDENCE_THRESHOLD}). Cannot proceed."
            )

        # ── Step 3: Extract actions ──────────────────────────────
        actions: list[ActionItem] = []
        is_sensitive = False

        if funcnum == "single":
            func_name = data.get("function", "")
            func_args = data.get("args", {})

            if not func_name or func_name == "none":
                return f"Unknown request. I could not map this to a known action."

            # Registry check
            if not self._registry.is_valid_function(func_name):
                return (
                    f"Function '{func_name}' is not in the registry. "
                    f"Rejecting hallucinated function."
                )

            actions.append(ActionItem(function=func_name, args=func_args))

            if func_name in config.SENSITIVE_FUNCTIONS:
                is_sensitive = True

        elif funcnum == "multi":
            raw_actions = data.get("actions", [])
            if not isinstance(raw_actions, list) or len(raw_actions) == 0:
                return "Multi-action intent has no 'actions' array."

            for i, action in enumerate(raw_actions):
                func_name = action.get("function", "")
                func_args = action.get("args", {})

                if not func_name:
                    return f"Action #{i+1} is missing a function name."

                if not self._registry.is_valid_function(func_name):
                    return (
                        f"Action #{i+1}: function '{func_name}' "
                        f"is not in the registry."
                    )

                actions.append(ActionItem(function=func_name, args=func_args))

                if func_name in config.SENSITIVE_FUNCTIONS:
                    is_sensitive = True

        # ── Step 4: Build validated intent ───────────────────────
        parsed = ParsedIntent(
            intent=intent,
            funcnum=funcnum,
            actions=actions,
            confidence=confidence,
            sensitive=is_sensitive,
            raw=data,
        )

        logger.info(
            f"Parsed intent: '{intent}' | {len(actions)} action(s) | "
            f"confidence={confidence:.2f} | sensitive={is_sensitive}"
        )
        return parsed
