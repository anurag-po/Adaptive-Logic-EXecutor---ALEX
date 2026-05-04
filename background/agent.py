"""
ALEX -- Background Agent (Phase 3)
Scheduler for deferred and periodic background tasks.
Supports one-shot reminders and recurring tasks.
Notifies via TTS + overlay state pulse.
"""

import threading
import time
import uuid
from datetime import datetime, timedelta
from utils.helpers import get_logger

logger = get_logger()


class ScheduledTask:
    """Represents a single scheduled task."""

    def __init__(self, task_id: str, message: str, fire_at: float,
                 recurring: bool = False, interval: float = 0):
        self.task_id = task_id
        self.message = message
        self.fire_at = fire_at          # Unix timestamp
        self.recurring = recurring
        self.interval = interval        # seconds (for recurring)
        self.cancelled = False

    def __lt__(self, other):
        return self.fire_at < other.fire_at


class BackgroundAgent:
    """
    Manages background scheduled tasks (reminders, periodic checks).
    Runs a daemon thread that checks for due tasks.
    """

    def __init__(self, notify_callback=None):
        """
        Args:
            notify_callback: callable(message: str) -- called when a task fires.
                             Typically speaks the message via TTS.
        """
        self._tasks: dict[str, ScheduledTask] = {}
        self._lock = threading.Lock()
        self._notify = notify_callback
        self._running = True
        self._counter = 0

        # Start the scheduler thread
        self._thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self._thread.start()
        logger.info("Background agent started.")

    def schedule_reminder(self, message: str, delay_minutes: int = 1) -> str:
        """
        Schedule a one-shot reminder.

        Args:
            message: The reminder message to speak.
            delay_minutes: Minutes from now to fire.

        Returns:
            Confirmation string with task ID.
        """
        try:
            delay_minutes = float(delay_minutes)
        except (TypeError, ValueError):
            return "Invalid delay value."

        if delay_minutes <= 0:
            return "Delay must be positive."

        task_id = self._generate_id()
        fire_at = time.time() + (delay_minutes * 60)

        task = ScheduledTask(
            task_id=task_id,
            message=message,
            fire_at=fire_at,
        )

        with self._lock:
            self._tasks[task_id] = task

        fire_time = datetime.fromtimestamp(fire_at).strftime("%I:%M %p")
        logger.info(f"Reminder scheduled: '{message}' at {fire_time} (ID: {task_id})")

        if delay_minutes >= 60:
            time_str = f"{int(delay_minutes // 60)} hour(s) and {int(delay_minutes % 60)} minutes"
        elif delay_minutes == 1:
            time_str = "1 minute"
        else:
            time_str = f"{int(delay_minutes)} minutes"

        return (
            f"Reminder set for {time_str} from now ({fire_time}). "
            f"Task ID: {task_id}"
        )

    def list_scheduled_tasks(self) -> str:
        """List all active scheduled tasks."""
        with self._lock:
            active = [
                t for t in self._tasks.values() if not t.cancelled
            ]

        if not active:
            return "No scheduled tasks."

        lines = [f"Active tasks ({len(active)}):"]
        for t in sorted(active):
            fire_str = datetime.fromtimestamp(t.fire_at).strftime("%I:%M %p")
            remaining = max(0, t.fire_at - time.time())
            mins_left = int(remaining / 60)
            lines.append(
                f"  [{t.task_id}] '{t.message}' "
                f"at {fire_str} ({mins_left} min left)"
            )

        return "\n".join(lines)

    def cancel_scheduled_task(self, task_id: str) -> str:
        """Cancel a scheduled task by ID."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and not task.cancelled:
                task.cancelled = True
                logger.info(f"Task cancelled: {task_id}")
                return f"Task {task_id} cancelled."

        return f"No active task found with ID '{task_id}'."

    def get_active_count(self) -> int:
        """Get the number of active (not cancelled, not fired) tasks."""
        with self._lock:
            return sum(
                1 for t in self._tasks.values()
                if not t.cancelled and t.fire_at > time.time()
            )

    def stop(self):
        """Stop the scheduler thread."""
        self._running = False

    # -- Internals -------------------------------------------------

    def _scheduler_loop(self):
        """Main scheduler loop -- checks for due tasks every second."""
        while self._running:
            time.sleep(1)
            now = time.time()

            with self._lock:
                fired_ids = []
                for task_id, task in self._tasks.items():
                    if task.cancelled:
                        fired_ids.append(task_id)
                        continue

                    if task.fire_at <= now:
                        # Fire the task
                        self._fire_task(task)

                        if task.recurring:
                            task.fire_at = now + task.interval
                        else:
                            fired_ids.append(task_id)

                # Clean up fired/cancelled tasks
                for tid in fired_ids:
                    del self._tasks[tid]

    def _fire_task(self, task: ScheduledTask):
        """Execute a due task -- notify via callback."""
        logger.info(f"Task fired: [{task.task_id}] {task.message}")

        if self._notify:
            try:
                self._notify(f"Reminder: {task.message}")
            except Exception as e:
                logger.error(f"Task notification failed: {e}")
        else:
            # Fallback: system beep
            try:
                import winsound
                winsound.Beep(1200, 400)
            except Exception:
                pass

    def _generate_id(self) -> str:
        """Generate a short human-readable task ID."""
        self._counter += 1
        return f"T{self._counter:03d}"
