# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests exhaustivos para main.py

Cobertura de _install_exception_hook, _run_verify_mode, y las
referencias al nombre de la aplicación en la configuración de QApplication.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# EXCEPTION HOOK
# =============================================================================

class TestInstallExceptionHook:
    """Tests de _install_exception_hook."""

    def test_installs_custom_hook(self):
        from main import _install_exception_hook
        original = sys.excepthook
        try:
            _install_exception_hook()
            assert sys.excepthook is not original
        finally:
            sys.excepthook = original

    def test_hook_does_not_raise(self):
        from main import _install_exception_hook
        original = sys.excepthook
        try:
            _install_exception_hook()
            # Should not propagate or crash
            sys.excepthook(ValueError, ValueError("test"), None)
        finally:
            sys.excepthook = original

    def test_hook_writes_to_stderr(self, capsys):
        from main import _install_exception_hook
        original = sys.excepthook
        try:
            _install_exception_hook()
            try:
                raise RuntimeError("test error")
            except RuntimeError:
                exc_type, exc_value, exc_tb = sys.exc_info()
                sys.excepthook(exc_type, exc_value, exc_tb)
            captured = capsys.readouterr()
            assert "UNHANDLED EXCEPTION" in captured.err
            assert "test error" in captured.err
        finally:
            sys.excepthook = original


# =============================================================================
# VERIFY MODE
# =============================================================================

class TestRunVerifyMode:
    """Tests de _run_verify_mode."""

    def test_exits_with_0_on_success(self):
        from main import _run_verify_mode
        with pytest.raises(SystemExit) as exc_info:
            _run_verify_mode()
        assert exc_info.value.code == 0

    def test_prints_verify_ok(self, capsys):
        from main import _run_verify_mode
        with pytest.raises(SystemExit):
            _run_verify_mode()
        captured = capsys.readouterr()
        assert "VERIFY_OK" in captured.out


# =============================================================================
# APP NAME IN MAIN
# =============================================================================

class TestAppNameInMain:
    """Tests de referencias al nombre de app en main.py."""

    def test_organization_name_in_source(self):
        """main.py debe contener setOrganizationName con SafeToolPix."""
        import inspect
        from main import main
        source = inspect.getsource(main)
        assert 'setOrganizationName("SafeToolPix")' in source

    def test_application_name_uses_config(self):
        """main.py debe usar Config.APP_NAME para setApplicationName."""
        import inspect
        from main import main
        source = inspect.getsource(main)
        assert "setApplicationName(Config.APP_NAME)" in source

    def test_windows_user_model_id(self):
        """Windows AppUserModelID debe contener SafeToolPix."""
        import inspect
        from main import main
        source = inspect.getsource(main)
        assert "SafeToolHub.SafeToolPix" in source

    def test_verify_mode_checks_i18n(self):
        """_run_verify_mode verifica i18n/app.name."""
        import inspect
        from main import _run_verify_mode
        source = inspect.getsource(_run_verify_mode)
        assert "app.name" in source
