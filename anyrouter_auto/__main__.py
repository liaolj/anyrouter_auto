"""Command line interface for AnyRouter automation."""

from __future__ import annotations

import argparse
import logging
import sys
import time
import webbrowser

from .browser import PlaywrightLauncher
from .auth import AuthorizationFlow
from .config import OAuthConfig, get_client_id
from .credentials import CredentialRecord, CredentialStore
from .history import HistoryStore
from .scheduler import DailyScheduler
from .signin import SignInClient

LOGGER = logging.getLogger("anyrouter_auto")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automate AnyRouter daily sign-in")
    sub = parser.add_subparsers(dest="command", required=True)

    authorize = sub.add_parser("authorize", help="Start OAuth authorization")
    authorize.add_argument("--client-id", help="GitHub OAuth client id", default=None)
    authorize.add_argument("--passphrase", help="Optional passphrase for credential storage")

    signin = sub.add_parser("signin", help="Execute the sign-in flow once")
    signin.add_argument("--passphrase", help="Passphrase used during authorization")

    status = sub.add_parser("status", help="Show credential & history state")
    status.add_argument("--passphrase", help="Passphrase used during authorization")
    status.add_argument("--limit", type=int, default=10, help="Number of history entries to show")

    schedule = sub.add_parser("schedule", help="Start background scheduler")
    schedule.add_argument("--passphrase", help="Passphrase used during authorization")

    clear = sub.add_parser("clear", help="Remove stored credentials")

    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _load_store(passphrase: str | None) -> CredentialStore:
    return CredentialStore(passphrase=passphrase)


def cmd_authorize(args: argparse.Namespace) -> None:
    client_id = args.client_id or get_client_id()
    if not client_id:
        print("ANYROUTER_CLIENT_ID missing. Provide via --client-id or environment.", file=sys.stderr)
        sys.exit(1)
    store = _load_store(args.passphrase)
    config = OAuthConfig(client_id=client_id)
    flow = AuthorizationFlow(config, store)
    state = flow.generate_state()
    url = flow.build_authorization_url(state)
    print("Open the following URL in your browser to authorize:")
    print(url)
    launcher = PlaywrightLauncher()
    launched = False
    try:
        launched = launcher.open(url)
        if launched:
            print("Playwright browser launched. Complete the GitHub login in the opened window.")
    except Exception as exc:  # pragma: no cover - depends on runtime Playwright setup
        LOGGER.warning("Unable to launch Playwright browser: %s", exc)
        launched = False
    if not launched:
        webbrowser.open(url)
        print("Falling back to the system browser.")
    print("Waiting for callback...")
    try:
        result = flow.wait_for_callback(state)
    except TimeoutError as exc:
        if launched:
            launcher.close()
        print(f"Authorization timed out: {exc}", file=sys.stderr)
        sys.exit(2)
    finally:
        if launched:
            launcher.close()
    record = flow.exchange_code(result)
    print("Authorization succeeded. Access token stored.")
    if record.expires_at:
        print(f"Token expires at {record.expires_at}")


def _ensure_credentials(store: CredentialStore, flow: AuthorizationFlow) -> CredentialRecord:
    record = store.load()
    if record is None:
        raise RuntimeError("Credentials missing. Run authorize first.")
    if record.is_expired:
        LOGGER.info("Access token expired. Refreshing...")
        record = flow.refresh(record)
    return record


def cmd_signin(args: argparse.Namespace) -> None:
    client_id = get_client_id()
    if not client_id:
        print("ANYROUTER_CLIENT_ID missing in environment. Needed for refresh operations.", file=sys.stderr)
    store = _load_store(args.passphrase)
    flow = AuthorizationFlow(OAuthConfig(client_id=client_id or ""), store)
    try:
        record = _ensure_credentials(store, flow)
    except Exception as exc:
        print(f"Unable to load credentials: {exc}", file=sys.stderr)
        sys.exit(1)
    client = SignInClient()
    result = client.perform_sign_in(record)
    HistoryStore().append(result)
    print(SignInClient.format_result(result))


def cmd_status(args: argparse.Namespace) -> None:
    store = _load_store(args.passphrase)
    record = store.load()
    if not record:
        print("No credentials stored.")
    else:
        status = "expired" if record.is_expired else "valid"
        print(f"Access token: {record.access_token[:6]}... status={status}")
        if record.expires_at:
            print(f"Expires at: {record.expires_at}")
    history = HistoryStore().load()
    print("Recent history:")
    for item in history[-args.limit :]:
        print(f"- {item.summary()}")


def cmd_schedule(args: argparse.Namespace) -> None:
    store = _load_store(args.passphrase)
    client_id = get_client_id()
    if not client_id:
        print("ANYROUTER_CLIENT_ID missing in environment. Needed for refresh operations.", file=sys.stderr)
    flow = AuthorizationFlow(OAuthConfig(client_id=client_id or ""), store)

    def job() -> None:
        record = _ensure_credentials(store, flow)
        client = SignInClient()
        result = client.perform_sign_in(record)
        HistoryStore().append(result)
        LOGGER.info("%s", SignInClient.format_result(result))

    scheduler = DailyScheduler(job)
    scheduler.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping scheduler...")
        scheduler.stop()


def cmd_clear(args: argparse.Namespace) -> None:
    store = CredentialStore()
    store.clear()
    print("Stored credentials removed.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    command = args.command
    if command == "authorize":
        cmd_authorize(args)
    elif command == "signin":
        cmd_signin(args)
    elif command == "status":
        cmd_status(args)
    elif command == "schedule":
        cmd_schedule(args)
    elif command == "clear":
        cmd_clear(args)
    else:  # pragma: no cover - argparse enforces choices
        parser.error(f"Unknown command {command}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
