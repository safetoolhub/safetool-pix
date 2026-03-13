#!/usr/bin/env python3
# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Build verification script for SafeTool Pix.

Runs a series of import and functional checks against the PyInstaller binary
to detect missing dependencies before release.

Usage:
    python dev-tools/verify_build.py                     # Auto-detect binary
    python dev-tools/verify_build.py dist/safetool-pix   # Explicit path

Exit codes:
    0 = All checks passed
    1 = One or more checks failed
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Check definitions ────────────────────────────────────────────────────────
# Each check is a Python snippet executed inside the binary's Python runtime.
# The snippet must print "OK" on success or raise/print an error on failure.

IMPORT_CHECKS = [
    # (name, python_code)
    ("imagehash", "import imagehash; print('OK')"),
    ("scipy", "import scipy; print('OK')"),
    ("scipy.fftpack", "import scipy.fftpack; print('OK')"),
    ("pywt", "import pywt; print('OK')"),
    ("numpy", "import numpy; print('OK')"),
    ("numpy.fft", "import numpy.fft; print('OK')"),
    ("PIL.Image", "from PIL import Image; print('OK')"),
    ("PyQt6.QtCore", "from PyQt6.QtCore import QCoreApplication; print('OK')"),
    ("PyQt6.QtWidgets", "from PyQt6.QtWidgets import QApplication; print('OK')"),
    ("PyQt6.QtSvg", "from PyQt6.QtSvg import QSvgRenderer; print('OK')"),
    ("sqlite3", "import sqlite3; print('OK')"),
    ("unittest", "import unittest; print('OK')"),
]

FUNCTIONAL_CHECKS = [
    (
        "imagehash.phash",
        "from PIL import Image; import imagehash; "
        "img = Image.new('RGB', (64, 64), 'red'); "
        "h = imagehash.phash(img, hash_size=16); "
        "assert h is not None; print('OK')"
    ),
    (
        "imagehash.dhash",
        "from PIL import Image; import imagehash; "
        "img = Image.new('RGB', (64, 64), 'blue'); "
        "h = imagehash.dhash(img, hash_size=8); "
        "assert h is not None; print('OK')"
    ),
    (
        "imagehash.average_hash",
        "from PIL import Image; import imagehash; "
        "img = Image.new('RGB', (64, 64), 'green'); "
        "h = imagehash.average_hash(img, hash_size=8); "
        "assert h is not None; print('OK')"
    ),
    # NOTE: App-specific checks (config, i18n, translations) cannot be tested
    # by importing from _internal — they only work inside the frozen binary.
    # The binary smoke test (--verify flag) covers these.
]


def find_binary() -> Path:
    """Auto-detect the PyInstaller binary in dist/."""
    if sys.platform == "win32":
        candidates = [ROOT / "dist" / "SafeToolPix" / "SafeToolPix.exe"]
    elif sys.platform == "darwin":
        candidates = [ROOT / "dist" / "SafeToolPix" / "SafeToolPix"]
    else:
        candidates = [ROOT / "dist" / "safetool-pix" / "safetool-pix"]

    for c in candidates:
        if c.exists():
            return c

    raise FileNotFoundError(
        f"No binary found. Looked in: {[str(c) for c in candidates]}. "
        f"Run 'python dev-tools/build.py --skip-installer' first."
    )


def run_check_in_binary(binary: Path, name: str, code: str) -> tuple[bool, str]:
    """
    Run a Python code snippet inside the PyInstaller binary's runtime.
    
    Uses the binary's internal Python by writing a temp script and running it
    via the binary's _internal python path, or falls back to subprocess.
    """
    # Method: create a verification script that the binary executes
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False, prefix='ipx_verify_'
    ) as f:
        f.write(code)
        script_path = f.name

    try:
        # Run the check script using the binary's bundled Python runtime
        # PyInstaller binaries can execute Python scripts if we use the
        # internal Python. But that's complex. Instead, we test by running
        # the binary's Python via its _internal directory.
        internal_dir = binary.parent / "_internal"
        
        # Find Python in _internal (PyInstaller bundles it)
        python_candidates = []
        if sys.platform == "win32":
            python_candidates = [internal_dir / "python.exe", internal_dir / "python3.exe"]
        else:
            python_candidates = list(internal_dir.glob("python3*")) + list(internal_dir.glob("python*"))
            # Filter out .so files
            python_candidates = [p for p in python_candidates if p.is_file() and not p.suffix == '.so']

        python_exe = None
        for candidate in python_candidates:
            if candidate.exists() and os.access(str(candidate), os.X_OK):
                python_exe = candidate
                break

        if python_exe:
            # Use the bundled Python directly
            env = os.environ.copy()
            # Set PYTHONPATH to include the _internal directory
            env["PYTHONPATH"] = str(internal_dir)
            result = subprocess.run(
                [str(python_exe), script_path],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                cwd=str(binary.parent),
            )
        else:
            # Fallback: run the system Python with the binary's _internal on sys.path
            # This simulates the binary environment
            wrapper_code = (
                f"import sys; sys.path.insert(0, {str(internal_dir)!r}); "
                f"exec(open({script_path!r}).read())"
            )
            result = subprocess.run(
                [sys.executable, "-c", wrapper_code],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(binary.parent),
            )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode == 0 and "OK" in stdout:
            return True, ""
        else:
            error_msg = stderr if stderr else stdout if stdout else f"exit code {result.returncode}"
            return False, error_msg

    except subprocess.TimeoutExpired:
        return False, "timeout (30s)"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def run_binary_smoke_test(binary: Path) -> tuple[bool, str]:
    """
    Run the actual binary with --verify flag for a quick smoke test.
    The binary should exit 0 if basic initialization works.
    """
    try:
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        result = subprocess.run(
            [str(binary), "--verify"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode == 0 and "VERIFY_OK" in stdout:
            return True, ""
        else:
            msg = stderr if stderr else stdout if stdout else f"exit code {result.returncode}"
            return False, msg
    except subprocess.TimeoutExpired:
        return False, "binary smoke test timed out (30s)"
    except Exception as e:
        return False, str(e)


def verify_build(binary_path: Path = None, json_output: bool = False) -> bool:
    """
    Run all verification checks against the binary.
    
    Returns True if all checks passed.
    """
    if binary_path is None:
        binary_path = find_binary()
    elif binary_path.is_dir():
        # If a directory is given, look for the binary inside
        if sys.platform in ("win32",):
            binary_path = binary_path / "SafeToolPix.exe"
        elif sys.platform == "darwin":
            binary_path = binary_path / "SafeToolPix"
        else:
            binary_path = binary_path / "safetool-pix"

    if not binary_path.exists():
        print(f"ERROR: Binary not found at {binary_path}")
        return False

    print(f"\n{'='*60}")
    print(f"  Build Verification: {binary_path}")
    print(f"{'='*60}\n")

    results = {}
    all_passed = True

    # 1. Basic binary check
    print("── Binary checks ──")
    if binary_path.stat().st_size < 1_000_000:
        print(f"  WARN  Binary is suspiciously small ({binary_path.stat().st_size} bytes)")

    internal_dir = binary_path.parent / "_internal"
    if internal_dir.exists():
        print(f"  OK    _internal directory exists")
    else:
        print(f"  FAIL  _internal directory missing")
        all_passed = False

    # 2. Import checks
    print("\n── Import checks ──")
    for name, code in IMPORT_CHECKS:
        passed, error = run_check_in_binary(binary_path, name, code)
        status = "OK  " if passed else "FAIL"
        results[f"import.{name}"] = {"passed": passed, "error": error}
        if passed:
            print(f"  {status}  {name}")
        else:
            print(f"  {status}  {name}: {error}")
            all_passed = False

    # 3. Functional checks
    print("\n── Functional checks ──")
    for name, code in FUNCTIONAL_CHECKS:
        passed, error = run_check_in_binary(binary_path, name, code)
        status = "OK  " if passed else "FAIL"
        results[f"func.{name}"] = {"passed": passed, "error": error}
        if passed:
            print(f"  {status}  {name}")
        else:
            print(f"  {status}  {name}: {error}")
            all_passed = False

    # 4. Binary smoke test
    print("\n── Binary smoke test ──")
    passed, error = run_binary_smoke_test(binary_path)
    results["smoke_test"] = {"passed": passed, "error": error}
    if passed:
        print(f"  OK    Binary starts and initializes correctly")
    else:
        print(f"  FAIL  Binary smoke test: {error}")
        all_passed = False

    # Summary
    total = len(results)
    passed_count = sum(1 for r in results.values() if r["passed"])
    failed_count = total - passed_count

    print(f"\n{'='*60}")
    if all_passed:
        print(f"  PASSED: All {total} checks passed")
    else:
        print(f"  FAILED: {failed_count}/{total} checks failed")
    print(f"{'='*60}\n")

    if json_output:
        print(json.dumps(results, indent=2))

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Verify SafeTool Pix build")
    parser.add_argument(
        "binary_path", nargs="?", type=Path, default=None,
        help="Path to the binary or its directory (auto-detected if omitted)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results in JSON format"
    )
    args = parser.parse_args()

    try:
        success = verify_build(args.binary_path, json_output=args.json)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
