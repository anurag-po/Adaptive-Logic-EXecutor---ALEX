"""
ALEX — System Actions
open_app, close_app, shutdown_system, restart_system
"""

import os
import subprocess
import shutil
from utils.helpers import get_logger

logger = get_logger()

# Common Windows app name → executable mapping
APP_ALIASES = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
    "settings": "ms-settings:",
    "snipping tool": "SnippingTool.exe",
    "wordpad": "wordpad.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "slack": "slack.exe",
    "teams": "ms-teams.exe",
    "microsoft teams": "ms-teams.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
}


def open_app(app_name: str) -> str:
    """Open an application by name."""
    app_lower = app_name.lower().strip()

    # Check alias table first
    exe = APP_ALIASES.get(app_lower)

    if exe:
        # Handle ms-settings: URI scheme
        if exe.startswith("ms-"):
            os.startfile(exe)
            logger.info(f"Opened {app_name} via URI: {exe}")
            return f"Opened {app_name}."

        # Try to find and launch the executable
        exe_path = shutil.which(exe)
        if exe_path:
            subprocess.Popen([exe_path], shell=False)
            logger.info(f"Opened {app_name} ({exe_path})")
            return f"Opened {app_name}."

        # Try direct launch (Windows might find it)
        try:
            subprocess.Popen([exe], shell=True)
            logger.info(f"Opened {app_name} via shell ({exe})")
            return f"Opened {app_name}."
        except FileNotFoundError:
            pass

    # Fallback: try os.startfile with the raw name
    try:
        os.startfile(app_lower)
        return f"Opened {app_name}."
    except OSError:
        pass

    # Last resort: search Start Menu
    try:
        subprocess.Popen(
            f'start "" "{app_name}"', shell=True
        )
        return f"Attempted to open {app_name}."
    except Exception as e:
        logger.error(f"Could not open {app_name}: {e}")
        return f"Could not find or open {app_name}."


def close_app(app_name: str) -> str:
    """Close an application by name."""
    app_lower = app_name.lower().strip()
    exe = APP_ALIASES.get(app_lower, f"{app_lower}.exe")

    try:
        result = subprocess.run(
            ["taskkill", "/IM", exe, "/F"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            logger.info(f"Closed {app_name} ({exe})")
            return f"Closed {app_name}."
        else:
            logger.warning(f"taskkill failed for {exe}: {result.stderr}")
            return f"Could not close {app_name}. It may not be running."
    except Exception as e:
        logger.error(f"Error closing {app_name}: {e}")
        return f"Error closing {app_name}: {e}"


def shutdown_system() -> str:
    """Shutdown the system with a 5-second delay."""
    logger.warning("SHUTDOWN requested")
    os.system("shutdown /s /t 5")
    return "System will shut down in 5 seconds."


def restart_system() -> str:
    """Restart the system with a 5-second delay."""
    logger.warning("RESTART requested")
    os.system("shutdown /r /t 5")
    return "System will restart in 5 seconds."
