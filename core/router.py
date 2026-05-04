"""
ALEX -- Router Engine (Phase 3)
Maps validated intent actions to Python callables and executes them safely.
Uses PluginLoader for auto-discovery and PermissionSystem for tiered checks.
"""

import time
import config
from core.intent_parser import ParsedIntent, ActionItem
from core.plugin_loader import PluginLoader
from core.permission_system import PermissionSystem, PermissionTier
from utils.helpers import get_logger, confirm_action

logger = get_logger()


class Router:
    """
    Dispatch table built via auto-discovery from actions/ modules.
    Executes actions with tiered permission checks and memory logging.
    """

    def __init__(self, registry=None, memory_db=None, session_id: str = None):
        """
        Args:
            registry: RegistryValidator instance (for plugin cross-reference)
            memory_db: MemoryDB instance (for execution logging)
            session_id: Current session ID
        """
        self._dispatch: dict[str, callable] = {}
        self._memory = memory_db
        self._session_id = session_id
        self._permissions = PermissionSystem(memory_db)

        # Build dispatch table via plugin loader
        if registry:
            loader = PluginLoader(registry.get_all_functions())
            self._dispatch = loader.discover()

        # Add inline memory actions (not in action modules)
        self._dispatch["recall_last_action"] = self._recall_last_action
        self._dispatch["set_preference"] = self._set_preference

        # Background agent actions will be injected by main.py
        # via inject_agent_actions()

        logger.info(f"Router loaded: {len(self._dispatch)} action handlers")

    # -- Public API ------------------------------------------------

    def inject_agent_actions(self, agent):
        """Inject background agent callable actions into dispatch."""
        self._dispatch["schedule_reminder"] = agent.schedule_reminder
        self._dispatch["list_scheduled_tasks"] = agent.list_scheduled_tasks
        self._dispatch["cancel_scheduled_task"] = agent.cancel_scheduled_task
        logger.info("Router: background agent actions injected")

    def inject_llm_client(self, llm_client):
        """Inject LLM client into productivity actions."""
        from actions import productivity_actions
        productivity_actions.set_llm_client(llm_client)

    def execute(self, intent: ParsedIntent) -> dict:
        """
        Execute a parsed intent. Returns a result dict with
        status, output, and any errors.
        """
        results = []

        for i, action in enumerate(intent.actions):
            logger.info(
                f"Executing [{i+1}/{len(intent.actions)}]: "
                f"{action.function}({action.args})"
            )

            # Permission check (Phase 3)
            tier = self._permissions.check(action.function)

            if tier == PermissionTier.DANGEROUS:
                if not confirm_action(action.function, action.args):
                    logger.info(f"User cancelled: {action.function}")
                    results.append({
                        "function": action.function,
                        "status": "cancelled",
                        "output": "Cancelled by user.",
                    })
                    continue

            if tier == PermissionTier.MODERATE:
                logger.info(
                    f"[MODERATE] {action.function} -- executing with warning"
                )

            # Dispatch with timing
            start = time.time()
            result = self._call(action)
            duration_ms = int((time.time() - start) * 1000)
            result["duration_ms"] = duration_ms
            results.append(result)

            # Log to memory database
            if self._memory:
                self._memory.log_execution(
                    function=action.function,
                    args=action.args,
                    status=result["status"],
                    duration_ms=duration_ms,
                    output=result.get("output", ""),
                )

            # Log browser actions
            if action.function in config.LOGGED_FUNCTIONS:
                logger.info(f"[LOGGED] {action.function}({action.args})")

            # Stop chain on error
            if result["status"] == "error":
                logger.error(
                    f"Chain halted at action #{i+1}: {result['error']}"
                )
                break

        # Aggregate result
        if len(results) == 1:
            return results[0]

        all_success = all(r["status"] == "success" for r in results)
        return {
            "function": "multi",
            "status": "success" if all_success else "partial",
            "output": " | ".join(
                r.get("output", "") for r in results if r.get("output")
            ),
            "details": results,
        }

    # -- Internals -------------------------------------------------

    def _call(self, action: ActionItem) -> dict:
        """Call a single action function safely."""
        func = self._dispatch.get(action.function)

        if func is None:
            return {
                "function": action.function,
                "status": "error",
                "error": f"No handler registered for '{action.function}'.",
            }

        try:
            output = func(**action.args)
            return {
                "function": action.function,
                "status": "success",
                "output": str(output) if output else "Completed.",
            }
        except TypeError as e:
            return {
                "function": action.function,
                "status": "error",
                "error": f"Argument error: {e}",
            }
        except Exception as e:
            logger.exception(f"Error executing {action.function}")
            return {
                "function": action.function,
                "status": "error",
                "error": str(e),
            }

    # -- Memory Actions (inline) -----------------------------------

    def _recall_last_action(self) -> str:
        """Recall the last action ALEX performed."""
        if not self._memory:
            return "Memory not available."
        turn = self._memory.get_last_assistant_turn(self._session_id or "")
        if turn:
            func = turn.get("function", "unknown")
            result = turn.get("result", "")
            return f"Last action: {func}. Result: {result}"
        return "No previous actions found in this session."

    def _set_preference(self, key: str, value: str) -> str:
        """Explicitly set a user preference."""
        if not self._memory:
            return "Memory not available."
        self._memory.set_preference(key, value, source="explicit")
        return f"Preference set: {key} = {value}"
