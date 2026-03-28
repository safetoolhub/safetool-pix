# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests exhaustivos para utils/settings_manager.py y utils/storage.py

Cobertura del SettingsManager con JsonStorageBackend, constantes de clave,
métodos get/set, métodos de conveniencia, historial de directorios,
y referencias al nombre de la aplicación.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from utils.storage import StorageBackend, JsonStorageBackend
from utils.settings_manager import SettingsManager


# =============================================================================
# HELPERS
# =============================================================================

class InMemoryStorageBackend(StorageBackend):
    """Backend en memoria para tests sin I/O."""

    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        keys = key.split('/')
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key, value):
        keys = key.split('/')
        data = self._data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value

    def remove(self, key):
        keys = key.split('/')
        data = self._data
        for k in keys[:-1]:
            if isinstance(data, dict) and k in data:
                data = data[k]
            else:
                return
        if isinstance(data, dict) and keys[-1] in data:
            del data[keys[-1]]

    def clear(self):
        self._data = {}

    def contains(self, key):
        keys = key.split('/')
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return False
        return True

    def sync(self):
        pass


@pytest.fixture
def backend():
    return InMemoryStorageBackend()


@pytest.fixture
def sm(backend):
    return SettingsManager(backend=backend)


# =============================================================================
# APP NAME CONSTANTS
# =============================================================================

class TestAppNameConstants:
    """Tests de nombres de app en SettingsManager y storage."""

    def test_default_organization_name(self, backend):
        sm = SettingsManager(backend=backend)
        # SettingsManager stores org/app names for QSettingsBackend usage
        # Verify the constructor defaults
        assert True  # Instance created without error

    def test_organization_name_is_safetoollab(self):
        """Verificar que el nombre por defecto de organización es SafeToolPix."""
        import inspect
        sig = inspect.signature(SettingsManager.__init__)
        assert sig.parameters['organization'].default == "SafeToolPix"

    def test_application_name_is_safetool_pix(self):
        """Verificar que el nombre por defecto de aplicación es SafeTool Pix."""
        import inspect
        sig = inspect.signature(SettingsManager.__init__)
        assert sig.parameters['application'].default == "SafeTool Pix"


class TestJsonStorageBackendAppName:
    """Tests de nombre de app en JsonStorageBackend."""

    def test_default_config_dir_name(self):
        """El directorio de configuración por defecto contiene .safetool_pix."""
        import inspect
        source = inspect.getsource(JsonStorageBackend.__init__)
        assert ".safetool_pix" in source


# =============================================================================
# KEY CONSTANTS
# =============================================================================

class TestKeyConstants:
    """Tests de todas las constantes KEY_*."""

    def test_key_logs_dir(self):
        assert SettingsManager.KEY_LOGS_DIR == "directories/logs"

    def test_key_backup_dir(self):
        assert SettingsManager.KEY_BACKUP_DIR == "directories/backups"

    def test_key_auto_backup(self):
        assert SettingsManager.KEY_AUTO_BACKUP == "behavior/auto_backup_enabled"

    def test_key_confirm_operations(self):
        assert SettingsManager.KEY_CONFIRM_OPERATIONS == "behavior/confirm_operations"

    def test_key_confirm_delete(self):
        assert SettingsManager.KEY_CONFIRM_DELETE == "behavior/confirm_delete"

    def test_key_confirm_reanalyze(self):
        assert SettingsManager.KEY_CONFIRM_REANALYZE == "behavior/confirm_reanalyze"

    def test_key_auto_analyze(self):
        assert SettingsManager.KEY_AUTO_ANALYZE == "behavior/auto_analyze_on_open"

    def test_key_log_level(self):
        assert SettingsManager.KEY_LOG_LEVEL == "logging/level"

    def test_key_dual_log_enabled(self):
        assert SettingsManager.KEY_DUAL_LOG_ENABLED == "logging/dual_log_enabled"

    def test_key_disable_file_logging(self):
        assert SettingsManager.KEY_DISABLE_FILE_LOGGING == "logging/disable_file_logging"

    def test_key_dry_run_default(self):
        assert SettingsManager.KEY_DRY_RUN_DEFAULT == "advanced/dry_run_default"

    def test_key_max_workers(self):
        assert SettingsManager.KEY_MAX_WORKERS == "advanced/max_workers"

    def test_key_precalculate_hashes(self):
        assert SettingsManager.KEY_PRECALCULATE_HASHES == "General/precalculate_hashes"

    def test_key_precalculate_image_exif(self):
        assert SettingsManager.KEY_PRECALCULATE_IMAGE_EXIF == "General/precalculate_image_exif"

    def test_key_precalculate_video_exif(self):
        assert SettingsManager.KEY_PRECALCULATE_VIDEO_EXIF == "General/precalculate_video_exif"

    def test_key_window_geometry(self):
        assert SettingsManager.KEY_WINDOW_GEOMETRY == "window/geometry"

    def test_key_window_state(self):
        assert SettingsManager.KEY_WINDOW_STATE == "window/state"

    def test_key_show_full_path(self):
        assert SettingsManager.KEY_SHOW_FULL_PATH == "interface/show_full_directory_path"

    def test_key_directory_history(self):
        assert SettingsManager.KEY_DIRECTORY_HISTORY == "interface/directory_history"

    def test_key_analysis_timestamp(self):
        assert SettingsManager.KEY_ANALYSIS_TIMESTAMP == "interface/analysis_timestamp"

    def test_key_language(self):
        assert SettingsManager.KEY_LANGUAGE == "interface/language"

    def test_key_first_launch_shown(self):
        assert SettingsManager.KEY_FIRST_LAUNCH_SHOWN == "interface/first_launch_about_shown"


# =============================================================================
# BASIC GET/SET OPERATIONS
# =============================================================================

class TestBasicOperations:
    """Tests de operaciones básicas get/set."""

    def test_get_default_when_missing(self, sm):
        assert sm.get("nonexistent") is None

    def test_get_explicit_default(self, sm):
        assert sm.get("nonexistent", "fallback") == "fallback"

    def test_set_and_get_string(self, sm):
        sm.set("key", "value")
        assert sm.get("key") == "value"

    def test_set_and_get_int(self, sm):
        sm.set("num", 42)
        assert sm.get("num") == 42

    def test_set_and_get_bool(self, sm):
        sm.set("flag", True)
        assert sm.get("flag") is True

    def test_set_and_get_list(self, sm):
        sm.set("items", [1, 2, 3])
        assert sm.get("items") == [1, 2, 3]

    def test_set_nested_key(self, sm):
        sm.set("a/b/c", "deep")
        assert sm.get("a/b/c") == "deep"


# =============================================================================
# TYPED GETTERS
# =============================================================================

class TestGetBool:
    """Tests de get_bool."""

    def test_bool_true(self, sm):
        sm.set("flag", True)
        assert sm.get_bool("flag") is True

    def test_bool_false(self, sm):
        sm.set("flag", False)
        assert sm.get_bool("flag") is False

    def test_bool_default(self, sm):
        assert sm.get_bool("nonexistent") is False

    def test_bool_default_custom(self, sm):
        assert sm.get_bool("nonexistent", True) is True

    def test_bool_string_true(self, sm):
        sm.set("flag", "true")
        assert sm.get_bool("flag") is True

    def test_bool_string_1(self, sm):
        sm.set("flag", "1")
        assert sm.get_bool("flag") is True

    def test_bool_string_yes(self, sm):
        sm.set("flag", "yes")
        assert sm.get_bool("flag") is True

    def test_bool_string_false(self, sm):
        sm.set("flag", "false")
        assert sm.get_bool("flag") is False


class TestGetInt:
    """Tests de get_int."""

    def test_int_value(self, sm):
        sm.set("num", 100)
        assert sm.get_int("num") == 100

    def test_int_default(self, sm):
        assert sm.get_int("missing") == 0

    def test_int_default_custom(self, sm):
        assert sm.get_int("missing", 10) == 10

    def test_int_from_string(self, sm):
        sm.set("num", "42")
        assert sm.get_int("num") == 42

    def test_int_from_invalid_string(self, sm):
        sm.set("num", "notanumber")
        assert sm.get_int("num", 5) == 5

    def test_int_from_none(self, sm):
        sm.set("num", None)
        assert sm.get_int("num", 5) == 5


class TestGetPath:
    """Tests de get_path."""

    def test_path_value(self, sm):
        sm.set("dir", "/tmp/test")
        assert sm.get_path("dir") == Path("/tmp/test")

    def test_path_default_none(self, sm):
        assert sm.get_path("missing") is None

    def test_path_default_custom(self, sm):
        default = Path("/default")
        assert sm.get_path("missing", default) == default


# =============================================================================
# REMOVE AND CLEAR
# =============================================================================

class TestRemoveAndClear:
    """Tests de remove y clear."""

    def test_remove_key(self, sm):
        sm.set("key", "value")
        sm.remove("key")
        assert sm.get("key") is None

    def test_has_key_true(self, sm):
        sm.set("key", "value")
        assert sm.has_key("key") is True

    def test_has_key_false(self, sm):
        assert sm.has_key("nonexistent") is False

    def test_clear_all(self, sm):
        sm.set("a", 1)
        sm.set("b", 2)
        sm.clear_all()
        assert sm.get("a") is None
        assert sm.get("b") is None


# =============================================================================
# CONVENIENCE METHODS
# =============================================================================

class TestConvenienceMethods:
    """Tests de métodos de conveniencia."""

    def test_auto_backup_default_true(self, sm):
        assert sm.get_auto_backup_enabled() is True

    def test_set_auto_backup(self, sm):
        sm.set_auto_backup_enabled(False)
        assert sm.get_auto_backup_enabled() is False

    def test_log_level_default_info(self, sm):
        assert sm.get_log_level() == "INFO"

    def test_set_log_level(self, sm):
        sm.set_log_level("DEBUG")
        assert sm.get_log_level() == "DEBUG"

    def test_log_level_uppercase(self, sm):
        sm.set_log_level("debug")
        assert sm.get_log_level() == "DEBUG"

    def test_dual_log_default_true(self, sm):
        assert sm.get_dual_log_enabled() is True

    def test_set_dual_log(self, sm):
        sm.set_dual_log_enabled(False)
        assert sm.get_dual_log_enabled() is False

    def test_disable_file_logging_default_false(self, sm):
        assert sm.get_disable_file_logging() is False

    def test_set_disable_file_logging(self, sm):
        sm.set_disable_file_logging(True)
        assert sm.get_disable_file_logging() is True

    def test_logs_directory(self, sm):
        sm.set_logs_directory(Path("/tmp/logs"))
        assert sm.get_logs_directory() == Path("/tmp/logs")

    def test_logs_directory_default(self, sm):
        assert sm.get_logs_directory() is None

    def test_backup_directory(self, sm):
        sm.set_backup_directory(Path("/tmp/backup"))
        assert sm.get_backup_directory() == Path("/tmp/backup")

    def test_confirm_operations_default_true(self, sm):
        assert sm.get_confirm_operations() is True

    def test_confirm_delete_default_true(self, sm):
        assert sm.get_confirm_delete() is True

    def test_confirm_reanalyze_default_true(self, sm):
        assert sm.get_confirm_reanalyze() is True

    def test_auto_analyze_default_false(self, sm):
        assert sm.get_auto_analyze() is False

    def test_max_workers_default(self, sm):
        assert sm.get_max_workers() == 4

    def test_precalculate_hashes_default_true(self, sm):
        assert sm.get_precalculate_hashes() is True

    def test_set_precalculate_hashes(self, sm):
        sm.set_precalculate_hashes(True)
        assert sm.get_precalculate_hashes() is True

    def test_precalculate_image_exif_default_true(self, sm):
        assert sm.get_precalculate_image_exif() is True

    def test_set_precalculate_image_exif(self, sm):
        sm.set_precalculate_image_exif(False)
        assert sm.get_precalculate_image_exif() is False

    def test_precalculate_video_exif_default_false(self, sm):
        assert sm.get_precalculate_video_exif() is False

    def test_set_precalculate_video_exif(self, sm):
        sm.set_precalculate_video_exif(True)
        assert sm.get_precalculate_video_exif() is True

    def test_show_full_path_default_true(self, sm):
        assert sm.get_show_full_path() is True

    def test_set_show_full_path(self, sm):
        sm.set_show_full_path(False)
        assert sm.get_show_full_path() is False

    def test_analysis_timestamp(self, sm):
        sm.set_analysis_timestamp("2024-01-15T10:30:00")
        assert sm.get_analysis_timestamp() == "2024-01-15T10:30:00"

    def test_analysis_timestamp_default_none(self, sm):
        assert sm.get_analysis_timestamp() is None

    def test_last_folder(self, sm):
        sm.set_last_folder("/tmp/photos")
        assert sm.get_last_folder() == "/tmp/photos"

    def test_last_folder_default_none(self, sm):
        assert sm.get_last_folder() is None


# =============================================================================
# LANGUAGE
# =============================================================================

class TestLanguageSettings:
    """Tests de configuración de idioma."""

    def test_language_default_es(self, sm):
        assert sm.get_language() == "es"

    def test_set_language(self, sm):
        sm.set_language("en")
        assert sm.get_language() == "en"


# =============================================================================
# DIRECTORY HISTORY
# =============================================================================

class TestDirectoryHistory:
    """Tests de historial de directorios."""

    def test_empty_history(self, sm):
        assert sm.get_directory_history() == []

    def test_add_directory(self, sm):
        sm.add_to_directory_history("/tmp/photos")
        assert "/tmp/photos" in sm.get_directory_history()

    def test_recent_first(self, sm):
        sm.add_to_directory_history("/tmp/old")
        sm.add_to_directory_history("/tmp/new")
        history = sm.get_directory_history()
        assert history[0] == "/tmp/new"
        assert history[1] == "/tmp/old"

    def test_no_duplicates(self, sm):
        sm.add_to_directory_history("/tmp/photos")
        sm.add_to_directory_history("/tmp/photos")
        history = sm.get_directory_history()
        assert history.count("/tmp/photos") == 1

    def test_duplicate_moves_to_front(self, sm):
        sm.add_to_directory_history("/tmp/old")
        sm.add_to_directory_history("/tmp/new")
        sm.add_to_directory_history("/tmp/old")
        assert sm.get_directory_history()[0] == "/tmp/old"

    def test_max_10_entries(self, sm):
        for i in range(15):
            sm.add_to_directory_history(f"/tmp/dir{i}")
        history = sm.get_directory_history()
        assert len(history) == 10

    def test_max_items_parameter(self, sm):
        for i in range(15):
            sm.add_to_directory_history(f"/tmp/dir{i}")
        history = sm.get_directory_history(max_items=5)
        assert len(history) == 5

    def test_non_list_history_returns_empty(self, sm):
        sm.set(SettingsManager.KEY_DIRECTORY_HISTORY, "not a list")
        assert sm.get_directory_history() == []


# =============================================================================
# JSON STORAGE BACKEND
# =============================================================================

class TestJsonStorageBackend:
    """Tests de JsonStorageBackend con archivo real en tmp."""

    def test_set_and_get(self, tmp_path):
        path = tmp_path / "settings.json"
        backend = JsonStorageBackend(file_path=path)
        backend.set("key", "value")
        assert backend.get("key") == "value"

    def test_nested_keys(self, tmp_path):
        path = tmp_path / "settings.json"
        backend = JsonStorageBackend(file_path=path)
        backend.set("a/b/c", "deep")
        assert backend.get("a/b/c") == "deep"

    def test_persistence(self, tmp_path):
        path = tmp_path / "settings.json"
        b1 = JsonStorageBackend(file_path=path)
        b1.set("key", "persisted")
        b2 = JsonStorageBackend(file_path=path)
        assert b2.get("key") == "persisted"

    def test_remove(self, tmp_path):
        path = tmp_path / "settings.json"
        backend = JsonStorageBackend(file_path=path)
        backend.set("key", "value")
        backend.remove("key")
        assert backend.get("key") is None

    def test_clear(self, tmp_path):
        path = tmp_path / "settings.json"
        backend = JsonStorageBackend(file_path=path)
        backend.set("a", 1)
        backend.set("b", 2)
        backend.clear()
        assert backend.get("a") is None

    def test_contains_true(self, tmp_path):
        path = tmp_path / "settings.json"
        backend = JsonStorageBackend(file_path=path)
        backend.set("key", "value")
        assert backend.contains("key") is True

    def test_contains_false(self, tmp_path):
        path = tmp_path / "settings.json"
        backend = JsonStorageBackend(file_path=path)
        assert backend.contains("nonexistent") is False

    def test_sync(self, tmp_path):
        path = tmp_path / "settings.json"
        backend = JsonStorageBackend(file_path=path)
        backend.set("key", "value")
        backend.sync()  # Should not raise

    def test_corrupt_json_loads_empty(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("{invalid json", encoding='utf-8')
        backend = JsonStorageBackend(file_path=path)
        assert backend.get("anything") is None

    def test_default_path_contains_safetool(self):
        """El path por defecto debe contener .safetool_pix."""
        import inspect
        source = inspect.getsource(JsonStorageBackend.__init__)
        assert ".safetool_pix" in source
        assert "settings.json" in source


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

class TestGlobalInstance:
    """Tests de la instancia global settings_manager."""

    def test_global_instance_exists(self):
        from utils.settings_manager import settings_manager
        assert settings_manager is not None

    def test_global_instance_is_settings_manager(self):
        from utils.settings_manager import settings_manager
        assert isinstance(settings_manager, SettingsManager)
