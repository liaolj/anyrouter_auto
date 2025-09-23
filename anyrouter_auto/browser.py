"""Browser helpers powered by Playwright for manual sign-in."""

from __future__ import annotations

import logging
import threading
from typing import Optional

LOGGER = logging.getLogger(__name__)


class PlaywrightLauncher:
    """Launch a non-headless Playwright browser in the background."""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._error: Optional[Exception] = None

    # ------------------------------------------------------------------
    def open(self, url: str) -> bool:
        """Open *url* in a Chromium browser window.

        Returns ``True`` when a Playwright-driven browser was launched. When
        Playwright is not available (for example because the optional
        dependency is missing) ``False`` is returned so the caller can fall
        back to other browser launching strategies.
        """

        if self._thread and self._thread.is_alive():
            LOGGER.debug("Playwright browser already running")
            return True

        try:
            from playwright.sync_api import sync_playwright
        except Exception:  # pragma: no cover - optional dependency
            LOGGER.debug("Playwright is not installed; falling back to system browser")
            return False

        self._stop.clear()
        self._ready.clear()
        self._stopped.clear()
        self._error = None

        def runner() -> None:
            browser = None
            context = None
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=False)
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto(url)
                    self._ready.set()
                    while not self._stop.wait(0.1):
                        pass
            except Exception as exc:  # pragma: no cover - relies on runtime browser availability
                self._error = exc
                LOGGER.error("Playwright session crashed: %%s", exc)
                self._ready.set()
            finally:
                try:
                    if context:
                        context.close()
                except Exception:  # pragma: no cover - best-effort cleanup
                    LOGGER.debug("Failed to close Playwright context", exc_info=True)
                try:
                    if browser:
                        browser.close()
                except Exception:  # pragma: no cover - best-effort cleanup
                    LOGGER.debug("Failed to close Playwright browser", exc_info=True)
                self._stopped.set()

        self._thread = threading.Thread(target=runner, name="playwright-launcher", daemon=True)
        self._thread.start()

        # Wait briefly for the browser to signal readiness or failure.
        if not self._ready.wait(timeout=5):
            LOGGER.warning("Timed out waiting for Playwright to start; falling back")
            self.close()
            return False
        if self._error:
            # Clean up resources and surface the exception to the caller.
            error = self._error
            self.close()
            raise RuntimeError("Playwright failed to start") from error
        return True

    # ------------------------------------------------------------------
    def close(self) -> None:
        """Stop the Playwright browser if it is running."""

        if not self._thread:
            return
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)
        if not self._stopped.is_set():
            # Give the worker thread a little more time before giving up.
            if not self._stopped.wait(timeout=1):
                LOGGER.debug("Playwright worker did not shut down cleanly")
        self._thread = None


__all__ = ["PlaywrightLauncher"]
