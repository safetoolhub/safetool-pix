# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for SafeTool Pix
# Supports Linux, Windows and macOS from a single spec file.

import os
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(SPECPATH).parent          # repo root (one level up from build/)
VERSION = os.environ.get("APP_VERSION", "0.0.0")

# ── Data files ───────────────────────────────────────────────────────────────
datas = [
    # Translations
    (str(ROOT / "i18n"),    "i18n"),
    # App assets (icon, etc.)
    (str(ROOT / "assets"),  "assets"),
    # License file (displayed in About → Information)
    (str(ROOT / "LICENSE"), "."),
]

# ── Hidden imports ───────────────────────────────────────────────────────────
# PyInstaller sometimes misses dynamic imports; enumerate them explicitly.
hidden_imports = [
    # PyQt6 core modules that may be referenced dynamically
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtSvg",
    "PyQt6.QtSvgWidgets",
    # Pillow
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "PIL.JpegImagePlugin",
    "PIL.PngImagePlugin",
    "PIL.BmpImagePlugin",
    "PIL.WebPImagePlugin",
    # imagehash (perceptual hashing) + its runtime dependencies.
    # PyInstaller doesn't auto-detect these because imagehash imports them
    # lazily (inside functions), causing them to appear as "conditional" imports.
    "imagehash",
    "scipy",
    "scipy.fftpack",
    "scipy.signal",
    "pywt",
    "pywt._extensions",
    "pywt._extensions._pywt",
    "numpy",
    "numpy.fft",
    # Standard library extras
    "sqlite3",
    "json",
    "logging.handlers",
    "email.mime.text",
]

# ── Exclude unnecessary modules to shrink the bundle ─────────────────────────
excludes = [
    "PyQt6.QtBluetooth",
    "PyQt6.QtNfc",
    "PyQt6.QtPositioning",
    "PyQt6.QtWebEngine",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebChannel",
    "tkinter",
    # NOTE: Do NOT exclude 'unittest' — numpy.testing imports it at module level
    # and PyInstaller bundles numpy.testing as part of numpy, causing runtime
    # failures in imagehash/scipy/pywt if unittest is excluded.
    # NOTE: Do NOT exclude 'distutils' — causes PyInstaller alias_module
    # conflict with setuptools vendored distutils.
    "test",
]

# ── Analysis ─────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ── Platform-specific output ──────────────────────────────────────────────────
if sys.platform == "darwin":
    # ── macOS: single .app bundle ────────────────────────────────────────────
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="SafeToolPix",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(ROOT / "assets" / "icon.icns"),
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="SafeToolPix",
    )
    app = BUNDLE(
        coll,
        name="SafeToolPix.app",
        icon=str(ROOT / "assets" / "icon.icns"),
        bundle_identifier="org.safetoolhub.safetoolpix",
        version=VERSION,
        info_plist={
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "CFBundleShortVersionString": VERSION,
        },
    )

elif sys.platform == "win32":
    # ── Windows: directory build (Inno Setup wraps it into an installer) ──────
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="SafeToolPix",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(ROOT / "assets" / "icon.ico"),
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="SafeToolPix",
    )

else:
    # ── Linux: directory build (dpkg/rpm wrap it) ────────────────────────────
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="safetool-pix",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(ROOT / "assets" / "icon.png"),
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="safetool-pix",
    )
