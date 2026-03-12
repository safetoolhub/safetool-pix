# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Gestor de configuración persistente.
Maneja preferencias de usuario que persisten entre sesiones.

Usa un backend de almacenamiento inyectable (StorageBackend) para desacoplar
de PyQt6. Por defecto intenta usar QSettingsBackend si PyQt6 está disponible,
sino usa JsonStorageBackend.
"""
from pathlib import Path
from typing import Any, Optional

from utils.logger import get_logger
from utils.storage import StorageBackend, JsonStorageBackend


class SettingsManager:
    """Gestor centralizado de configuración de usuario persistente"""

    # Constantes para claves de configuración
    # === DIRECTORIOS ===
    KEY_LOGS_DIR = "directories/logs"
    KEY_BACKUP_DIR = "directories/backups"

    # === COMPORTAMIENTO ===
    KEY_AUTO_BACKUP = "behavior/auto_backup_enabled"
    KEY_CONFIRM_OPERATIONS = "behavior/confirm_operations"
    KEY_CONFIRM_DELETE = "behavior/confirm_delete"
    KEY_CONFIRM_REANALYZE = "behavior/confirm_reanalyze"
    KEY_AUTO_ANALYZE = "behavior/auto_analyze_on_open"

    # === LOGGING ===
    KEY_LOG_LEVEL = "logging/level"
    KEY_DUAL_LOG_ENABLED = "logging/dual_log_enabled"
    KEY_DISABLE_FILE_LOGGING = "logging/disable_file_logging"

    # === AVANZADO ===
    KEY_DRY_RUN_DEFAULT = "advanced/dry_run_default"
    KEY_MAX_WORKERS = "advanced/max_workers"
    
    # === ANÁLISIS INICIAL (movido a General) ===
    KEY_PRECALCULATE_HASHES = "General/precalculate_hashes"
    KEY_PRECALCULATE_IMAGE_EXIF = "General/precalculate_image_exif"
    KEY_PRECALCULATE_VIDEO_EXIF = "General/precalculate_video_exif"

    # === VENTANA ===
    KEY_WINDOW_GEOMETRY = "window/geometry"
    KEY_WINDOW_STATE = "window/state"

    # === INTERFAZ ===
    KEY_SHOW_FULL_PATH = "interface/show_full_directory_path"
    KEY_DIRECTORY_HISTORY = "interface/directory_history"
    KEY_ANALYSIS_TIMESTAMP = "interface/analysis_timestamp"  # Timestamp del último análisis
    KEY_LANGUAGE = "interface/language"
    KEY_FIRST_LAUNCH_SHOWN = "interface/first_launch_about_shown"  # Si ya se mostró el about en el primer lanzamiento

    def __init__(self, backend: Optional[StorageBackend] = None,
                 organization: str = "SafeToolPix", application: str = "SafeTool Pix"):
        """
        Inicializa el gestor de configuración.

        Args:
            backend: Backend de almacenamiento a usar. Si es None, intenta usar
                    QSettingsBackend (si PyQt6 disponible), sino JsonStorageBackend.
            organization: Nombre de la organización (solo para QSettingsBackend)
            application: Nombre de la aplicación (solo para QSettingsBackend)
        """
        self.logger = get_logger('SettingsManager')
        
        if backend is None:
            # Intentar usar QSettings si está disponible, sino JSON
            try:
                from utils.storage import QSettingsBackend
                backend = QSettingsBackend(organization, application)
                self.logger.debug("Using QSettingsBackend")
            except ImportError:
                backend = JsonStorageBackend()
                self.logger.debug("PyQt6 not available, using JsonStorageBackend")
        
        self.backend = backend
        self.logger.debug(f"SettingsManager initialized with {type(backend).__name__}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración.

        Args:
            key: Clave de configuración
            default: Valor por defecto si no existe

        Returns:
            Valor guardado o default
        """
        value = self.backend.get(key, default)
        self.logger.debug(f"get({key}) = {value} (default={default})")
        return value

    def set(self, key: str, value: Any) -> None:
        """
        Guarda un valor de configuración.

        Args:
            key: Clave de configuración
            value: Valor a guardar
        """
        self.logger.debug(f"set({key}, {value})")
        self.backend.set(key, value)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Obtiene un valor booleano de configuración.

        Args:
            key: Clave de configuración
            default: Valor por defecto

        Returns:
            Valor booleano
        """
        value = self.backend.get(key, default)
        # QSettings puede devolver strings "true"/"false" en algunos casos
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value)

    def get_int(self, key: str, default: int = 0) -> int:
        """
        Obtiene un valor entero de configuración.

        Args:
            key: Clave de configuración
            default: Valor por defecto

        Returns:
            Valor entero
        """
        value = self.backend.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_path(self, key: str, default: Optional[Path] = None) -> Optional[Path]:
        """
        Obtiene un valor de ruta de configuración.

        Args:
            key: Clave de configuración
            default: Valor por defecto

        Returns:
            Path o None
        """
        value = self.backend.get(key, default)
        if value is None:
            return default
        return Path(value)

    def remove(self, key: str) -> None:
        """
        Elimina una clave de configuración.

        Args:
            key: Clave a eliminar
        """
        self.logger.debug(f"remove({key})")
        self.backend.remove(key)

    def clear_all(self) -> None:
        """Elimina toda la configuración guardada"""
        self.logger.warning("Clearing all settings")
        self.backend.clear()

    def has_key(self, key: str) -> bool:
        """
        Verifica si existe una clave.

        Args:
            key: Clave a verificar

        Returns:
            True si existe
        """
        return self.backend.contains(key)

    # === MÉTODOS DE CONVENIENCIA PARA CONFIGURACIÓN COMÚN ===

    def get_auto_backup_enabled(self) -> bool:
        """Obtiene si los backups automáticos están habilitados (por defecto True)"""
        return self.get_bool(self.KEY_AUTO_BACKUP, True)

    def set_auto_backup_enabled(self, enabled: bool) -> None:
        """Establece si los backups automáticos están habilitados"""
        self.set(self.KEY_AUTO_BACKUP, enabled)

    def get_log_level(self, default: str = "INFO") -> str:
        """Obtiene el nivel de log guardado"""
        return str(self.get(self.KEY_LOG_LEVEL, default)).upper()

    def set_log_level(self, level: str) -> None:
        """Establece el nivel de log"""
        self.set(self.KEY_LOG_LEVEL, level.upper())

    def get_dual_log_enabled(self) -> bool:
        """Obtiene si el log dual (warnings/errors) está habilitado (por defecto True)"""
        return self.get_bool(self.KEY_DUAL_LOG_ENABLED, True)

    def set_dual_log_enabled(self, enabled: bool) -> None:
        """Establece si el log dual (warnings/errors) está habilitado"""
        self.set(self.KEY_DUAL_LOG_ENABLED, enabled)

    def get_disable_file_logging(self) -> bool:
        """Obtiene si la escritura de logs en disco está deshabilitada (por defecto False).
        
        Cuando True: no se escriben archivos de log, solo WARNING/ERROR en consola.
        Cuando False (default): comportamiento normal de logging.
        """
        return self.get_bool(self.KEY_DISABLE_FILE_LOGGING, False)

    def set_disable_file_logging(self, disabled: bool) -> None:
        """Establece si la escritura de logs en disco debe deshabilitarse"""
        self.set(self.KEY_DISABLE_FILE_LOGGING, disabled)

    def get_logs_directory(self, default: Optional[Path] = None) -> Optional[Path]:
        """Obtiene el directorio de logs configurado"""
        return self.get_path(self.KEY_LOGS_DIR, default)

    def set_logs_directory(self, path: Path) -> None:
        """Establece el directorio de logs"""
        self.set(self.KEY_LOGS_DIR, str(path))

    def get_backup_directory(self, default: Optional[Path] = None) -> Optional[Path]:
        """Obtiene el directorio de backups configurado"""
        return self.get_path(self.KEY_BACKUP_DIR, default)

    def set_backup_directory(self, path: Path) -> None:
        """Establece el directorio de backups"""
        self.set(self.KEY_BACKUP_DIR, str(path))

    def get_confirm_operations(self) -> bool:
        """Obtiene si se debe confirmar operaciones (por defecto True)"""
        return self.get_bool(self.KEY_CONFIRM_OPERATIONS, True)

    def get_confirm_delete(self) -> bool:
        """Obtiene si se debe confirmar eliminaciones (por defecto True)"""
        return self.get_bool(self.KEY_CONFIRM_DELETE, True)

    def get_confirm_reanalyze(self) -> bool:
        """Obtiene si se debe confirmar antes de reanalizar tras operaciones (por defecto True)"""
        return self.get_bool(self.KEY_CONFIRM_REANALYZE, True)

    def get_auto_analyze(self) -> bool:
        """Obtiene si se debe auto-analizar al abrir directorio (por defecto False)"""
        return self.get_bool(self.KEY_AUTO_ANALYZE, False)

    def get_max_workers(self, default: int = 4) -> int:
        """Obtiene el número máximo de workers"""
        return self.get_int(self.KEY_MAX_WORKERS, default)
    
    def get_precalculate_hashes(self) -> bool:
        """Obtiene si se debe pre-calcular hashes SHA256 durante el escaneo (por defecto True)"""
        return self.get_bool(self.KEY_PRECALCULATE_HASHES, True)
    
    def set_precalculate_hashes(self, enabled: bool) -> None:
        """Establece si se debe pre-calcular hashes SHA256 durante el escaneo"""
        self.set(self.KEY_PRECALCULATE_HASHES, enabled)
    
    def get_precalculate_image_exif(self) -> bool:
        """Obtiene si se debe pre-calcular EXIF de imágenes durante el escaneo (por defecto True)"""
        return self.get_bool(self.KEY_PRECALCULATE_IMAGE_EXIF, True)
    
    def set_precalculate_image_exif(self, enabled: bool) -> None:
        """Establece si se debe pre-calcular EXIF de imágenes durante el escaneo"""
        self.set(self.KEY_PRECALCULATE_IMAGE_EXIF, enabled)
    
    def get_precalculate_video_exif(self) -> bool:
        """Obtiene si se debe pre-calcular EXIF de videos durante el escaneo (por defecto False)"""
        return self.get_bool(self.KEY_PRECALCULATE_VIDEO_EXIF, False)
    
    def set_precalculate_video_exif(self, enabled: bool) -> None:
        """Establece si se debe pre-calcular EXIF de videos durante el escaneo"""
        self.set(self.KEY_PRECALCULATE_VIDEO_EXIF, enabled)

    def get_show_full_path(self) -> bool:
        """Obtiene si se debe mostrar la ruta completa del directorio (por defecto True)"""
        return self.get_bool(self.KEY_SHOW_FULL_PATH, True)

    def set_show_full_path(self, enabled: bool) -> None:
        """Establece si se debe mostrar la ruta completa del directorio"""
        self.set(self.KEY_SHOW_FULL_PATH, enabled)

    def get_directory_history(self, max_items: int = 10) -> list:
        """Obtiene el historial de directorios recientes (máximo 10)"""
        history = self.get(self.KEY_DIRECTORY_HISTORY, [])
        if not isinstance(history, list):
            return []
        return history[:max_items]

    def add_to_directory_history(self, directory_path: str) -> None:
        """Agrega un directorio al historial (mantiene últimos 10, sin duplicados)"""
        history = self.get_directory_history()
        path_str = str(directory_path)
        
        # Remover si ya existe (para moverlo al principio)
        if path_str in history:
            history.remove(path_str)
        
        # Agregar al principio
        history.insert(0, path_str)
        
        # Mantener máximo 10 elementos
        history = history[:10]
        
        self.set(self.KEY_DIRECTORY_HISTORY, history)

    def get_analysis_timestamp(self) -> Optional[str]:
        """Obtiene el timestamp del último análisis"""
        return self.get(self.KEY_ANALYSIS_TIMESTAMP, None)

    def set_analysis_timestamp(self, timestamp: str) -> None:
        """Establece el timestamp del último análisis"""
        self.set(self.KEY_ANALYSIS_TIMESTAMP, timestamp)

    def get_last_folder(self) -> Optional[str]:
        """Obtiene la última carpeta analizada"""
        return self.get('last_analyzed_folder', None)

    def set_last_folder(self, folder_path: str) -> None:
        """Establece la última carpeta analizada"""
        self.set('last_analyzed_folder', folder_path)

    def get_language(self, default: str = "es") -> str:
        """Get the configured UI language code (default: 'es')."""
        return str(self.get(self.KEY_LANGUAGE, default))

    def set_language(self, lang: str) -> None:
        """Set the UI language code."""
        self.set(self.KEY_LANGUAGE, lang)


# Instancia global del gestor de configuración
# Por defecto intenta usar QSettingsBackend si PyQt6 está disponible
settings_manager = SettingsManager()
