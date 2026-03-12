# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
File Metadata Repository Cache - Sistema de Caché Centralizado

Repositorio singleton que actúa como caché inteligente para metadatos de archivos.
Diseñado para ser migrado a SQLite en el futuro.

Arquitectura:
- Backend en memoria (dict) actualmente
- Interfaz preparada para backend SQLite/BBDD (Protocol)
- Singleton thread-safe
- Auto-population con diferentes estrategias


Estrategias de población:
1. FILESYSTEM_METADATA: Solo filesystem metadata (rápido, scan inicial, OBLIGATORIO primero)
2. HASH: Solo hash SHA256 (requiere FILESYSTEM_METADATA previo, para duplicados exactos)
3. EXIF_IMAGES: Solo EXIF de imágenes (requiere FILESYSTEM_METADATA previo, para organización)
4. EXIF_VIDEOS: Solo EXIF de videos (requiere FILESYSTEM_METADATA previo, muy costoso)
5. BEST_DATE: Calcula mejor fecha disponible (requiere FILESYSTEM_METADATA y EXIF previo, rápido)

Los servicios consultan este repositorio sin recibirlo como parámetro.
El repositorio es global y compartido entre todos los servicios.

Uso:
    # Paso 1: Scan inicial con FILESYSTEM_METADATA (OBLIGATORIO)
    repo = FileInfoRepositoryCache.get_instance()
    repo.populate_from_scan(files, strategy=PopulationStrategy.FILESYSTEM_METADATA)
    
    # Paso 2: Análisis incremental bajo demanda
    repo.populate_from_scan(files, strategy=PopulationStrategy.HASH)  # Solo hashes
    repo.populate_from_scan(files, strategy=PopulationStrategy.EXIF_IMAGES)  # Solo EXIF imágenes
    
    # Consultar desde servicios (solo lectura)
    hash_val = repo.get_hash(file_path)
    exif = repo.get_exif(file_path)
    
    # Limpiar entre datasets
    repo.clear()

Preparado para migración a SQLite:
- Protocol IFileRepository define interfaz abstracta
- Métodos to_dict/from_dict en FileMetadata
- Separación clara entre lógica y almacenamiento
"""
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Any, OrderedDict
from enum import Enum
from dataclasses import dataclass, replace
from datetime import datetime
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import OrderedDict

from services.file_metadata import FileMetadata
from utils.logger import get_logger
from utils.file_utils import calculate_file_hash


class PopulationStrategy(Enum):
    """
    Estrategias para poblar el repositorio con metadatos.
    
    IMPORTANTE: FILESYSTEM_METADATA debe ejecutarse PRIMERO (scan inicial).
    Las demás estrategias son incrementales y requieren que FILESYSTEM_METADATA ya se haya ejecutado.
    """
    FILESYSTEM_METADATA = "filesystem_metadata"  # Solo filesystem metadata (OBLIGATORIO primero, rápido)
    HASH = "hash"                                # Solo hash SHA256 (requiere FILESYSTEM_METADATA previo, para duplicados)
    EXIF_IMAGES = "exif_images"                  # Solo EXIF imágenes (requiere FILESYSTEM_METADATA previo, moderado)
    EXIF_VIDEOS = "exif_videos"                  # Solo EXIF videos (requiere FILESYSTEM_METADATA previo, muy costoso)
    BEST_DATE = "best_date"                      # Calcula mejor fecha (requiere FILESYSTEM_METADATA y EXIF previo, rápido)


class IFileRepository(Protocol):
    """
    Interfaz abstracta del repositorio de archivos.
    
    Define el contrato que debe cumplir cualquier implementación
    (memoria, SQLite, MySQL, PostgreSQL, etc.)
    
    Facilita la migración futura sin cambiar el código de los servicios.
    """
    # Operaciones básicas
    def add_file(self, path: Path, metadata: FileMetadata) -> None: ...
    def get_file(self, path: Path) -> Optional[FileMetadata]: ...
    def has_file(self, path: Path) -> bool: ...
    def update_metadata(self, path: Path, **updates) -> None: ...
    def clear(self) -> None: ...
    
    # Consultas
    def get_all_files(self) -> List[FileMetadata]: ...
    def get_files_by_size(self, size: int) -> List[FileMetadata]: ...
    def get_file_metadata(self, path: Path) -> Optional[FileMetadata]: ...
    def get_hash(self, path: Path) -> Optional[str]: ...
    def get_exif(self, path: Path) -> Dict[str, Any]: ...
    def get_best_date(self, path: Path) -> tuple: ...  # (datetime, source)
    
    # Contadores
    def count(self) -> int: ...
    def get_file_count(self) -> int: ...
    def count_with_hash(self) -> int: ...
    def count_with_exif(self) -> int: ...
    def count_with_best_date(self) -> int: ...
    
    # Actualizaciones
    def set_hash(self, path: Path, hash_val: str) -> bool: ...
    def set_exif(self, path: Path, exif_data: Dict[str, Any]) -> bool: ...
    def set_best_date(self, path: Path, best_date: datetime, source: str) -> bool: ...
    
    # Gestión de caché
    def remove_file(self, path: Path) -> bool: ...
    def remove_files(self, paths: List[Path]) -> int: ...
    def move_file(self, old_path: Path, new_path: Path) -> bool: ...
    def set_max_entries(self, max_entries: int) -> None: ...
    
    # Estadísticas
    def get_cache_statistics(self) -> 'RepositoryStats': ...
    
    # Persistencia
    def save_to_disk(self, path: Path) -> None: ...
    def load_from_disk(self, path: Path, validate: bool = True) -> int: ...


@dataclass
class RepositoryStats:
    """Estadísticas del repositorio"""
    total_files: int
    files_with_hash: int
    files_with_exif: int
    files_with_best_date: int
    cache_hits: int
    cache_misses: int
    hit_rate: float


class FileInfoRepositoryCache:
    """
    Repositorio centralizado de información de archivos (Singleton - Cache).
    
    Sistema de caché inteligente thread-safe para metadatos de archivos.
    Actúa como fuente única de verdad para todos los servicios.
    
    Características:
    - Singleton: Una única instancia compartida globalmente
    - Thread-safe: Usa RLock para acceso concurrente seguro
    - Estrategias de población: Control fino sobre qué datos cargar
    - LRU Cache: Política de eviction inteligente basada en valor de datos
    - Cache Management: remove_file(), remove_files(), set_max_entries()
    - Estadísticas: Hit/miss tracking para optimización
    - Preparado para BBDD: Arquitectura desacoplada
    
    Patrón de uso:
        # Los servicios NO reciben el repositorio como parámetro
        # Acceden a la instancia global directamente
        
        # En Directory_Scanner (scan inicial):
        repo = FileInfoRepositoryCache.get_instance()
        repo.populate_from_scan(files, PopulationStrategy.FILESYSTEM_METADATA)
        
        # En cualquier servicio:
        repo = FileInfoRepositoryCache.get_instance()
        hash_val = repo.get_hash(path)           # None si no está
        exif = repo.get_exif(path)               # {} si no está
        
        # Entre datasets:
        repo.clear()
    
    Diseño para migración a BBDD:
    - Backend actual: dict en memoria (rápido, datasets pequeños/medianos)
    - Backend futuro: SQLite (datasets enormes, persistencia)
    - Interfaz IFileRepository: contrato abstracto
    - Métodos to_dict/from_dict en FileMetadata: serialización lista
    - Separación lógica/almacenamiento: fácil swap de backend
    """
    
    _instance: Optional['FileInfoRepositoryCache'] = None
    _lock_singleton = threading.Lock()
    
    def __new__(cls):
        """Implementación del patrón Singleton"""
        if cls._instance is None:
            with cls._lock_singleton:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Inicializa el repositorio vacío (solo la primera vez)"""
        if not hasattr(self, '_initialized'):
            # Backend de almacenamiento (OrderedDict para LRU integrado)
            self._cache: OrderedDict[Path, FileMetadata] = OrderedDict()
            
             # (Remove access_order)
            
            # Thread safety
            self._lock = threading.RLock()
            
            # Configuración
            self._max_entries = 100000
            
            # Estadísticas
            self._hits = 0
            self._misses = 0
            
            # Logger
            self._logger = get_logger('FileInfoRepositoryCache')
            
            self._initialized = True
            self._logger.info("FileInfoRepositoryCache initialized (Singleton)")
    
    @classmethod
    def get_instance(cls) -> 'FileInfoRepositoryCache':
        """
        Obtiene la instancia singleton del repositorio.
        
        Este es el método principal para acceder al repositorio desde cualquier servicio.
        
        Returns:
            FileInfoRepositoryCache: Instancia única del repositorio
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """
        Resetea la instancia singleton.
        
        PRECAUCIÓN: Solo usar en tests o al cambiar de dataset completo.
        """
        with cls._lock_singleton:
            if cls._instance is not None:
                cls._instance.clear()
                cls._instance = None
    
    # =========================================================================
    # POBLACIÓN DEL REPOSITORIO
    # =========================================================================
    
    def populate_from_scan(
        self,
        files: List[Path],
        strategy: PopulationStrategy = PopulationStrategy.FILESYSTEM_METADATA,
        max_workers: Optional[int] = None,
        progress_callback: Optional[callable] = None,
        stop_check_callback: Optional[callable] = None
    ) -> None:
        """
        Puebla el repositorio con información de archivos usando una estrategia.
        
        Este método es llamado por el Directory Scanner después del scan inicial
        del directorio. Población en paralelo para rendimiento.
        
        Args:
            files: Lista de rutas de archivos a procesar
            strategy: Estrategia de población (qué información cargar)
            max_workers: Número de workers paralelos (None = auto)
            progress_callback: Callback opcional para reportar progreso
            stop_check_callback: Callback opcional que retorna True si debe cancelarse
        
        Examples:
            # Paso 1: SIEMPRE empezar con FILESYSTEM_METADATA (scan inicial)
            repo.populate_from_scan(files, PopulationStrategy.FILESYSTEM_METADATA)
            
            # Paso 2: Análisis incremental según necesidad
            # Para detector de duplicados exactos (solo calcula hashes)
            repo.populate_from_scan(files, PopulationStrategy.HASH)
            
            # Para organizador/renombrador de fotos (solo EXIF de imágenes)
            repo.populate_from_scan(files, PopulationStrategy.EXIF_IMAGES)
            
            # Para análisis de videos (solo EXIF de videos, muy costoso)
            repo.populate_from_scan(files, PopulationStrategy.EXIF_VIDEOS)
        """
        if not files:
            self._logger.warning("populate_from_scan called with empty list")
            return
        
        self._logger.info(f"Starting population with strategy {strategy.value} - {len(files)} files")
        
        # Actualizar límite de entradas
        self.update_max_entries(len(files))
        
        # Determinar función de procesamiento según estrategia
        if strategy == PopulationStrategy.FILESYSTEM_METADATA:
            process_func = self._process_file_filesystem_metadata
        elif strategy == PopulationStrategy.HASH:
            process_func = self._process_file_hash
        elif strategy == PopulationStrategy.EXIF_IMAGES:
            process_func = self._process_file_exif_images
        elif strategy == PopulationStrategy.EXIF_VIDEOS:
            process_func = self._process_file_exif_videos
        elif strategy == PopulationStrategy.BEST_DATE:
            process_func = self._process_file_best_date
        else:
            raise ValueError(f"Estrategia desconocida: {strategy}")
        
        # Procesar en paralelo
        processed = 0
        errors = 0
        last_progress_report = 0
        progress_report_interval = max(1, len(files) // 100)  # Report every 1% or at least every file
        
        max_workers = max_workers or min(32, (len(files) // 10) + 1)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_func, file_path): file_path 
                      for file_path in files}
            
            for future in as_completed(futures):
                # Check for cancellation request BEFORE processing result
                if stop_check_callback and stop_check_callback():
                    self._logger.info(f"Cancellation detected - Processed: {processed}/{len(files)}")
                    # Cancel pending futures cooperatively
                    for pending_future in futures:
                        if not pending_future.done():
                            pending_future.cancel()
                    break
                
                file_path = futures[future]
                try:
                    metadata = future.result()
                    if metadata:
                        with self._lock:
                            self._cache[metadata.path] = metadata
                        processed += 1
                    else:
                        errors += 1
                except PermissionError as e:
                    self._logger.warning(f"Permission denied: {file_path.name}")
                    errors += 1
                except OSError as e:
                    self._logger.error(f"I/O error processing {file_path.name}: {e}")
                    errors += 1
                except Exception as e:
                    self._logger.error(f"Unexpected error processing {file_path.name}: {type(e).__name__}: {e}")
                    errors += 1
                
                # Progress callback with throttling (report every N files or on last file)
                if progress_callback:
                    should_report = (
                        processed - last_progress_report >= progress_report_interval or
                        processed == len(files) or
                        processed % 100 == 0  # Always report every 100 files
                    )
                    if should_report:
                        if not progress_callback(processed, len(files)):
                            self._logger.warning("Population cancelled by progress_callback")
                            break
                        last_progress_report = processed
        
        # Log final con información de cancelación si aplica
        cancelled = (stop_check_callback and stop_check_callback()) or processed < len(files)
        status = "cancelled" if cancelled else "completed"
        self._logger.info(
            f"Population {status} - "
            f"Processed: {processed}/{len(files)}, "
            f"Errors: {errors}, "
            f"Total in cache: {len(self._cache)}"
        )
    
    def _process_file_filesystem_metadata(self, path: Path) -> Optional[FileMetadata]:
        """
        Procesa archivo con estrategia FILESYSTEM_METADATA: solo filesystem metadata.
        
        Rápido, sin I/O costoso.
        """
        from utils.file_utils import get_file_stat_info
        
        try:
            if not path.exists():
                self._logger.debug(f"File does not exist: {path}")
                return None
            
            stat_info = get_file_stat_info(path, resolve_path=False)
            metadata = FileMetadata(
                path=path.resolve(),
                fs_size=stat_info['size'],
                fs_ctime=stat_info['ctime'],
                fs_mtime=stat_info['mtime'],
                fs_atime=stat_info['atime']
            )
            self._logger.debug(f"Basic metadata processed for {path.name}: {stat_info['size']} bytes")
            return metadata
        except (FileNotFoundError, PermissionError, OSError):
            # Logging detallado ya hecho en get_file_stat_info()
            self._logger.debug(f"Cannot process file: {path.name} to get basic metadata")
            return None
        except Exception as e:
            self._logger.error(f"Unexpected error in _process_file_filesystem_metadata for {path.name}: {type(e).__name__}: {e}")
            return None
    
    def _process_file_hash(self, path: Path) -> Optional[FileMetadata]:
        """
        Procesa archivo con estrategia HASH: solo calcula hash SHA256.
        
        Requiere que FILESYSTEM_METADATA ya se haya ejecutado.
        Si el archivo no está en caché, hace autofetch de filesystem metadata.
        """
        path = path.resolve()
        
        # Obtener metadata existente (autofetch si no existe)
        with self._lock:
            metadata = self._cache.get(path)
        
        if not metadata:
            # Autofetch: crear metadata básica
            metadata = self._process_file_filesystem_metadata(path)
            if not metadata:
                return None
            with self._lock:
                self._cache[path] = metadata
        
        # Ya tiene hash? Skip
        if metadata.sha256:
            self._logger.debug(f"Hash already calculated for {path.name}: {metadata.sha256[:8]}...")
            return metadata
        
        # Calcular hash (fuera del lock porque es costoso)
        hash_val = None
        try:
            hash_val = calculate_file_hash(path)
            self._logger.debug(f"Hash {path.name} calculated: {hash_val[:8]}...")
        except (PermissionError, FileNotFoundError, IOError):
            # Logging detallado ya hecho en calculate_file_hash()
            self._logger.debug(f"Could not calculate hash: {path.name}")
        except Exception as e:
            self._logger.error(f"Unexpected error calculating hash for {path.name}: {type(e).__name__}: {e}")
        
        # Actualizar metadata con lock (thread-safe)
        if hash_val:
            with self._lock:
                # Volver a obtener metadata del caché por si cambió
                cached_metadata = self._cache.get(path)
                if cached_metadata:
                    cached_metadata.sha256 = hash_val
                    self._logger.debug(f"Hash {path.name} assigned in cache: {hash_val[:8]}...")
                else:
                    # Raro pero posible: se eliminó del caché entre tanto
                    metadata.sha256 = hash_val
                    self._cache[path] = metadata
        
        return metadata
    
    def _process_file_exif_images(self, path: Path) -> Optional[FileMetadata]:
        """
        Procesa archivo con estrategia EXIF_IMAGES: solo extrae EXIF de imágenes.
        
        Requiere que FILESYSTEM_METADATA ya se haya ejecutado.
        Si el archivo no está en caché, hace autofetch de filesystem metadata.
        Solo procesa si es imagen y no tiene EXIF ya.
        """
        path = path.resolve()
        
        # Obtener metadata existente (autofetch si no existe)
        with self._lock:
            metadata = self._cache.get(path)
        
        if not metadata:
            # Autofetch: crear metadata básica
            metadata = self._process_file_filesystem_metadata(path)
            if not metadata:
                return None
            with self._lock:
                self._cache[path] = metadata
        
        # No es imagen? Skip
        if not metadata.is_image:
            self._logger.debug(f"Not an image, skipping EXIF: {path.name}")
            return metadata
        
        # Ya tiene EXIF? Skip
        if metadata.has_exif:
            self._logger.debug(f"EXIF already extracted for image {path.name}: {len(metadata.get_exif_dates())} fields")
            return metadata
        
        # Extraer EXIF de imágenes (fuera del lock porque es costoso)
        exif_data_from_image = None
        try:
            from utils.file_utils import get_exif_from_image
            
            exif_data_from_image = get_exif_from_image(path)
            exif_count = len(exif_data_from_image)
            self._logger.debug(f"EXIF extracted for image {path.name}: {exif_count} fields")
                
        except Exception as e:
            self._logger.warning(f"Error extracting EXIF from {path.name}: {e}")
        
        # Helper para convertir datetime a string EXIF
        def _datetime_to_exif_str(dt: datetime) -> str:
            """Convierte datetime a string en formato EXIF: 'YYYY:MM:DD HH:MM:SS'"""
            return dt.strftime('%Y:%m:%d %H:%M:%S')
        
        # Actualizar metadata con lock (thread-safe)
        if exif_data_from_image:
            with self._lock:
                # Volver a obtener metadata del caché por si cambió
                cached_metadata = self._cache.get(path)
                if cached_metadata:
                    # Establecer campos EXIF de fecha
                    # CRÍTICO: Convertir datetime objects a strings EXIF porque FileMetadata espera strings
                    if exif_data_from_image.get('DateTimeOriginal'):
                        cached_metadata.exif_DateTimeOriginal = _datetime_to_exif_str(exif_data_from_image['DateTimeOriginal'])
                    if exif_data_from_image.get('CreateDate'):
                        cached_metadata.exif_DateTime = _datetime_to_exif_str(exif_data_from_image['CreateDate'])  # CreateDate mapea a DateTime
                    if exif_data_from_image.get('DateTimeDigitized'):
                        cached_metadata.exif_DateTimeDigitized = _datetime_to_exif_str(exif_data_from_image['DateTimeDigitized'])
                    if exif_data_from_image.get('SubSecTimeOriginal'):
                        cached_metadata.exif_SubSecTimeOriginal = exif_data_from_image['SubSecTimeOriginal']
                    if exif_data_from_image.get('OffsetTimeOriginal'):
                        cached_metadata.exif_OffsetTimeOriginal = exif_data_from_image['OffsetTimeOriginal']
                    if exif_data_from_image.get('GPSDateStamp'):
                        cached_metadata.exif_GPSDateStamp = _datetime_to_exif_str(exif_data_from_image['GPSDateStamp'])
                    if exif_data_from_image.get('Software'):
                        cached_metadata.exif_Software = exif_data_from_image['Software']
                    if exif_data_from_image.get('ExifVersion'):
                        cached_metadata.exif_ExifVersion = exif_data_from_image['ExifVersion']
                    if exif_data_from_image.get('ImageWidth'):
                        cached_metadata.exif_ImageWidth = exif_data_from_image['ImageWidth']
                    if exif_data_from_image.get('ImageLength'):
                        cached_metadata.exif_ImageLength = exif_data_from_image['ImageLength']
                    self._logger.debug(f"EXIF assigned in cache for image {path.name}: {len(exif_data_from_image)} fields")
                else:
                    # Raro pero posible: se eliminó del caché entre tanto
                    if exif_data_from_image.get('DateTimeOriginal'):
                        metadata.exif_DateTimeOriginal = _datetime_to_exif_str(exif_data_from_image['DateTimeOriginal'])
                    if exif_data_from_image.get('CreateDate'):
                        metadata.exif_DateTime = _datetime_to_exif_str(exif_data_from_image['CreateDate'])
                    if exif_data_from_image.get('DateTimeDigitized'):
                        metadata.exif_DateTimeDigitized = _datetime_to_exif_str(exif_data_from_image['DateTimeDigitized'])
                    if exif_data_from_image.get('SubSecTimeOriginal'):
                        metadata.exif_SubSecTimeOriginal = exif_data_from_image['SubSecTimeOriginal']
                    if exif_data_from_image.get('OffsetTimeOriginal'):
                        metadata.exif_OffsetTimeOriginal = exif_data_from_image['OffsetTimeOriginal']
                    if exif_data_from_image.get('GPSDateStamp'):
                        metadata.exif_GPSDateStamp = _datetime_to_exif_str(exif_data_from_image['GPSDateStamp'])
                    if exif_data_from_image.get('Software'):
                        metadata.exif_Software = exif_data_from_image['Software']
                    if exif_data_from_image.get('ExifVersion'):
                        metadata.exif_ExifVersion = exif_data_from_image['ExifVersion']
                    if exif_data_from_image.get('ImageWidth'):
                        metadata.exif_ImageWidth = exif_data_from_image['ImageWidth']
                    if exif_data_from_image.get('ImageLength'):
                        metadata.exif_ImageLength = exif_data_from_image['ImageLength']
                    self._cache[path] = metadata
        
        return metadata
    
    def _process_file_exif_videos(self, path: Path) -> Optional[FileMetadata]:
        """
        Procesa archivo con estrategia EXIF_VIDEOS: solo extrae EXIF de videos.
        
        Requiere que FILESYSTEM_METADATA ya se haya ejecutado.
        Si el archivo no está en caché, hace autofetch de filesystem metadata.
        Solo procesa si es video y no tiene EXIF ya.
        Muy costoso (videos requieren más procesamiento).
        """
        path = path.resolve()
        
        # Obtener metadata existente (autofetch si no existe)
        with self._lock:
            metadata = self._cache.get(path)
        
        if not metadata:
            # Autofetch: crear metadata básica
            metadata = self._process_file_filesystem_metadata(path)
            if not metadata:
                return None
            with self._lock:
                self._cache[path] = metadata
        
        # No es video? Skip
        if not metadata.is_video:
            self._logger.debug(f"Not a video, skipping EXIF: {path.name}")
            return metadata
        
        # Ya tiene EXIF? Skip
        if metadata.has_exif:
            self._logger.debug(f"EXIF already extracted for video {path.name}: {len(metadata.get_exif_dates())} fields")
            return metadata
        
        # Extraer EXIF de videos (fuera del lock porque es muy costoso)
        video_metadata = None
        try:
            from utils.file_utils import get_exif_from_video
            
            video_metadata = get_exif_from_video(path)
            
            if video_metadata:
                field_count = len(video_metadata)
                self._logger.debug(f"Video metadata extracted for {path.name}: {field_count} fields")
            else:
                self._logger.debug(f"No metadata found for video {path.name}")
                
        except Exception as e:
            self._logger.warning(f"Error extracting video metadata for {path.name}: {e}")
        
        # Helper para convertir datetime a string EXIF
        def _datetime_to_exif_str(dt: datetime) -> str:
            """Convierte datetime a string en formato EXIF: 'YYYY:MM:DD HH:MM:SS'"""
            return dt.strftime('%Y:%m:%d %H:%M:%S')
        
        # Actualizar metadata con lock (thread-safe)
        if video_metadata:
            with self._lock:
                # Volver a obtener metadata del caché por si cambió
                cached_metadata = self._cache.get(path)
                target_metadata = cached_metadata if cached_metadata else metadata
                
                # Mapear creation_time (fecha de creación)
                if 'creation_time' in video_metadata and video_metadata['creation_time']:
                    creation_date_str = _datetime_to_exif_str(video_metadata['creation_time'])
                    target_metadata.exif_DateTimeOriginal = creation_date_str
                    target_metadata.exif_DateTime = creation_date_str
                
                # Mapear offset de timezone (de com.apple.quicktime.creationdate)
                if 'creation_time_offset' in video_metadata and video_metadata['creation_time_offset']:
                    target_metadata.exif_OffsetTimeOriginal = video_metadata['creation_time_offset']
                
                # Mapear dimensiones de video
                if 'width' in video_metadata and video_metadata['width']:
                    target_metadata.exif_ImageWidth = video_metadata['width']
                if 'height' in video_metadata and video_metadata['height']:
                    target_metadata.exif_ImageLength = video_metadata['height']
                
                # Mapear información de duración
                # Nota: FileMetadata no tiene campo específico para duration, 
                # pero se podría agregar en el futuro
                
                # Mapear información de codec y formato
                # Nota: FileMetadata no tiene campos específicos para codec/format,
                # pero esta información está disponible si se agregan campos en el futuro
                
                # Mapear encoder (Software)
                if 'encoder' in video_metadata and video_metadata['encoder']:
                    target_metadata.exif_Software = video_metadata['encoder']
                
                # Mapear duración en segundos
                if 'duration_seconds' in video_metadata and video_metadata['duration_seconds']:
                    target_metadata.exif_VideoDurationSeconds = video_metadata['duration_seconds']
                
                if not cached_metadata:
                    # Si no estaba en caché, agregarlo
                    self._cache[path] = metadata
                
                fields_set = sum([
                    1 if 'creation_time' in video_metadata else 0,
                    1 if 'width' in video_metadata else 0,
                    1 if 'height' in video_metadata else 0,
                    1 if 'encoder' in video_metadata else 0,
                    1 if 'duration' in video_metadata else 0,
                ])
                self._logger.debug(
                    f"Video metadata assigned in cache for {path.name}: "
                    f"{fields_set} fields mapped to FileMetadata"
                )
        
        return metadata
    
    

    def _process_file_best_date(self, path: Path) -> Optional[FileMetadata]:
        """
        Procesa archivo con estrategia BEST_DATE: calcula la mejor fecha disponible.
        
        Usa la lógica de select_best_date_from_file() de date_utils.py que prioriza:
        1. EXIF DateTimeOriginal (con/sin timezone)
        2. EXIF CreateDate
        3. EXIF DateTimeDigitized
        4. Fecha del nombre de archivo
        5. Fecha de filesystem (mtime/ctime)
        
        Requiere que FILESYSTEM_METADATA y EXIF ya se hayan ejecutado para obtener el mejor resultado.
        Si no hay EXIF, usará fechas del filesystem como fallback.
        
        Es una operación rápida porque solo consulta datos ya en caché.
        """
        from utils.date_utils import select_best_date_from_file
        
        path = path.resolve()
        
        # Obtener metadata existente
        with self._lock:
            file_metadata = self._cache.get(path)
        
        if not file_metadata:
            self._logger.debug(f"Cannot calculate best_date: file not in cache: {path.name}")
            return None
        
        # Ya tiene best_date? Skip
        if file_metadata.has_best_date:
            self._logger.debug(f"best_date already calculated for {path.name}: {file_metadata.best_date}")
            return file_metadata
        
        # Calcular la mejor fecha pasando directamente el FileMetadata
        selected_date, selected_source = select_best_date_from_file(file_metadata)
        
        if selected_date:
            # Usar el source original sin normalizar
            source = selected_source if selected_source else 'unknown'
            
            # Actualizar metadata con lock
            with self._lock:
                cached_metadata = self._cache.get(path)
                if cached_metadata:
                    cached_metadata.best_date = selected_date
                    cached_metadata.best_date_source = source
                    self._logger.debug(
                        f"best_date calculated for {path.name}: "
                        f"{selected_date.strftime('%Y-%m-%d %H:%M:%S')} ({source})"
                    )
                    return cached_metadata
        else:
            self._logger.debug(f"Could not determine best_date for {path.name}")
        
        return file_metadata
    

    
    # =========================================================================
    # CONSULTAS (GET) 
    # =========================================================================
    
    def get_file_metadata(
        self,
        path: Path
    ) -> Optional[FileMetadata]:
        """
        Obtiene metadatos completos de un archivo.
        
        Args:
            path: Ruta del archivo
            
        Returns:
            FileMetadata si existe en caché, None en caso contrario
        """
        path = path.resolve()
        
        with self._lock:
            if path in self._cache:
                self._hits += 1
                self._update_access_order(path)  # Actualizar LRU
                return self._cache[path]
            self._misses += 1
        
        return None
    
    def get_hash(self, path: Path) -> Optional[str]:
        """
        Obtiene el hash SHA256 de un archivo desde la caché.
        
        Args:
            path: Ruta del archivo
            
        Returns:
            str: Hash SHA256 en hexadecimal, o None si no está calculado/cacheado
        """
        path = path.resolve()
        metadata = self.get_file_metadata(path)
        
        # Si tiene hash cacheado, retornarlo
        if metadata and metadata.sha256:
            return metadata.sha256
        
        return None
    
    def get_exif(self, path: Path) -> Dict[str, Any]:
        """
        Obtiene datos EXIF de un archivo desde la caché.
        
        Args:
            path: Ruta del archivo
            
        Returns:
            Dict con campos EXIF presentes (vacío si no hay datos o no está cacheado)
        """
        path = path.resolve()
        metadata = self.get_file_metadata(path)
        
        if not metadata:
            return {}
        
        return metadata.get_exif_dates()
    
    def get_filesystem_metadata(
        self,
        path: Path
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene metadatos del sistema de archivos desde la caché.
        
        Args:
            path: Ruta del archivo
            
        Returns:
            Dict con fs_size, fs_ctime, fs_mtime, fs_atime, o None si no existe
        """
        path = path.resolve()
        metadata = self.get_file_metadata(path)
        
        if not metadata:
            return None
        
        return {
            'fs_size': metadata.fs_size,
            'fs_ctime': metadata.fs_ctime,
            'fs_mtime': metadata.fs_mtime,
            'fs_atime': metadata.fs_atime
        }
    
    def get_best_date(self, path: Path) -> tuple[Optional[datetime], Optional[str]]:
        """
        Obtiene la mejor fecha disponible de un archivo desde la caché.
        
        Esta fecha se calcula en Phase 5 del InitialScanner usando la lógica
        de select_best_date_from_file() que prioriza EXIF sobre filesystem.
        
        Args:
            path: Ruta del archivo
            
        Returns:
            Tuple (datetime, source) donde:
            - datetime: La mejor fecha disponible, o None si no está calculada
            - source: Fuente de la fecha (ej: 'EXIF DateTimeOriginal', 'mtime', 'exif_date_time_original')
        """
        path = path.resolve()
        metadata = self.get_file_metadata(path)
        
        if not metadata:
            return None, None
        
        return metadata.best_date, metadata.best_date_source
    
    def get_filesystem_modification_date(self, path: Path) -> Optional[datetime]:
        """
        Obtiene la fecha de modificación del filesystem desde la caché.
        
        Útil como fallback rápido cuando best_date no está disponible.
        
        Args:
            path: Ruta del archivo
            
        Returns:
            datetime de fs_mtime, o None si no existe en caché
        """
        path = path.resolve()
        metadata = self.get_file_metadata(path)
        
        if not metadata:
            return None
        
        return datetime.fromtimestamp(metadata.fs_mtime)
    
    # =========================================================================
    # ACTUALIZACIONES (SET) - Solo para archivos ya en caché
    # =========================================================================
    
    def set_hash(self, path: Path, hash_val: str) -> bool:
        """
        Establece el hash SHA256 de un archivo.
        
        Solo actualiza si el archivo ya está en caché.
        Útil cuando el hash se ha calculado externamente.
        
        Args:
            path: Ruta del archivo
            hash_val: Hash SHA256 en hexadecimal
            
        Returns:
            bool: True si se actualizó, False si el archivo no está en caché
        """
        path = path.resolve()
        
        with self._lock:
            if path not in self._cache:
                self._logger.warning(
                    f"Attempt to set_hash for file not in cache: {path.name}"
                )
                return False
            
            self._cache[path].sha256 = hash_val
            return True
    
    def set_exif(self, path: Path, exif_data: Dict[str, Any]) -> bool:
        """
        Establece datos EXIF de un archivo.
        
        Solo actualiza si el archivo ya está en caché.
        
        Args:
            path: Ruta del archivo
            exif_data: Diccionario con campos EXIF
            
        Returns:
            bool: True si se actualizó, False si el archivo no está en caché
        """
        path = path.resolve()
        
        with self._lock:
            if path not in self._cache:
                self._logger.warning(
                    f"Attempt to set_exif for file not in cache: {path.name}"
                )
                return False
            
            metadata = self._cache[path]
            
            # Actualizar campos EXIF presentes
            if 'ImageWidth' in exif_data:
                metadata.exif_ImageWidth = exif_data['ImageWidth']
            if 'ImageLength' in exif_data:
                metadata.exif_ImageLength = exif_data['ImageLength']
            if 'DateTime' in exif_data:
                metadata.exif_DateTime = exif_data['DateTime']
            if 'GPSTimeStamp' in exif_data:
                metadata.exif_GPSTimeStamp = exif_data['GPSTimeStamp']
            if 'GPSDateStamp' in exif_data:
                metadata.exif_GPSDateStamp = exif_data['GPSDateStamp']
            if 'DateTimeOriginal' in exif_data:
                metadata.exif_DateTimeOriginal = exif_data['DateTimeOriginal']
            if 'DateTimeDigitized' in exif_data:
                metadata.exif_DateTimeDigitized = exif_data['DateTimeDigitized']
            if 'ExifVersion' in exif_data:
                metadata.exif_ExifVersion = exif_data['ExifVersion']
            
            return True
    
    def set_best_date(self, path: Path, best_date: datetime, source: str) -> bool:
        """
        Establece la mejor fecha disponible de un archivo.
        
        Solo actualiza si el archivo ya está en caché.
        
        Args:
            path: Ruta del archivo
            best_date: La fecha calculada como la mejor disponible
            source: Fuente de la fecha (ej: 'EXIF DateTimeOriginal', 'mtime', 'exif_date_time_original')
            
        Returns:
            bool: True si se actualizó, False si el archivo no está en caché
        """
        path = path.resolve()
        
        with self._lock:
            if path not in self._cache:
                self._logger.debug(
                    f"Attempt to set_best_date for file not in cache: {path.name}"
                )
                return False
            
            metadata = self._cache[path]
            metadata.best_date = best_date
            metadata.best_date_source = source
            return True
    
    # =========================================================================
    # CONSULTAS MASIVAS Y AGRUPACIONES
    # =========================================================================
    
    def get_all_files(self) -> List[FileMetadata]:
        """
        Obtiene todos los archivos del repositorio.
        
        Returns:
            List[FileMetadata]: Lista de todos los archivos
        """
        with self._lock:
            return list(self._cache.values())
    
    def get_files_by_size(self) -> Dict[int, List[FileMetadata]]:
        """
        Agrupa archivos por tamaño.
        
        Útil para detección de duplicados exactos (pre-filtrado).
        
        Returns:
            Dict[int, List[FileMetadata]]: size -> lista de archivos
        """
        by_size: Dict[int, List[FileMetadata]] = {}
        
        with self._lock:
            for metadata in self._cache.values():
                if metadata.fs_size not in by_size:
                    by_size[metadata.fs_size] = []
                by_size[metadata.fs_size].append(metadata)
        
        return by_size
    
    def count(self) -> int:
        """
        Número total de archivos en el repositorio.
        
        Método optimizado, usar en lugar de len(get_all_files()).
        
        Returns:
            int: Número de archivos
        """
        with self._lock:
            return len(self._cache)
    
    def get_file_count(self) -> int:
        """
        Alias de count() para compatibilidad con servicios existentes.
        
        Returns:
            int: Número de archivos
        """
        return self.count()
    
    def count_with_hash(self) -> int:
        """Número de archivos con hash calculado"""
        with self._lock:
            return sum(1 for m in self._cache.values() if m.has_hash)
    
    def count_with_exif(self) -> int:
        """Número de archivos con EXIF"""
        with self._lock:
            return sum(1 for m in self._cache.values() if m.has_exif)
    
    def count_with_best_date(self) -> int:
        """Número de archivos con best_date calculado"""
        with self._lock:
            return sum(1 for m in self._cache.values() if m.has_best_date)
    
    # =========================================================================
    # UTILIDADES
    # =========================================================================
    
    def update_max_entries(self, total_files: int) -> None:
        """
        Actualiza el límite interno basado en el conteo de archivos.
        
        Args:
            total_files: Número total de archivos en el dataset
        """
        with self._lock:
            old_max = self._max_entries
            self._max_entries = max(self._max_entries, total_files + 1000)
            if old_max != self._max_entries:
                self._logger.info(
                    f"Entry limit updated: {old_max} -> {self._max_entries}"
                )
    
    def get_cache_statistics(self) -> RepositoryStats:
        """
        Obtiene estadísticas del repositorio.
        
        Returns:
            RepositoryStats: Estadísticas actuales
        """
        with self._lock:
            total = len(self._cache)
            with_hash = self.count_with_hash()
            with_exif = self.count_with_exif()
            with_best_date = self.count_with_best_date()
            total_access = self._hits + self._misses
            hit_rate = (self._hits / total_access * 100) if total_access > 0 else 0.0
        
        return RepositoryStats(
            total_files=total,
            files_with_hash=with_hash,
            files_with_exif=with_exif,
            files_with_best_date=with_best_date,
            cache_hits=self._hits,
            cache_misses=self._misses,
            hit_rate=hit_rate
        )
    
    def log_cache_statistics(self, level: int = logging.INFO) -> None:
        """
        Registra estadísticas en el log con el nivel especificado.
        
        Args:
            level: Nivel de logging (ej: logging.DEBUG, logging.INFO, logging.WARNING)
        """
        stats = self.get_cache_statistics()
        self._logger.log(level,
            f"[REPO CACHE STATUS] - "
            f"Files: {stats.total_files}, "
            f"With hash: {stats.files_with_hash}, "
            f"With EXIF: {stats.files_with_exif}, "
            f"With best_date: {stats.files_with_best_date}, "
            f"Hits: {stats.cache_hits}, "
            f"Misses: {stats.cache_misses}, "
            f"Hit rate: {stats.hit_rate:.1f}%"
        )
    
    def clear(self) -> None:
        """
        Limpia completamente el repositorio.
        
        Usar al cambiar de dataset o después de operaciones destructivas.
        """
        with self._lock:
            old_size = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._logger.info(f"Repository cleared - {old_size} files removed")
    
    # =========================================================================
    # GESTIÓN DE CACHÉ Y ELIMINACIÓN
    # =========================================================================
    
    def remove_file(self, path: Path) -> bool:
        """
        Elimina un archivo del repositorio.
        
        Útil cuando se borra un archivo del disco y queremos actualizar la caché
        sin necesidad de reanalizar todo el dataset.
        
        Args:
            path: Ruta del archivo a eliminar
            
        Returns:
            bool: True si se eliminó, False si no estaba en caché
        """
        path = path.resolve()
        
        with self._lock:
            if path in self._cache:
                del self._cache[path]
                self._logger.debug(f"File removed from repository: {path.name}")
                return True
            return False
    
    def remove_files(self, paths: List[Path]) -> int:
        """
        Elimina múltiples archivos del repositorio en batch.
        
        Más eficiente que llamar a remove_file() múltiples veces.
        
        Args:
            paths: Lista de rutas a eliminar
            
        Returns:
            int: Número de archivos eliminados
        """
        removed = 0
        
        with self._lock:
            for path in paths:
                path_resolved = path.resolve()
                if path_resolved in self._cache:
                    del self._cache[path_resolved]
                    # _access_order was removed, OrderedDict handles LRU directly
                    removed += 1
            
            if removed > 0:
                self._logger.info(f"Removed {removed} files from repository")
        
        return removed
    
    def move_file(self, old_path: Path, new_path: Path) -> bool:
        """
        Mueve un archivo en la caché de un path a otro.
        
        Útil cuando se renombra o mueve un archivo en el disco.
        Preserva todos los metadatos (hash, EXIF, etc.) pero actualiza el path.
        
        Args:
            old_path: Ruta original del archivo
            new_path: Nueva ruta del archivo
            
        Returns:
            bool: True si se movió correctamente, False si no existía el archivo original
        """
        old_path_resolved = old_path.resolve()
        new_path_resolved = new_path.resolve()
        
        with self._lock:
            if old_path_resolved in self._cache:
                # Obtener metadatos del archivo antiguo
                metadata = self._cache[old_path_resolved]
                
                # Crear nueva entrada con el path actualizado
                # FileMetadata es inmutable, así que necesitamos crear uno nuevo
                new_metadata = replace(metadata, path=new_path_resolved)
                
                # Eliminar entrada antigua
                del self._cache[old_path_resolved]
                # _access_order was removed, OrderedDict handles LRU directly
                
                # Agregar entrada nueva
                self._cache[new_path_resolved] = new_metadata
                # OrderedDict automatically maintains insertion order
                
                # No es necesario enforce_max_entries aquí porque no estamos
                # añadiendo una nueva entrada, solo moviendo una existente
                
                self._logger.debug(f"File moved in repository: {old_path.name} -> {new_path.name}")
                return True
            return False
    
    def save_to_disk(self, path: Path) -> None:
        """
        Guarda el estado actual del repositorio a disco.
        
        Útil para datasets grandes que no cambian seguido. Permite recargar
        el repositorio sin tener que reanalizar todos los archivos.
        
        Args:
            path: Ruta del archivo donde guardar (extensión .json recomendada)
            
        Raises:
            IOError: Si no se puede escribir el archivo
        """
        import json
        
        with self._lock:
            cache_data = {
                'version': 1,
                'metadata': {
                    'total_files': len(self._cache),
                    'files_with_hash': self.count_with_hash(),
                    'files_with_exif': self.count_with_exif(),
                },
                'files': [
                    metadata.to_dict() for metadata in self._cache.values()
                ]
            }
            
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2, default=str, ensure_ascii=False)
                
                self._logger.info(
                    f"Repository saved to disk: {path} "
                    f"({len(self._cache)} files, {path.stat().st_size / 1024 / 1024:.2f} MB)"
                )
            except PermissionError as e:
                self._logger.error(f"Permission denied saving repository to {path}: {e}")
                raise IOError(f"Permission denied: {e}") from e
            except OSError as e:
                self._logger.error(f"I/O error saving repository: {e}")
                raise IOError(f"I/O error: {e}") from e
            except Exception as e:
                self._logger.error(f"Unexpected error saving repository: {type(e).__name__}: {e}")
                raise IOError(f"Could not save repository: {e}") from e
    
    def load_from_disk(self, path: Path, validate: bool = True) -> int:
        """
        Carga el repositorio desde un archivo guardado previamente.
        
        Args:
            path: Ruta del archivo a cargar
            validate: Si True, valida que los archivos aún existan en disco
            
        Returns:
            int: Número de archivos cargados (después de validación si aplica)
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si el archivo está corrupto o tiene versión incompatible
        """
        import json
        
        if not path.exists():
            raise FileNotFoundError(f"Cache file not found: {path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Validar versión
            version = cache_data.get('version', 0)
            if version != 1:
                raise ValueError(f"Incompatible cache version: {version}")
            
            # Cargar archivos
            files_data = cache_data.get('files', [])
            loaded = 0
            skipped = 0
            
            with self._lock:
                # Limpiar caché actual
                self._cache.clear()
                
                for file_data in files_data:
                    try:
                        metadata = FileMetadata.from_dict(file_data)
                        
                        # Validar que el archivo existe si está solicitado
                        if validate and not metadata.path.exists():
                            skipped += 1
                            continue
                        
                        self._cache[metadata.path] = metadata
                        # OrderedDict maintains insertion order automatically
                        loaded += 1
                        
                    except (KeyError, ValueError, TypeError) as e:
                        self._logger.warning(f"Invalid data in entry: {type(e).__name__}: {e}")
                        skipped += 1
                    except Exception as e:
                        self._logger.warning(f"Unexpected error loading entry: {type(e).__name__}: {e}")
                        skipped += 1
                
                # Actualizar límite de entradas
                self.update_max_entries(loaded)
                
                self._logger.info(
                    f"Repository loaded from disk: {path} "
                    f"({loaded} files loaded, {skipped} skipped)"
                )
                
                if validate and skipped > 0:
                    self._logger.warning(
                        f"Validation: {skipped} files no longer exist on disk"
                    )
            
            return loaded
            
        except json.JSONDecodeError as e:
            self._logger.error(f"Corrupt cache file: {e}")
            raise ValueError(f"Corrupt cache file: {e}") from e
        except PermissionError as e:
            self._logger.error(f"Permission denied reading {path}: {e}")
            raise
        except OSError as e:
            self._logger.error(f"I/O error reading cache: {e}")
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error loading repository: {type(e).__name__}: {e}")
            raise
    
    def set_max_entries(self, max_entries: int) -> None:
        """
        Establece el límite máximo de entradas en la caché.
        
        Si el nuevo límite es menor que el actual número de entradas,
        se aplicará la política LRU para eliminar las entradas menos usadas.
        
        Args:
            max_entries: Nuevo límite máximo (debe ser > 0)
            
        Raises:
            ValueError: Si max_entries <= 0
        """
        if max_entries <= 0:
            raise ValueError("max_entries debe ser mayor que 0")
        
        with self._lock:
            old_max = self._max_entries
            self._max_entries = max_entries
            
            self._logger.info(
                f"Cache limit updated: {old_max} -> {self._max_entries}"
            )
            
            # Si excedemos el límite, aplicar política de eviction
            current_size = len(self._cache)
            if current_size > self._max_entries:
                self._evict_lru_entries(current_size - self._max_entries)
    
    def _evict_lru_entries(self, num_to_evict: int) -> None:
        """
        Elimina las entradas menos recientemente usadas (LRU).
        
        Args:
            num_to_evict: Número de entradas a eliminar
        """
        if num_to_evict <= 0:
            return
        
        # Ya estamos dentro de self._lock
        evicted = 0
        while len(self._cache) > self._max_entries and evicted < num_to_evict * 2: # Limit iterations safely
             self._cache.popitem(last=False) # FIFO = LIFO of LRU (last=False pops oldest)
             evicted += 1
             
             if len(self._cache) <= self._max_entries:
                 break
        
        self._logger.info(
            f"LRU policy: Evicted {evicted} entries "
            f"(limit: {self._max_entries}, current: {len(self._cache)})"
        )
    
    def _update_access_order(self, path: Path) -> None:
        """
        Actualiza el orden de acceso para LRU.
        
        Mueve el path al final del OrderedDict (más reciente).
        O(1) operation.
        
        Args:
            path: Path accedido recientemente
        """
        # Ya estamos dentro de self._lock
        
        if path in self._cache:
            self._cache.move_to_end(path)
    
    # =========================================================================
    # OPERADORES
    # =========================================================================
    
    def __len__(self) -> int:
        """Permite usar len(repository)"""
        return self.count()
    
    def __contains__(self, path: Path) -> bool:
        """Permite usar 'path in repository'"""
        path = path.resolve()
        with self._lock:
            return path in self._cache
    
    def __getitem__(self, path: Path) -> Optional[FileMetadata]:
        """Permite usar repository[path]"""
        return self.get_file_metadata(path)

