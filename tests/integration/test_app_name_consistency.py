# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests de integración para consistencia del nombre de la aplicación.

Verifica que todas las referencias al nombre "SafeTool Pix" / "SafeToolPix"
sean coherentes entre Config, i18n, settings_manager, storage, logger y main.py.
Estos tests actúan como red de seguridad para futuras operaciones de renombrado.
"""

import pytest
import inspect
import json
from pathlib import Path

from config import Config


# =============================================================================
# CONSTANTES ESPERADAS
# =============================================================================

# Estas constantes definen los nombres canónicos. Si se renombra la app,
# hay que actualizar estas constantes y todos los tests deberían fallar
# señalando exactamente qué más necesita cambio.
EXPECTED_APP_NAME = "SafeTool Pix"
EXPECTED_ORG_NAME = "SafeToolPix"
EXPECTED_DIR_NAME = "SafeTool_Pix"  # Para DEFAULT_BASE_DIR
EXPECTED_CONFIG_DIR = ".safetool_pix"  # Para storage.py
EXPECTED_LOGGER_NAME = "SafeToolPix"  # Para logger.py
EXPECTED_REPO_SLUG = "safetool-pix"  # Para APP_REPO URL


# =============================================================================
# CONFIG.PY
# =============================================================================

class TestConfigAppName:
    """Verifica Config.APP_NAME y derivados."""

    def test_app_name(self):
        assert Config.APP_NAME == EXPECTED_APP_NAME

    def test_default_base_dir_contains_name(self):
        assert Config.DEFAULT_BASE_DIR.name == EXPECTED_DIR_NAME

    def test_app_repo_contains_slug(self):
        assert EXPECTED_REPO_SLUG in Config.APP_REPO


# =============================================================================
# I18N (TRADUCCIONES)
# =============================================================================

class TestI18nAppName:
    """Verifica que las traducciones contienen el nombre correcto."""

    @pytest.fixture(autouse=True)
    def init_i18n(self):
        from utils.i18n import init_i18n
        init_i18n('es')

    def test_tr_app_name_matches_config(self):
        from utils.i18n import tr
        assert tr("app.name") == Config.APP_NAME

    def test_both_languages_same_app_name(self):
        base = Path(__file__).resolve().parent.parent.parent / "i18n"
        for lang in ('es', 'en'):
            with open(base / f"{lang}.json", 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert data["app"]["name"] == EXPECTED_APP_NAME, \
                f"app.name en {lang}.json no coincide"


# =============================================================================
# SETTINGS MANAGER
# =============================================================================

class TestSettingsManagerAppName:
    """Verifica nombres de org/app en SettingsManager."""

    def test_default_organization(self):
        sig = inspect.signature(
            __import__('utils.settings_manager', fromlist=['SettingsManager']).SettingsManager.__init__
        )
        assert sig.parameters['organization'].default == EXPECTED_ORG_NAME

    def test_default_application(self):
        sig = inspect.signature(
            __import__('utils.settings_manager', fromlist=['SettingsManager']).SettingsManager.__init__
        )
        assert sig.parameters['application'].default == EXPECTED_APP_NAME


# =============================================================================
# STORAGE BACKEND
# =============================================================================

class TestStorageAppName:
    """Verifica el directorio de configuración en JsonStorageBackend."""

    def test_default_config_dir(self):
        source = inspect.getsource(
            __import__('utils.storage', fromlist=['JsonStorageBackend']).JsonStorageBackend.__init__
        )
        assert EXPECTED_CONFIG_DIR in source


# =============================================================================
# LOGGER
# =============================================================================

class TestLoggerAppName:
    """Verifica el nombre del logger raíz."""

    def test_root_logger_name(self):
        from utils.logger import _ROOT_LOGGER_NAME
        assert _ROOT_LOGGER_NAME == EXPECTED_LOGGER_NAME


# =============================================================================
# MAIN.PY
# =============================================================================

class TestMainAppName:
    """Verifica referencias en main.py."""

    def test_organization_in_main(self):
        source = inspect.getsource(__import__('main').main)
        assert f'setOrganizationName("{EXPECTED_ORG_NAME}")' in source

    def test_app_name_from_config_in_main(self):
        source = inspect.getsource(__import__('main').main)
        assert "setApplicationName(Config.APP_NAME)" in source

    def test_windows_app_id_in_main(self):
        source = inspect.getsource(__import__('main').main)
        assert f"SafeToolHub.{EXPECTED_ORG_NAME}" in source


# =============================================================================
# CROSS-MODULE CONSISTENCY
# =============================================================================

class TestCrossModuleConsistency:
    """Verifica que todos los módulos usan el mismo nombre base."""

    def test_config_name_consistent_with_dir(self):
        """APP_NAME sin espacios y con _ debe ser el nombre del directorio base."""
        expected = Config.APP_NAME.replace(" ", "_")
        assert Config.DEFAULT_BASE_DIR.name == expected

    def test_org_name_is_camelcase_of_app_name(self):
        """El org name debe ser CamelCase del app name."""
        assert EXPECTED_ORG_NAME == Config.APP_NAME.replace(" ", "")

    def test_config_dir_is_lowercase_with_underscores(self):
        """El directorio de config debe ser .app_name en lowercase con _."""
        expected = "." + Config.APP_NAME.lower().replace(" ", "_")
        assert EXPECTED_CONFIG_DIR == expected
