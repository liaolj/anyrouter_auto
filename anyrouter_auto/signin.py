"""Client for AnyRouter sign-in endpoint."""

from __future__ import annotations

import datetime as dt
import json
import logging
import time
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional

from .credentials import CredentialRecord

SIGNIN_ENDPOINT = "https://anyrouter.top/api/checkin"
CSRF_ENDPOINT = "https://anyrouter.top/api/session"
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SignInResult:
    success: bool
    message: str
    reward: Optional[str]
    timestamp: float


class SignInClient:
    """Perform authenticated requests against AnyRouter."""

    def __init__(self, user_agent: str | None = None) -> None:
        self._user_agent = user_agent or "anyrouter-auto/0.1"

    # ------------------------------------------------------------------
    def _build_request(self, url: str, token: str, method: str = "GET", data: Optional[Dict[str, str]] = None) -> urllib.request.Request:
        encoded = None
        if data:
            encoded = json.dumps(data).encode("utf-8")
        request = urllib.request.Request(url, data=encoded, method=method)
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("User-Agent", self._user_agent)
        if data:
            request.add_header("Content-Type", "application/json")
        return request

    # ------------------------------------------------------------------
    def fetch_csrf_token(self, record: CredentialRecord) -> Optional[str]:
        request = self._build_request(CSRF_ENDPOINT, record.access_token)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # nosec: B310
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network heavy
            LOGGER.warning("Failed to refresh session metadata: %s", exc)
            return None
        return payload.get("csrf_token")

    # ------------------------------------------------------------------
    def perform_sign_in(self, record: CredentialRecord) -> SignInResult:
        body = {"timestamp": int(time.time())}
        request = self._build_request(SIGNIN_ENDPOINT, record.access_token, method="POST", data=body)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:  # nosec: B310
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network heavy
            LOGGER.error("Sign-in request failed: %s", exc)
            raise
        reward = payload.get("reward")
        message = payload.get("message", "")
        success = bool(payload.get("success", False))
        timestamp = payload.get("timestamp")
        if timestamp is None:
            timestamp = time.time()
        return SignInResult(success=success, message=message, reward=reward, timestamp=float(timestamp))

    # ------------------------------------------------------------------
    @staticmethod
    def format_result(result: SignInResult) -> str:
        status = "SUCCESS" if result.success else "FAILED"
        when = dt.datetime.fromtimestamp(result.timestamp).isoformat()
        reward = result.reward or ""
        return f"[{when}] {status} {result.message} {reward}".strip()


__all__ = ["SignInClient", "SignInResult"]
