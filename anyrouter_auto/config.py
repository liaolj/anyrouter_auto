"""Configuration helpers for AnyRouter automation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_CALLBACK_PORT = 8765
DEFAULT_CALLBACK_HOST = "127.0.0.1"
DEFAULT_SCHEDULE_HOUR = 9


@dataclass(slots=True)
class AppPaths:
    """Resolve application directories lazily."""

    base_dir: Path = Path.home() / ".anyrouter_auto"

    def ensure(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def credentials_file(self) -> Path:
        self.ensure()
        return self.base_dir / "credentials.json"

    @property
    def schedule_file(self) -> Path:
        self.ensure()
        return self.base_dir / "schedule.json"


@dataclass(slots=True)
class OAuthConfig:
    """High-level OAuth settings for anyrouter.top GitHub login."""

    client_id: str
    redirect_host: str = DEFAULT_CALLBACK_HOST
    redirect_port: int = DEFAULT_CALLBACK_PORT
    scope: str = "read:user"

    @property
    def redirect_uri(self) -> str:
        return f"http://{self.redirect_host}:{self.redirect_port}/callback"


@dataclass(slots=True)
class ScheduleConfig:
    hour: int = DEFAULT_SCHEDULE_HOUR
    minute: int = 0

    @classmethod
    def from_env(cls) -> "ScheduleConfig":
        hour = int(os.environ.get("ANYROUTER_SCHEDULE_HOUR", DEFAULT_SCHEDULE_HOUR))
        minute = int(os.environ.get("ANYROUTER_SCHEDULE_MINUTE", 0))
        return cls(hour=hour, minute=minute)


def get_client_id() -> Optional[str]:
    """Return GitHub OAuth client id from environment or config file."""

    return os.environ.get("ANYROUTER_CLIENT_ID")
