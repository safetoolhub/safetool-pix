# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests exhaustivos para config.py

Cobertura completa de Config: nombre de aplicación, versiones, rutas,
extensiones soportadas, cálculos de workers, caché, umbrales y constantes.

Especial atención al nombre de la aplicación y todos sus derivados,
para detectar cualquier inconsistencia tras renombrados.
"""

import pytest
from pathlib import Path
from unittest.mock import patch


from config import Config


# =============================================================================
# APP IDENTITY (Nombre, versión, autor) - MÁXIMA COBERTURA
# =============================================================================

class TestAppIdentity:
    """Tests de identidad de la aplicación: nombre, versión, autor, URLs."""

    def test_app_name_value(self):
        """El nombre oficial es 'SafeTool Pix'."""
        assert Config.APP_NAME == "SafeTool Pix"

    def test_app_name_is_string(self):
        assert isinstance(Config.APP_NAME, str)

    def test_app_name_not_empty(self):
        assert len(Config.APP_NAME) > 0

    def test_app_name_contains_safetool(self):
        """El nombre siempre contiene 'SafeTool'."""
        assert "SafeTool" in Config.APP_NAME

    def test_app_name_contains_pix(self):
        """El nombre siempre contiene 'Pix'."""
        assert "Pix" in Config.APP_NAME

    def test_app_version_format(self):
        """La versión tiene formato semántico X.Y.Z."""
        parts = Config.APP_VERSION.split('.')
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' is not numeric"

    def test_app_version_is_string(self):
        assert isinstance(Config.APP_VERSION, str)

    def test_app_version_suffix_valid(self):
        """APP_VERSION_SUFFIX es string (puede estar vacío o ser 'beta', 'rc1', etc.)."""
        assert isinstance(Config.APP_VERSION_SUFFIX, str)
        if Config.APP_VERSION_SUFFIX:
            assert Config.APP_VERSION_SUFFIX in ("beta", "rc1", "rc2", "alpha")

    def test_get_full_version_with_suffix(self):
        """Con sufijo, devuelve 'X.Y.Z-suffix'."""
        original = Config.APP_VERSION_SUFFIX
        try:
            Config.APP_VERSION_SUFFIX = "beta"
            result = Config.get_full_version()
            assert result == f"{Config.APP_VERSION}-beta"
            assert "-" in result
        finally:
            Config.APP_VERSION_SUFFIX = original

    def test_get_full_version_without_suffix(self):
        """Sin sufijo, devuelve solo 'X.Y.Z'."""
        original = Config.APP_VERSION_SUFFIX
        try:
            Config.APP_VERSION_SUFFIX = ""
            result = Config.get_full_version()
            assert result == Config.APP_VERSION
            assert "-" not in result
        finally:
            Config.APP_VERSION_SUFFIX = original

    def test_get_full_version_returns_string(self):
        assert isinstance(Config.get_full_version(), str)

    def test_app_author(self):
        assert Config.APP_AUTHOR == "SafeToolHub"

    def test_app_contact_is_email(self):
        assert "@" in Config.APP_CONTACT
        assert "." in Config.APP_CONTACT

    def test_app_website_is_https(self):
        assert Config.APP_WEBSITE.startswith("https://")

    def test_app_repo_is_github(self):
        assert "github.com" in Config.APP_REPO
        assert "safetool-pix" in Config.APP_REPO

    def test_app_repo_contains_author(self):
        """El repo contiene el nombre del autor en la URL."""
        assert "safetoolhub" in Config.APP_REPO.lower()

    def test_app_description_not_empty(self):
        assert len(Config.APP_DESCRIPTION) > 0

    def test_app_description_mentions_privacy(self):
        """La descripción menciona privacidad."""
        assert "privacy" in Config.APP_DESCRIPTION.lower() or "local" in Config.APP_DESCRIPTION.lower()

    def test_app_license(self):
        assert Config.APP_LICENSE == "GPLv3"

    def test_app_attribution_requirement_not_empty(self):
        assert len(Config.APP_ATTRIBUTION_REQUIREMENT) > 0

    def test_app_attribution_mentions_safetoolhub(self):
        assert "SafeToolHub" in Config.APP_ATTRIBUTION_REQUIREMENT


# =============================================================================
# PATHS AND DIRECTORIES (Rutas con nombre de app)
# =============================================================================

class TestPaths:
    """Tests de rutas y directorios derivados del nombre de la aplicación."""

    def test_default_base_dir_type(self):
        assert isinstance(Config.DEFAULT_BASE_DIR, Path)

    def test_default_base_dir_under_home(self):
        """El directorio base está bajo el home del usuario."""
        assert str(Path.home()) in str(Config.DEFAULT_BASE_DIR)

    def test_default_base_dir_name_contains_safetool(self):
        """El nombre del directorio base contiene 'SafeTool'."""
        assert "SafeTool" in Config.DEFAULT_BASE_DIR.name

    def test_default_base_dir_name(self):
        """El directorio base se llama 'SafeTool_Pix'."""
        assert Config.DEFAULT_BASE_DIR.name == "SafeTool_Pix"

    def test_log_dir_is_subdir_of_base(self):
        """logs/ está dentro del directorio base."""
        assert Config.DEFAULT_LOG_DIR.parent == Config.DEFAULT_BASE_DIR

    def test_log_dir_name(self):
        assert Config.DEFAULT_LOG_DIR.name == "logs"

    def test_backup_dir_is_subdir_of_base(self):
        assert Config.DEFAULT_BACKUP_DIR.parent == Config.DEFAULT_BASE_DIR

    def test_backup_dir_name(self):
        assert Config.DEFAULT_BACKUP_DIR.name == "backups"

    def test_cache_saved_dir_is_subdir_of_base(self):
        assert Config.DEFAULT_CACHE_SAVED_DIR.parent == Config.DEFAULT_BASE_DIR

    def test_cache_saved_dir_name(self):
        assert Config.DEFAULT_CACHE_SAVED_DIR.name == "cache_saved"

    def test_assets_dir_type(self):
        assert isinstance(Config.ASSETS_DIR, Path)

    def test_app_icon_path_type(self):
        assert isinstance(Config.APP_ICON_PATH, Path)

    def test_app_icon_path_under_assets(self):
        assert Config.APP_ICON_PATH.parent == Config.ASSETS_DIR

    def test_app_icon_filename(self):
        assert Config.APP_ICON_PATH.name == "icon.png"


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

class TestLoggingConfig:
    """Tests de configuración de logging."""

    def test_log_level_default(self):
        assert Config.LOG_LEVEL == "INFO"

    def test_max_log_file_size_positive(self):
        assert Config.MAX_LOG_FILE_SIZE_MB > 0

    def test_max_log_file_size_value(self):
        assert Config.MAX_LOG_FILE_SIZE_MB == 10

    def test_max_log_backup_count_positive(self):
        assert Config.MAX_LOG_BACKUP_COUNT > 0

    def test_max_log_backup_count_value(self):
        assert Config.MAX_LOG_BACKUP_COUNT == 9999


# =============================================================================
# WORKER THREADS CONFIGURATION
# =============================================================================

class TestWorkerThreads:
    """Tests de cálculo de workers dinámicos."""

    def test_worker_factor_per_core(self):
        assert Config._WORKER_FACTOR_PER_CORE == 2

    def test_min_workers(self):
        assert Config._MIN_WORKERS == 4

    def test_max_workers(self):
        assert Config._MAX_WORKERS == 16

    def test_max_worker_threads_constant(self):
        assert Config.MAX_WORKER_THREADS == 16

    def test_get_cpu_count_returns_positive_int(self):
        result = Config.get_cpu_count()
        assert isinstance(result, int)
        assert result >= 1

    def test_get_optimal_worker_threads_minimum(self):
        """Siempre al menos _MIN_WORKERS."""
        result = Config.get_optimal_worker_threads()
        assert result >= Config._MIN_WORKERS

    def test_get_optimal_worker_threads_maximum(self):
        """Nunca excede _MAX_WORKERS."""
        result = Config.get_optimal_worker_threads()
        assert result <= Config._MAX_WORKERS

    def test_get_optimal_worker_threads_type(self):
        assert isinstance(Config.get_optimal_worker_threads(), int)

    def test_get_cpu_bound_workers_minimum(self):
        result = Config.get_cpu_bound_workers()
        assert result >= Config._MIN_WORKERS

    def test_get_cpu_bound_workers_maximum(self):
        result = Config.get_cpu_bound_workers()
        assert result <= Config._MAX_WORKERS

    def test_get_cpu_bound_workers_type(self):
        assert isinstance(Config.get_cpu_bound_workers(), int)

    def test_io_workers_gte_cpu_workers(self):
        """I/O workers >= CPU workers (factor 2x vs 1x)."""
        io_workers = Config.get_optimal_worker_threads()
        cpu_workers = Config.get_cpu_bound_workers()
        assert io_workers >= cpu_workers

    @patch('config.get_cpu_count', return_value=2)
    def test_get_optimal_workers_with_2_cores(self, mock_cpu):
        result = Config.get_optimal_worker_threads()
        assert result == 4  # max(4, min(2*2=4, 16)) = 4

    @patch('config.get_cpu_count', return_value=4)
    def test_get_optimal_workers_with_4_cores(self, mock_cpu):
        result = Config.get_optimal_worker_threads()
        assert result == 8  # max(4, min(4*2=8, 16)) = 8

    @patch('config.get_cpu_count', return_value=12)
    def test_get_optimal_workers_with_12_cores(self, mock_cpu):
        result = Config.get_optimal_worker_threads()
        assert result == 16  # max(4, min(12*2=24, 16)) = 16

    @patch('config.get_cpu_count', return_value=1)
    def test_get_optimal_workers_with_1_core(self, mock_cpu):
        result = Config.get_optimal_worker_threads()
        assert result == 4  # Floor at _MIN_WORKERS

    def test_get_actual_worker_threads_with_override(self):
        """Override > 0 usa el override (capped a MAX_WORKER_THREADS)."""
        result = Config.get_actual_worker_threads(override=8, io_bound=True)
        assert result == 8

    def test_get_actual_worker_threads_override_capped(self):
        """Override no puede exceder MAX_WORKER_THREADS."""
        result = Config.get_actual_worker_threads(override=100)
        assert result == Config.MAX_WORKER_THREADS

    def test_get_actual_worker_threads_no_override_io_bound(self):
        result = Config.get_actual_worker_threads(override=0, io_bound=True)
        assert result == Config.get_optimal_worker_threads()

    def test_get_actual_worker_threads_no_override_cpu_bound(self):
        result = Config.get_actual_worker_threads(override=0, io_bound=False)
        assert result == Config.get_cpu_bound_workers()


# =============================================================================
# FILE EXTENSIONS
# =============================================================================

class TestFileExtensions:
    """Tests de extensiones de archivos soportados."""

    def test_image_extensions_is_set(self):
        assert isinstance(Config.SUPPORTED_IMAGE_EXTENSIONS, set)

    def test_video_extensions_is_set(self):
        assert isinstance(Config.SUPPORTED_VIDEO_EXTENSIONS, set)

    def test_image_extensions_include_common_formats(self):
        common = {'.jpg', '.jpeg', '.png', '.heic'}
        assert common.issubset(Config.SUPPORTED_IMAGE_EXTENSIONS)

    def test_image_extensions_include_uppercase(self):
        assert '.JPG' in Config.SUPPORTED_IMAGE_EXTENSIONS
        assert '.PNG' in Config.SUPPORTED_IMAGE_EXTENSIONS
        assert '.HEIC' in Config.SUPPORTED_IMAGE_EXTENSIONS

    def test_video_extensions_include_common_formats(self):
        common = {'.mp4', '.mov', '.avi'}
        assert common.issubset(Config.SUPPORTED_VIDEO_EXTENSIONS)

    def test_video_extensions_include_uppercase(self):
        assert '.MP4' in Config.SUPPORTED_VIDEO_EXTENSIONS
        assert '.MOV' in Config.SUPPORTED_VIDEO_EXTENSIONS

    def test_all_supported_is_union(self):
        """ALL_SUPPORTED_EXTENSIONS = IMAGES | VIDEOS."""
        expected = Config.SUPPORTED_IMAGE_EXTENSIONS | Config.SUPPORTED_VIDEO_EXTENSIONS
        assert Config.ALL_SUPPORTED_EXTENSIONS == expected

    def test_no_overlap_image_video(self):
        """No hay extensiones compartidas entre imágenes y videos."""
        overlap = Config.SUPPORTED_IMAGE_EXTENSIONS & Config.SUPPORTED_VIDEO_EXTENSIONS
        assert len(overlap) == 0

    def test_all_extensions_start_with_dot(self):
        for ext in Config.ALL_SUPPORTED_EXTENSIONS:
            assert ext.startswith('.'), f"Extension '{ext}' does not start with '.'"

    def test_webp_is_image(self):
        assert '.webp' in Config.SUPPORTED_IMAGE_EXTENSIONS

    def test_heif_is_image(self):
        assert '.heif' in Config.SUPPORTED_IMAGE_EXTENSIONS

    def test_mkv_is_video(self):
        assert '.mkv' in Config.SUPPORTED_VIDEO_EXTENSIONS

    def test_flv_is_video(self):
        assert '.flv' in Config.SUPPORTED_VIDEO_EXTENSIONS


# =============================================================================
# ANALYSIS THRESHOLDS
# =============================================================================

class TestAnalysisThresholds:
    """Tests de umbrales de análisis."""

    def test_max_time_difference_heic(self):
        assert Config.MAX_TIME_DIFFERENCE_SECONDS == 1

    def test_live_photo_max_time_difference(self):
        assert Config.LIVE_PHOTO_MAX_TIME_DIFFERENCE_SECONDS == 50

    def test_live_photo_max_video_size(self):
        assert Config.LIVE_PHOTO_MAX_VIDEO_SIZE == 8 * 1024 * 1024

    def test_live_photo_max_video_duration(self):
        assert Config.LIVE_PHOTO_MAX_VIDEO_DURATION_SECONDS == 3.6

    def test_max_hamming_threshold(self):
        assert Config.MAX_HAMMING_THRESHOLD == 20

    def test_thresholds_are_positive(self):
        assert Config.MAX_TIME_DIFFERENCE_SECONDS > 0
        assert Config.LIVE_PHOTO_MAX_TIME_DIFFERENCE_SECONDS > 0
        assert Config.LIVE_PHOTO_MAX_VIDEO_SIZE > 0
        assert Config.LIVE_PHOTO_MAX_VIDEO_DURATION_SECONDS > 0
        assert Config.MAX_HAMMING_THRESHOLD > 0


# =============================================================================
# PERCEPTUAL HASH CONFIGURATION
# =============================================================================

class TestPerceptualHashConfig:
    """Tests de configuración de hash perceptual."""

    def test_algorithm(self):
        assert Config.PERCEPTUAL_HASH_ALGORITHM == "phash"

    def test_hash_size(self):
        assert Config.PERCEPTUAL_HASH_SIZE == 16

    def test_hash_target(self):
        assert Config.PERCEPTUAL_HASH_TARGET == "images"

    def test_highfreq_factor(self):
        assert Config.PERCEPTUAL_HASH_HIGHFREQ_FACTOR == 4

    def test_hash_size_is_power_of_2(self):
        size = Config.PERCEPTUAL_HASH_SIZE
        assert size > 0 and (size & (size - 1)) == 0


# =============================================================================
# CACHE AND MEMORY
# =============================================================================

class TestCacheMemory:
    """Tests de configuración de caché y memoria."""

    def test_get_max_cache_entries_returns_int(self):
        result = Config.get_max_cache_entries()
        assert isinstance(result, int)

    def test_get_max_cache_entries_minimum(self):
        result = Config.get_max_cache_entries()
        assert result >= 5000

    def test_get_max_cache_entries_maximum(self):
        result = Config.get_max_cache_entries()
        assert result <= 200000

    def test_get_max_cache_entries_with_file_count(self):
        result = Config.get_max_cache_entries(file_count=1000)
        assert isinstance(result, int)
        assert result >= 5000

    def test_get_large_dataset_threshold_returns_int(self):
        result = Config.get_large_dataset_threshold()
        assert isinstance(result, int)

    def test_get_large_dataset_threshold_minimum(self):
        result = Config.get_large_dataset_threshold()
        assert result >= 3000

    def test_get_large_dataset_threshold_maximum(self):
        result = Config.get_large_dataset_threshold()
        assert result <= 50000

    def test_similarity_dialog_auto_open_threshold(self):
        result = Config.get_similarity_dialog_auto_open_threshold()
        assert isinstance(result, int)
        # Should be 60% of large dataset threshold
        expected = int(Config.get_large_dataset_threshold() * 0.6)
        assert result == expected


# =============================================================================
# UI AND BEHAVIOR CONSTANTS
# =============================================================================

class TestUIConstants:
    """Tests de constantes de UI y comportamiento."""

    def test_ui_update_interval(self):
        assert Config.UI_UPDATE_INTERVAL == 10

    def test_final_delay_before_stage3(self):
        assert Config.FINAL_DELAY_BEFORE_STAGE3_SECONDS == 1.0

    def test_final_delay_is_positive(self):
        assert Config.FINAL_DELAY_BEFORE_STAGE3_SECONDS > 0


# =============================================================================
# DEVELOPMENT MODE
# =============================================================================

class TestDevelopmentMode:
    """Tests de configuración de desarrollo."""

    def test_development_mode_is_bool(self):
        assert isinstance(Config.DEVELOPMENT_MODE, bool)

    def test_saved_cache_dev_mode_path_is_string(self):
        assert isinstance(Config.SAVED_CACHE_DEV_MODE_PATH, str)

    def test_saved_cache_path_contains_base_dir(self):
        assert "cache_saved" in Config.SAVED_CACHE_DEV_MODE_PATH

    def test_skip_first_launch_about_is_bool(self):
        assert isinstance(Config.SKIP_FIRST_LAUNCH_ABOUT, bool)

    def test_dev_reset_first_launch_is_bool(self):
        assert isinstance(Config.DEV_RESET_FIRST_LAUNCH, bool)


# =============================================================================
# SYSTEM INFO
# =============================================================================

class TestSystemInfo:
    """Tests de get_system_info()."""

    def test_get_system_info_returns_dict(self):
        result = Config.get_system_info()
        assert isinstance(result, dict)

    def test_system_info_has_required_keys(self):
        info = Config.get_system_info()
        required_keys = [
            'ram_total_gb', 'cpu_count', 'io_workers', 'cpu_workers',
            'max_cache_entries', 'large_dataset_threshold', 'auto_open_threshold',
        ]
        for key in required_keys:
            assert key in info, f"Missing key: {key}"

    def test_system_info_ram_is_positive(self):
        info = Config.get_system_info()
        assert info['ram_total_gb'] > 0

    def test_system_info_cpu_count_positive(self):
        info = Config.get_system_info()
        assert info['cpu_count'] >= 1

    def test_system_info_workers_positive(self):
        info = Config.get_system_info()
        assert info['io_workers'] >= 4
        assert info['cpu_workers'] >= 4
