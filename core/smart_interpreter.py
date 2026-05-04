"""
ALEX — Smart Query Interpreter (Phase 2)
Pre-processes user input before sending to the LLM.
Handles pronoun resolution, implicit references, fuzzy matching,
and follow-up detection.
"""

import re
from utils.helpers import get_logger

logger = get_logger()

# Patterns that indicate a follow-up to the previous turn
FOLLOW_UP_STARTERS = (
    "also", "and", "then", "now", "next", "after that",
    "do that again", "repeat", "one more", "same thing",
    "what about", "how about", "try",
)

# Pronouns that may reference the previous action/object
PRONOUNS = {"it", "that", "this", "them", "those", "the same"}

# Common app name normalization
FUZZY_APP_NAMES = {
    "note pad": "notepad",
    "note-pad": "notepad",
    "calc": "calculator",
    "file explorer": "explorer",
    "vs code": "vscode",
    "visual studio": "vscode",
    "power point": "powerpoint",
    "power shell": "powershell",
    "google": "chrome",
    "task mgr": "task manager",
}


class SmartInterpreter:
    """
    Refines raw user input before it reaches the LLM.
    Uses the last conversation turn for context resolution.
    """

    def interpret(self, raw_input: str, last_turn: dict | None) -> str:
        """
        Process raw user input and return a refined version.

        Args:
            raw_input: The user's raw text input.
            last_turn: The last conversation turn dict (or None).

        Returns:
            Refined input string with context resolved.
        """
        text = raw_input.strip()
        if not text:
            return text

        original = text

        # Step 1: Normalize fuzzy app names
        text = self._normalize_app_names(text)

        # Step 2: Resolve pronouns using last turn context
        if last_turn:
            text = self._resolve_pronouns(text, last_turn)
            text = self._resolve_follow_ups(text, last_turn)

        if text != original:
            logger.info(f"Smart interpret: '{original}' -> '{text}'")

        return text

    def is_follow_up(self, text: str) -> bool:
        """Check if the input appears to be a follow-up to a previous turn."""
        lower = text.lower().strip()
        return any(lower.startswith(s) for s in FOLLOW_UP_STARTERS)

    # ── Internal Methods ──────────────────────────────────────────

    def _normalize_app_names(self, text: str) -> str:
        """Fix common misspellings and alternative names."""
        lower = text.lower()
        for fuzzy, correct in FUZZY_APP_NAMES.items():
            if fuzzy in lower:
                text = re.sub(
                    re.escape(fuzzy), correct, text, flags=re.IGNORECASE
                )
        return text

    def _resolve_pronouns(self, text: str, last_turn: dict) -> str:
        """
        Replace pronouns like 'it', 'that' with the object from the last turn.
        Example: "close it" -> "close notepad" if last action was open_app(notepad)
        """
        lower = text.lower()

        # Check if any pronoun is present
        words = set(lower.split())
        matching_pronouns = words & PRONOUNS

        if not matching_pronouns:
            return text

        # Extract the object from the last turn
        last_function = last_turn.get("function", "")
        last_content = last_turn.get("content", "")
        resolved_object = self._extract_object(last_function, last_content)

        if not resolved_object:
            return text

        # Replace pronouns with the resolved object
        for pronoun in matching_pronouns:
            # Only replace standalone words, not substrings
            pattern = r'\b' + re.escape(pronoun) + r'\b'
            text = re.sub(pattern, resolved_object, text, flags=re.IGNORECASE)

        return text

    def _resolve_follow_ups(self, text: str, last_turn: dict) -> str:
        """
        Enhance follow-up queries with context from the last turn.
        Example: "do that again" -> "open notepad again" if last was open_app(notepad)
        """
        lower = text.lower().strip()

        # "do that again" / "repeat" / "same thing"
        if lower in ("do that again", "repeat", "repeat that",
                      "same thing", "again", "one more time"):
            last_content = last_turn.get("content", "")
            if last_content and last_turn.get("role") == "user":
                logger.info(f"Repeating last command: {last_content}")
                return last_content

        return text

    def _extract_object(self, function: str, content: str) -> str | None:
        """
        Extract the key object from a function call or content string.
        Used for pronoun resolution.
        """
        if not function:
            return None

        # Pattern: extract app name from open_app, close_app
        if function in ("open_app", "close_app"):
            # Try to extract from content
            for pattern in [
                r"open(?:ed)?\s+(.+?)(?:\.|$)",
                r"close(?:d)?\s+(.+?)(?:\.|$)",
            ]:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1).strip()

        # Pattern: extract URL from browser actions
        if function in ("open_website", "search_google"):
            for pattern in [
                r"(?:opened|searching)\s+(.+?)(?:\.|$)",
                r"for\s+'(.+?)'",
            ]:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1).strip()

        # Pattern: extract path from file actions
        if function in ("create_folder", "open_folder", "delete_file"):
            for pattern in [
                r"(?:folder|file):\s*(.+?)(?:\.|$)",
                r"(?:at|to)\s+(.+?)(?:\.|$)",
            ]:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1).strip()

        return None
