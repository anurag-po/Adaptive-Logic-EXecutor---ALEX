"""
ALEX — Media Actions (MVP Stubs)
play_music, pause_media, resume_media
Uses Windows media key simulation via ctypes for pause/resume.
"""

import ctypes
import webbrowser
from urllib.parse import quote_plus
from utils.helpers import get_logger

logger = get_logger()

# Windows virtual key codes for media keys
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_STOP = 0xB2
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _press_media_key(vk_code: int):
    """Simulate a media key press on Windows."""
    try:
        ctypes.windll.user32.keybd_event(
            vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0
        )
        ctypes.windll.user32.keybd_event(
            vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0
        )
    except Exception as e:
        logger.error(f"Media key simulation failed: {e}")


def play_music(song_name: str) -> str:
    """
    Play music by searching YouTube (MVP).
    In Phase 2, this can be upgraded to Spotify/local player integration.
    """
    url = (
        f"https://www.youtube.com/results?"
        f"search_query={quote_plus(song_name + ' music')}"
    )
    webbrowser.open(url)
    logger.info(f"Playing music: {song_name}")
    return f"Searching for '{song_name}' on YouTube."


def pause_media() -> str:
    """Pause the currently playing media."""
    _press_media_key(VK_MEDIA_PLAY_PAUSE)
    logger.info("Media paused")
    return "Media paused."


def resume_media() -> str:
    """Resume the currently playing media."""
    _press_media_key(VK_MEDIA_PLAY_PAUSE)
    logger.info("Media resumed")
    return "Media resumed."
