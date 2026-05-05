"""
ALEX -- Adaptive Logic Execution eXecutor (Phase 3)
Main entry point. Orchestrates all modules including:
  - Plugin auto-discovery
  - Tiered permissions
  - Persistent memory (SQLite)
  - Multi-turn context awareness
  - Smart query interpretation
  - Continuous listening mode
  - Background agent (reminders, scheduled tasks)
  - Analytics dashboard
  - Overlay UI, voice/text input, LLM, and action execution

Architecture:
  - Main thread    : PyQt6 event loop (overlay + dashboard)
  - Worker thread  : Assistant pipeline
  - Keyboard hook  : Ctrl+Space (voice), Escape (stop listening)
  - Background     : Agent scheduler thread
"""

import sys
import uuid
import time
import threading
from queue import Queue

import config
from utils.helpers import setup_logging, format_result, get_logger
from core.registry_validator import RegistryValidator
from core.intent_parser import IntentParser, ParsedIntent
from core.router import Router
from core.smart_interpreter import SmartInterpreter
from llm.groq_client import GroqClient
from memory.database import MemoryDB
from memory.context_manager import ContextManager
from background.agent import BackgroundAgent
from voice.speech_to_text import WhisperSTT
from voice.text_to_speech import TTS
from ui.setup_window import run_setup
from ui.overlay import launch_overlay_app, AssistantState
import os
import dotenv


# ═══════════════════════════════════════════════════════════════════
# SHARED QUEUES
# ═══════════════════════════════════════════════════════════════════

audio_fft_queue = Queue(maxsize=30)    # FFT data -> overlay
state_queue = Queue(maxsize=10)        # State changes -> overlay


def set_state(state: AssistantState):
    """Push a state change to the overlay."""
    try:
        state_queue.put_nowait(state)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# ASSISTANT PIPELINE (Phase 3)
# ═══════════════════════════════════════════════════════════════════

class AssistantWorker:
    """
    Full assistant pipeline with Phase 3 features:
      - Plugin auto-discovery (no manual dispatch table)
      - Tiered permission system
      - Continuous listening after first hotkey press
      - Background agent for reminders/scheduled tasks
      - Analytics dashboard
    """

    def __init__(self):
        self.logger = get_logger()

        # -- Initialize modules ------------------------------------
        self.logger.info("=" * 50)
        self.logger.info("  ALEX - Adaptive Logic Execution eXecutor v3")
        self.logger.info("=" * 50)

        # Session ID -- unique per launch
        self.session_id = uuid.uuid4().hex[:12]
        self.logger.info(f"Session: {self.session_id}")

        # Registry
        self.registry = RegistryValidator(config.KNOWLEDGE_PATH)

        # Memory
        self.memory = MemoryDB()

        # Context manager
        self.context = ContextManager(self.memory, self.session_id)

        # LLM
        self.llm = GroqClient(self.registry.get_registry_text())

        # Smart interpreter
        self.interpreter = SmartInterpreter()

        # Intent parser
        self.parser = IntentParser(self.registry)

        # Background agent (Phase 3)
        self.agent = BackgroundAgent(
            notify_callback=self._agent_notify
        )

        # Router (Phase 3: uses plugin loader for auto-discovery)
        self.router = Router(
            registry=self.registry,
            memory_db=self.memory,
            session_id=self.session_id,
        )
        # Inject background agent actions into router
        self.router.inject_agent_actions(self.agent)
        # Inject LLM client into productivity actions
        self.router.inject_llm_client(self.llm)

        # Voice
        self.stt = WhisperSTT(audio_fft_queue=audio_fft_queue)
        self.tts = TTS(state_callback=self._tts_state_callback)

        # -- Continuous listening state (Phase 3) ------------------
        self._continuous_mode = False
        self._listening_lock = threading.Lock()

        self.running = True

    # -- Callbacks -------------------------------------------------

    def _tts_state_callback(self, state_str: str):
        """Called by TTS to update overlay state."""
        if state_str == "speaking":
            set_state(AssistantState.SPEAKING)
        else:
            set_state(AssistantState.IDLE)

    def _agent_notify(self, message: str):
        """Called by background agent when a task fires."""
        self.logger.info(f"[AGENT] {message}")
        set_state(AssistantState.SPEAKING)
        self.tts.speak(message)
        set_state(AssistantState.IDLE)

    # -- Pipeline --------------------------------------------------

    def process_input(self, user_text: str):
        """Run the full Phase 3 pipeline for a given text input."""
        if not user_text.strip():
            return

        self.logger.info(f"User: {user_text}")

        # -- Check for stop phrases (exit continuous listening) -----
        text_lower = user_text.strip().lower()
        if any(phrase in text_lower for phrase in config.STOP_PHRASES):
            self._continuous_mode = False
            self.logger.info("Continuous listening stopped by user.")
            self.tts.speak("Going idle. Press control space when you need me.")
            set_state(AssistantState.IDLE)
            return

        # -- Save user turn to memory -----------------------------
        self.memory.save_turn(
            role="user",
            content=user_text,
            session_id=self.session_id,
        )

        # -- Step 1: Smart interpretation --------------------------
        last_turn = self.context.get_last_assistant_turn()
        refined_input = self.interpreter.interpret(user_text, last_turn)

        # -- Step 2: Build context-aware messages ------------------
        set_state(AssistantState.PROCESSING)

        if self.interpreter.is_follow_up(user_text) or last_turn:
            messages = self.context.build_messages(
                refined_input, self.llm._system_prompt
            )
            llm_response = self.llm.query_with_context(messages)
        else:
            llm_response = self.llm.query(refined_input)

        # -- Step 3: Parse intent ----------------------------------
        result = self.parser.parse(llm_response)

        if isinstance(result, str):
            self.logger.warning(f"Parse error: {result}")
            self._respond(result, intent="error", function="none")
            return

        # -- Step 4: Route & execute -------------------------------
        self.logger.info(f"Executing: {result.intent}")
        exec_result = self.router.execute(result)

        # -- Step 5: Format and speak result -----------------------
        speech_text = format_result(exec_result)
        func_names = ", ".join(a.function for a in result.actions)
        self._respond(
            speech_text,
            intent=result.intent,
            function=func_names,
        )

    def _respond(self, text: str, intent: str = "", function: str = ""):
        """Speak the result and save to memory."""
        self.memory.save_turn(
            role="assistant",
            content=text,
            session_id=self.session_id,
            intent=intent,
            function=function,
            result=text,
        )

        self.tts.speak(text)
        set_state(AssistantState.IDLE)

    # -- Text Input ------------------------------------------------
    
    def handle_text_input(self, text: str):
        """Handle text input from the overlay UI in a background thread."""
        t = threading.Thread(target=self.process_input, args=(text,), daemon=True)
        t.start()

    # -- Voice Input -----------------------------------------------

    def handle_voice_input(self):
        """Handle a voice input session triggered by hotkey."""
        with self._listening_lock:
            set_state(AssistantState.LISTENING)
            text = self.stt.listen_and_transcribe()

            if text:
                self.logger.info(f"Transcribed: {text}")
                self.process_input(text)

                # Phase 3: Enter continuous listening mode after first response
                text_l = text.strip().lower()
                if not any(p in text_l for p in config.STOP_PHRASES):
                    self._continuous_mode = True
                    self._continuous_listen_loop()
            else:
                self.logger.info("No speech detected.")
                self.tts.speak("I didn't catch that. Please try again.")
                set_state(AssistantState.IDLE)

    def _continuous_listen_loop(self):
        """
        Continuous listening mode (Phase 3).
        After the first hotkey press, ALEX auto-listens for follow-ups
        until the user says a stop phrase or the silence timeout is hit.
        """
        while self._continuous_mode and self.running:
            self.logger.info("Continuous listening: waiting for input...")
            set_state(AssistantState.LISTENING)

            text = self.stt.listen_and_transcribe(
                timeout_override=config.CONTINUOUS_LISTEN_TIMEOUT
            )

            if not text:
                # Silence timeout -- exit continuous mode
                self.logger.info(
                    "Continuous listening: silence timeout, going idle."
                )
                self._continuous_mode = False
                set_state(AssistantState.IDLE)
                break

            self.logger.info(f"Continuous: {text}")

            # Check for stop phrases
            text_l = text.strip().lower()
            if any(p in text_l for p in config.STOP_PHRASES):
                self._continuous_mode = False
                self.tts.speak("Going idle.")
                set_state(AssistantState.IDLE)
                break

            self.process_input(text)

    def stop_continuous(self):
        """Stop continuous listening (called by escape hotkey)."""
        if self._continuous_mode:
            self._continuous_mode = False
            self.logger.info("Continuous listening stopped (Escape key).")

    # -- Console Loop ----------------------------------------------

    def console_loop(self):
        """
        Run a console input loop for text-based interaction.
        Registers global hotkeys for voice input and escape.
        """
        # Register hotkeys
        try:
            import keyboard

            def on_hotkey():
                self.logger.info(f"Hotkey pressed: {config.VOICE_HOTKEY}")
                t = threading.Thread(
                    target=self.handle_voice_input, daemon=True
                )
                t.start()

            def on_escape():
                self.stop_continuous()

            keyboard.add_hotkey(config.VOICE_HOTKEY, on_hotkey)
            keyboard.add_hotkey(config.ESCAPE_HOTKEY, on_escape)

            self.logger.info(
                f"Voice hotkey registered: {config.VOICE_HOTKEY.upper()}"
            )
            self.logger.info(
                f"Escape hotkey registered: {config.ESCAPE_HOTKEY.upper()}"
            )
        except ImportError:
            self.logger.warning(
                "keyboard module not installed. "
                "Voice hotkey disabled. Install with: pip install keyboard"
            )
        except Exception as e:
            self.logger.warning(f"Could not register hotkey: {e}")

        # Show status
        print()
        print("=" * 50)
        print("  ALEX v3 is ready. (Phase 3 - Full)")
        print(f"  Voice     : Press {config.VOICE_HOTKEY.upper()}")
        print(f"  Stop      : Press {config.ESCAPE_HOTKEY.upper()} or say 'stop'")
        print("  Dashboard : Double-click the orb")
        print("  Text      : Type below and press Enter")
        print("  Quit      : Type 'exit' or 'quit'")
        print(f"  Session   : {self.session_id}")
        print("=" * 50)
        print()

        # Show learned preferences
        prefs = self.memory.get_all_preferences()
        if prefs:
            print("  Remembered preferences:")
            for k, v in prefs.items():
                print(f"    {k} = {v}")
            print()

        # Show active background tasks
        task_count = self.agent.get_active_count()
        if task_count:
            print(f"  Active background tasks: {task_count}")
            print()

        while self.running:
            try:
                user_input = input("You > ").strip()

                if user_input.lower() in ("exit", "quit", "q"):
                    self.logger.info("User requested exit.")
                    self.running = False
                    self.agent.stop()
                    from PyQt6.QtWidgets import QApplication
                    app = QApplication.instance()
                    if app:
                        app.quit()
                    break

                if user_input:
                    self.process_input(user_input)

            except (EOFError, KeyboardInterrupt):
                self.logger.info("Interrupted. Shutting down.")
                self.running = False
                self.agent.stop()
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    app.quit()
                break


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    """Launch ALEX v3: overlay + dashboard in main thread, assistant in background."""
    setup_logging()
    logger = get_logger()

    # Check for API Keys before anything else
    dotenv.load_dotenv()
    if not os.path.exists(".env") or not os.getenv("GROQ_API_KEY") or not os.getenv("GROQ_API_KEY_2"):
        logger.info("API keys missing. Launching Setup Window...")
        if not run_setup():
            logger.error("Setup cancelled. Exiting.")
            return
        # Reload env after setup
        dotenv.load_dotenv(override=True)

    # Validate config
    if not config.ACTIVE_SLOTS:
        logger.warning("No API keys found in config after setup.")

    # Create assistant worker
    worker = AssistantWorker()

    # Start console/hotkey loop in background thread
    console_thread = threading.Thread(
        target=worker.console_loop, daemon=True
    )
    console_thread.start()

    # Launch overlay UI in main thread
    app, overlay = launch_overlay_app(audio_fft_queue, state_queue, text_callback=worker.handle_text_input)

    # Create and attach dashboard panel (Phase 3)
    from ui.dashboard import DashboardPanel
    dashboard = DashboardPanel(
        parent=None,
        memory_db=worker.memory,
        session_id=worker.session_id,
        background_agent=worker.agent,
    )
    overlay.set_dashboard(dashboard)

    logger.info("Starting ALEX overlay...")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
