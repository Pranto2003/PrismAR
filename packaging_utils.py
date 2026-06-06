"""
Runtime helpers for source and PyInstaller builds.

PyInstaller one-file apps extract bundled files into a temporary directory and
expose that directory as ``sys._MEIPASS``. Code that opens assets by normal
relative paths often breaks after packaging. These helpers centralize path
resolution so assets work in both development and frozen EXE modes.
"""

from pathlib import Path
import sys
from typing import Optional


APP_NAME = "PrismAR"
PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR_NAME = "assets"


def is_frozen() -> bool:
    """Return True when the app is running from a PyInstaller executable."""
    return bool(getattr(sys, "frozen", False))


def bundled_base_path() -> Path:
    """
    Return the base path for bundled read-only resources.

    In source mode this is the project folder. In a PyInstaller build this is
    the temporary extraction folder stored in ``sys._MEIPASS``.
    """
    return Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))


def executable_dir() -> Path:
    """
    Return the folder beside the EXE in frozen mode, or the project folder in
    source mode.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def resource_path(*parts: str) -> Path:
    """Return a path to a bundled read-only resource."""
    return bundled_base_path().joinpath(*parts)


def asset_path(filename: str) -> Path:
    """Return the expected bundled path for an asset file."""
    return resource_path(ASSETS_DIR_NAME, filename)


def external_asset_path(filename: str) -> Path:
    """
    Return a writable asset path next to the EXE or project.

    This is useful as a fallback when an optional asset was not bundled and must
    be downloaded or placed manually by the user.
    """
    return executable_dir() / ASSETS_DIR_NAME / filename


def find_existing_asset(filename: str) -> Optional[Path]:
    """
    Find an asset in the bundled app first, then beside the executable.

    Returning the bundled path first is important for one-file builds because
    the release ZIP only needs the EXE when assets are embedded.
    """
    candidates = (
        asset_path(filename),
        external_asset_path(filename),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def writable_asset_path(filename: str) -> Path:
    """Return a writable fallback location for an asset."""
    path = external_asset_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
