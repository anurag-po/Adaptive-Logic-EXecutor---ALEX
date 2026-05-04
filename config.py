import os
import sys
from dotenv import load_dotenv

# -- EXE Path Handling (PyInstaller) --
if getattr(sys, 'frozen', False):
    # If running as EXE, bundled files (knowledge.md) are in _MEIPASS
    PROJECT_ROOT = sys._MEIPASS
    # Persisted files (.env, memory/) should be next to the EXE
    BASE_DIR = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = PROJECT_ROOT

# Load environment variables from BASE_DIR (where the EXE/Script is)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# -- Auto-create Directories --
for folder in ["memory", "logs"]:
    path = os.path.join(BASE_DIR, folder)
    if not os.path.exists(path):
        os.makedirs(path)

# ═══════════════════════════════════════════════════════════════════
# API CONFIGURATION — 1 primary + 3 fallback slots
# ═══════════════════════════════════════════════════════════════════

API_SLOTS = [
    {
        "key": os.getenv("GROQ_API_KEY", ""),
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "label": "Primary",
    },
    {
        "key": os.getenv("GROQ_API_KEY_2", ""),
        "model": os.getenv("GROQ_MODEL_2", "llama-3.1-8b-instant"),
        "label": "Fallback-1",
    },
    {
        "key": os.getenv("GROQ_API_KEY_3", ""),
        "model": os.getenv("GROQ_MODEL_3", "llama-3.3-70b-versatile"),
        "label": "Fallback-2",
    },
    {
        "key": os.getenv("GROQ_API_KEY_4", ""),
        "model": os.getenv("GROQ_MODEL_4", "llama-3.1-8b-instant"),
        "label": "Fallback-3",
    },
]

# Filter to only slots that have a valid API key
ACTIVE_SLOTS = [s for s in API_SLOTS if s["key"]]


# ═══════════════════════════════════════════════════════════════════
# LLM SETTINGS
# ═══════════════════════════════════════════════════════════════════

CONFIDENCE_THRESHOLD = 0.7
MAX_TOKENS = 1024
TEMPERATURE = 0.1


# ═══════════════════════════════════════════════════════════════════
# SAFETY GATE — Functions that require user confirmation
# ═══════════════════════════════════════════════════════════════════

SENSITIVE_FUNCTIONS = [
    "delete_file",
    "shutdown_system",
    "restart_system",
    "move_file",
]

LOGGED_FUNCTIONS = [
    "open_website",
    "search_google",
    "open_youtube_video",
    "play_youtube_music",
]


# ═══════════════════════════════════════════════════════════════════
# VOICE — Whisper STT (on-demand)
# ═══════════════════════════════════════════════════════════════════

WHISPER_MODEL = "base"
SAMPLE_RATE = 16000
RECORD_MAX_SECONDS = 15
SILENCE_THRESHOLD = 0.01
SILENCE_DURATION = 2.0   # seconds of silence before auto-stop


# ═══════════════════════════════════════════════════════════════════
# TTS — pyttsx3
# ═══════════════════════════════════════════════════════════════════

TTS_RATE = 175
TTS_VOLUME = 1.0


# ═══════════════════════════════════════════════════════════════════
# HOTKEY
# ═══════════════════════════════════════════════════════════════════

VOICE_HOTKEY = "ctrl+space"


# ═══════════════════════════════════════════════════════════════════
# PERSISTENT MEMORY (Phase 2)
# ═══════════════════════════════════════════════════════════════════

KNOWLEDGE_PATH = os.path.join(PROJECT_ROOT, "knowledge", "knowledge.md")
MEMORY_DB_PATH = os.path.join(BASE_DIR, "memory", "alex.db")
CONTEXT_WINDOW_SIZE = 10          # Last N turns sent to LLM
MAX_HISTORY_DAYS = 30             # Auto-cleanup after 30 days
PREFERENCE_LEARN_INTERVAL = 10    # Analyze patterns every N executions


# ═══════════════════════════════════════════════════════════════════
# BROWSER AUTOMATION (Phase 2)
# ═══════════════════════════════════════════════════════════════════

BROWSER_TIMEOUT = 30000           # ms — page load timeout
BROWSER_IDLE_TIMEOUT = 300        # seconds before auto-close browser


# ═══════════════════════════════════════════════════════════════════
# CONTENT GENERATION (Phase 2)
# ═══════════════════════════════════════════════════════════════════

CONTENT_MAX_TOKENS = 2048
CONTENT_TEMPERATURE = 0.7


# ═══════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════

KNOWLEDGE_PATH = os.path.join(PROJECT_ROOT, "knowledge", "knowledge.md")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DOCUMENTS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "ALEX")


# ═══════════════════════════════════════════════════════════════════
# PLUGIN ARCHITECTURE (Phase 3)
# ═══════════════════════════════════════════════════════════════════

PLUGIN_DIR = os.path.join(PROJECT_ROOT, "actions")


# ═══════════════════════════════════════════════════════════════════
# CONTINUOUS LISTENING (Phase 3)
# ═══════════════════════════════════════════════════════════════════

CONTINUOUS_LISTEN_TIMEOUT = 30    # seconds of silence before exiting
ESCAPE_HOTKEY = "escape"          # exit continuous listening
STOP_PHRASES = [
    "stop listening", "go idle", "sleep", "stop",
    "go to sleep", "that's all", "thats all", "nevermind",
]


# ═══════════════════════════════════════════════════════════════════
# PERMISSION TIERS (Phase 3)
# ═══════════════════════════════════════════════════════════════════

PERMISSION_TIERS = {
    "SAFE": [
        "open_app", "close_app", "calculate", "set_timer", "set_alarm",
        "search_google", "open_website", "open_youtube_video",
        "play_youtube_music", "open_folder", "search_file",
        "open_recent_files", "screenshot_desktop", "play_music",
        "pause_media", "resume_media", "recall_last_action",
        "browse_and_extract", "take_page_screenshot",
        "summarize_text", "list_scheduled_tasks",
    ],
    "MODERATE": [
        "create_folder", "move_file", "write_document",
        "generate_email", "fill_web_form", "click_element",
        "set_preference", "schedule_reminder",
    ],
    "DANGEROUS": [
        "delete_file", "shutdown_system", "restart_system",
        "cancel_scheduled_task",
    ],
}

