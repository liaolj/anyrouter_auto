"""OAuth helpers for the AnyRouter automation CLI."""

from __future__ import annotations

import json
import secrets
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional

from .config import OAuthConfig
from .credentials import CredentialRecord, CredentialStore

AUTHORIZATION_ENDPOINT = "https://anyrouter.top/api/oauth/authorize"
TOKEN_ENDPOINT = "https://anyrouter.top/api/oauth/token"


@dataclass(slots=True)
class AuthorizationResult:
    code: str
    state: str
    received_at: float


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler capturing OAuth redirect parameters."""

    result: Optional[AuthorizationResult] = None
    expected_state: Optional[str] = None
    event: Optional[threading.Event] = None

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown path")
            return
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        if not code or not state:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing query parameters")
            return
        if self.expected_state and state != self.expected_state:
            self.send_error(HTTPStatus.UNAUTHORIZED, "State mismatch")
            return
        self.result = AuthorizationResult(code=code, state=state, received_at=time.time())
        if self.event:
            self.event.set()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<html><body>Authorization complete. You may close this window.</body></html>")

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - matching signature
        return


class AuthorizationFlow:
    """Drive OAuth authorization with minimal dependencies."""

    def __init__(self, config: OAuthConfig, store: CredentialStore) -> None:
        self._config = config
        self._store = store

    # ------------------------------------------------------------------
    def generate_state(self) -> str:
        return secrets.token_urlsafe(16)

    # ------------------------------------------------------------------
    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
            "scope": self._config.scope,
            "state": state,
        }
        query = urllib.parse.urlencode(params)
        return f"{AUTHORIZATION_ENDPOINT}?{query}"

    # ------------------------------------------------------------------
    def wait_for_callback(self, state: str, timeout: float = 300.0) -> AuthorizationResult:
        event = threading.Event()
        CallbackHandler.expected_state = state
        CallbackHandler.event = event
        server = HTTPServer((self._config.redirect_host, self._config.redirect_port), CallbackHandler)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        finished = event.wait(timeout)
        server.server_close()
        if not finished or CallbackHandler.result is None:
            raise TimeoutError("Authorization callback not received")
        result = CallbackHandler.result
        CallbackHandler.result = None
        return result

    # ------------------------------------------------------------------
    def exchange_code(self, result: AuthorizationResult) -> CredentialRecord:
        payload = urllib.parse.urlencode(
            {
                "client_id": self._config.client_id,
                "redirect_uri": self._config.redirect_uri,
                "grant_type": "authorization_code",
                "code": result.code,
            }
        ).encode("utf-8")
        request = urllib.request.Request(TOKEN_ENDPOINT, data=payload, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec: B310 - target controlled by user
            content = response.read()
        data: Dict[str, str] = json.loads(content.decode("utf-8"))
        expires_in = data.get("expires_in")
        expires_at = time.time() + float(expires_in) if expires_in else None
        record = CredentialRecord(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            scope=data.get("scope"),
            client_id=self._config.client_id,
        )
        self._store.save(record)
        return record

    # ------------------------------------------------------------------
    def refresh(self, record: CredentialRecord) -> CredentialRecord:
        if not record.refresh_token:
            raise RuntimeError("Refresh token missing; re-run authorization")
        payload = urllib.parse.urlencode(
            {
                "client_id": self._config.client_id,
                "redirect_uri": self._config.redirect_uri,
                "grant_type": "refresh_token",
                "refresh_token": record.refresh_token,
            }
        ).encode("utf-8")
        request = urllib.request.Request(TOKEN_ENDPOINT, data=payload, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec: B310
            content = response.read()
        data: Dict[str, str] = json.loads(content.decode("utf-8"))
        expires_in = data.get("expires_in")
        record.access_token = data["access_token"]
        record.refresh_token = data.get("refresh_token", record.refresh_token)
        record.expires_at = time.time() + float(expires_in) if expires_in else None
        record.scope = data.get("scope", record.scope)
        self._store.save(record)
        return record


__all__ = ["AuthorizationFlow", "AuthorizationResult"]
