# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Utilities for file operations shared across services.

Organized by thematic categories:

1. FILE TYPE DETECTION:
   - is_image_file(filename)
   - is_video_file(filename)
   - is_media_file(filename)
   - is_supported_file(filename)
   - get_file_type(filename)

2. SOURCE/ORIGIN DETECTION:
   - detect_file_source(filename, file_path, exif_data)
   - is_whatsapp_file(filename, file_path)

3. FILE VALIDATION:
   - validate_file_exists(path)
   - validate_directory_exists(path)
   - to_path(obj, attr_names)

4. FILE HASHING:
   - calculate_file_hash(file_path, chunk_size, cache)

5. BACKUP OPERATIONS:
   - launch_backup_creation(files, base_directory, backup_prefix, progress_callback, metadata_name)

6. FILE SYSTEM OPERATIONS:
   - cleanup_empty_directories(root_directory)
   - delete_file_securely(file_path)
   - find_next_available_name(base_path, base_name, extension)

7. METADATA EXTRACTION:
   - get_file_stat_info(file_path)
   - get_exif_from_image(file_path)
   - get_exif_from_video(file_path)

8. DATA STRUCTURES:
   - FileInfo (dataclass)
   - validate_and_get_file_info(file_path)

These are pure helpers designed to centralize duplicated code from services.
"""
from pathlib import Path
from datetime import datetime
import shutil
import re
from typing import Iterable, Optional, Tuple, List, Callable
import hashlib
from dataclasses import dataclass
from utils.format_utils import format_size
from utils.callback_utils import safe_progress_callback
from utils.logger import get_logger

# =============================================================================
# CONSTANTS
# =============================================================================

# Patrones de WhatsApp (iPhone y Android)
WHATSAPP_PATTERNS = [
    r'^IMG-\d{8}-WA\d{4}\..*$',  # IMG-20231025-WA0001.jpg (Android)
    r'^VID-\d{8}-WA\d{4}\..*$',  # VID-20231025-WA0001.mp4 (Android)
    r'^AUD-\d{8}-WA\d{4}\..*$',  # AUD-20231025-WA0001.opus (Android)
    r'^PTT-\d{8}-WA\d{4}\..*$',  # PTT (voice notes)
    r'^WhatsApp\s+Image\s+\d{4}-\d{2}-\d{2}\s+at\s+.*\..*$',  # WhatsApp Image 2023-10-25 at 12.34.56.jpg
    r'^WhatsApp\s+Video\s+\d{4}-\d{2}-\d{2}\s+at\s+.*\..*$',  # WhatsApp Video 2023-10-25 at 12.34.56.mp4
    r'^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}(_\d{3})?\.(jpg|jpeg|png|mp4|mov|heic)$',  # UUID format (iPhone export) with optional suffix
]


# =============================================================================
# FILE TYPE DETECTION
# =============================================================================

def is_image_file(filename: str | Path) -> bool:
    """
    Verifica si un archivo es una imagen soportada.
    
    Args:
        filename: Nombre o Path del archivo a verificar
    
    Returns:
        True si es una imagen soportada, False en caso contrario
    """
    from config import Config
    ext = Path(filename).suffix.lower()
    return ext in Config.SUPPORTED_IMAGE_EXTENSIONS


def is_video_file(filename: str | Path) -> bool:
    """
    Verifica si un archivo es un video soportado.
    
    Args:
        filename: Nombre o Path del archivo a verificar
    
    Returns:
        True si es un video soportado, False en caso contrario
    """
    from config import Config
    ext = Path(filename).suffix.lower()
    return ext in Config.SUPPORTED_VIDEO_EXTENSIONS


def is_media_file(filename: str | Path) -> bool:
    """
    Verifica si un archivo es multimedia soportado (imagen o video).
    
    Args:
        filename: Nombre o Path del archivo a verificar
    
    Returns:
        True si es multimedia soportado, False en caso contrario
    """
    return is_image_file(filename) or is_video_file(filename)


def is_supported_file(filename: str | Path) -> bool:
    """
    Verifica si un archivo es soportado.
    
    Args:
        filename: Nombre o Path del archivo a verificar
    
    Returns:
        True si es soportado, False en caso contrario
    """
    return is_media_file(filename)


def get_file_type(filename: str | Path) -> str:
    """
    Obtiene el tipo de archivo.
    
    Args:
        filename: Nombre o Path del archivo
    
    Returns:
        'PHOTO', 'VIDEO', u 'OTHER'
    """
    if is_image_file(filename):
        return 'PHOTO'
    elif is_video_file(filename):
        return 'VIDEO'
    else:
        return 'OTHER'


# =============================================================================
# SOURCE/ORIGIN DETECTION
# =============================================================================

def detect_file_source(filename: str, file_path: Optional[Path] = None, exif_data: Optional[dict] = None) -> str:
    """
    Detecta la fuente/origen de un archivo basándose en patrones y metadata.
    
    Args:
        filename: Nombre del archivo
        file_path: Path completo del archivo (opcional, para análisis de ruta)
        exif_data: Datos EXIF del archivo (opcional, para detectar dispositivo)
    
    Returns:
        Fuente detectada: 'WhatsApp', 'iPhone', 'Android', 'Screenshot', 
                         'Camera', 'Scanner', 'Unknown'
    
    Examples:
        >>> detect_file_source('IMG-20231025-WA0001.jpg')
        'WhatsApp'
        >>> detect_file_source('IMG_1234.HEIC')
        'iPhone'
        >>> detect_file_source('Screenshot_2023.png')
        'Screenshot'
    """
    filename_lower = filename.lower()
    
    # 1. WhatsApp (máxima prioridad)
    if is_whatsapp_file(filename, file_path):
        return 'WhatsApp'
    
    # 2. Screenshots
    screenshot_patterns = [
        r'^screenshot[_\s-]',  # Screenshot_...
        r'^captura[_\s-]',     # Captura de pantalla
        r'^screen[_\s-]',      # Screen_...
        r'^scrnshot',          # Scrnshot_...
    ]
    if any(re.match(pattern, filename_lower) for pattern in screenshot_patterns):
        return 'Screenshot'
    
    # 3. iPhone (HEIC, IMG_XXXX, formato Live Photo)
    if filename_lower.endswith('.heic'):
        return 'iPhone'
    # iPhone patterns: IMG_XXXX.JPG, IMG_EXXXX.JPG (edits), IMG_XXXX.MOV, with optional _NNN suffix
    if re.match(r'^img_[e]?\d{4}(_\d{3})?\.(jpg|jpeg|png|mov|mp4)$', filename_lower):
        return 'iPhone'
    
    # 4. Android (patrón típico)
    android_patterns = [
        r'^pxl_\d{8}(_\d{3})?\..*$',       # Google Pixel
        r'^img-\d{8}(_\d{3})?\..*$',       # Algunos Android (sin WA)
        r'^\d{8}_\d{6}(_\d{3})?\..*$',      # Samsung: YYYYMMDD_HHMMSS
        r'^signal-\d{4}(_\d{3})?\..*$',     # Signal app
    ]
    if any(re.match(pattern, filename_lower) for pattern in android_patterns):
        return 'Android'
    
    # 5. Cámara digital (DSC, DCIM patterns)
    camera_patterns = [
        r'^dsc[_-]?\d+(_\d{3})?\.',      # DSC_0001.jpg or DSC_0001_001.jpg
        r'^p\d{7}(_\d{3})?\.',           # P0001234.jpg
        r'^_dsc\d+(_\d{3})?\.',          # _DSC1234.jpg (Nikon)
        r'^img_\d{4,}(_\d{3})?\.',       # IMG_12345.jpg (cámaras Canon, etc.)
    ]
    if any(re.match(pattern, filename_lower) for pattern in camera_patterns):
        return 'Camera'
    
    # 6. Escáner
    scanner_patterns = [
        r'^scan[_\s-]',       # Scan_...
        r'^scanned[_\s-]',    # Scanned_...
        r'^escanear',         # Escanear_...
    ]
    if any(re.match(pattern, filename_lower) for pattern in scanner_patterns):
        return 'Scanner'
    
    # 7. EXIF data (si está disponible)
    if exif_data:
        model = exif_data.get('Model', '').lower()
        make = exif_data.get('Make', '').lower()
        
        if 'iphone' in model or 'iphone' in make:
            return 'iPhone'
        if 'samsung' in make or 'pixel' in model or 'android' in model:
            return 'Android'
        if model or make:  # Cualquier otra cámara con metadata
            return 'Camera'
    
    # 8. Análisis de ruta (último recurso)
    if file_path:
        path_str = str(file_path).lower()
        if 'whatsapp' in path_str:
            return 'WhatsApp'
        if 'dcim' in path_str or 'camera' in path_str:
            return 'Camera'
        if 'screenshot' in path_str:
            return 'Screenshot'
    
    return 'Unknown'


def is_whatsapp_file(filename: str, file_path: Path = None) -> bool:
    """Verifica si un archivo es de WhatsApp basándose en su nombre y/o ruta.
    
    Detecta archivos de WhatsApp por:
    1. Patrones de nombre conocidos (IMG-WA, VID-WA, WhatsApp Image, etc.)
    2. Formato UUID de iPhone (82DB60A3-002F-4FAE-80FC-96082431D247.jpg)
    3. Ruta que contenga "whatsapp" en cualquier nivel
    
    Args:
        filename: Nombre del archivo
        file_path: Path completo del archivo (opcional)
    
    Returns:
        True si el nombre coincide con patrones de WhatsApp o está en carpeta WhatsApp
    
    Examples:
        >>> is_whatsapp_file('IMG-20231025-WA0001.jpg')
        True
        >>> is_whatsapp_file('82DB60A3-002F-4FAE-80FC-96082431D247.jpg')
        True
        >>> is_whatsapp_file('photo.jpg', Path('/photos/WhatsApp/photo.jpg'))
        True
        >>> is_whatsapp_file('vacation.jpg', Path('/photos/vacation.jpg'))
        False
    """
    # Verificar por nombre (patrones conocidos)
    for pattern in WHATSAPP_PATTERNS:
        if re.match(pattern, filename, re.IGNORECASE):
            return True
    
    # Verificar por ruta (carpeta contiene "whatsapp" en cualquier nivel)
    if file_path:
        path_str = str(file_path).lower()
        if 'whatsapp' in path_str:
            return True
    
    return False


# =============================================================================
# FILE VALIDATION
# =============================================================================

def validate_file_exists(path) -> Path:
    """Normalize input to Path and verify the file exists and is a file.

    Args:
        path: str or Path-like to validate

    Returns:
        Path object for the validated file

    Raises:
        FileNotFoundError: if the path does not exist or is not a file
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    if not p.is_file():
        raise FileNotFoundError(f"Not a valid file: {p}")
    return p


def validate_directory_exists(path) -> Path:
    """Normalize input to Path and verify the directory exists.

    Args:
        path: str or Path-like to validate

    Returns:
        Path object for the validated directory

    Raises:
        FileNotFoundError: if the path does not exist
        NotADirectoryError: if the path is not a directory
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Directory does not exist: {p}")
    if not p.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {p}")
    return p


def to_path(obj, attr_names=('path', 'source_path', 'original_path')) -> Path:
    """Convierte un objeto flexible a Path.

    Args:
        obj: str, bytes, Path, dict o objeto con atributos
        attr_names: tuple de nombres de atributos a buscar

    Returns:
        Path: ruta del archivo

    Raises:
        ValueError: si no se puede extraer una ruta válida
    """
    if isinstance(obj, (str, bytes)):
        return Path(obj)
    if isinstance(obj, Path):
        return obj
    if isinstance(obj, dict):
        for k in attr_names:
            if k in obj:
                return Path(obj[k])
        if obj:
            return Path(next(iter(obj.values())))
    for k in attr_names:
        if hasattr(obj, k):
            return Path(getattr(obj, k))

    try:
        return Path(obj)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Could not convert {type(obj).__name__} to Path") from e


# =============================================================================
# FILE HASHING
# =============================================================================

def calculate_file_hash(file_path: Path, chunk_size: int = 8192, cache: Optional[dict] = None) -> str:
    """Calculate SHA256 hash of a file.

    If a cache dict is provided, the function will store and reuse computed hashes
    keyed by the file's string path.
    
    Raises:
        FileNotFoundError: Si el archivo no existe
        PermissionError: Si no hay permisos para leer el archivo
        IOError: Si hay un error de I/O durante la lectura
    """
    key = str(file_path)
    if cache is not None and key in cache:
        return cache[key]

    try:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                sha256.update(chunk)

        digest = sha256.hexdigest()
        if cache is not None:
            cache[key] = digest
        return digest
    except FileNotFoundError:
        logger = get_logger('file_utils')
        logger.error(f"File not found: {file_path}")
        raise
    except PermissionError as e:
        logger = get_logger('file_utils')
        logger.error(f"Permission denied reading {file_path.name}: {e}")
        raise
    except IOError as e:
        logger = get_logger('file_utils')
        logger.error(f"I/O error reading {file_path.name}: {e}")
        raise


# =============================================================================
# BACKUP OPERATIONS
# =============================================================================

def _ensure_backup_dir(backup_dir: Path):
    """Crea el directorio de backup si no existe (helper privado)."""
    backup_dir.mkdir(parents=True, exist_ok=True)


def launch_backup_creation(
    files: Iterable[Path],
    base_directory: Path,
    backup_prefix: str = "backup",
    progress_callback=None,
    metadata_name: Optional[str] = None
) -> Path:
    """Create a backup directory and copy the given files preserving relative paths.

    Args:
        files: Iterable of Path objects to back up
        base_directory: Base directory used to compute relative paths
        backup_prefix: Prefix used to name the backup folder
        progress_callback: optional callback (current, total, message)
        metadata_name: filename used to store metadata (defaults to backup_prefix + '_metadata.txt')

    Returns:
        Path to the created backup directory
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{backup_prefix}_{base_directory.name}_{timestamp}"

    from config import Config
    backup_root = Config.DEFAULT_BACKUP_DIR

    backup_path = backup_root / backup_name
    _ensure_backup_dir(backup_path)

    files_list = []
    for item in files:
        try:
            normalized = to_path(item)
            files_list.append(normalized)
        except ValueError as ve:
            raise ValueError(
                f"launch_backup_creation: cannot normalize item to a path: type={type(item).__name__}, repr={repr(item)}"
            ) from ve

    total = len(files_list)
    copied = 0
    total_size = 0

    for file_path in files_list:
        try:
            if base_directory in file_path.parents:
                relative_path = file_path.relative_to(base_directory)
            else:
                relative_path = file_path.parent.name / file_path.name

            dest = backup_path / relative_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dest)
            copied += 1
            total_size += file_path.stat().st_size

            safe_progress_callback(progress_callback, copied, total, f"Creating backup: {backup_path} ({copied}/{total})")

        except PermissionError as e:
            logger = get_logger('file_utils')
            logger.error(f"Permission denied copying {file_path.name}: {e}")
            raise PermissionError(f"Could not create backup of {file_path.name}: permission denied") from e
        except FileNotFoundError as e:
            logger = get_logger('file_utils')
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File {file_path.name} not found during backup") from e
        except OSError as e:
            logger = get_logger('file_utils')
            logger.error(f"I/O error copying {file_path.name}: {e}")
            raise OSError(f"Error creating backup of {file_path.name}: {e}") from e
        except Exception as e:
            logger = get_logger('file_utils')
            logger.error(f"Unexpected error in backup of {file_path.name}: {type(e).__name__}: {e}")
            raise

    # Write metadata
    metadata_name = metadata_name or f"{backup_prefix}_metadata.txt"
    metadata_path = backup_path / metadata_name
    with open(metadata_path, 'w', encoding='utf-8') as f:
        f.write(f"BACKUP: {backup_prefix}\n")
        f.write(f"Created: {datetime.now()}\n")
        f.write(f"Base directory: {base_directory}\n")
        f.write(f"Files backed up: {copied}\n")
        f.write(f"Total size: {format_size(total_size)}\n")
        f.write("\nBACKED UP FILES:\n")
        for p in files_list:
            f.write(f"- {p}\n")

    return backup_path


# =============================================================================
# FILE SYSTEM OPERATIONS
# =============================================================================

def cleanup_empty_directories(root_directory: Path) -> int:
    """Remove empty directories under root_directory (excluding root).

    A directory is considered empty if it contains no files, or only
    system junk files (.nomedia, .DS_Store, Thumbs.db, .thumbnails, desktop.ini).
    Those junk files are deleted before removing the directory.

    Returns the number of directories removed.
    """
    # Archivos de sistema que no cuentan como contenido real
    JUNK_FILES = {'.nomedia', '.ds_store', 'thumbs.db', '.thumbnails', 'desktop.ini'}
    
    removed_count = 0
    logger = get_logger('file_utils')
    for item in sorted(root_directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if item.is_dir() and item != root_directory:
            try:
                contents = list(item.iterdir())
                if not contents:
                    # Directorio realmente vacío
                    item.rmdir()
                    removed_count += 1
                elif all(
                    c.is_file() and c.name.lower() in JUNK_FILES
                    for c in contents
                ):
                    # Only contains system files -> delete them and then the directory
                    for junk in contents:
                        try:
                            junk.unlink()
                            logger.debug(f"System file deleted: {junk}")
                        except OSError:
                            pass
                    # Verificar que quedó vacío tras eliminar junk
                    if not any(item.iterdir()):
                        item.rmdir()
                        removed_count += 1
            except PermissionError:
                logger.debug(f"Permission denied deleting directory: {item.name}")
            except OSError as e:
                logger.debug(f"Could not delete directory {item.name}: {e}")
    return removed_count


def delete_file_securely(file_path: Path) -> bool:
    """
    Elimina un archivo de forma segura (intentando enviar a la papelera primero).
    Si send2trash no está disponible, usa eliminación permanente.
    
    Args:
        file_path: Ruta del archivo a eliminar
        
    Returns:
        True si se eliminó correctamente
    """
    logger = get_logger('file_utils')
    try:
        try:
            from send2trash import send2trash
            send2trash(str(file_path))
            logger.debug(f"File sent to trash: {file_path.name}")
        except ImportError:
            # Fallback a eliminación permanente si no hay send2trash
            file_path.unlink()
            logger.debug(f"File permanently deleted: {file_path.name}")
        return True
    except PermissionError as e:
        logger.warning(f"Permission denied deleting {file_path.name}: {e}")
        return False
    except FileNotFoundError:
        logger.debug(f"File no longer exists: {file_path.name}")
        return False
    except OSError as e:
        logger.error(f"I/O error deleting {file_path.name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting {file_path.name}: {type(e).__name__}: {e}")
        return False


def find_next_available_name(base_path: Path, base_name: str, extension: str) -> Tuple[str, int]:
    """Find next available filename with numeric suffix (XXX) in base_path.

    Returns (new_name, sequence)
    
    Si el nombre base termina en un sufijo numérico de 3 dígitos (_XXX), lo reemplaza.
    Si termina en un sufijo numérico de otra longitud (_X, _XX, _XXXX), lo preserva y añade el nuevo sufijo.
    """
    parts = base_name.split('_')
    
    # Detectar si tiene un sufijo numérico de 3 dígitos (patrón estándar)
    if len(parts) >= 4 and len(parts[-1]) == 3 and parts[-1].isdigit():
        base_without_suffix = '_'.join(parts[:-1])
        start_sequence = int(parts[-1])
    else:
        # No tiene sufijo de 3 dígitos, usar el nombre completo como base
        base_without_suffix = base_name
        start_sequence = 0

    existing_sequences = set()
    for file_path in base_path.iterdir():
        if file_path.is_file() and file_path.stem.startswith(base_without_suffix):
            file_parts = file_path.stem.split('_')
            if file_parts and len(file_parts[-1]) == 3 and file_parts[-1].isdigit():
                existing_sequences.add(int(file_parts[-1]))

    if existing_sequences:
        sequence = max(existing_sequences) + 1
    else:
        sequence = start_sequence + 1 if start_sequence > 0 else 1

    while sequence in existing_sequences:
        sequence += 1

    new_name = f"{base_without_suffix}_{sequence:03d}{extension}"
    return new_name, sequence


# =============================================================================
# METADATA EXTRACTION
# =============================================================================

def get_file_stat_info(file_path: Path, resolve_path: bool = True) -> dict:
    """
    Obtiene información básica del sistema de archivos para un archivo.
    
    Función centralizada para evitar duplicación de código al obtener
    metadatos del sistema de archivos.
    
    Args:
        file_path: Ruta del archivo
        resolve_path: Si True, incluye el path resuelto en el resultado
        
    Returns:
        Diccionario con size, ctime, mtime, atime y opcionalmente resolved_path
        
    Raises:
        FileNotFoundError: Si el archivo no existe
        PermissionError: Si no hay permisos para acceder al archivo
        OSError: Si hay un error de I/O
    """
    try:
        stat_info = file_path.stat()
        result = {
            'size': stat_info.st_size,
            'ctime': stat_info.st_ctime,
            'mtime': stat_info.st_mtime,
            'atime': stat_info.st_atime
        }
        
        if resolve_path:
            result['resolved_path'] = file_path.resolve()
        
        return result
    except FileNotFoundError:
        logger = get_logger('file_utils')
        logger.error(f"File not found: {file_path}")
        raise
    except PermissionError as e:
        logger = get_logger('file_utils')
        logger.error(f"Permission denied accessing {file_path.name}: {e}")
        raise
    except OSError as e:
        logger = get_logger('file_utils')
        logger.error(f"I/O error getting info for {file_path.name}: {e}")
        raise


def get_exif_from_image(file_path: Path) -> dict:
    """
    Extrae campos de fecha EXIF y metadatos básicos de una imagen
    
    Campos extraídos:
    - Fechas EXIF: DateTimeOriginal, CreateDate, DateTimeDigitized, GPS DateStamp/TimeStamp
    - Dimensiones: ImageWidth, ImageLength
    - Metadatos técnicos: Software, ExifVersion, SubSecTimeOriginal, OffsetTimeOriginal
    
    NOTA: Solo soporta imágenes (JPEG, PNG, HEIC, etc.). No hay soporte para EXIF en videos.

    Args:
        file_path: Ruta a la imagen (NO videos)

    Returns:
        Dict con los campos EXIF encontrados:
        {
            'DateTimeOriginal': datetime or None,     # Fecha de captura original
            'CreateDate': datetime or None,           # Fecha de creación (DateTime en EXIF)
            'DateTimeDigitized': datetime or None,    # Fecha de digitalización
            'SubSecTimeOriginal': str or None,        # Subsegundos de precisión
            'OffsetTimeOriginal': str or None,        # Zona horaria de captura
            'GPSDateStamp': str or None,              # Fecha GPS en formato 'YYYY:MM:DD'
            'GPSTimeStamp': str or None,              # Hora GPS en formato 'HH:MM:SS'
            'Software': str or None,                  # Software usado (detecta edición)
            'ExifVersion': str or None,               # Versión del estándar EXIF (ej: '0232')
            'ImageWidth': int or None,                # Ancho de la imagen en píxeles
            'ImageLength': int or None                # Alto de la imagen en píxeles
        }
    
    Examples:
        >>> # Imagen con EXIF completo
        >>> dates = get_exif_from_image(Path('photo.jpg'))
        >>> dates['DateTimeOriginal']
        datetime(2023, 1, 15, 10, 30, 0)
        >>> dates['OffsetTimeOriginal']
        '+01:00'
        >>> dates['Software']
        'Adobe Photoshop CS6'
        >>> dates['ExifVersion']
        '0232'
        >>> dates['ImageWidth']
        4032
        >>> dates['ImageLength']
        3024
    """
    result = {
        'DateTimeOriginal': None,
        'CreateDate': None,
        'DateTimeDigitized': None,
        'SubSecTimeOriginal': None,
        'OffsetTimeOriginal': None,
        'GPSDateStamp': None,
        'GPSTimeStamp': None,
        'Software': None,
        'ExifVersion': None,
        'ImageWidth': None,
        'ImageLength': None
    }
    
    try:
        # Intentar con PIL/Pillow
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        # Para archivos HEIC, necesitamos pillow-heif
        if file_path.suffix.lower() in ['.heic', '.heif']:
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except ImportError:
                logger = get_logger('file_utils')
                logger.warning(f"pillow-heif not available, cannot process {file_path.name}")
                return result

        with Image.open(file_path) as image:
            # Obtener dimensiones directamente de la imagen (más confiable que EXIF)
            if hasattr(image, 'width') and hasattr(image, 'height'):
                result['ImageWidth'] = image.width
                result['ImageLength'] = image.height
            
            # Obtener datos EXIF usando API moderna (getexif()) que funciona para todos los formatos
            try:
                exif = image.getexif()
                if not exif:
                    return result
            except AttributeError:
                # Fallback a API antigua para versiones muy viejas de Pillow
                exif_data = image._getexif()
                if not exif_data:
                    return result
                # Convertir a objeto Exif-like para API unificada
                from PIL import Image as PIL_Image
                exif = PIL_Image.Exif()
                for k, v in exif_data.items():
                    exif[k] = v
            
            # Procesar tags principales (nivel superior)
            gps_info = None
            
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)

                # Extraer cada campo de fecha EXIF
                if tag == 'DateTimeOriginal':
                    try:
                        result['DateTimeOriginal'] = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    except ValueError:
                        pass
                elif tag == 'DateTime':  # Este es el CreateDate
                    try:
                        result['CreateDate'] = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    except ValueError:
                        pass
                elif tag == 'DateTimeDigitized':
                    try:
                        result['DateTimeDigitized'] = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    except ValueError:
                        pass
                elif tag == 'SubSecTimeOriginal':
                    result['SubSecTimeOriginal'] = str(value)
                elif tag == 'OffsetTimeOriginal':
                    result['OffsetTimeOriginal'] = str(value)
                elif tag == 'Software':
                    result['Software'] = str(value)
                elif tag == 'ExifVersion':
                    # ExifVersion es bytes, convertir a string legible
                    result['ExifVersion'] = value.decode('utf-8') if isinstance(value, bytes) else str(value)
                elif tag in ['ImageWidth', 'ExifImageWidth'] and not result['ImageWidth']:
                    result['ImageWidth'] = int(value) if value else None
                elif tag in ['ImageLength', 'ImageHeight', 'ExifImageHeight'] and not result['ImageLength']:
                    result['ImageLength'] = int(value) if value else None
                elif tag == 'GPSInfo':
                    gps_info = value
            
            # Procesar EXIF IFD (sub-tags) - muchos campos importantes están aquí
            try:
                exif_ifd = exif.get_ifd(0x8769)  # ExifOffset IFD
                if exif_ifd:
                    for tag_id, value in exif_ifd.items():
                        tag = TAGS.get(tag_id, tag_id)
                        
                        if tag == 'DateTimeOriginal' and not result['DateTimeOriginal']:
                            try:
                                result['DateTimeOriginal'] = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                            except ValueError:
                                pass
                        elif tag == 'DateTimeDigitized' and not result['DateTimeDigitized']:
                            try:
                                result['DateTimeDigitized'] = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                            except ValueError:
                                pass
                        elif tag == 'SubsecTimeOriginal' and not result['SubSecTimeOriginal']:
                            result['SubSecTimeOriginal'] = str(value)
                        elif tag == 'OffsetTimeOriginal' and not result['OffsetTimeOriginal']:
                            result['OffsetTimeOriginal'] = str(value)
                        elif tag == 'ExifVersion' and not result['ExifVersion']:
                            # ExifVersion es bytes, convertir a string legible
                            result['ExifVersion'] = value.decode('utf-8') if isinstance(value, bytes) else str(value)
                        elif tag in ['ExifImageWidth', 'PixelXDimension'] and not result['ImageWidth']:
                            result['ImageWidth'] = int(value) if value else None
                        elif tag in ['ExifImageHeight', 'PixelYDimension'] and not result['ImageLength']:
                            result['ImageLength'] = int(value) if value else None
            except (KeyError, AttributeError):
                # No hay EXIF IFD o no se puede acceder
                pass
            
            # Procesar GPS IFD si existe
            if gps_info:
                
                # Procesar información GPS si existe
                if gps_info:
                    try:
                        gps_date = None
                        gps_time = None
                        
                        for gps_tag_id, gps_value in gps_info.items():
                            gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                            
                            if gps_tag == 'GPSDateStamp':
                                gps_date = gps_value
                            elif gps_tag == 'GPSTimeStamp':
                                gps_time = gps_value
                        
                        # Combinar fecha y hora GPS
                        if gps_date and gps_time:
                            try:
                                # GPSDateStamp formato: 'YYYY:MM:DD'
                                # GPSTimeStamp formato: (HH, MM, SS) como tupla de racionales
                                
                                # Guardar GPSDateStamp como string de fecha
                                result['GPSDateStamp'] = gps_date
                                
                                # Convertir tupla de racionales a hora y guardar GPSTimeStamp
                                hours = int(gps_time[0]) if hasattr(gps_time[0], '__int__') else int(gps_time[0].numerator / gps_time[0].denominator)
                                minutes = int(gps_time[1]) if hasattr(gps_time[1], '__int__') else int(gps_time[1].numerator / gps_time[1].denominator)
                                seconds = int(gps_time[2]) if hasattr(gps_time[2], '__int__') else int(gps_time[2].numerator / gps_time[2].denominator)
                                
                                result['GPSTimeStamp'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                            except (ValueError, AttributeError, IndexError, TypeError):
                                pass
                    except Exception:
                        pass

    except ImportError:
        # PIL no disponible, continuar sin EXIF
        pass
    except Exception as e:
        # Error accediendo a EXIF
        logger = get_logger('file_utils')
        logger.warning(f"Error extracting EXIF from {file_path.name}: {e}")
    
    return result


def _parse_apple_creationdate(value: str) -> Optional[tuple]:
    """
    Parsea com.apple.quicktime.creationdate de ffprobe.
    
    Formatos conocidos:
    - "2025-11-30T07:26:47+0100"
    - "2025-11-30T07:26:47+01:00"  
    - "2025-11-30T07:26:47Z"
    
    Returns:
        Tuple (datetime_local, offset_str) o None si no se puede parsear.
        - datetime_local: la fecha/hora local (sin timezone info)
        - offset_str: el offset original (ej: '+01:00') para propagación
    """
    if not value or not isinstance(value, str):
        return None
    
    logger = get_logger('file_utils')
    
    try:
        # Intentar parsear con timezone info
        # Formato: "2025-11-30T07:26:47+0100" o "2025-11-30T07:26:47+01:00"
        
        # Separar la parte de fecha/hora de la parte de timezone
        # Buscar el offset al final: +HHMM, +HH:MM, -HHMM, -HH:MM, o Z
        date_part = value
        offset_str = None
        
        if value.endswith('Z'):
            date_part = value[:-1]
            offset_str = '+00:00'
        else:
            # Buscar +/- seguido de dígitos al final
            for i in range(len(value) - 1, max(len(value) - 7, 0), -1):
                if value[i] in ('+', '-') and i > 10:  # No confundir con el - de la fecha
                    date_part = value[:i]
                    tz_part = value[i:]
                    # Normalizar a formato +HH:MM
                    if len(tz_part) == 5:  # +HHMM
                        offset_str = f"{tz_part[:3]}:{tz_part[3:]}"
                    elif len(tz_part) == 6:  # +HH:MM
                        offset_str = tz_part
                    else:
                        offset_str = tz_part
                    break
        
        # Parsear solo la parte de fecha/hora (sin timezone)
        dt = None
        for fmt in ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
            try:
                dt = datetime.strptime(date_part, fmt)
                break
            except ValueError:
                continue
        
        if dt is None:
            logger.debug(f"Could not parse apple.creationdate date part: '{date_part}'")
            return None
        
        logger.debug(f"Parsed apple.creationdate: {dt} (offset={offset_str})")
        return (dt, offset_str)
        
    except Exception as e:
        logger.debug(f"Error parsing apple.creationdate '{value}': {e}")
        return None


def get_exif_from_video(file_path: Path) -> dict:
    """
    Extrae metadatos completos de archivos de video usando exiftool y ffprobe.
    
    PRIORIDAD PARA FECHA:
    1. exiftool Keys:CreationDate - Para Live Photos de iPhone (campo correcto)
    2. ffprobe com.apple.quicktime.creationdate - Fecha exacta con timezone (iPhone)
    3. ffprobe creation_time - Para otros videos (UTC, menos preciso)
    
    METADATOS TÉCNICOS (con ffprobe):
    - Dimensiones (width, height)
    - Duración (duration)
    - Códec (video_codec)
    - Frame rate (fps)
    - Bitrate
    - Formato contenedor
    
    Esta función requiere que exiftool o ffprobe esté instalado en el sistema.
    Si ninguno está disponible, devuelve dict vacío sin generar error.

    Args:
        file_path: Ruta al archivo de video

    Returns:
        Diccionario con metadatos del video:
        {
            'creation_time': datetime or None,          # Fecha de creación (hora local)
            'creation_time_offset': str or None,         # Offset timezone (ej: '+01:00')
            'width': int or None,                        # Ancho en píxeles
            'height': int or None,              # Alto en píxeles
            'duration': str or None,            # Duración (ej: "5:23 min")
            'duration_seconds': float or None,  # Duración en segundos
            'fps': str or None,                 # Frame rate (ej: "30.00 fps")
            'video_codec': str or None,         # Códec (ej: "h264")
            'video_codec_long': str or None,    # Nombre largo del códec
            'bitrate': str or None,             # Bitrate (ej: "5000 kbps")
            'format': str or None,              # Formato contenedor
            'format_long': str or None,         # Nombre largo del formato
            'pixel_format': str or None,        # Formato de píxel (ej: "yuv420p")
            'encoder': str or None              # Software de codificación
        }
        
    Examples:
        >>> # Live Photo MOV con Keys:CreationDate
        >>> metadata = get_exif_from_video(Path('IMG_0017_HAYLIVE.MOV'))
        >>> metadata['creation_time']
        datetime(2019, 11, 13, 15, 38, 59)
        >>> metadata['width']
        1920
        
        >>> # Video regular con metadata de creación
        >>> metadata = get_exif_from_video(Path('video.mp4'))
        >>> metadata['creation_time']
        datetime(2024, 1, 15, 14, 30, 0)
        >>> metadata['duration']
        '5:23 min'
        
        >>> # Video sin metadata
        >>> metadata = get_exif_from_video(Path('video_without_metadata.mp4'))
        >>> metadata
        {}
    """
    import subprocess
    import json
    
    logger = get_logger('file_utils')
    
    result = {}
    creation_date = None
    
    # PRIORIDAD 1: Intentar leer Keys:CreationDate con exiftool (Live Photos)
    if shutil.which('exiftool'):
        try:
            exiftool_result = subprocess.run(
                ['exiftool', '-Keys:CreationDate', '-d', '%Y:%m:%d %H:%M:%S', '-s3', str(file_path)],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if exiftool_result.returncode == 0 and exiftool_result.stdout.strip():
                creation_date_str = exiftool_result.stdout.strip()
                try:
                    # Formato: "2019:11:13 15:38:59+01:00" o "2019:11:13 15:38:59"
                    # Extraer solo fecha y hora, ignorar zona horaria
                    if '+' in creation_date_str or '-' in creation_date_str[-6:]:
                        # Tiene zona horaria
                        date_part = creation_date_str.rsplit('+', 1)[0].rsplit('-', 1)[0]
                    else:
                        date_part = creation_date_str
                    
                    creation_date = datetime.strptime(date_part.strip(), '%Y:%m:%d %H:%M:%S')
                    result['creation_time'] = creation_date
                    logger.debug(f"Video {file_path.name}: using Keys:CreationDate = {creation_date}")
                except ValueError as e:
                    logger.debug(f"Error parsing Keys:CreationDate '{creation_date_str}': {e}")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            logger.debug(f"Error running exiftool on {file_path.name}: {e}")
    
    # PRIORIDAD 2: Intentar ffprobe para metadatos técnicos + creation_time
    if not shutil.which('ffprobe'):
        logger.debug("ffprobe not available")
        return result
    
    try:
        # Ejecutar ffprobe para obtener TODOS los metadatos
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(file_path)
        ]
        
        ffprobe_result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10  # Timeout de 10 segundos
        )
        
        if ffprobe_result.returncode != 0:
            return result
        
        # Parsear JSON
        data = json.loads(ffprobe_result.stdout)
        
        # Extraer información del formato
        if 'format' in data:
            fmt = data['format']
            
            # Duración
            if 'duration' in fmt:
                try:
                    duration_sec = float(fmt['duration'])
                    minutes = int(duration_sec // 60)
                    seconds = int(duration_sec % 60)
                    result['duration'] = f"{minutes}:{seconds:02d} min"
                    result['duration_seconds'] = duration_sec
                except (ValueError, TypeError):
                    pass
            
            # Bitrate
            if 'bit_rate' in fmt:
                try:
                    bitrate_kbps = int(fmt['bit_rate']) // 1000
                    result['bitrate'] = f"{bitrate_kbps} kbps"
                except (ValueError, TypeError):
                    pass
            
            # Formato
            if 'format_name' in fmt:
                result['format'] = fmt['format_name']
            
            if 'format_long_name' in fmt:
                result['format_long'] = fmt['format_long_name']
            
            # Tags (creation_time, encoder, etc.)
            if 'tags' in fmt:
                tags = fmt['tags']
                
                # PRIORIDAD: com.apple.quicktime.creationdate (fecha exacta con timezone)
                # Esta fecha es la que Apple almacena como fecha real de captura
                # en hora local CON offset de timezone. Es MUCHO más precisa que
                # creation_time (que es UTC y puede tener desfase de minutos).
                apple_creationdate = tags.get('com.apple.quicktime.creationdate')
                if not creation_date and apple_creationdate:
                    try:
                        parsed = _parse_apple_creationdate(apple_creationdate)
                        if parsed:
                            creation_date, offset_str = parsed
                            result['creation_time'] = creation_date
                            if offset_str:
                                result['creation_time_offset'] = offset_str
                            logger.debug(
                                f"Video {file_path.name}: using apple.creationdate = "
                                f"{creation_date} (offset={offset_str})"
                            )
                    except Exception as e:
                        logger.debug(f"Error parsing apple.creationdate '{apple_creationdate}': {e}")
                
                # Fallback: creation_time genérico (UTC, menos preciso)
                if not creation_date and 'creation_time' in tags:
                    creation_time_str = tags['creation_time']
                    try:
                        # Formato típico: '2024-01-15T14:30:00.000000Z'
                        for fmt_str in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']:
                            try:
                                creation_date = datetime.strptime(creation_time_str, fmt_str)
                                result['creation_time'] = creation_date
                                logger.debug(f"Video {file_path.name}: using ffprobe creation_time = {creation_date}")
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass
                
                if 'encoder' in tags:
                    result['encoder'] = tags['encoder']
        
        # Información de streams de video
        if 'streams' in data:
            for stream in data['streams']:
                if stream.get('codec_type') == 'video':
                    if 'width' in stream:
                        result['width'] = stream['width']
                    if 'height' in stream:
                        result['height'] = stream['height']
                    if 'codec_name' in stream:
                        result['video_codec'] = stream['codec_name']
                    if 'codec_long_name' in stream:
                        result['video_codec_long'] = stream['codec_long_name']
                    if 'r_frame_rate' in stream:
                        # Frame rate como fracción "30000/1001"
                        try:
                            num, den = stream['r_frame_rate'].split('/')
                            fps = float(num) / float(den)
                            result['fps'] = f"{fps:.2f} fps"
                        except (ValueError, ZeroDivisionError, AttributeError):
                            pass
                    if 'pix_fmt' in stream:
                        result['pixel_format'] = stream['pix_fmt']
                    break  # Solo el primer stream de video
        
        return result
        
    except subprocess.TimeoutExpired:
        logger.debug(f"Timeout running ffprobe for {file_path.name}")
        return result
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError) as e:
        logger.debug(f"Error parsing metadata for {file_path.name}: {e}")
        return result
    except Exception as e:
        logger.debug(f"Error getting video metadata for {file_path.name}: {e}")
        return result


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class FileInfo:
    """
    Información estándar de archivo para logging y procesamiento.
    
    Attributes:
        path: Path original del archivo
        size: Tamaño en bytes
        size_formatted: Tamaño formateado (ej: "5.2 MB")
        date: datetime de modificación
        date_formatted: Fecha formateada (ej: "2023-11-12 14:30:22")
    """
    path: Path
    size: int
    size_formatted: str
    date: Optional[datetime]
    date_formatted: str


def validate_and_get_file_info(file_path: Path) -> FileInfo:
    """
    Obtiene información estándar de archivo para logging y procesamiento.
    
    Centraliza la lógica de obtención de información de archivos
    que estaba duplicada en múltiples servicios.
    
    Args:
        file_path: Path del archivo a inspeccionar
    
    Returns:
        FileInfo con información completa del archivo
    
    Raises:
        FileNotFoundError: Si el archivo no existe
        Exception: Si hay error obteniendo información
    
    Example:
        >>> info = validate_and_get_file_info(Path('/path/photo.jpg'))
        >>> print(info.size_formatted)
        '2.5 MB'
        >>> print(info.date_formatted)
        '2023-11-12 14:30:22'
    """
    # Validar existencia
    validate_file_exists(file_path)
    
    # Obtener tamaño
    try:
        file_size = file_path.stat().st_size
        size_formatted = format_size(file_size)
    except Exception as e:
        logger = get_logger('ServiceUtils')
        logger.warning(f"Error getting size of {file_path}: {e}")
        file_size = 0
        size_formatted = "0 B"
    
    # Obtener fecha
    try:
        from utils.date_utils import select_best_date_from_file, get_all_metadata_from_file
        file_metadata = get_all_metadata_from_file(file_path)
        file_date, _ = select_best_date_from_file(file_metadata)
        date_formatted = (
            file_date.strftime('%Y%m%d_%H%M%S')
            if file_date else 'unknown date'
        )
    except Exception as e:
        logger = get_logger('ServiceUtils')
        logger.warning(f"Error getting date of {file_path}: {e}")
        file_date = None
        date_formatted = 'unknown date'
    
    return FileInfo(
        path=file_path,
        size=file_size,
        size_formatted=size_formatted,
        date=file_date,
        date_formatted=date_formatted
    )
