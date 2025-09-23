"""Simple daily scheduler for sign-in job."""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .config import AppPaths, ScheduleConfig

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ScheduleState:
    hour: int
    minute: int
    last_run: Optional[float] = None

    def to_payload(self) -> dict[str, int | float | None]:
        return {"hour": self.hour, "minute": self.minute, "last_run": self.last_run}

    @classmethod
    def from_payload(cls, payload: dict[str, int | float | None]) -> "ScheduleState":
        return cls(hour=int(payload["hour"]), minute=int(payload["minute"]), last_run=payload.get("last_run"))


class DailyScheduler:
    """Run a callable at a fixed daily time."""

    def __init__(self, callback: Callable[[], None], config: Optional[ScheduleConfig] = None, paths: Optional[AppPaths] = None) -> None:
        self._callback = callback
        self._config = config or ScheduleConfig.from_env()
        self._paths = paths or AppPaths()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    def _state_file(self) -> Path:
        return self._paths.schedule_file

    # ------------------------------------------------------------------
    def load_state(self) -> ScheduleState:
        path = self._state_file()
        if not path.exists():
            return ScheduleState(hour=self._config.hour, minute=self._config.minute)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return ScheduleState.from_payload(payload)
        except Exception:  # pragma: no cover - defensive parsing
            return ScheduleState(hour=self._config.hour, minute=self._config.minute)

    # ------------------------------------------------------------------
    def save_state(self, state: ScheduleState) -> None:
        payload = json.dumps(state.to_payload(), indent=2)
        self._state_file().write_text(payload, encoding="utf-8")

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        state = self.load_state()
        LOGGER.info("Scheduler started for %02d:%02d", state.hour, state.minute)
        while not self._stop_event.is_set():
            now = dt.datetime.now()
            target = now.replace(hour=state.hour, minute=state.minute, second=0, microsecond=0)
            if target <= now:
                target = target + dt.timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            LOGGER.debug("Next run at %s (%.0f seconds)", target.isoformat(), wait_seconds)
            finished = self._stop_event.wait(wait_seconds)
            if finished:
                break
            try:
                self._callback()
                state.last_run = time.time()
                self.save_state(state)
            except Exception as exc:  # pragma: no cover - runtime safety
                LOGGER.exception("Scheduled job failed: %s", exc)


__all__ = ["DailyScheduler", "ScheduleState"]
