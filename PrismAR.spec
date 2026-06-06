# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build specification for PrismAR.

Build with:
    python -m PyInstaller --noconfirm --clean PrismAR.spec

This spec intentionally builds a one-file, windowed Windows desktop executable
named PrismAR.exe and bundles the assets folder for MediaPipe Tasks.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path(SPECPATH)


def safe_collect_data_files(package_name):
    try:
        return collect_data_files(package_name)
    except Exception:
        return []


def safe_collect_submodules(package_name):
    try:
        return collect_submodules(package_name)
    except Exception:
        return []


def safe_copy_metadata(package_name):
    try:
        return copy_metadata(package_name)
    except Exception:
        return []


datas = []
hiddenimports = []

assets_dir = project_root / "assets"
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

# MediaPipe dynamically imports several modules and ships data files that
# PyInstaller may not discover automatically, especially with the Tasks API.
datas += safe_collect_data_files("mediapipe")
datas += safe_copy_metadata("mediapipe")
hiddenimports += safe_collect_submodules("mediapipe")
hiddenimports += [
    "mediapipe.tasks",
    "mediapipe.tasks.python",
    "mediapipe.tasks.python.vision",
    "mediapipe.tasks.python.vision.hand_landmarker",
    "mediapipe.tasks.python.vision.core",
]

# OpenCV's PyInstaller hook usually handles cv2, but explicit collection keeps
# the spec resilient across PyInstaller/OpenCV releases.
hiddenimports += safe_collect_submodules("cv2")

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PrismAR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
