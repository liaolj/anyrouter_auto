"""Automation toolkit for AnyRouter daily sign-in."""

from __future__ import annotations

from importlib import resources

__all__ = ["__version__", "read_text_resource"]


def __version__() -> str:
    """Return package version.

    The version is stored in :mod:`anyrouter_auto.version` to keep the import
    graph lightweight for CLI usage. A fallback of ``"0.1.0"`` is returned when
    the version module is missing (for example during local development).
    """

    try:
        from .version import VERSION
    except Exception:  # pragma: no cover - defensive fallback
        return "0.1.0"
    return VERSION


def read_text_resource(package: str, name: str) -> str:
    """Read an embedded text resource from *package*.

    This helper is used by the CLI to ship default templates without touching
    the filesystem when running from a frozen binary.
    """

    return resources.files(package).joinpath(name).read_text(encoding="utf-8")
