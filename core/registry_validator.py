"""
ALEX — Registry Validator
Parses knowledge.md at startup to build the canonical function registry.
Only functions listed here are permitted for execution.
"""

import re
from utils.helpers import get_logger

logger = get_logger()


class RegistryValidator:
    """
    Parses knowledge.md and maintains a mapping of
    function_name -> list[param_names].
    """

    def __init__(self, knowledge_path: str):
        self._registry: dict[str, list[str]] = {}
        self._raw_text: str = ""
        self._parse(knowledge_path)

    # ── Public API ────────────────────────────────────────────────

    def is_valid_function(self, name: str) -> bool:
        """Check if a function name exists in the registry."""
        return name in self._registry

    def get_function_params(self, name: str) -> list[str]:
        """Return the parameter names for a registered function."""
        return self._registry.get(name, [])

    def get_all_functions(self) -> dict[str, list[str]]:
        """Return the full registry dict."""
        return dict(self._registry)

    def get_registry_text(self) -> str:
        """Return the raw knowledge.md text for LLM system prompt injection."""
        return self._raw_text

    # ── Internals ─────────────────────────────────────────────────

    def _parse(self, path: str):
        """
        Read knowledge.md and extract function signatures.
        Expected format per line:  - function_name(param1, param2)
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._raw_text = f.read()
        except FileNotFoundError:
            logger.error(f"knowledge.md not found at {path}")
            raise

        # Match lines like: - function_name(arg1, arg2, arg3)
        pattern = re.compile(r"-\s+(\w+)\(([^)]*)\)")

        for match in pattern.finditer(self._raw_text):
            func_name = match.group(1)
            raw_params = match.group(2).strip()
            params = (
                [p.strip() for p in raw_params.split(",") if p.strip()]
                if raw_params
                else []
            )
            self._registry[func_name] = params

        logger.info(
            f"Registry loaded: {len(self._registry)} functions from knowledge.md"
        )
        logger.debug(f"Functions: {list(self._registry.keys())}")
