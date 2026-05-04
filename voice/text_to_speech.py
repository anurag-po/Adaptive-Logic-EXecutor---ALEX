"""
ALEX — Text-to-Speech (pyttsx3 / Windows SAPI5)
Offline TTS engine. Notifies overlay of speaking state.
"""

import pyttsx3
import config
from utils.helpers import get_logger

logger = get_logger()


class TTS:
    """
    Wraps pyttsx3 for offline text-to-speech on Windows.
    Manages engine lifecycle and state notifications.
    """

    def __init__(self, state_callback=None):
        """
        Args:
            state_callback: Optional callable(state_str) to notify
                            overlay of speaking start/stop.
        """
        self._state_callback = state_callback
        self._engine = None
        self._init_engine()

    def _init_engine(self):
        """Initialize or reinitialize the pyttsx3 engine."""
        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", config.TTS_RATE)
            self._engine.setProperty("volume", config.TTS_VOLUME)

            # Try to use a female voice if available
            voices = self._engine.getProperty("voices")
            if len(voices) > 1:
                self._engine.setProperty("voice", voices[1].id)

            logger.info("TTS engine initialized (pyttsx3 / SAPI5)")
        except Exception as e:
            logger.error(f"TTS initialization failed: {e}")
            self._engine = None

    def speak(self, text: str):
        """
        Speak the given text. Blocks until speech is complete.
        Notifies state callback of speaking start/stop.
        """
        if not text:
            return

        if self._engine is None:
            self._init_engine()
            if self._engine is None:
                logger.error("Cannot speak — TTS engine unavailable.")
                return

        logger.info(f"Speaking: {text[:80]}...")

        # Notify overlay: speaking started
        if self._state_callback:
            self._state_callback("speaking")

        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except RuntimeError:
            # Engine sometimes gets into a bad state; reinitialize
            logger.warning("TTS engine error, reinitializing...")
            self._init_engine()
            if self._engine:
                self._engine.say(text)
                self._engine.runAndWait()
        except Exception as e:
            logger.error(f"TTS error: {e}")
        finally:
            # Notify overlay: speaking finished
            if self._state_callback:
                self._state_callback("idle")
