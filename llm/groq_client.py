"""
ALEX — Groq LLM Client (Phase 2)
Wraps the Groq SDK. Supports:
  - Single-shot queries (Phase 1)
  - Context-aware multi-turn queries (Phase 2)
  - Content generation queries (Phase 2) for productivity actions
  - 4 API slots with automatic fallback
"""

import json
from groq import Groq
import config
from utils.helpers import get_logger

logger = get_logger()

# ═══════════════════════════════════════════════════════════════════
# System prompt — injected with the function registry at runtime
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_TEMPLATE = """You are ALEX — Adaptive Logic Execution eXecutor.
You convert natural language instructions into structured JSON action calls.

STRICT RULES:
1. Output ONLY valid JSON. No prose, no markdown, no explanation.
2. You may ONLY use functions listed in the FUNCTION REGISTRY below.
3. Never invent or hallucinate function names.
4. If a request cannot be mapped to a registered function, respond with:
   {{"intent": "unknown", "funcnum": "single", "function": "none", "args": {{}}, "confidence": 0.0}}
5. Use conversation history to resolve ambiguous references (e.g., "close it" means close the last opened app).

FUNCTION REGISTRY:
{registry}

OUTPUT SCHEMA — Single action:
{{
  "intent": "short description of user intent",
  "funcnum": "single",
  "function": "function_name_from_registry",
  "args": {{"arg1": "value"}},
  "confidence": 0.95
}}

OUTPUT SCHEMA — Multiple sequential actions:
{{
  "intent": "overall task description",
  "funcnum": "multi",
  "actions": [
    {{"function": "function_name_1", "args": {{"arg1": "value"}}}},
    {{"function": "function_name_2", "args": {{"arg1": "value"}}}}
  ],
  "confidence": 0.9
}}

SAFETY FLAGS:
- delete_file, shutdown_system, restart_system -> mark with "sensitive": true
- Browser actions -> always permitted but logged

Respond with JSON only. No other text."""


# ═══════════════════════════════════════════════════════════════════
# Content generation prompt (for productivity actions)
# ═══════════════════════════════════════════════════════════════════

CONTENT_SYSTEM_PROMPT = """You are ALEX — an AI writing assistant.
Generate high-quality content based on the user's request.
Write clearly and professionally. Do NOT output JSON.
Output only the requested content — no meta-commentary."""


class GroqClient:
    """
    Manages Groq API calls with automatic fallback across configured slots.
    Supports intent queries, context-aware queries, and content generation.
    """

    def __init__(self, registry_text: str):
        self._system_prompt = SYSTEM_PROMPT_TEMPLATE.format(registry=registry_text)
        self._clients: list[dict] = []

        for slot in config.API_SLOTS:
            if slot["key"]:
                self._clients.append({
                    "client": Groq(api_key=slot["key"]),
                    "model": slot["model"],
                    "label": slot["label"],
                })

        if not self._clients:
            logger.warning(
                "No Groq API keys configured! Set GROQ_API_KEY in .env file."
            )

    # ── Phase 1: Simple query ─────────────────────────────────────

    def query(self, user_input: str) -> dict:
        """
        Send user input to Groq and return parsed JSON dict.
        Tries each configured API slot in order until one succeeds.
        """
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_input},
        ]
        return self._query_json(messages)

    # ── Phase 2: Context-aware query ──────────────────────────────

    def query_with_context(self, messages: list[dict]) -> dict:
        """
        Send a full message list (system + history + current) to Groq.
        Used for multi-turn contextual understanding.
        """
        return self._query_json(messages)

    # ── Phase 2: Content generation ───────────────────────────────

    def generate_content(self, prompt: str) -> str:
        """
        Generate text content (documents, emails, summaries).
        Returns raw text, not JSON.
        """
        messages = [
            {"role": "system", "content": CONTENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        return self._query_text(messages)

    # ── Internal: JSON query ──────────────────────────────────────

    def _query_json(self, messages: list[dict]) -> dict:
        """Execute a JSON-mode query with fallback."""
        errors = []

        for slot in self._clients:
            try:
                logger.debug(
                    f"Querying [{slot['label']}] model={slot['model']}"
                )
                completion = slot["client"].chat.completions.create(
                    model=slot["model"],
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=config.MAX_TOKENS,
                    temperature=config.TEMPERATURE,
                )

                raw = completion.choices[0].message.content
                logger.debug(f"Raw LLM response: {raw}")

                parsed = json.loads(raw)
                logger.info(
                    f"LLM responded via [{slot['label']}]: "
                    f"intent={parsed.get('intent', '?')}"
                )
                return parsed

            except json.JSONDecodeError as e:
                logger.error(f"[{slot['label']}] Invalid JSON from LLM: {e}")
                errors.append(f"{slot['label']}: JSON parse error")
            except Exception as e:
                logger.error(f"[{slot['label']}] API error: {e}")
                errors.append(f"{slot['label']}: {e}")

        logger.error(f"All API slots failed: {errors}")
        return {
            "intent": "error",
            "funcnum": "single",
            "function": "none",
            "args": {},
            "confidence": 0.0,
            "error": f"All API slots failed: {'; '.join(errors)}",
        }

    # ── Internal: Text query ──────────────────────────────────────

    def _query_text(self, messages: list[dict]) -> str:
        """Execute a plain text query (for content generation)."""
        errors = []

        for slot in self._clients:
            try:
                completion = slot["client"].chat.completions.create(
                    model=slot["model"],
                    messages=messages,
                    max_tokens=config.CONTENT_MAX_TOKENS,
                    temperature=config.CONTENT_TEMPERATURE,
                )
                text = completion.choices[0].message.content
                logger.info(
                    f"Content generated via [{slot['label']}]: "
                    f"{len(text)} chars"
                )
                return text

            except Exception as e:
                logger.error(f"[{slot['label']}] Content gen error: {e}")
                errors.append(f"{slot['label']}: {e}")

        return f"Error: Could not generate content. {'; '.join(errors)}"
