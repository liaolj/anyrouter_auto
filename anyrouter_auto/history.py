"""Historical logging helpers for sign-in runs."""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from .config import AppPaths
from .signin import SignInResult


@dataclass(slots=True)
class HistoryRecord:
    timestamp: float
    status: str
    reward: str
    message: str

    def summary(self) -> str:
        when = dt.datetime.fromtimestamp(self.timestamp).isoformat()
        reward = f" reward={self.reward}" if self.reward else ""
        return f"[{when}] {self.status.upper()} {self.message}{reward}".strip()


class HistoryStore:
    """Persist sign-in outcomes in CSV format."""

    def __init__(self, paths: AppPaths | None = None) -> None:
        self._paths = paths or AppPaths()

    @property
    def csv_path(self) -> Path:
        self._paths.ensure()
        return self._paths.base_dir / "history.csv"

    def append(self, result: SignInResult) -> None:
        record = HistoryRecord(
            timestamp=result.timestamp,
            status="success" if result.success else "failure",
            reward=result.reward or "",
            message=result.message,
        )
        path = self.csv_path
        is_new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if is_new:
                writer.writerow(["timestamp", "status", "reward", "message"])
            writer.writerow([record.timestamp, record.status, record.reward, record.message])

    def load(self) -> List[HistoryRecord]:
        path = self.csv_path
        if not path.exists():
            return []
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            items: List[HistoryRecord] = []
            for row in reader:
                items.append(
                    HistoryRecord(
                        timestamp=float(row["timestamp"]),
                        status=row["status"],
                        reward=row.get("reward", ""),
                        message=row.get("message", ""),
                    )
                )
        return items

    def format(self, records: Iterable[HistoryRecord]) -> str:
        lines = ["timestamp,status,reward,message"]
        for item in records:
            when = dt.datetime.fromtimestamp(item.timestamp).isoformat()
            lines.append(f"{when},{item.status},{item.reward},{item.message}")
        return "\n".join(lines)


__all__ = ["HistoryStore", "HistoryRecord"]
