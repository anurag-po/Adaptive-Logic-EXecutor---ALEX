"""
ALEX — Context Manager (Phase 2)
Builds the LLM message history for multi-turn contextual understanding.
Combines system prompt, user preferences, recent conversation turns,
and the current user input into a structured message list.
"""

import config
from memory.database import MemoryDB
from utils.helpers import get_logger

logger = get_logger()


class ContextManager:
    """
    Manages the conversation context window for the Groq LLM.
    Builds a list of messages that gives the LLM awareness of:
      - Prior turns in this session
      - User preferences
      - The current input
    """

    def __init__(self, memory: MemoryDB, session_id: str):
        self._memory = memory
        self._session_id = session_id
        self._window_size = config.CONTEXT_WINDOW_SIZE

    def build_messages(
        self, user_input: str, system_prompt: str
    ) -> list[dict]:
        """
        Build the full message list for a context-aware LLM query.

        Returns:
            [
                {"role": "system", "content": "...system prompt + prefs..."},
                {"role": "user", "content": "turn 1"},
                {"role": "assistant", "content": "turn 1 response"},
                ...
                {"role": "user", "content": "current input"},
            ]
        """
        messages = []

        # ── 1. System prompt with preferences injected ────────────
        prefs = self._memory.get_all_preferences()
        enhanced_prompt = system_prompt

        if prefs:
            pref_lines = [f"- {k}: {v}" for k, v in prefs.items()]
            pref_block = "\n".join(pref_lines)
            enhanced_prompt += (
                f"\n\nUSER PREFERENCES (use these to personalize responses):\n"
                f"{pref_block}"
            )

        messages.append({"role": "system", "content": enhanced_prompt})

        # ── 2. Recent conversation history ────────────────────────
        recent = self._memory.get_recent_turns(
            self._session_id, self._window_size
        )

        for turn in recent:
            role = turn["role"]
            content = turn["content"]

            # For assistant turns, include what was executed for richer context
            if role == "assistant" and turn.get("function"):
                content = (
                    f"[Executed: {turn['function']}] {content}"
                )

            messages.append({"role": role, "content": content})

        # ── 3. Current user input ─────────────────────────────────
        messages.append({"role": "user", "content": user_input})

        logger.debug(
            f"Context built: {len(messages)} messages "
            f"({len(recent)} history turns, {len(prefs)} preferences)"
        )

        return messages

    def get_last_turn(self) -> dict | None:
        """Get the last turn in the session for smart interpretation."""
        return self._memory.get_last_turn(self._session_id)

    def get_last_assistant_turn(self) -> dict | None:
        """Get the last assistant turn for recall."""
        return self._memory.get_last_assistant_turn(self._session_id)
