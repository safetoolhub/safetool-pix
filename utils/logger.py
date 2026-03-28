# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Logger para SafeTool Pix

Convenciones de niveles de log:
- DEBUG: detalles internos de bajo nivel, útiles para debugging
- INFO: operaciones importantes completadas exitosamente
- WARNING: situaciones recuperables que merecen atención
- ERROR: errores que requieren atención inmediata

Todos los mensajes de log deben ser texto plano, sin HTML.

Thread-safety:
- Los logs están protegidos con un lock para evitar mezclas en ambientes concurrentes
- El procesamiento paralelo no se ve afectado, solo se serializan las escrituras de logs

File management:
- Logs se escriben tanto a archivo como a consola
- Archivo de log timestamped en directorio configurable
- Método para cambiar directorio de logs en runtime
"""
import logging
import sys
import re
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler


# Logger raíz para toda la aplicación
_ROOT_LOGGER_NAME = 'SafeToolPix'
_root_logger = None
_current_level = logging.INFO
_log_lock = threading.RLock()  # RLock permite re-entrada del mismo thread
_log_file: Optional[Path] = None
_log_file_warnings: Optional[Path] = None  # Archivo solo para WARNING/ERROR
_logs_directory: Optional[Path] = None
_dual_log_enabled = True  # Por defecto habilitado
_file_logging_disabled = False  # Cuando True, no se escriben archivos y solo WARNING/ERROR en consola


class ThreadSafeHandler(logging.Handler):
    """
    Base handler thread-safe que usa un RLock para serializar escrituras de logs.
    
    RLock (re-entrant lock) permite que el mismo thread adquiera el lock
    múltiples veces, evitando deadlocks en log_block().
    
    Esto evita que los logs de múltiples threads se mezclen, manteniendo
    cada mensaje completo sin interrupciones.
    """
    
    def emit(self, record):
        """Emite el log usando el RLock global para thread-safety"""
        with _log_lock:
            super().emit(record)


class ThreadSafeStreamHandler(ThreadSafeHandler, logging.StreamHandler):
    """Stream handler con thread-safety"""
    pass


class ThreadSafeFileHandler(ThreadSafeHandler, logging.FileHandler):
    """File handler con thread-safety"""
    pass


class ThreadSafeRotatingFileHandler(RotatingFileHandler):
    """
    Rotating file handler con thread-safety para rotación por tamaño.
    
    Mejora sobre RotatingFileHandler estándar:
    - Usa RLock global para thread-safety que permite re-entrada
    - Verifica el tamaño del archivo al inicializarse
    - Si el archivo ya existe y excede maxBytes, lo rota inmediatamente
    - Esto previene que archivos crezcan indefinidamente durante sesiones largas
    - Mantiene la lógica completa de rotación de RotatingFileHandler.emit()
    """
    
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False):
        """
        Inicializa el handler y rota el archivo si ya es muy grande.
        
        Args:
            filename: Ruta del archivo de log
            mode: Modo de apertura ('a' para append)
            maxBytes: Tamaño máximo antes de rotar (0 = sin límite)
            backupCount: Número de backups a mantener (0 = ilimitado)
            encoding: Codificación del archivo
            delay: Si True, retrasa la apertura del archivo
        """
        # Llamar al constructor padre de RotatingFileHandler
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        
        # Verificar si el archivo ya existe y es demasiado grande
        if maxBytes > 0 and not delay:
            try:
                from pathlib import Path
                log_path = Path(filename)
                if log_path.exists():
                    current_size = log_path.stat().st_size
                    if current_size >= maxBytes:
                        # Archivo existente es muy grande, rotarlo inmediatamente
                        self.doRollover()
            except Exception:
                # Si falla la verificación, continuar normalmente
                pass
    
    def emit(self, record):
        """
        Emite un registro de log con rotación automática y thread-safety.
        
        Este método reimplementa RotatingFileHandler.emit() pero usando
        nuestro RLock global en lugar del lock interno del handler.
        Esto permite thread-safety verdadera entre múltiples handlers.
        """
        try:
            # Usar nuestro lock global en lugar del lock interno
            with _log_lock:
                # Verificar si debemos rotar
                if self.shouldRollover(record):
                    self.doRollover()
                # Escribir el registro usando FileHandler.emit()
                logging.FileHandler.emit(self, record)
        except Exception:
            self.handleError(record)


def _ensure_root_logger():
    """Asegura que el logger raíz esté configurado"""
    global _root_logger, _current_level
    
    if _root_logger is None:
        _root_logger = logging.getLogger(_ROOT_LOGGER_NAME)
        
        # Si file logging está deshabilitado, forzar WARNING
        effective_level = logging.WARNING if _file_logging_disabled else _current_level
        _root_logger.setLevel(effective_level)
        
        if not _root_logger.handlers:
            # Formato mejorado con nombre del módulo para mejor trazabilidad
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Handler thread-safe para consola
            stream_handler = ThreadSafeStreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            if _file_logging_disabled:
                stream_handler.setLevel(logging.WARNING)
            _root_logger.addHandler(stream_handler)
            
            # File handlers solo si file logging está habilitado
            if not _file_logging_disabled:
                # Handler thread-safe para archivo (si se ha configurado)
                if _log_file:
                    try:
                        from config import Config
                        max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)  # Convertir MB a bytes
                        backup_count = Config.MAX_LOG_BACKUP_COUNT
                        
                        file_handler = ThreadSafeRotatingFileHandler(
                            _log_file, 
                            maxBytes=max_bytes,
                            backupCount=backup_count,
                            encoding='utf-8'
                        )
                        file_handler.setFormatter(formatter)
                        _root_logger.addHandler(file_handler)
                    except Exception as e:
                        # If creating file fails, use console only
                        _root_logger.error(f"Could not create log file: {e}")
                
                # Handler adicional para WARNING/ERROR si está habilitado
                if _log_file_warnings and _dual_log_enabled:
                    try:
                        from config import Config
                        max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
                        backup_count = Config.MAX_LOG_BACKUP_COUNT
                        
                        warning_handler = ThreadSafeRotatingFileHandler(
                            _log_file_warnings,
                            maxBytes=max_bytes,
                            backupCount=backup_count,
                            encoding='utf-8'
                        )
                        warning_handler.setFormatter(formatter)
                        warning_handler.setLevel(logging.WARNING)  # Solo WARNING y ERROR
                        _root_logger.addHandler(warning_handler)
                    except Exception as e:
                        _root_logger.error(f"Could not create warnings log file: {e}")
    
    return _root_logger


def set_global_log_level(level):
    """Configura el nivel de log globalmente para todos los loggers
    
    Args:
        level: logging.DEBUG, logging.INFO, logging.WARNING, o logging.ERROR
    """
    global _current_level
    _current_level = level
    
    # Actualizar el logger raíz
    root = _ensure_root_logger()
    root.setLevel(level)
    
    # Actualizar todos los loggers hijos
    for name in logging.Logger.manager.loggerDict:
        if name.startswith(_ROOT_LOGGER_NAME):
            logger = logging.getLogger(name)
            logger.setLevel(level)


class SimpleLogger:
    """Logger simplificado para la aplicación con niveles estandarizados"""

    def __init__(self, name="SafeToolPix"):
        # Crear logger hijo del logger raíz
        if name == "SafeToolPix":
            self.logger = _ensure_root_logger()
        else:
            # Crear como hijo del logger raíz para heredar configuración
            full_name = f"{_ROOT_LOGGER_NAME}.{name}"
            self.logger = logging.getLogger(full_name)
            self.logger.setLevel(_current_level)
            # Los handlers se heredan del padre, no agregar duplicados

    def debug(self, message):
        """Log de detalles internos para debugging"""
        self.logger.debug(self._sanitize_message(message))

    def info(self, message):
        """Log de operaciones importantes completadas"""
        self.logger.info(self._sanitize_message(message))

    def warning(self, message):
        """Log de situaciones recuperables"""
        self.logger.warning(self._sanitize_message(message))

    def error(self, message):
        """Log de errores que requieren atención"""
        self.logger.error(self._sanitize_message(message))

    def critical(self, message):
        """Log de errores críticos que impiden el funcionamiento"""
        self.logger.critical(self._sanitize_message(message))
    
    def log(self, level, message):
        """Log genérico con nivel especificado"""
        self.logger.log(level, self._sanitize_message(message))
    
    def setLevel(self, level):
        """Configura el nivel de log para este logger específico"""
        self.logger.setLevel(level)
    
    def isEnabledFor(self, level):
        """Verifica si el logger está habilitado para el nivel especificado"""
        return self.logger.isEnabledFor(level)
    
    def log_block(self, level, *messages):
        """
        Registra múltiples mensajes de forma atómica (sin interrupciones).
        
        Útil para logging de secciones que deben aparecer juntas en el log,
        especialmente en ambientes concurrentes.
        
        Args:
            level: logging.INFO, logging.DEBUG, etc.
            *messages: Mensajes a registrar en bloque
            
        Example:
            logger.log_block(logging.INFO,
                "=" * 80,
                "*** INICIANDO OPERACIÓN",
                "*** Archivos: 10",
                "=" * 80
            )
        """
        with _log_lock:
            for message in messages:
                sanitized = self._sanitize_message(message)
                self.logger.log(level, sanitized)

    @staticmethod
    def _sanitize_message(message):
        """Asegura que el mensaje sea texto plano en una sola línea, sin HTML"""
        if not isinstance(message, str):
            message = str(message)
        
        # Reemplazar saltos de línea HTML con espacio
        message = re.sub(r'<br\s*/?>', ' ', message)
        
        # Remover todas las etiquetas HTML
        message = re.sub(r'<[^>]+>', '', message)
        
        # Decodificar entidades HTML comunes
        message = message.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        message = message.replace('&nbsp;', ' ')
        
        # Reemplazar múltiples saltos de línea con espacio
        message = re.sub(r'\n+', ' ', message)
        
        # Reemplazar múltiples espacios con uno solo
        message = re.sub(r'\s+', ' ', message)
        
        # Limpiar espacios al inicio y final
        message = message.strip()
        
        return message


# Instancia global
logger = SimpleLogger()


def get_logger(name=None):
    """Obtiene una instancia de logger
    
    Args:
        name: Nombre del módulo/componente. Si es None, retorna el logger global
        
    Returns:
        SimpleLogger: Instancia de logger configurada
    """
    if name:
        return SimpleLogger(name)
    return logger


def configure_logging(
    logs_dir: Optional[Path | str] = None,
    level: str = "INFO",
    dual_log_enabled: bool = True,
    disable_file_logging: bool = False,
) -> tuple[Path, Path]:
    """
    Configura el sistema de logging con archivo y directorio.
    
    Debe llamarse al inicio de la aplicación antes de usar get_logger().
    Crea archivo de log timestamped y configura handlers para archivo y consola.
    Si dual_log_enabled=True y level es INFO o DEBUG, crea un segundo archivo
    solo con WARNING y ERROR.
    
    Args:
        logs_dir: Directorio donde guardar logs. Si es None, usa el directorio actual
        level: Nivel de logging ("DEBUG", "INFO", "WARNING", "ERROR")
        dual_log_enabled: Si True, crea archivo adicional para WARNING/ERROR (solo si level=INFO/DEBUG)
        disable_file_logging: Si True, no crea archivos de log y solo muestra WARNING/ERROR en consola
        
    Returns:
        tuple: (ruta_archivo_log, directorio_logs)
        
    Example:
        log_file, logs_dir = configure_logging(
            logs_dir=Path.home() / "Documents" / "MyApp" / "logs",
            level="INFO",
            dual_log_enabled=True
        )
    """
    global _log_file, _log_file_warnings, _logs_directory, _current_level, _root_logger, _dual_log_enabled, _file_logging_disabled
    
    _file_logging_disabled = disable_file_logging
    
    # Configurar directorio
    if logs_dir:
        _logs_directory = Path(logs_dir)
    else:
        _logs_directory = Path.cwd()
    
    try:
        _logs_directory.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        # Permission error: user lacks permissions to create directory
        import sys as _sys
        print(f"WARNING: Insufficient permissions to create logs directory '{_logs_directory}'", file=_sys.stderr)
        print(f"WARNING: Details: {e}", file=_sys.stderr)
        print(f"WARNING: Logs will be saved in current directory: {Path.cwd()}", file=_sys.stderr)
        _logs_directory = Path.cwd()
    except OSError as e:
        # Filesystem error (disk full, invalid name, etc.)
        import sys as _sys
        error_type = "Disk full" if e.errno == 28 else "Filesystem error"
        print(f"WARNING: {error_type} creating logs directory '{_logs_directory}'", file=_sys.stderr)
        print(f"WARNING: Details: {e}", file=_sys.stderr)
        print(f"WARNING: Logs will be saved in current directory: {Path.cwd()}", file=_sys.stderr)
        _logs_directory = Path.cwd()
    except Exception as e:
        # Other unexpected errors
        import sys as _sys
        print(f"WARNING: Unexpected error creating logs directory '{_logs_directory}'", file=_sys.stderr)
        print(f"WARNING: Type: {type(e).__name__}, Details: {e}", file=_sys.stderr)
        print(f"WARNING: Logs will be saved in current directory: {Path.cwd()}", file=_sys.stderr)
        _logs_directory = Path.cwd()
    
    # Configurar nivel
    level_upper = level.upper()
    _current_level = getattr(logging, level_upper, logging.INFO)
    _dual_log_enabled = dual_log_enabled
    
    # Si file logging está deshabilitado, forzar nivel WARNING para consola
    # y no crear archivos de log
    if _file_logging_disabled:
        _log_file = None
        _log_file_warnings = None
    else:
        # Crear archivo de log con timestamp y sufijo de nivel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _log_file = _logs_directory / f"safetool_pix_{timestamp}_{level_upper}.log"
        
        # Crear archivo adicional para WARNING/ERROR si está habilitado
        # Solo para niveles INFO o DEBUG (WARNING/ERROR ya tienen todo en el log principal)
        _log_file_warnings = None
        if _dual_log_enabled and level_upper in ('INFO', 'DEBUG'):
            _log_file_warnings = _logs_directory / f"safetool_pix_{timestamp}_WARNERROR.log"
    
    # Si el logger ya existe, limpiar handlers viejos
    if _root_logger is not None:
        for handler in _root_logger.handlers[:]:
            _root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
    
    # Crear/configurar logger raíz
    _root_logger = logging.getLogger(_ROOT_LOGGER_NAME)
    _root_logger.handlers = []  # Limpiar cualquier handler previo
    
    # Formato mejorado con nombre del módulo para mejor trazabilidad
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler thread-safe para consola
    stream_handler = ThreadSafeStreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    if _file_logging_disabled:
        # Solo WARNING y ERROR en consola cuando file logging está deshabilitado
        stream_handler.setLevel(logging.WARNING)
        _root_logger.setLevel(logging.WARNING)
    else:
        _root_logger.setLevel(_current_level)
    _root_logger.addHandler(stream_handler)
    
    # File handlers solo si file logging está habilitado
    if not _file_logging_disabled:
        # Handler thread-safe para archivo principal
        try:
            from config import Config
            max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)  # Convertir MB a bytes
            backup_count = Config.MAX_LOG_BACKUP_COUNT
            
            file_handler = ThreadSafeRotatingFileHandler(
                _log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            _root_logger.addHandler(file_handler)
        except Exception as e:
            _root_logger.error(f"Could not create log file: {e}")
        
        # Handler adicional para WARNING/ERROR si está habilitado
        if _log_file_warnings:
            try:
                from config import Config
                max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
                backup_count = Config.MAX_LOG_BACKUP_COUNT
                
                warning_handler = ThreadSafeRotatingFileHandler(
                    _log_file_warnings,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding='utf-8'
                )
                warning_handler.setFormatter(formatter)
                warning_handler.setLevel(logging.WARNING)  # Solo WARNING y ERROR
                _root_logger.addHandler(warning_handler)
            except Exception as e:
                _root_logger.error(f"Could not create warnings log file: {e}")
    
    # Actualizar todos los loggers hijos que ya existan para que hereden el nuevo nivel
    # Esto es necesario porque módulos pueden haber sido importados antes de configure_logging()
    # y sus loggers habrían sido creados con el nivel por defecto (INFO)
    effective_level = logging.WARNING if _file_logging_disabled else _current_level
    set_global_log_level(effective_level)
    
    return _log_file, _logs_directory


def change_logs_directory(new_dir: Path | str, dual_log_enabled: Optional[bool] = None) -> tuple[Path, Path]:
    """
    Cambia el directorio de logs en runtime y crea un nuevo archivo de log.
    
    Cierra el handler de archivo anterior y crea uno nuevo en el nuevo directorio.
    El StreamHandler de consola se mantiene sin cambios.
    
    Args:
        new_dir: Nuevo directorio para logs
        dual_log_enabled: Si especificado, actualiza la configuración de dual log
        
    Returns:
        tuple: (ruta_nuevo_archivo_log, nuevo_directorio_logs)
        
    Example:
        new_log_file, new_logs_dir = change_logs_directory(
            Path.home() / "Documents" / "MyApp" / "logs",
            dual_log_enabled=True
        )
    """
    global _log_file, _log_file_warnings, _logs_directory, _dual_log_enabled
    
    # Actualizar configuración de dual log si se especificó
    if dual_log_enabled is not None:
        _dual_log_enabled = dual_log_enabled
    
    # Configurar nuevo directorio
    _logs_directory = Path(new_dir)
    try:
        _logs_directory.mkdir(parents=True, exist_ok=True)
    except Exception:
        _logs_directory = Path.cwd()
    
    # Obtener nivel actual
    level_name = logging.getLevelName(_current_level)
    
    # Crear nuevo archivo de log con sufijo de nivel
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_file = _logs_directory / f"safetool_pix_{timestamp}_{level_name}.log"
    
    # Crear archivo adicional para WARNING/ERROR si está habilitado
    _log_file_warnings = None
    if _dual_log_enabled and level_name in ('INFO', 'DEBUG'):
        _log_file_warnings = _logs_directory / f"safetool_pix_{timestamp}_WARNERROR.log"
    
    root = _ensure_root_logger()
    
    # Remover handlers de archivo viejos
    old_file_handlers = [
        h for h in root.handlers 
        if isinstance(h, (logging.FileHandler, ThreadSafeFileHandler, ThreadSafeRotatingFileHandler))
    ]
    for handler in old_file_handlers:
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass  # Ignorar errores al cerrar
    
    # Crear nuevo file handler principal
    try:
        from config import Config
        max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
        backup_count = Config.MAX_LOG_BACKUP_COUNT
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler = ThreadSafeRotatingFileHandler(
            _log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(_current_level)
        root.addHandler(file_handler)
        
        root.info(f"Logs directory changed to: {_logs_directory}")
        root.info(f"New log file: {_log_file}")
    except Exception as e:
        root.error(f"Could not create new log file: {e}")
    
    # Crear handler adicional para WARNING/ERROR si está habilitado
    if _log_file_warnings:
        try:
            from config import Config
            max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
            backup_count = Config.MAX_LOG_BACKUP_COUNT
            
            warning_handler = ThreadSafeRotatingFileHandler(
                _log_file_warnings,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            warning_handler.setFormatter(formatter)
            warning_handler.setLevel(logging.WARNING)
            root.addHandler(warning_handler)
            root.info(f"Warnings/errors log file: {_log_file_warnings}")
        except Exception as e:
            root.error(f"Could not create warnings log file: {e}")
    
    return _log_file, _logs_directory


def is_dual_log_enabled() -> bool:
    """Retorna si el sistema de dual logging está habilitado"""
    return _dual_log_enabled


def set_dual_log_enabled(enabled: bool) -> None:
    """
    Activa o desactiva el sistema de dual logging.
    
    Esto reconfigurará los handlers de log. Si se activa y el nivel actual
    es INFO o DEBUG, se creará el archivo de WARNING/ERROR adicional.
    
    Args:
        enabled: True para activar dual logging, False para desactivar
    """
    global _dual_log_enabled, _log_file_warnings
    
    if _dual_log_enabled == enabled:
        return  # No hay cambio
    
    _dual_log_enabled = enabled
    root = _ensure_root_logger()
    level_name = logging.getLevelName(_current_level)
    
    if enabled and level_name in ('INFO', 'DEBUG') and _logs_directory:
        # Activar: crear archivo de warnings si no existe
        if not _log_file_warnings:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            _log_file_warnings = _logs_directory / f"safetool_pix_{timestamp}_WARNERROR.log"
            
            try:
                from config import Config
                max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
                backup_count = Config.MAX_LOG_BACKUP_COUNT
                
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                warning_handler = ThreadSafeRotatingFileHandler(
                    _log_file_warnings,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding='utf-8'
                )
                warning_handler.setFormatter(formatter)
                warning_handler.setLevel(logging.WARNING)
                root.addHandler(warning_handler)
                root.info(f"Dual logging enabled. Warnings/errors file: {_log_file_warnings}")
            except Exception as e:
                root.error(f"Could not create warnings log file: {e}")
    else:
        # Desactivar: remover handler de warnings
        handlers_to_remove = []
        for handler in root.handlers[:]:
            # Identificar handlers de archivo que apuntan a archivos WARNERROR
            if isinstance(handler, (ThreadSafeFileHandler, ThreadSafeRotatingFileHandler, logging.FileHandler)):
                # Verificar si es un handler de warnings/errors por su nivel o por el nombre del archivo
                if handler.level == logging.WARNING:
                    handlers_to_remove.append(handler)
                elif hasattr(handler, 'baseFilename') and '_WARNERROR' in handler.baseFilename:
                    handlers_to_remove.append(handler)
        
        for handler in handlers_to_remove:
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        
        if handlers_to_remove:
            root.info("Dual logging disabled")
        _log_file_warnings = None


def is_file_logging_disabled() -> bool:
    """Retorna si la escritura de logs en disco está deshabilitada"""
    return _file_logging_disabled


def set_file_logging_disabled(disabled: bool) -> None:
    """
    Activa o desactiva la escritura de logs en disco en runtime.
    
    Cuando se desactiva la escritura en disco:
    - Se eliminan todos los file handlers
    - Se configura el console handler para solo WARNING y ERROR
    - Los mensajes DEBUG e INFO se descartan completamente
    
    Cuando se reactiva:
    - Se reconfiguran los file handlers según la configuración actual
    - Se restaura el nivel de log original en consola
    
    Args:
        disabled: True para deshabilitar escritura en disco, False para habilitarla
    """
    global _file_logging_disabled
    
    if _file_logging_disabled == disabled:
        return  # No hay cambio
    
    _file_logging_disabled = disabled
    root = _ensure_root_logger()
    
    if disabled:
        # Deshabilitar: remover todos los file handlers y limitar consola a WARNING
        file_handlers = [
            h for h in root.handlers[:]
            if isinstance(h, (logging.FileHandler, ThreadSafeFileHandler, ThreadSafeRotatingFileHandler))
        ]
        for handler in file_handlers:
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        
        # Configurar consola solo para WARNING y ERROR
        for handler in root.handlers[:]:
            if isinstance(handler, (ThreadSafeStreamHandler, logging.StreamHandler)):
                handler.setLevel(logging.WARNING)
        root.setLevel(logging.WARNING)
        
        # Actualizar todos los loggers hijos
        set_global_log_level(logging.WARNING)
        
        root.warning("File logging disabled - only WARNING and ERROR will be shown in console")
    else:
        # Rehabilitar: reconfigurar con la configuración actual
        # Restaurar nivel original en consola
        for handler in root.handlers[:]:
            if isinstance(handler, (ThreadSafeStreamHandler, logging.StreamHandler)):
                handler.setLevel(logging.NOTSET)  # Hereda del logger padre
        root.setLevel(_current_level)
        
        # Recrear file handlers si hay directorio configurado
        if _logs_directory:
            from utils.logger import change_logs_directory
            change_logs_directory(_logs_directory, dual_log_enabled=_dual_log_enabled)
        
        # Actualizar todos los loggers hijos
        set_global_log_level(_current_level)
        
        root.info("File logging re-enabled")


# Funciones utilitarias para logging discreto (disponibles globalmente)
def log_section_header_discrete(logger, title: str, mode: str = ""):
    """
    Logging discreto de encabezado (para operaciones no relevantes como análisis).
    
    Args:
        logger: Instancia de logger
        title: Título de la sección
        mode: Modo opcional (ej: "SIMULACIÓN", "ANÁLISIS")
    
    Example:
        log_section_header_discrete(logger, "ANÁLISIS DE LIVE PHOTOS")
    """
    mode_label = f"[{mode.upper()}] " if mode else ""
    logger.log_block(
        logging.INFO,
        f"--- {mode_label}{title} ---"
    )


def log_section_footer_discrete(logger, result_summary: str):
    """
    Logging discreto de cierre (para operaciones no relevantes como análisis).
    
    Args:
        logger: Instancia de logger
        result_summary: Resumen del resultado
    
    Example:
        log_section_footer_discrete(logger, "Análisis completado: 5 Live Photos encontrados")
    """
    logger.log_block(
        logging.INFO,
        f"--- {result_summary} ---"
    )


def log_section_header_relevant(logger, title: str, mode: str = ""):
    """
    Logging estandarizado de encabezado con banner ASCII (para operaciones relevantes).
    
    Args:
        logger: Instancia de logger
        title: Título de la sección
        mode: Modo opcional (ej: "SIMULACIÓN", "ANÁLISIS")
    
    Example:
        log_section_header_relevant(logger, "INICIANDO RENOMBRADO", "SIMULACIÓN")
        # Resultado:
        # ================================================================================
        # *** [SIMULACIÓN] INICIANDO RENOMBRADO
        # ================================================================================
    """
    mode_label = f"[{mode.upper()}] " if mode else ""
    logger.log_block(
        logging.INFO,
        "=" * 80,
        f"*** {mode_label}{title}",
        "=" * 80
    )


def log_section_footer_relevant(logger, result_summary: str):
    """
    Logging estandarizado de cierre (para operaciones relevantes).
    
    Args:
        logger: Instancia de logger
        result_summary: Resumen del resultado
    
    Example:
        log_section_footer_relevant(logger, "Operación completada: 10 archivos procesados")
    """
    logger.log_block(
        logging.INFO,
        f"*** {result_summary}",
        "=" * 80
    )
