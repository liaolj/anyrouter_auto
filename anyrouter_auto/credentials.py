"""Credential storage with lightweight XOR-based protection."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from .config import AppPaths


@dataclass(slots=True)
class CredentialRecord:
    """Persisted tokens required to call AnyRouter endpoints."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    scope: Optional[str] = None
    client_id: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at

    def to_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        return {k: v for k, v in payload.items() if v is not None}

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "CredentialRecord":
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=payload.get("expires_at"),
            scope=payload.get("scope"),
            client_id=payload.get("client_id"),
        )


class CredentialStore:
    """Store credentials on disk with optional passphrase obfuscation.

    The implementation intentionally avoids heavyweight dependencies. When the
    ``passphrase`` argument is provided the JSON payload is XOR-masked with a key
    derived from the passphrase. The mechanism is not intended to compete with
    industry-grade encryption but merely to prevent accidental disclosure of the
    token contents. Users should place stronger secrets into their OS keychain if
    required.
    """

    def __init__(self, paths: Optional[AppPaths] = None, passphrase: str | None = None) -> None:
        self._paths = paths or AppPaths()
        self._passphrase = passphrase or ""

    # ------------------------------------------------------------------
    def load(self) -> Optional[CredentialRecord]:
        path = self._paths.credentials_file
        if not path.exists():
            return None
        data = path.read_bytes()
        payload = self._decode(data)
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return CredentialRecord.from_payload(raw)

    # ------------------------------------------------------------------
    def save(self, record: CredentialRecord) -> None:
        path = self._paths.credentials_file
        payload = json.dumps(record.to_payload(), indent=2, sort_keys=True)
        path.write_bytes(self._encode(payload))

    # ------------------------------------------------------------------
    def clear(self) -> None:
        path = self._paths.credentials_file
        if path.exists():
            path.unlink()

    # ------------------------------------------------------------------
    def _encode(self, text: str) -> bytes:
        buffer = text.encode("utf-8")
        if not self._passphrase:
            return buffer
        key = _derive_key(self._passphrase, len(buffer))
        return bytes(b ^ k for b, k in zip(buffer, key))

    # ------------------------------------------------------------------
    def _decode(self, data: bytes) -> str:
        if not self._passphrase:
            return data.decode("utf-8")
        key = _derive_key(self._passphrase, len(data))
        buffer = bytes(b ^ k for b, k in zip(data, key))
        return buffer.decode("utf-8")


def _derive_key(passphrase: str, size: int) -> bytes:
    # Simple derivation using repeated SHA256 digests.
    import hashlib

    digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
    key = bytearray()
    while len(key) < size:
        key.extend(digest)
        digest = hashlib.sha256(digest).digest()
    return bytes(key[:size])


__all__ = ["CredentialRecord", "CredentialStore"]
