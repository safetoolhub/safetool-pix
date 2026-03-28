# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests for build verification.

These tests validate that the PyInstaller spec file and build output
include all required dependencies.

Tests are organized in two groups:
1. Spec validation: checks the .spec file without building (fast, always run)
2. Binary verification: checks built binary (slow, requires existing build)

Usage:
    # Run only spec validation (fast, no build needed):
    pytest tests/test_build_verification.py -k "TestSpecValidation" -v

    # Run binary tests (requires dist/safetool-pix to exist):
    pytest tests/test_build_verification.py -k "TestBinaryVerification" -v

    # Run all:
    pytest tests/test_build_verification.py -v
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = ROOT / "build" / "safetool-pix.spec"
DIST_DIR = ROOT / "dist"


class TestSpecValidation:
    """Validate the PyInstaller spec file has all required configuration."""

    def setup_method(self):
        """Read and parse the spec file."""
        assert SPEC_FILE.exists(), f"Spec file not found: {SPEC_FILE}"
        self.spec_content = SPEC_FILE.read_text()

    def test_spec_file_exists(self):
        assert SPEC_FILE.exists()

    def test_imagehash_in_hidden_imports(self):
        assert '"imagehash"' in self.spec_content

    def test_scipy_in_hidden_imports(self):
        assert '"scipy"' in self.spec_content

    def test_scipy_fftpack_in_hidden_imports(self):
        assert '"scipy.fftpack"' in self.spec_content

    def test_pywt_in_hidden_imports(self):
        assert '"pywt"' in self.spec_content

    def test_numpy_in_hidden_imports(self):
        assert '"numpy"' in self.spec_content

    def test_numpy_fft_in_hidden_imports(self):
        assert '"numpy.fft"' in self.spec_content

    def test_pil_in_hidden_imports(self):
        assert '"PIL"' in self.spec_content
        assert '"PIL.Image"' in self.spec_content

    def test_pyqt6_core_in_hidden_imports(self):
        assert '"PyQt6.QtCore"' in self.spec_content
        assert '"PyQt6.QtGui"' in self.spec_content
        assert '"PyQt6.QtWidgets"' in self.spec_content

    def test_unittest_not_excluded(self):
        """unittest must NOT be in excludes — numpy.testing needs it at runtime."""
        # Parse excludes list from spec
        in_excludes = False
        excludes_lines = []
        for line in self.spec_content.split('\n'):
            if 'excludes' in line and '=' in line and '[' in line:
                in_excludes = True
            if in_excludes:
                excludes_lines.append(line)
                if ']' in line:
                    break
        excludes_text = '\n'.join(excludes_lines)
        # "unittest" should not be in the excludes (as an active entry)
        # It might be in a comment which is fine
        for line in excludes_lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            assert '"unittest"' not in stripped, (
                "unittest must not be excluded — numpy.testing imports it at module level"
            )

    def test_i18n_in_datas(self):
        """Translation files must be bundled."""
        assert '"i18n"' in self.spec_content or "'i18n'" in self.spec_content

    def test_assets_in_datas(self):
        """Assets directory must be bundled."""
        assert '"assets"' in self.spec_content or "'assets'" in self.spec_content

    def test_license_in_datas(self):
        """LICENSE file must be in datas — About dialog reads it at runtime."""
        assert '"LICENSE"' in self.spec_content or "'LICENSE'" in self.spec_content, (
            "LICENSE not found in spec datas — About dialog will show 'Unknown' in binary"
        )

    def test_pywt_extensions_in_hidden_imports(self):
        """pywt C extensions must be included for phash to work."""
        assert '"pywt._extensions"' in self.spec_content


class TestPerceptualHashDependencies:
    """Test that imagehash and its dependencies work correctly in-process."""

    def test_imagehash_import(self):
        import imagehash
        assert imagehash is not None

    def test_scipy_fftpack_import(self):
        import scipy.fftpack
        assert scipy.fftpack is not None

    def test_pywt_import(self):
        import pywt
        assert pywt is not None

    def test_phash_works(self):
        """phash requires scipy.fftpack — this catches missing deps."""
        import imagehash
        from PIL import Image

        img = Image.new('RGB', (64, 64), 'red')
        h = imagehash.phash(img, hash_size=16)
        assert h is not None

    def test_dhash_works(self):
        import imagehash
        from PIL import Image

        img = Image.new('RGB', (64, 64), 'blue')
        h = imagehash.dhash(img, hash_size=8)
        assert h is not None

    def test_average_hash_works(self):
        import imagehash
        from PIL import Image

        img = Image.new('RGB', (64, 64), 'green')
        h = imagehash.average_hash(img, hash_size=8)
        assert h is not None

    def test_phash_with_highfreq_factor(self):
        """phash with highfreq_factor uses pywt internally."""
        import imagehash
        from PIL import Image

        img = Image.new('RGB', (100, 100), 'yellow')
        h = imagehash.phash(img, hash_size=16, highfreq_factor=4)
        assert h is not None

    def test_phash_produces_different_hashes_for_different_images(self):
        import imagehash
        from PIL import Image
        import numpy as np

        # Use textured images (solid colors produce identical phashes)
        rng = np.random.RandomState(42)
        arr1 = rng.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        arr2 = rng.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        img1 = Image.fromarray(arr1)
        img2 = Image.fromarray(arr2)
        h1 = imagehash.phash(img1, hash_size=8)
        h2 = imagehash.phash(img2, hash_size=8)
        assert h1 != h2


class TestBinaryVerification:
    """
    Tests that verify the actual PyInstaller binary.
    
    These tests require a build to exist at dist/safetool-pix/.
    Skip if no build is available.
    """

    @pytest.fixture(autouse=True)
    def _check_binary_exists(self):
        """Skip all tests in this class if no binary exists."""
        if sys.platform == "win32":
            self.binary = DIST_DIR / "SafeToolPix" / "SafeToolPix.exe"
        elif sys.platform == "darwin":
            self.binary = DIST_DIR / "SafeToolPix" / "SafeToolPix"
        else:
            self.binary = DIST_DIR / "safetool-pix" / "safetool-pix"

        if not self.binary.exists():
            pytest.skip(f"No binary found at {self.binary} — run build first")

    def test_binary_exists_and_is_executable(self):
        assert self.binary.exists()
        assert os.access(str(self.binary), os.X_OK)

    def test_internal_directory_exists(self):
        internal = self.binary.parent / "_internal"
        assert internal.exists(), "_internal directory missing from build"

    def test_i18n_bundled(self):
        """Check that translation files are in the bundle."""
        internal = self.binary.parent / "_internal"
        i18n_dir = internal / "i18n"
        assert i18n_dir.exists(), "i18n directory not bundled"
        assert (i18n_dir / "es.json").exists(), "es.json not bundled"
        assert (i18n_dir / "en.json").exists(), "en.json not bundled"

    def test_assets_bundled(self):
        """Check that assets are in the bundle."""
        internal = self.binary.parent / "_internal"
        # Assets can be in _internal/assets or binary_dir/assets depending on PyInstaller version
        assets_in_internal = internal / "assets"
        assets_in_root = self.binary.parent / "assets"
        assert assets_in_internal.exists() or assets_in_root.exists(), (
            "assets directory not bundled (checked _internal/assets and binary_dir/assets)"
        )

    def test_license_bundled(self):
        """LICENSE must be bundled — About dialog reads it to show license text."""
        internal = self.binary.parent / "_internal"
        # LICENSE is added to datas with dest "." so it lands in _internal/
        license_path = internal / "LICENSE"
        assert license_path.exists(), (
            "LICENSE file not bundled in _internal/ — About dialog will show 'Unknown'"
        )
        assert license_path.stat().st_size > 0, "Bundled LICENSE file is empty"

    def test_binary_verify_mode(self):
        """Run the binary with --verify flag for a quick smoke test."""
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"

        result = subprocess.run(
            [str(self.binary), "--verify"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        assert result.returncode == 0, (
            f"Binary --verify failed (exit {result.returncode}).\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )
        assert "VERIFY_OK" in stdout, (
            f"Binary --verify did not output VERIFY_OK.\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    def test_binary_size_reasonable(self):
        """Binary should be at least a few MB (sanity check)."""
        size_mb = self.binary.stat().st_size / (1024 * 1024)
        assert size_mb > 5, f"Binary suspiciously small: {size_mb:.1f} MB"
