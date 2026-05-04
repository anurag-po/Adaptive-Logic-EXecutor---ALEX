"""
ALEX — Utility Actions
calculate, set_timer, set_alarm, screenshot_desktop
"""

import os
import ast
import time
import threading
from datetime import datetime, timedelta
from utils.helpers import get_logger

logger = get_logger()

# Store active timers/alarms for potential cancellation
_active_timers = []


def calculate(expression: str) -> str:
    """
    Safely evaluate a mathematical expression.
    Uses ast.parse to validate before eval for safety.
    """
    try:
        # Sanitize: only allow math operations
        allowed_chars = set("0123456789+-*/().% ")
        if not all(c in allowed_chars for c in expression):
            return f"Invalid characters in expression: {expression}"

        # Parse and validate AST
        tree = ast.parse(expression, mode="eval")
        for node in ast.walk(tree):
            if isinstance(node, (ast.Call, ast.Attribute, ast.Import)):
                return "Unsafe expression detected. Only basic math is allowed."

        result = eval(compile(tree, "<calc>", "eval"))
        logger.info(f"Calculated: {expression} = {result}")
        return f"{expression} = {result}"
    except ZeroDivisionError:
        return "Error: Division by zero."
    except Exception as e:
        return f"Calculation error: {e}"


def set_timer(seconds: int) -> str:
    """Set a countdown timer that notifies when complete."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "Invalid timer duration."

    if seconds <= 0:
        return "Timer duration must be positive."

    def _timer_callback():
        logger.info(f"Timer complete! ({seconds} seconds)")
        # On Windows, play a system beep
        try:
            import winsound
            winsound.Beep(1000, 500)
            winsound.Beep(1200, 500)
        except Exception:
            print("\a")  # Terminal bell fallback

    timer = threading.Timer(seconds, _timer_callback)
    timer.daemon = True
    timer.start()
    _active_timers.append(timer)

    if seconds >= 60:
        mins = seconds // 60
        secs = seconds % 60
        time_str = f"{mins} minute{'s' if mins != 1 else ''}"
        if secs:
            time_str += f" and {secs} seconds"
    else:
        time_str = f"{seconds} seconds"

    logger.info(f"Timer set for {time_str}")
    return f"Timer set for {time_str}."


def set_alarm(time_str: str, label: str = None) -> str:
    """
    Set an alarm for a specific time (HH:MM format, 24h or 12h).
    """
    try:
        # Try parsing various time formats
        now = datetime.now()
        target = None

        for fmt in ["%H:%M", "%I:%M %p", "%I:%M%p", "%H:%M:%S"]:
            try:
                parsed = datetime.strptime(time_str.strip(), fmt)
                target = now.replace(
                    hour=parsed.hour, minute=parsed.minute,
                    second=0, microsecond=0
                )
                break
            except ValueError:
                continue

        if target is None:
            return f"Could not parse time: '{time_str}'. Use HH:MM format."

        # If target time has passed today, set for tomorrow
        if target <= now:
            target += timedelta(days=1)

        delay = (target - now).total_seconds()

        label_str = f" ({label})" if label else ""

        def _alarm_callback():
            logger.info(f"ALARM! {time_str}{label_str}")
            try:
                import winsound
                for _ in range(3):
                    winsound.Beep(1500, 300)
                    winsound.Beep(1800, 300)
            except Exception:
                print("\a\a\a")

        timer = threading.Timer(delay, _alarm_callback)
        timer.daemon = True
        timer.start()
        _active_timers.append(timer)

        logger.info(f"Alarm set for {target.strftime('%H:%M')}{label_str}")
        return (
            f"Alarm set for {target.strftime('%I:%M %p')}"
            f"{label_str}."
        )

    except Exception as e:
        return f"Could not set alarm: {e}"


def screenshot_desktop(save_path: str = None, delay: int = 0) -> str:
    """Take a screenshot of the desktop."""
    try:
        delay = int(delay) if delay else 0
    except (TypeError, ValueError):
        delay = 0

    if delay > 0:
        logger.info(f"Screenshot in {delay} seconds...")
        time.sleep(delay)

    try:
        from PIL import ImageGrab

        screenshot = ImageGrab.grab()

        if not save_path:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(desktop, f"screenshot_{timestamp}.png")

        screenshot.save(save_path)
        logger.info(f"Screenshot saved: {save_path}")
        return f"Screenshot saved to {save_path}."

    except ImportError:
        return "Pillow is not installed. Cannot take screenshot."
    except Exception as e:
        return f"Screenshot failed: {e}"
