# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Configuración centralizada para SafeTool Pix
"""
from pathlib import Path
from typing import Optional, Dict

from utils.platform_utils import get_cpu_count, get_system_ram_gb, get_system_info as sys_get_system_info


class Config:
    """Configuración principal de la aplicación"""

    # ========================================================================
    # 1. INFORMACIÓN DE LA APLICACIÓN
    # ========================================================================
    APP_NAME = "SafeTool Pix"
    APP_VERSION = "0.9.7"
    APP_VERSION_SUFFIX: str = "beta"  # "beta", "rc1", "" (empty for stable)
    APP_AUTHOR = "SafeToolHub"
    APP_CONTACT = "safetoolhub@protonmail.com"
    APP_WEBSITE = "https://safetoolhub.org"
    APP_REPO = "https://github.com/safetoolhub/safetool-pix"
    APP_DESCRIPTION = "Privacy-first photo and video management. 100% local, no cloud."
    APP_LICENSE = "GPLv3"
    APP_ATTRIBUTION_REQUIREMENT = "Mandatory attribution to SafeToolHub and safetoolhub.org"
    
    @classmethod
    def get_full_version(cls) -> str:
        """Returns full version string, e.g. '0.8.0-beta' or '1.0.0'."""
        if cls.APP_VERSION_SUFFIX:
            return f"{cls.APP_VERSION}-{cls.APP_VERSION_SUFFIX}"
        return cls.APP_VERSION

    # ========================================================================
    # 2. RUTAS Y DIRECTORIOS
    # ========================================================================
    DEFAULT_BASE_DIR = Path.home() / "SafeTool_Pix"
    DEFAULT_LOG_DIR = DEFAULT_BASE_DIR / "logs"
    DEFAULT_BACKUP_DIR = DEFAULT_BASE_DIR / "backups"
    DEFAULT_CACHE_SAVED_DIR = DEFAULT_BASE_DIR / "cache_saved"
    
    # Rutas de assets
    ASSETS_DIR = Path(__file__).resolve().parent / "assets"
    APP_ICON_PATH = ASSETS_DIR / "icon.png"

    # ========================================================================
    # 3. LOGGING
    # ========================================================================
    LOG_LEVEL = "INFO"
    
    # Rotación de logs
    MAX_LOG_FILE_SIZE_MB = 10  # 10 MB
    MAX_LOG_BACKUP_COUNT = 9999  # "Ilimitado"

    # ========================================================================
    # 4. RENDIMIENTO Y WORKERS
    # ========================================================================
    # Factores de cálculo para workers dinámicos
    _WORKER_FACTOR_PER_CORE = 2  # 2 workers por core (I/O bound)
    _MIN_WORKERS = 4
    _MAX_WORKERS = 16
    
    MAX_WORKER_THREADS = 16  # Límite máximo absoluto para la UI

    @classmethod
    def get_cpu_count(cls) -> int:
        """Wrapper para utils.system_utils.get_cpu_count"""
        return get_cpu_count()

    @classmethod
    def get_optimal_worker_threads(cls) -> int:
        """
        Calcula workers para I/O bound (lectura, hashing).
        Fórmula: min(max(cores * 2, 4), 16)
        """
        cores = get_cpu_count()
        optimal = cores * cls._WORKER_FACTOR_PER_CORE
        return max(cls._MIN_WORKERS, min(optimal, cls._MAX_WORKERS))
    
    @classmethod
    def get_cpu_bound_workers(cls) -> int:
        """
        Calcula workers para CPU bound (análisis imágenes).
        Fórmula: 1x cores
        """
        cores = get_cpu_count()
        return max(cls._MIN_WORKERS, min(cores, cls._MAX_WORKERS))
    
    @classmethod
    def get_actual_worker_threads(cls, override: int = 0, io_bound: bool = True) -> int:
        """Determina el número final de workers respetando override."""
        if override > 0:
            return min(override, cls.MAX_WORKER_THREADS)
        return cls.get_optimal_worker_threads() if io_bound else cls.get_cpu_bound_workers()

    # ========================================================================
    # 5. EXTENSIONES SOPORTADAS
    # ========================================================================
    SUPPORTED_IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.heic', '.heif',
        '.tiff', '.tif', '.bmp', '.webp',
        # Uppercase variants
        '.JPG', '.JPEG', '.PNG', '.HEIC', '.HEIF',
        '.TIFF', '.TIF', '.BMP', '.WEBP'
    }

    SUPPORTED_VIDEO_EXTENSIONS = {
        '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv',
        # Uppercase variants
        '.MP4', '.MOV', '.AVI', '.MKV', '.WMV', '.FLV'
    }

    ALL_SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS

    # ========================================================================
    # 6. LÍMITES Y UMBRALES DE ANÁLISIS
    # ========================================================================
    
    # Configuración para detección de duplicados HEIC/JPG
    MAX_TIME_DIFFERENCE_SECONDS = 1  # Tolerancia máxima de tiempo entre archivos duplicados (segundos)
    
    # Live Photos
    LIVE_PHOTO_MAX_TIME_DIFFERENCE_SECONDS = 50  # Tolerancia máxima entre imagen y video de Live Photo (segundos)
    LIVE_PHOTO_MAX_VIDEO_SIZE = 8 * 1024 * 1024  # 8 MB (solo para warning, no para filtrado)
    LIVE_PHOTO_MAX_VIDEO_DURATION_SECONDS = 3.6  # Videos > 3.6s no se eliminan (Live Photos alrededor de 3s)

    # Archivos Similares (Clustering)
    MAX_HAMMING_THRESHOLD = 20  # Máximo threshold de distancia de Hamming (0-20)
    
    # ========================================================================
    # 6.1 CONFIGURACIÓN DE HASH PERCEPTUAL (INTERNO - NO MODIFICAR)
    # ========================================================================
    # Configuración óptima determinada por benchmarks y uso real:
    # - phash (Perceptual Hash): Más robusto para detectar ediciones, recortes,
    #   cambios de resolución y ajustes de brillo/contraste. Basado en DCT.
    # - hash_size=16: 256 bits. Excelente balance velocidad/precisión.
    # - target=images: Videos son costosos y raramente tienen "similares".
    # - highfreq_factor=4: Suficiente para la mayoría de casos.
    PERCEPTUAL_HASH_ALGORITHM = "phash"
    PERCEPTUAL_HASH_SIZE = 16
    PERCEPTUAL_HASH_TARGET = "images"
    PERCEPTUAL_HASH_HIGHFREQ_FACTOR = 4

    # ========================================================================
    # 7. GESTIÓN DE MEMORIA Y CACHÉ
    # ========================================================================
    @classmethod
    def get_max_cache_entries(cls, file_count: Optional[int] = None) -> int:
        """Calcula entradas de caché máximas basado en RAM."""
        ram_gb = get_system_ram_gb()
        
        if file_count is None:
            max_entries = int(ram_gb * 1000)
        else:
            cache_needed = file_count
            available_ram_kb = ram_gb * 1024 * 1024 * 0.1  # 10% RAM
            max_entries_by_ram = int(available_ram_kb)
            max_entries = min(cache_needed, max_entries_by_ram)
            max_entries = max(max_entries, int(ram_gb * 1000))
        
        return max(5000, min(200000, max_entries))
    
    @classmethod
    def get_large_dataset_threshold(cls) -> int:
        """Umbral para dataset grande (optimizaciones de memoria)."""
        ram_gb = get_system_ram_gb()
        threshold = int(ram_gb * 500)
        return max(3000, min(50000, threshold))
    
    @classmethod
    def get_similarity_dialog_auto_open_threshold(cls) -> int:
        """Umbral para auto-abrir diálogo de similares."""
        return int(cls.get_large_dataset_threshold() * 0.6)

    # ========================================================================
    # 8. CONSTANTES DE UI Y COMPORTAMIENTO
    # ========================================================================
    UI_UPDATE_INTERVAL = 10
    FINAL_DELAY_BEFORE_STAGE3_SECONDS = 1.0

    # ========================================================================
    # 9. DESARROLLO
    # ========================================================================
    DEVELOPMENT_MODE = False
    SAVED_CACHE_DEV_MODE_PATH = str(DEFAULT_CACHE_SAVED_DIR / "dev_cache.json")
    SKIP_FIRST_LAUNCH_ABOUT = False  # Si True, nunca muestra el about_dialog automático al primer lanzamiento
    DEV_RESET_FIRST_LAUNCH = False   # TEMPORAL: Si True, resetea el flag para que el about vuelva a aparecer
    
    @classmethod
    def get_system_info(cls) -> Dict:
        """Delegado a system_utils, inyectando getters de configuración."""
        return sys_get_system_info(
            max_cache_entries_func=cls.get_max_cache_entries,
            large_dataset_threshold_func=cls.get_large_dataset_threshold,
            auto_open_threshold_func=cls.get_similarity_dialog_auto_open_threshold,
            io_workers_func=cls.get_optimal_worker_threads,
            cpu_workers_func=cls.get_cpu_bound_workers
        )
