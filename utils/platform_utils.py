# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Utilidades multiplataforma para operaciones del sistema operativo.
Funciones independientes de UI para interactuar con el SO (abrir archivos, carpetas, etc.)
"""

import subprocess
import platform
import os
import shutil
import psutil
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Tuple
from dataclasses import dataclass
from utils.logger import get_logger
from utils.i18n import tr


logger = get_logger('PlatformUtils')


# =============================================================================
# SYSTEM TOOLS DETECTION
# =============================================================================

@dataclass
class ToolStatus:
    """Estado de una herramienta del sistema."""
    name: str
    available: bool
    path: Optional[str] = None
    version: Optional[str] = None
    error: Optional[str] = None


def find_executable(name: str) -> Optional[str]:
    """
    Busca un ejecutable en el PATH del sistema de forma multiplataforma.
    
    Args:
        name: Nombre del ejecutable (sin extensión en Windows)
    
    Returns:
        Ruta completa al ejecutable si se encuentra, None si no existe
    """
    # shutil.which funciona en Windows, Linux y macOS
    return shutil.which(name)


def get_tool_version(tool_name: str, version_args: list[str], timeout: int = 5) -> Optional[str]:
    """
    Obtiene la versión de una herramienta ejecutando un comando.
    
    Args:
        tool_name: Nombre del ejecutable
        version_args: Argumentos para obtener la versión (ej: ['-version'], ['-ver'])
        timeout: Tiempo máximo de espera en segundos
    
    Returns:
        String con la versión o None si falla
    """
    try:
        result = subprocess.run(
            [tool_name] + version_args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def check_ffprobe() -> ToolStatus:
    """
    Verifica si ffprobe está instalado y obtiene su versión.
    
    Returns:
        ToolStatus con información sobre ffprobe
    """
    path = find_executable('ffprobe')
    if not path:
        return ToolStatus(
            name='ffprobe',
            available=False,
            error=tr("platform.tool.ffprobe_not_installed")
        )
    
    version_output = get_tool_version('ffprobe', ['-version'])
    version = None
    if version_output:
        # Extraer primera línea: "ffprobe version X.X.X ..."
        first_line = version_output.split('\n')[0]
        version = first_line[:50] if len(first_line) > 50 else first_line
    
    return ToolStatus(
        name='ffprobe',
        available=True,
        path=path,
        version=version
    )


def check_exiftool() -> ToolStatus:
    """
    Verifica si exiftool está instalado y obtiene su versión.
    
    Returns:
        ToolStatus con información sobre exiftool
    """
    path = find_executable('exiftool')
    if not path:
        return ToolStatus(
            name='exiftool',
            available=False,
            error=tr("platform.tool.exiftool_not_installed")
        )
    
    version = get_tool_version('exiftool', ['-ver'])
    
    return ToolStatus(
        name='exiftool',
        available=True,
        path=path,
        version=version
    )


def are_video_tools_available() -> bool:
    """
    Verifica si las herramientas necesarias para extraer metadatos de video están disponibles.
    
    Para extraer metadatos de video (duración, fecha de creación) se necesita
    al menos una de estas herramientas: ffprobe o exiftool.
    
    Returns:
        True si al menos una herramienta está disponible, False si ninguna
    """
    return find_executable('ffprobe') is not None or find_executable('exiftool') is not None


def check_all_video_tools() -> Tuple[ToolStatus, ToolStatus]:
    """
    Verifica el estado de todas las herramientas de video.
    
    Returns:
        Tupla con (ffprobe_status, exiftool_status)
    """
    return check_ffprobe(), check_exiftool()


# =============================================================================
# CLIPBOARD OPERATIONS
# =============================================================================

def copy_to_clipboard(text: str, error_callback: Optional[Callable[[str], None]] = None) -> bool:
    """
    Copia texto al portapapeles de forma multiplataforma.
    
    Usa PyQt6 QClipboard internamente, que funciona en Linux, Windows y macOS.
    
    Args:
        text: Texto a copiar al portapapeles
        error_callback: Función opcional para manejar errores. Recibe el mensaje de error.
                       Si no se proporciona, los errores se registran en el log.
    
    Returns:
        True si se copió correctamente, False si hubo error
        
    Example:
        >>> from utils.platform_utils import copy_to_clipboard
        >>> copy_to_clipboard("/home/user/photos/IMG_001.jpg")
        True
    """
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QClipboard
        
        # QApplication debe existir para acceder al clipboard
        app = QApplication.instance()
        if app is None:
            error_msg = "No QApplication instance available"
            logger.warning(error_msg)
            if error_callback:
                error_callback(error_msg)
            return False
        
        clipboard = app.clipboard()
        clipboard.setText(text)
        logger.debug(f"Text copied to clipboard: {text[:50]}..." if len(text) > 50 else f"Text copied to clipboard: {text}")
        return True
        
    except ImportError as e:
        error_msg = f"PyQt6 not available for clipboard operations: {e}"
        logger.error(error_msg)
        if error_callback:
            error_callback(error_msg)
        return False
    except Exception as e:
        error_msg = f"Error copying to clipboard: {e}"
        logger.error(error_msg)
        if error_callback:
            error_callback(error_msg)
        return False


def get_install_instructions() -> Dict[str, str]:
    """
    Obtiene instrucciones de instalación de herramientas según el SO.
    
    Returns:
        Diccionario con instrucciones por sistema operativo
    """
    return {
        'linux_debian': 'sudo apt install ffmpeg libimage-exiftool-perl',
        'linux_fedora': 'sudo dnf install ffmpeg perl-Image-ExifTool',
        'linux_arch': 'sudo pacman -S ffmpeg perl-image-exiftool',
        'macos': 'brew install ffmpeg exiftool',
        'windows': tr("platform.install.windows_instructions")
    }


def get_current_os_install_hint() -> str:
    """
    Obtiene la sugerencia de instalación para el SO actual.
    
    Returns:
        String con el comando o instrucción de instalación
    """
    system = platform.system()
    
    if system == 'Linux':
        # Intentar detectar la distribución
        try:
            with open('/etc/os-release', 'r') as f:
                content = f.read().lower()
                if 'debian' in content or 'ubuntu' in content or 'mint' in content:
                    return 'sudo apt install ffmpeg libimage-exiftool-perl'
                elif 'fedora' in content or 'rhel' in content or 'centos' in content:
                    return 'sudo dnf install ffmpeg perl-Image-ExifTool'
                elif 'arch' in content or 'manjaro' in content:
                    return 'sudo pacman -S ffmpeg perl-image-exiftool'
        except (FileNotFoundError, PermissionError):
            pass
        return 'sudo apt install ffmpeg libimage-exiftool-perl'  # Default to Debian
    elif system == 'Darwin':
        return 'brew install ffmpeg exiftool'
    elif system == 'Windows':
        return tr("platform.install.windows_instructions")
    else:
        return tr("platform.install.generic_instructions")


# =============================================================================
# APPIMAGE ENVIRONMENT CLEANUP
# =============================================================================

def _is_running_in_appimage() -> bool:
    """Detect if the application is running inside an AppImage."""
    return bool(os.environ.get('APPIMAGE'))


def _get_clean_env_for_subprocess() -> Optional[dict]:
    """
    Return a clean environment dict for subprocess calls on Linux when running
    inside an AppImage. Returns None when no cleanup is needed (non-AppImage).

    AppImage injects LD_LIBRARY_PATH, LD_PRELOAD, PYTHONPATH, etc. into the
    environment. When we call host utilities (xdg-open, nautilus, etc.) they
    inherit those paths, loading wrong library versions and crashing silently.

    This helper restores the original host environment by:
    1. Removing AppImage-injected variables.
    2. Restoring APPIMAGE_ORIGINAL_* / APPRUN_ORIGINAL_* saved values.
    """
    if not _is_running_in_appimage():
        return None

    env = os.environ.copy()

    # Variables that AppImage / AppRun typically inject
    appimage_vars = [
        'LD_LIBRARY_PATH',
        'LD_PRELOAD',
        'PYTHONPATH',
        'PYTHONHOME',
        'GDK_PIXBUF_MODULE_FILE',
        'GDK_PIXBUF_MODULEDIR',
        'GSETTINGS_SCHEMA_DIR',
        'GTK_PATH',
        'GTK_EXE_PREFIX',
        'GTK_DATA_PREFIX',
        'XDG_DATA_DIRS',
        'QT_PLUGIN_PATH',
        'PERLLIB',
        'PERL5LIB',
        'GI_TYPELIB_PATH',
    ]

    for var in appimage_vars:
        # Try to restore the original value saved by AppRun
        for prefix in ('APPIMAGE_ORIGINAL_', 'APPRUN_ORIGINAL_', 'APPDIR_ORIGINAL_'):
            original_key = f"{prefix}{var}"
            if original_key in env:
                original_value = env[original_key]
                if original_value:
                    env[var] = original_value
                else:
                    env.pop(var, None)
                break
        else:
            # No saved original — remove the injected variable entirely
            env.pop(var, None)

    # Also remove AppImage-specific internal variables
    for key in list(env.keys()):
        if key.startswith(('APPIMAGE_', 'APPRUN_', 'APPDIR')):
            if key not in ('APPIMAGE',):  # Keep APPIMAGE itself for detection
                env.pop(key, None)

    return env


# =============================================================================
# FILE OPERATIONS
# =============================================================================


def open_file_with_default_app(file_path: Path, 
                                error_callback: Optional[Callable[[str], None]] = None) -> bool:
    """
    Abre un archivo con la aplicación predeterminada del sistema operativo.
    
    Esta función es independiente de UI y puede usarse en scripts CLI.
    
    Args:
        file_path: Ruta del archivo a abrir
        error_callback: Función opcional para manejar errores. Recibe el mensaje de error.
                       Si no se proporciona, los errores se registran en el log.
    
    Returns:
        True si el archivo se abrió correctamente, False si hubo error
        
    Example:
        >>> from pathlib import Path
        >>> from utils.platform_utils import open_file_with_default_app
        >>> 
        >>> # Uso simple
        >>> open_file_with_default_app(Path("photo.jpg"))
        >>> 
        >>> # Con callback de error
        >>> def handle_error(msg):
        ...     print(f"Error: {msg}")
        >>> open_file_with_default_app(Path("photo.jpg"), error_callback=handle_error)
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        error_msg = tr("platform.error.file_not_found", path=str(file_path))
        logger.warning(f"File does not exist: {file_path}")
        if error_callback:
            error_callback(error_msg)
        return False
    
    if not file_path.is_file():
        error_msg = tr("platform.error.path_not_a_file", path=str(file_path))
        logger.warning(f"Path is not a file: {file_path}")
        if error_callback:
            error_callback(error_msg)
        return False
    
    try:
        system = platform.system()
        logger.debug(f"Opening file on {system}: {file_path}")
        
        if system == 'Linux':
            clean_env = _get_clean_env_for_subprocess()
            subprocess.Popen(['xdg-open', str(file_path)], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL,
                           env=clean_env)
        elif system == 'Darwin':  # macOS
            subprocess.Popen(['open', str(file_path)],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        elif system == 'Windows':
            subprocess.Popen(['start', str(file_path)], shell=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        else:
            error_msg = tr("platform.error.unsupported_os", system=system)
            logger.error(f"Unsupported operating system: {system}")
            if error_callback:
                error_callback(error_msg)
            return False
        
        logger.info(f"File opened successfully: {file_path.name}")
        return True
        
    except Exception as e:
        error_msg = tr("platform.error.open_file_failed", error=str(e))
        logger.error(f"Error opening file: {e}")
        if error_callback:
            error_callback(error_msg)
        return False


def open_folder_in_explorer(folder_path: Path,
                            select_file: Optional[Path] = None,
                            error_callback: Optional[Callable[[str], None]] = None) -> bool:
    """
    Abre una carpeta en el explorador de archivos del sistema operativo.
    
    Esta función es independiente de UI y puede usarse en scripts CLI.
    
    Args:
        folder_path: Ruta de la carpeta a abrir
        select_file: Archivo opcional dentro de la carpeta a seleccionar/resaltar
        error_callback: Función opcional para manejar errores. Recibe el mensaje de error.
                       Si no se proporciona, los errores se registran en el log.
    
    Returns:
        True si la carpeta se abrió correctamente, False si hubo error
        
    Example:
        >>> from pathlib import Path
        >>> from utils.platform_utils import open_folder_in_explorer
        >>> 
        >>> # Abrir carpeta
        >>> open_folder_in_explorer(Path("/home/user/photos"))
        >>> 
        >>> # Abrir carpeta y seleccionar archivo
        >>> open_folder_in_explorer(Path("/home/user/photos"), 
        ...                         select_file=Path("/home/user/photos/image.jpg"))
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        error_msg = tr("platform.error.folder_not_found", path=str(folder_path))
        logger.warning(f"Folder does not exist: {folder_path}")
        if error_callback:
            error_callback(error_msg)
        return False
    
    if not folder_path.is_dir():
        error_msg = tr("platform.error.path_not_a_folder", path=str(folder_path))
        logger.warning(f"Path is not a folder: {folder_path}")
        if error_callback:
            error_callback(error_msg)
        return False
    
    try:
        system = platform.system()
        logger.debug(f"Opening folder on {system}: {folder_path}")
        
        if system == 'Linux':
            clean_env = _get_clean_env_for_subprocess()
            # En Linux, xdg-open no soporta selección de archivo directamente
            if select_file and select_file.exists():
                # Intentar usar el file manager específico si está disponible
                try:
                    # Intentar con nautilus (GNOME)
                    subprocess.Popen(['nautilus', '--select', str(select_file)],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   env=clean_env)
                except FileNotFoundError:
                    # Si nautilus no está disponible, solo abrir la carpeta
                    subprocess.Popen(['xdg-open', str(folder_path)],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   env=clean_env)
            else:
                subprocess.Popen(['xdg-open', str(folder_path)],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               env=clean_env)
                               
        elif system == 'Darwin':  # macOS
            if select_file and select_file.exists():
                # macOS soporta -R para revelar/seleccionar archivo
                subprocess.Popen(['open', '-R', str(select_file)],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(['open', str(folder_path)],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                               
        elif system == 'Windows':
            if select_file and select_file.exists():
                # Windows Explorer soporta /select para seleccionar archivo
                subprocess.Popen(['explorer', '/select,', str(select_file)],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(['explorer', str(folder_path)],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        else:
            error_msg = tr("platform.error.unsupported_os", system=system)
            logger.error(f"Unsupported operating system: {system}")
            if error_callback:
                error_callback(error_msg)
            return False
        
        logger.info(f"Folder opened successfully: {folder_path.name}")
        return True
        
    except Exception as e:
        error_msg = tr("platform.error.open_folder_failed", error=str(e))
        logger.error(f"Error opening folder: {e}")
        if error_callback:
            error_callback(error_msg)
        return False


# ============================================================================
# SYSTEM HARDWARE INFO
# ============================================================================

def get_cpu_count() -> int:
    """
    Obtiene el número de CPUs/cores del sistema.
    
    Returns:
        Número de cores, o 4 si no se puede detectar
    """
    try:
        # os.cpu_count() funciona en Linux, macOS y Windows
        return os.cpu_count() or 4
    except Exception:
        return 4


def get_system_ram_gb() -> float:
    """
    Obtiene la RAM total del sistema en GB.
    
    Returns:
        RAM en GB, o 8.0 si no se puede detectar
    """
    try:
        # psutil es cross-platform
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        # psutil no disponible, asumir 8GB por defecto
        # Fallback básico podría implementarse para cada OS, pero 8GB es seguro
        return 8.0
    except Exception:
        return 8.0


def get_system_info(
    max_cache_entries_func: Optional[Any] = None,
    large_dataset_threshold_func: Optional[Any] = None,
    auto_open_threshold_func: Optional[Any] = None,
    io_workers_func: Optional[Any] = None,
    cpu_workers_func: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Obtiene información completa del sistema para logging.
    Acepta funciones opcionales para obtener valores de configuración que dependen del sistema.
    
    Returns:
        Dict con ram_gb, ram_available_gb, cpu_count, etc.
    """
    ram_gb = get_system_ram_gb()
    
    try:
        ram_available_gb = psutil.virtual_memory().available / (1024 ** 3)
        psutil_available = True
    except (ImportError, Exception):
        ram_available_gb = None
        psutil_available = False
    
    info = {
        'ram_total_gb': ram_gb,
        'ram_available_gb': ram_available_gb,
        'psutil_available': psutil_available,
        'cpu_count': get_cpu_count(),
        'os': platform.system(),
        'os_release': platform.release()
    }

    # Add optional config-dependent values if functions are provided
    if max_cache_entries_func:
        info['max_cache_entries'] = max_cache_entries_func()
    if large_dataset_threshold_func:
        info['large_dataset_threshold'] = large_dataset_threshold_func()
    if auto_open_threshold_func:
        info['auto_open_threshold'] = auto_open_threshold_func()
    if io_workers_func:
        info['io_workers'] = io_workers_func()
    if cpu_workers_func:
        info['cpu_workers'] = cpu_workers_func()
        
    return info
