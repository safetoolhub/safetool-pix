# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Utilidades para extracción de fechas de archivos multimedia
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Any, runtime_checkable, TYPE_CHECKING

from functools import lru_cache
from utils.logger import get_logger

if TYPE_CHECKING:
    from services.file_metadata import FileMetadata

_logger = get_logger("DateUtils")

# Constante para fecha epoch zero
_EPOCH_ZERO = datetime(1970, 1, 1, 0, 0, 0)


# ==============================================================================
# HELPER FUNCTIONS - Funciones de parseo reutilizables
# ==============================================================================

def _parse_exif_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parsea un string de fecha EXIF a datetime.
    
    Soporta dos formatos comunes:
    - Formato EXIF estándar: "2023:01:15 10:30:00"
    - Formato ISO 8601: "2023-01-15T10:30:00Z" o "2023-01-15T10:30:00+02:00"
    
    Args:
        date_str: String de fecha EXIF o None
        
    Returns:
        datetime parseado o None si el string es inválido
        
    Examples:
        >>> _parse_exif_date("2023:01:15 10:30:00")
        datetime.datetime(2023, 1, 15, 10, 30)
        
        >>> _parse_exif_date("2023-01-15T10:30:00Z")
        datetime.datetime(2023, 1, 15, 10, 30, tzinfo=datetime.timezone.utc)
        
        >>> _parse_exif_date(None)
        None
    """
    if not date_str:
        return None
    try:
        # Formato típico EXIF: "2023:01:15 10:30:00"
        if ':' in date_str[:10]:
            return datetime.strptime(date_str[:19], '%Y:%m:%d %H:%M:%S')
        # Formato ISO
        elif 'T' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return None
    except (ValueError, TypeError):
        return None


def _is_epoch_zero_date(dt: datetime) -> bool:
    """
    Verifica si un datetime es la fecha de epoch 0 (1970-01-01 00:00:00).
    
    Esta fecha representa "no hay fecha" en muchos sistemas y debe ser
    tratada como inválida para propósitos de selección de mejor fecha.
    
    Args:
        dt: datetime a verificar
        
    Returns:
        True si es epoch 0, False en caso contrario
        
    Examples:
        >>> _is_epoch_zero_date(datetime(1970, 1, 1, 0, 0, 0))
        True
        
        >>> _is_epoch_zero_date(datetime(2023, 1, 15, 10, 30, 0))
        False
    """
    return dt == _EPOCH_ZERO


def _parse_gps_datetime(gps_datestamp: Optional[str], gps_timestamp: Optional[str]) -> Optional[datetime]:
    """
    Combina GPSDateStamp y GPSTimeStamp en un solo datetime.
    
    Los metadatos GPS almacenan fecha y hora en campos separados.
    Esta función los combina cuando ambos están presentes,
    o intenta parsear solo la fecha si está disponible.
    
    Args:
        gps_datestamp: String de fecha GPS "YYYY:MM:DD"
        gps_timestamp: String de hora GPS "HH:MM:SS"
        
    Returns:
        datetime combinado o None si no se puede parsear
        
    Examples:
        >>> _parse_gps_datetime("2023:01:15", "10:30:00")
        datetime.datetime(2023, 1, 15, 10, 30)
        
        >>> _parse_gps_datetime("2023:01:15", None)
        datetime.datetime(2023, 1, 15, 0, 0)
        
        >>> _parse_gps_datetime(None, "10:30:00")
        None
    """
    if gps_datestamp and gps_timestamp:
        try:
            gps_datetime_str = f"{gps_datestamp} {gps_timestamp}"
            return datetime.strptime(gps_datetime_str, '%Y:%m:%d %H:%M:%S')
        except (ValueError, TypeError):
            pass
    elif gps_datestamp:
        # Solo fecha GPS disponible
        return _parse_exif_date(gps_datestamp)
    
    return None


@dataclass(frozen=True)
class DateCoherenceResult:
    """Resultado de la validación de coherencia de fechas.
    
    Frozen dataclass inmutable con el resultado de _validate_date_coherence().
    
    Attributes:
        is_valid: True si pasa todas las validaciones críticas
        warnings: Tupla de códigos de advertencia (inmutable)
        confidence: Nivel de confianza: 'high', 'medium', 'low'
    """
    is_valid: bool
    warnings: tuple[str, ...]
    confidence: str  # 'high', 'medium', 'low'


def _parse_timezone_offset(offset_str: Optional[str]) -> Optional[int]:
    """
    Parsea un string de offset de timezone y retorna el offset en segundos.
    
    Args:
        offset_str: String de offset como '+02:00', '-05:00', 'Z', etc.
        
    Returns:
        Offset en segundos (positivo para este del UTC, negativo para oeste)
        None si el offset no es válido o no se puede parsear
    """
    if not offset_str:
        return None
    
    offset_str = offset_str.strip()
    
    # UTC
    if offset_str in ('Z', 'UTC', '+00:00', '-00:00'):
        return 0
    
    try:
        # Formato ±HH:MM o ±HHMM
        if len(offset_str) >= 5 and offset_str[0] in ('+', '-'):
            sign = 1 if offset_str[0] == '+' else -1
            
            # Con : (ej: +02:00)
            if ':' in offset_str:
                parts = offset_str[1:].split(':')
                hours = int(parts[0])
                minutes = int(parts[1]) if len(parts) > 1 else 0
            else:
                # Sin : (ej: +0200)
                hours = int(offset_str[1:3])
                minutes = int(offset_str[3:5]) if len(offset_str) >= 5 else 0
            
            return sign * (hours * 3600 + minutes * 60)
    except (ValueError, IndexError):
        pass
    
    return None


def select_best_date_from_common_date_to_2_files(
    file1: Any, 
    file2: Any,
    verbose: bool = False
) -> Optional[Tuple[datetime, datetime, str]]:
    """
    Compara las fechas de creación más realistas posibles de dos archivos.
    
    Devuelve una tupla con (fecha_file1, fecha_file2, fuente) donde las fechas son
    del mismo tipo para ambos archivos (nunca mezcla EXIF con filesystem).
    Usado por HEICService y LivePhotoService para determinar la fecha correcta de los pares de archivos.
    
    NORMALIZACIÓN DE TIMEZONE:
    - Si AMBOS archivos tienen offset de timezone: se normaliza a UTC para comparación justa
    - Si NINGUNO tiene offset o solo uno tiene offset: se usa hora local sin normalizar
      (asumiendo que ambos están en la misma zona horaria local)
    - Esto corrige el bug donde archivos sin offset eran incorrectamente tratados como UTC
    
    Prioriza fidelidad al momento de captura/creación original:
    1. EXIF DateTimeOriginal (Captura exacta)
    2. EXIF CreateDate (Creación digital)
    3. EXIF ModifyDate (Última modificación EXIF)
    4. Filesystem ctime (Change time - creación/metadatos)
    5. Filesystem mtime (Modify time - contenido)
    6. Filesystem atime (Access time - último recurso)
    
    Args:
        file1: Objeto con metadatos del primer archivo (FileInfo/FileMetadata)
        file2: Objeto con metadatos del segundo archivo (FileInfo/FileMetadata)
        
    Returns:
        Tuple[datetime, datetime, str]: (fecha1, fecha2, fuente_usada)
        None: Si no se puede determinar ninguna fecha válida común
        
    Examples:
        >>> from types import SimpleNamespace
        >>> dt1 = datetime(2023, 1, 1, 12, 0, 0)
        >>> dt2 = datetime(2023, 1, 2, 12, 0, 0)
        >>> f1 = SimpleNamespace(path='f1', exif_date_time_original=dt1)
        >>> f2 = SimpleNamespace(path='f2', exif_date_time_original=dt2)
        >>> select_best_date_from_common_date_to_2_files(f1, f2)
        (datetime.datetime(2023, 1, 1, 12, 0), datetime.datetime(2023, 1, 2, 12, 0), 'exif_date_time_original')
    """
    from datetime import timedelta
    
    # Validar que los objetos tienen los atributos necesarios
    # Se usa getattr para seguridad si los objetos no cumplen estrictamente el protocolo
    
    def _get_val(obj, *attrs):
        for attr in attrs:
            val = getattr(obj, attr, None)
            if val is not None:
                if verbose: _logger.debug(f"      - Found {attr} on {getattr(obj, 'path', 'file')}: {val}")
                return val
        return None

    def _to_dt(val):
        if val is None: return None
        if isinstance(val, datetime): return val
        if isinstance(val, (int, float)): return datetime.fromtimestamp(val)
        # Parse EXIF string format usando helper global
        if isinstance(val, str):
            return _parse_exif_date(val)
        return None
    
    def _normalize_to_utc(dt: datetime, offset_str: Optional[str], has_peer_offset: bool = False) -> datetime:
        """
        Normaliza un datetime a UTC usando el offset de timezone si está disponible.
        
        - Si offset_str tiene un valor (ej: '+02:00'), resta el offset para obtener UTC
        - Si offset_str es None Y has_peer_offset es False: retorna sin cambios (hora local)
        - Si offset_str es None Y has_peer_offset es True: retorna sin cambios (no podemos asumir UTC)
        
        Args:
            dt: datetime a normalizar
            offset_str: string de offset de timezone (ej: '+02:00', '-05:00')
            has_peer_offset: si el archivo par tiene offset (para decisión de normalización)
            
        Returns:
            datetime normalizado a UTC si tiene offset, o sin cambios si no
        """
        offset_seconds = _parse_timezone_offset(offset_str)
        if offset_seconds is not None and offset_seconds != 0:
            # Restar el offset para obtener UTC
            # Si es +02:00, la hora local es 2 horas adelante de UTC
            return dt - timedelta(seconds=offset_seconds)
        return dt

    def _fmt(dt):
        return dt.strftime('%Y-%m-%d %H:%M:%S.%f') if dt else 'None'

    # Nota: _is_epoch_zero_date está definido a nivel de módulo

    if verbose:
        _logger.debug(f"DEBUG: Comparing dates for {getattr(file1, 'path', 'f1')} and {getattr(file2, 'path', 'f2')}")

    # ---------------------------------------------------------
    # 1. PRIORIDAD: AMBOS TIENEN EXIF VÁLIDOS
    # ---------------------------------------------------------
    
    # Obtener offsets de timezone para normalización
    file1_offset = _get_val(file1, 'exif_offset_time_original', 'exif_OffsetTimeOriginal')
    file2_offset = _get_val(file2, 'exif_offset_time_original', 'exif_OffsetTimeOriginal')
    
    # Priority 1: EXIF DateTimeOriginal
    file1_datetime_original = _to_dt(_get_val(file1, 'exif_date_time_original', 'exif_DateTimeOriginal'))
    file2_datetime_original = _to_dt(_get_val(file2, 'exif_date_time_original', 'exif_DateTimeOriginal'))
    
    if verbose: _logger.debug(f"    - EXIF DateTimeOriginal: file1={_fmt(file1_datetime_original)}, file2={_fmt(file2_datetime_original)}")
    if file1_datetime_original is not None and file2_datetime_original is not None and not _is_epoch_zero_date(file1_datetime_original) and not _is_epoch_zero_date(file2_datetime_original):
        # CORRECCIÓN DE BUG DE TIMEZONE:
        # Solo normalizar a UTC si AMBOS archivos tienen offset de timezone.
        # Si alguno no tiene offset, NO normalizar (asumir ambos en hora local).
        # Esto evita comparar incorrectamente hora local vs UTC.
        both_have_offset = (file1_offset is not None and file2_offset is not None)
        
        if both_have_offset:
            # Caso normal: ambos tienen offset, normalizar a UTC
            file1_utc = _normalize_to_utc(file1_datetime_original, file1_offset)
            file2_utc = _normalize_to_utc(file2_datetime_original, file2_offset)
            
            if verbose:
                _logger.debug(f"    - Normalized to UTC: file1={_fmt(file1_utc)} (offset={file1_offset}), file2={_fmt(file2_utc)} (offset={file2_offset})")
                _logger.debug("    => Match found: exif_date_time_original")
            _logger.debug(f"Source selected: exif_date_time_original for {getattr(file1, 'path', 'f1')} and {getattr(file2, 'path', 'f2')}")
            return file1_utc, file2_utc, 'exif_date_time_original'
        else:
            # Caso de archivos sin offset o mixto: usar hora local directamente
            # Esto corrige el bug donde videos sin offset eran tratados como UTC
            if verbose:
                _logger.debug(f"    - Using local time (no normalization): file1={_fmt(file1_datetime_original)} (offset={file1_offset}), file2={_fmt(file2_datetime_original)} (offset={file2_offset})")
                _logger.debug("    => Match found: exif_date_time_original (local time)")
            _logger.debug(f"Source selected: exif_date_time_original (local) for {getattr(file1, 'path', 'f1')} and {getattr(file2, 'path', 'f2')}")
            return file1_datetime_original, file2_datetime_original, 'exif_date_time_original'
        
    # Priority 2: EXIF CreateDate
    file1_create_date = _to_dt(_get_val(file1, 'exif_create_date', 'exif_CreateDate', 'exif_DateTimeDigitized'))
    file2_create_date = _to_dt(_get_val(file2, 'exif_create_date', 'exif_CreateDate', 'exif_DateTimeDigitized'))
    
    if verbose: _logger.debug(f"    - EXIF CreateDate: file1={_fmt(file1_create_date)}, file2={_fmt(file2_create_date)}")
    if file1_create_date is not None and file2_create_date is not None and not _is_epoch_zero_date(file1_create_date) and not _is_epoch_zero_date(file2_create_date):
        if verbose: _logger.debug("    => Match found: exif_create_date")
        _logger.debug(f"Source selected: exif_create_date for {getattr(file1, 'path', 'f1')} and {getattr(file2, 'path', 'f2')}")
        return file1_create_date, file2_create_date, 'exif_create_date'
        
    # Priority 3: EXIF ModifyDate
    file1_modify_date = _to_dt(_get_val(file1, 'exif_modify_date', 'exif_DateTime'))
    file2_modify_date = _to_dt(_get_val(file2, 'exif_modify_date', 'exif_DateTime'))
    
    if verbose: _logger.debug(f"    - EXIF ModifyDate: file1={_fmt(file1_modify_date)}, file2={_fmt(file2_modify_date)}")
    if file1_modify_date is not None and file2_modify_date is not None and not _is_epoch_zero_date(file1_modify_date) and not _is_epoch_zero_date(file2_modify_date):
        if verbose: _logger.debug("    => Match found: exif_modify_date")
        _logger.debug(f"Source selected: exif_modify_date for {getattr(file1, 'path', 'f1')} and {getattr(file2, 'path', 'f2')}")
        return file1_modify_date, file2_modify_date, 'exif_modify_date'

    # -------------------------------------------------------------------------
    # 2. FILESYSTEM FALLBACK (Solo uno o ninguno tiene EXIF)
    # -------------------------------------------------------------------------
    # Buscamos la fecha más antigua común entre mtime, ctime y atime.
    # Priorizar la fecha más antigua ayuda a encontrar la fecha original incluso
    # si el archivo fue copiado (reseteando ctime) o modificado (reseteando mtime).
    
    # Fuentes a evaluar en orden de relevancia lógica (mtime suele ser la más real)
    filesystem_sources = [
        ('mtime', 'fs_mtime'),
        ('ctime', 'fs_ctime'),
        ('atime', 'fs_atime')
    ]
    
    common_candidates = []
    
    # Solo consideramos fuentes que ESTÉN PRESENTES EN AMBOS archivos
    for attr_name, source_label in filesystem_sources:
        date_f1 = _to_dt(_get_val(file1, attr_name, f'fs_{attr_name}'))
        date_f2 = _to_dt(_get_val(file2, attr_name, f'fs_{attr_name}'))
        
        if date_f1 and date_f2:
            common_candidates.append({
                'date1': date_f1,
                'date2': date_f2,
                'source': source_label
            })
            
    if common_candidates:
        # Seleccionamos la combinación que contenga la fecha absoluta más antigua
        # Para evitar sesgos, comparamos el mínimo de ambas fechas en cada candidato
        best_match = min(common_candidates, key=lambda candidate: min(candidate['date1'], candidate['date2']))
        
        result_date1 = best_match['date1']
        result_date2 = best_match['date2']
        selected_source = best_match['source']
        
        # Log de advertencia si la fuente elegida no es la de modificación (mtime)
        if selected_source != 'fs_mtime':
            # Extraer todos los valores para un log informativo completo
            file1_stats = {source: _fmt(_to_dt(_get_val(file1, source, f'fs_{source}'))) for source, _ in filesystem_sources}
            file2_stats = {source: _fmt(_to_dt(_get_val(file2, source, f'fs_{source}'))) for source, _ in filesystem_sources}
            
            _logger.warning(
                f"ANOMALÍA DE FECHAS: Se ha seleccionado '{selected_source}' por ser la fuente común más antigua "
                f"entre {getattr(file1, 'path', 'f1')} y {getattr(file2, 'path', 'f2')}.\n"
                f"File 1: mtime={file1_stats['mtime']}, ctime={file1_stats['ctime']}, atime={file1_stats['atime']}\n"
                f"File 2: mtime={file2_stats['mtime']}, ctime={file2_stats['ctime']}, atime={file2_stats['atime']}"
            )
        elif verbose:
            _logger.debug(f"    => Match found: {selected_source} (Earliest common FS date)")
            
        return result_date1, result_date2, selected_source

    # -------------------------------------------------------------------------
    # 3. FALLBACK FINAL
    # -------------------------------------------------------------------------
    if verbose: _logger.debug("    !! NO COMMON DATE SOURCE FOUND !!")
    return None


def select_best_date_from_file(file_metadata: 'FileMetadata') -> tuple[Optional[datetime], Optional[str]]:
    """
    Selecciona la fecha más representativa de un archivo según lógica de priorización avanzada.
    
    LÓGICA DE PRIORIZACIÓN:
    
    PASO 1 - PRIORIDAD MÁXIMA (Fechas EXIF de cámara):
    1. DateTimeOriginal con OffsetTimeOriginal (la más precisa)
    2. DateTimeOriginal sin OffsetTimeOriginal
    3. CreateDate (DateTime en FileMetadata)
    4. DateTimeDigitized
    
    Regla: Se comparan TODAS estas fechas EXIF y se devuelve la MÁS ANTIGUA.
    Si existe al menos una de estas fechas, NO se continúa a los siguientes pasos.
    
    PASO 2 - PRIORIDAD SECUNDARIA (Fechas alternativas):
    5. Fecha extraída del nombre de archivo
       - Útil para WhatsApp y otros archivos sin EXIF
       - Patrones: IMG-YYYYMMDD-WA, Screenshot_YYYYMMDD_HHMMSS, etc.
    
    6. Video metadata (para archivos de video usa exif_DateTime)
    
    PASO 3 - VALIDACIÓN GPS (NO se usa como fecha principal):
    - GPS DateStamp se valida contra DateTimeOriginal
    - Si difiere más de 24 horas, se registra warning
    - GPS está en UTC y puede estar redondeado, por lo que NO es confiable
    
    PASO 4 - ÚLTIMO RECURSO (Fechas de sistema):
    7. fs_ctime y fs_mtime del sistema de archivos
       - Se comparan ambas y se devuelve la más antigua
       - Menos confiables por cambiar al copiar/mover
    
    Args:
        metadata: FileMetadata con todos los metadatos del archivo

    Returns:
        Tupla (fecha_seleccionada, fuente_seleccionada)
        - fecha_seleccionada: datetime de la fecha según la prioridad
        - fuente_seleccionada: string descriptivo de la fuente
        - Devuelve (None, None) si no hay fechas disponibles
    
    Examples:
        >>> from services.file_metadata import FileMetadata
        >>> file_metadata = FileMetadata(
        ...     path=Path('/test.jpg'),
        ...     fs_size=1000, fs_ctime=1609459200.0, fs_mtime=1609459200.0, fs_atime=1609459200.0,
        ...     exif_DateTimeOriginal='2021:08:04 18:49:23',
        ...     exif_OffsetTimeOriginal='+02:00'
        ... )
        >>> select_best_date_from_file(file_metadata)
        (datetime(2021, 8, 4, 18, 49, 23), 'EXIF DateTimeOriginal (+02:00)')
    """
    import platform
    from services.file_metadata import FileMetadata
    
    # Nota: _parse_exif_date, _is_epoch_zero_date y _parse_gps_datetime 
    # están definidos a nivel de módulo
    
    # Extraer fechas de FileMetadata
    exif_date_time_original = _parse_exif_date(file_metadata.exif_DateTimeOriginal)
    exif_create_date = _parse_exif_date(file_metadata.exif_DateTime)  # CreateDate mapea a DateTime
    exif_date_digitized = _parse_exif_date(file_metadata.exif_DateTimeDigitized)
    
    # GPS Date: Combinar GPSDateStamp y GPSTimeStamp usando helper global
    exif_gps_date = _parse_gps_datetime(
        file_metadata.exif_GPSDateStamp, 
        file_metadata.exif_GPSTimeStamp
    )
    
    exif_offset_time = file_metadata.exif_OffsetTimeOriginal
    
    # Fechas del filesystem
    fs_ctime = datetime.fromtimestamp(file_metadata.fs_ctime) if file_metadata.fs_ctime else None
    fs_mtime = datetime.fromtimestamp(file_metadata.fs_mtime) if file_metadata.fs_mtime else None
    
    # Fecha del nombre de archivo
    filename_date = extract_date_from_filename(file_metadata.path.name)
    
    # Video metadata (para videos usamos exif_DateTime)
    video_metadata_date = exif_create_date if file_metadata.is_video else None
    
    # Determinar fuente de creation (birth vs ctime)
    filesystem_creation_source = 'birth' if platform.system() == 'Darwin' else 'ctime'
    
    # Validar coherencia de fechas directamente con FileMetadata
    validation = _validate_date_coherence(file_metadata)
    
    # Loguear warnings si existen
    if validation.warnings:
        _logger.debug(f"Coherence warnings for {file_metadata.path}: {', '.join(validation.warnings)} (confidence: {validation.confidence})")
    
    # ============================================================================
    # PASO 1: PRIORIDAD MÁXIMA - Fechas EXIF de cámara (primera válida en orden)
    # ============================================================================
    # IMPORTANTE: Se devuelve la PRIMERA fecha válida según orden de prioridad,
    # NO la más antigua. Esto evita que fechas corruptas (ej: DateTimeDigitized=2002)
    # tengan precedencia sobre DateTimeOriginal correcta.
    
    # Priority 1: DateTimeOriginal con zona horaria (la más precisa)
    if exif_date_time_original and not _is_epoch_zero_date(exif_date_time_original) and exif_offset_time:
        selected_date = exif_date_time_original
        source = f"EXIF DateTimeOriginal ({exif_offset_time})"
        _validate_gps_coherence(file_metadata, selected_date)
        return selected_date, source
    
    # Priority 2: DateTimeOriginal sin zona horaria
    if exif_date_time_original and not _is_epoch_zero_date(exif_date_time_original):
        selected_date = exif_date_time_original
        source = 'EXIF DateTimeOriginal'
        _validate_gps_coherence(file_metadata, selected_date)
        return selected_date, source
    
    # Priority 3: CreateDate
    if exif_create_date and not _is_epoch_zero_date(exif_create_date):
        selected_date = exif_create_date
        source = 'EXIF CreateDate'
        _validate_gps_coherence(file_metadata, selected_date)
        return selected_date, source
    
    # Priority 4: DateTimeDigitized (último recurso EXIF)
    if exif_date_digitized and not _is_epoch_zero_date(exif_date_digitized):
        selected_date = exif_date_digitized
        source = 'EXIF DateTimeDigitized'
        _validate_gps_coherence(file_metadata, selected_date)
        return selected_date, source
    
    # ============================================================================
    # PASO 2: PRIORIDAD SECUNDARIA - Fechas alternativas
    # ============================================================================
    
    # Fecha del nombre de archivo con validación de precisión
    # Si filename_date tiene el mismo año-mes-día que mtime pero con hora 00:00:00,
    # es mejor usar mtime (más precisa) ya que el nombre probablemente no incluía hora
    if filename_date:
        # Verificar si filename_date tiene hora 00:00:00 (sin información horaria)
        if filename_date.hour == 0 and filename_date.minute == 0 and filename_date.second == 0:
            # Comparar con mtime si está disponible
            if fs_mtime:
                # Si tienen el mismo año-mes-día, preferir mtime (más precisa)
                if (filename_date.year == fs_mtime.year and 
                    filename_date.month == fs_mtime.month and 
                    filename_date.day == fs_mtime.day):
                    return fs_mtime, 'mtime (more precise than filename)'
        
        # En cualquier otro caso, usar filename_date
        return filename_date, 'Filename'
    
    # Video metadata
    if video_metadata_date:
        return video_metadata_date, 'Video Metadata'
    
    # ============================================================================
    # PASO 3: GPS DateStamp - Solo para validación (ya ejecutado en PASO 1)
    # ============================================================================
    # La validación GPS se ejecuta en el PASO 1 si hay fechas EXIF disponibles
    # GPS no se usa como fecha principal debido a problemas de redondeo y UTC
    
    # ============================================================================
    # PASO 4: ÚLTIMO RECURSO - Fechas del sistema de archivos
    # ============================================================================
    fs_dates = []
    
    if fs_ctime:
        fs_dates.append((fs_ctime, filesystem_creation_source))
    
    if fs_mtime:
        fs_dates.append((fs_mtime, 'mtime'))
    
    if fs_dates:
        earliest_fs = min(fs_dates, key=lambda x: x[0])
        return earliest_fs[0], earliest_fs[1]
    
    # No hay fechas disponibles
    return None, None


def get_all_metadata_from_file(file_path: Path, force_search: bool = False) -> 'FileMetadata':
    """
    Obtiene toda la información de metadatos disponible para un archivo.
    
    Usa el caché de FileInfoRepositoryCache primero. Si no está disponible,
    intenta obtener directamente según configuración o si force_search=True.
    
    Args:
        file_path: Ruta al archivo a analizar
        force_search: Si True, fuerza la búsqueda de todos los metadatos (hash, EXIF)
                     ignorando la configuración de la aplicación. Por defecto False.
    
    Returns:
        FileMetadata: Objeto con metadatos completos del archivo.
                     Los campos opcionales (sha256, exif_*) serán None si no están disponibles.
    
    Note:
        - Metadatos básicos del filesystem (fs_size, fs_mtime, fs_ctime, fs_atime) siempre están disponibles
        - Hash SHA256 solo si está habilitado en settings, force_search=True, o está en caché
        - EXIF de imágenes solo si está habilitado en settings, force_search=True, o está en caché
        - EXIF de videos solo si está habilitado en settings, force_search=True, o está en caché
        - force_search=True es útil para análisis bajo demanda en diálogos que requieren datos completos
    """
    from services.file_metadata import FileMetadata
    from config import Config
    from utils.file_utils import get_exif_from_image, get_exif_from_video, is_image_file, is_video_file, get_file_stat_info
    from services.file_metadata_repository_cache import FileInfoRepositoryCache
    from utils.settings_manager import settings_manager
    
    try:
        repo = FileInfoRepositoryCache.get_instance()
        
        # 1. Intentar obtener metadata completo del caché primero (solo si NO es force_search)
        if not force_search:
            cached_metadata = repo.get_file_metadata(file_path)
            if cached_metadata:
                _logger.debug(f"Complete metadata obtained from cache for {file_path.name}")
                return cached_metadata
        else:
            _logger.debug(f"force_search=True: ignoring cache, extracting metadata directly for {file_path.name}")
        
        # 2. Si no está en caché completo, construir metadatos paso a paso
        # usando métodos dedicados del caché cuando sea posible
        
        # 2a. Metadatos del filesystem - intentar del caché primero
        fs_metadata = repo.get_filesystem_metadata(file_path)
        if fs_metadata:
            _logger.debug(f"Filesystem metadata obtained from cache for {file_path.name}")
            metadata = FileMetadata(
                path=file_path.resolve(),
                fs_size=fs_metadata['fs_size'],
                fs_ctime=fs_metadata['fs_ctime'],
                fs_mtime=fs_metadata['fs_mtime'],
                fs_atime=fs_metadata['fs_atime']
            )
        else:
            # Si no está en caché, obtener directamente del filesystem (siempre disponible)
            stat_info = get_file_stat_info(file_path, resolve_path=False)
            metadata = FileMetadata(
                path=file_path.resolve(),
                fs_size=stat_info['size'],
                fs_ctime=stat_info['ctime'],
                fs_mtime=stat_info['mtime'],
                fs_atime=stat_info['atime']
            )
            _logger.debug(f"Filesystem metadata obtained directly for {file_path.name}")
        
        # 2b. Hash SHA256 - intentar del caché primero
        cached_hash = repo.get_hash(file_path)
        if cached_hash:
            metadata.sha256 = cached_hash
            _logger.debug(f"Hash obtained from cache for {file_path.name}: {cached_hash[:8]}...")
        elif force_search or settings_manager.get_precalculate_hashes():
            # Si force_search=True o está habilitado en settings, calcular directamente
            try:
                from utils.file_utils import calculate_file_hash
                metadata.sha256 = calculate_file_hash(file_path)
                _logger.debug(f"Hash calculated directly for {file_path.name}: {metadata.sha256[:8]}...")
            except Exception as e:
                _logger.debug(f"Could not calculate hash for {file_path.name}: {e}")
        
        # 2c. EXIF - Con force_search, extraer directamente; sin force_search, intentar caché primero
        if force_search:
            # FORCE SEARCH: Extraer directamente ignorando caché
            # 2c.1. EXIF de imágenes
            if is_image_file(file_path):
                try:
                    exif_data = get_exif_from_image(file_path)
                    if exif_data:
                        # Mapear los campos EXIF al formato de FileMetadata
                        # get_exif_from_image devuelve datetime objects para fechas, necesitamos convertirlos a strings
                        def datetime_to_str(dt):
                            """Convierte datetime a string ISO format"""
                            if dt is None:
                                return None
                            if isinstance(dt, datetime):
                                return dt.isoformat()
                            return str(dt)
                        
                        metadata.exif_DateTimeOriginal = datetime_to_str(exif_data.get('DateTimeOriginal'))
                        metadata.exif_DateTime = datetime_to_str(exif_data.get('CreateDate') or exif_data.get('DateTime'))
                        metadata.exif_DateTimeDigitized = datetime_to_str(exif_data.get('DateTimeDigitized'))
                        # GPS Date/Time son strings, no datetime
                        metadata.exif_GPSDateStamp = exif_data.get('GPSDateStamp')
                        metadata.exif_GPSTimeStamp = exif_data.get('GPSTimeStamp')
                        metadata.exif_SubSecTimeOriginal = exif_data.get('SubSecTimeOriginal')
                        metadata.exif_OffsetTimeOriginal = exif_data.get('OffsetTimeOriginal')
                        metadata.exif_Software = exif_data.get('Software')
                        metadata.exif_ExifVersion = exif_data.get('ExifVersion')
                        _logger.debug(f"Image EXIF extracted directly (force_search) for {file_path.name}")
                except Exception as e:
                    _logger.debug(f"Could not extract image EXIF for {file_path.name}: {e}")
            
            # 2c.2. EXIF de videos
            elif is_video_file(file_path):
                try:
                    video_metadata = get_exif_from_video(file_path)
                    if video_metadata:
                        # Mapear fecha de creación
                        if 'creation_time' in video_metadata and video_metadata['creation_time']:
                            creation_time = video_metadata['creation_time']
                            if isinstance(creation_time, datetime):
                                # IMPORTANTE: Usar formato EXIF string 'YYYY:MM:DD HH:MM:SS' no ISO
                                exif_date_str = creation_time.strftime('%Y:%m:%d %H:%M:%S')
                                metadata.exif_DateTimeOriginal = exif_date_str
                                metadata.exif_DateTime = exif_date_str
                                _logger.debug(f"Video EXIF date mapped: DateTimeOriginal={exif_date_str}, DateTime={exif_date_str}")
                        
                        # Mapear dimensiones
                        if 'width' in video_metadata and video_metadata['width']:
                            metadata.exif_ImageWidth = video_metadata['width']
                        if 'height' in video_metadata and video_metadata['height']:
                            metadata.exif_ImageLength = video_metadata['height']
                        
                        # Mapear duración en segundos
                        if 'duration_seconds' in video_metadata and video_metadata['duration_seconds']:
                            metadata.exif_VideoDurationSeconds = video_metadata['duration_seconds']
                        
                        # Mapear encoder (Software)
                        if 'encoder' in video_metadata and video_metadata['encoder']:
                            metadata.exif_Software = video_metadata['encoder']
                        
                        _logger.debug(f"Video EXIF extracted directly (force_search) for {file_path.name}: {len(video_metadata)} fields")
                        _logger.debug(f"Metadata state after mapping: has_exif={metadata.has_exif}, DateTimeOriginal={metadata.exif_DateTimeOriginal}, DateTime={metadata.exif_DateTime}")
                except Exception as e:
                    _logger.debug(f"Could not extract video EXIF for {file_path.name}: {e}")
        else:
            # SIN FORCE SEARCH: Intentar del caché primero
            cached_exif = repo.get_exif(file_path)
            if cached_exif:
                # Mapear EXIF del caché al formato FileMetadata
                def datetime_to_str(dt):
                    """Convierte datetime a string ISO format"""
                    if dt is None:
                        return None
                    if isinstance(dt, datetime):
                        return dt.isoformat()
                    return str(dt)
                
                metadata.exif_DateTimeOriginal = datetime_to_str(cached_exif.get('DateTimeOriginal'))
                metadata.exif_DateTime = datetime_to_str(cached_exif.get('DateTime'))
                metadata.exif_DateTimeDigitized = datetime_to_str(cached_exif.get('DateTimeDigitized'))
                # GPS Date/Time son strings en caché
                metadata.exif_GPSDateStamp = cached_exif.get('GPSDateStamp')
                metadata.exif_GPSTimeStamp = cached_exif.get('GPSTimeStamp')
                _logger.debug(f"EXIF obtained from cache for {file_path.name}: {len(cached_exif)} fields")
            else:
                # Si no está en caché, extraer según tipo y configuración
                
                # 2c.1. EXIF de imágenes (si está habilitado)
                if is_image_file(file_path) and settings_manager.get_precalculate_image_exif():
                    try:
                        exif_data = get_exif_from_image(file_path)
                        if exif_data:
                            # Mapear los campos EXIF al formato de FileMetadata
                            # get_exif_from_image devuelve datetime objects, necesitamos convertirlos a strings
                            def datetime_to_str(dt):
                                """Convierte datetime a string ISO format"""
                                if dt is None:
                                    return None
                                if isinstance(dt, datetime):
                                    return dt.isoformat()
                                return str(dt)
                            
                            metadata.exif_DateTimeOriginal = datetime_to_str(exif_data.get('DateTimeOriginal'))
                            metadata.exif_DateTime = datetime_to_str(exif_data.get('CreateDate') or exif_data.get('DateTime'))
                            metadata.exif_DateTimeDigitized = datetime_to_str(exif_data.get('DateTimeDigitized'))
                            # GPS Date/Time son strings, no datetime
                            metadata.exif_GPSDateStamp = exif_data.get('GPSDateStamp')
                            metadata.exif_GPSTimeStamp = exif_data.get('GPSTimeStamp')
                            _logger.debug(f"Image EXIF extracted directly for {file_path.name}")
                    except Exception as e:
                        _logger.debug(f"Could not extract image EXIF for {file_path.name}: {e}")
                
                # 2c.2. EXIF de videos (si está habilitado)
                elif is_video_file(file_path) and settings_manager.get_precalculate_video_exif():
                    try:
                        video_metadata = get_exif_from_video(file_path)
                        if video_metadata:
                            # Mapear fecha de creación
                            if 'creation_time' in video_metadata and video_metadata['creation_time']:
                                creation_time = video_metadata['creation_time']
                                if isinstance(creation_time, datetime):
                                    # IMPORTANTE: Usar formato EXIF string 'YYYY:MM:DD HH:MM:SS' no ISO
                                    exif_date_str = creation_time.strftime('%Y:%m:%d %H:%M:%S')
                                    metadata.exif_DateTimeOriginal = exif_date_str
                                    metadata.exif_DateTime = exif_date_str
                            
                            # Mapear dimensiones
                            if 'width' in video_metadata and video_metadata['width']:
                                metadata.exif_ImageWidth = video_metadata['width']
                            if 'height' in video_metadata and video_metadata['height']:
                                metadata.exif_ImageLength = video_metadata['height']
                            
                            # Mapear duración en segundos
                            if 'duration_seconds' in video_metadata and video_metadata['duration_seconds']:
                                metadata.exif_VideoDurationSeconds = video_metadata['duration_seconds']
                            
                            # Mapear encoder (Software)
                            if 'encoder' in video_metadata and video_metadata['encoder']:
                                metadata.exif_Software = video_metadata['encoder']
                            
                            _logger.debug(f"Video EXIF extracted directly for {file_path.name}: {len(video_metadata)} fields")
                    except Exception as e:
                        _logger.debug(f"Could not extract video EXIF for {file_path.name}: {e}")
        
        return metadata
        
    except Exception as e:
        _logger.error(f"Error getting metadata for {file_path}: {e}")
        # Retornar metadatos mínimos en caso de error
        try:
            stat = file_path.stat()
            return FileMetadata(
                path=file_path.resolve(),
                fs_size=stat.st_size,
                fs_ctime=stat.st_ctime,
                fs_mtime=stat.st_mtime,
                fs_atime=stat.st_atime
            )
        except:
            # Si incluso stat() falla, crear un objeto con valores por defecto
            return FileMetadata(
                path=file_path.resolve(),
                fs_size=0,
                fs_ctime=0.0,
                fs_mtime=0.0,
                fs_atime=0.0
            )


def format_renamed_name(date: datetime, file_type: str, extension: str, sequence: Optional[int] = None) -> str:
    """
    Genera nombre de archivo renombrado en formato estandarizado
    
    Args:
        date: Fecha a usar en el nombre
        file_type: Tipo de archivo ('PHOTO', 'VIDEO', etc.)
        extension: Extensión del archivo (incluyendo punto)
        sequence: Número de secuencia opcional para evitar conflictos
        
    Returns:
        Nombre de archivo formateado: YYYYMMDD_HHMMSS_TYPE[_SEQ].EXT
        
    Examples:
        >>> from datetime import datetime
        >>> format_renamed_name(datetime(2023, 1, 15, 10, 30, 45), 'PHOTO', '.jpg')
        '20230115_103045_PHOTO.JPG'
        
        >>> format_renamed_name(datetime(2023, 1, 15, 10, 30, 45), 'VIDEO', '.mov', sequence=5)
        '20230115_103045_VIDEO_005.MOV'
    """
    base_name = date.strftime('%Y%m%d_%H%M%S')
    type_part = f"_{file_type}"
    
    if sequence is not None and sequence > 0:
        sequence_part = f"_{sequence:03d}"
    else:
        sequence_part = ""
    
    extension_part = extension.upper()
    
    return f"{base_name}{type_part}{sequence_part}{extension_part}"


def is_renamed_filename(filename: str) -> bool:
    """
    Verifica si un nombre de archivo sigue el patrón de nombres renombrados
    
    Args:
        filename: Nombre del archivo a verificar
        
    Returns:
        True si el nombre sigue el patrón YYYYMMDD_HHMMSS_TYPE[_SEQ].EXT
        
    Examples:
        >>> is_renamed_filename('20230115_103045_PHOTO.JPG')
        True
        
        >>> is_renamed_filename('20230115_103045_VIDEO_042.MOV')
        True
        
        >>> is_renamed_filename('IMG_1234.JPG')
        False
        
        >>> is_renamed_filename('20230115_103045_VIDEO.MP4')
        True
    """
    import re
    
    # Patrón: YYYYMMDD_HHMMSS_TYPE[_SEQ].EXT
    # Nota: extensiones pueden incluir dígitos (ej: MP4, M4V, 3GP)
    pattern = r'^\d{8}_\d{6}_[A-Z]+(?:_\d{3})?\.[A-Z0-9]{2,4}$'
    return bool(re.match(pattern, filename))


def extract_date_from_filename(filename: str) -> Optional[datetime]:
    """
    Intenta extraer una fecha del nombre de archivo usando patrones comunes
    
    Args:
        filename: Nombre del archivo (sin path)
        
    Returns:
        datetime si se encuentra un patrón válido, None en caso contrario
        
    Patrones soportados:
        - IMG_YYYYMMDD_HHMMSS.ext
        - DSC_YYYYMMDD_HHMMSS.ext  
        - YYYYMMDD_HHMMSS.ext
        - YYYY-MM-DD_HH-MM-SS.ext
        - WhatsApp: IMG-YYYYMMDD-WAXXXX.ext
    """
    import re
    from pathlib import Path
    
    # Remover extensión
    name_without_ext = Path(filename).stem
    
    # Patrones de fecha comunes en nombres de archivo
    patterns = [
        # IMG_20231113_123456 o DSC_20231113_123456
        r'(?:IMG|DSC)_(\d{8})_(\d{6})',
        # 20231113_123456 (sin prefijo)
        r'^(\d{8})_(\d{6})',
        # YYYY-MM-DD_HH-MM-SS
        r'(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})',
        # WhatsApp: IMG-20231113-WA0001
        r'IMG-(\d{8})-WA\d+',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, name_without_ext)
        if match:
            groups = match.groups()
            
            try:
                if len(groups) == 2:  # YYYYMMDD_HHMMSS
                    date_str, time_str = groups
                    year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
                    hour, minute, second = int(time_str[:2]), int(time_str[2:4]), int(time_str[4:6])
                    
                elif len(groups) == 6:  # YYYY-MM-DD_HH-MM-SS
                    year, month, day, hour, minute, second = map(int, groups)
                    
                elif len(groups) == 1:  # WhatsApp IMG-YYYYMMDD
                    date_str = groups[0]
                    year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
                    hour = minute = second = 0  # WhatsApp no incluye hora
                    
                else:
                    continue
                    
                # Validar rangos básicos
                if not (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
                    continue
                    
                return datetime(year, month, day, hour, minute, second)
                
            except (ValueError, TypeError):
                continue
    
    return None



def _validate_gps_coherence(file_metadata: 'FileMetadata', selected_date: datetime) -> None:
    """
    Valida coherencia entre GPS DateStamp y DateTimeOriginal.
    
    GPS DateStamp puede diferir significativamente de DateTimeOriginal debido a:
    - GPS está siempre en UTC (sin zona horaria local)
    - Muchos dispositivos redondean GPS timestamp a horas completas
    - GPS puede estar ausente o incorrecto por problemas de señal
    
    Esta función registra warnings cuando la diferencia es mayor a 24 horas.
    
    Args:
        file_metadata: FileMetadata con los metadatos del archivo
        selected_date: Fecha seleccionada (normalmente DateTimeOriginal)
    """
    # Nota: _parse_gps_datetime está definido a nivel de módulo
    gps_date = _parse_gps_datetime(
        file_metadata.exif_GPSDateStamp,
        file_metadata.exif_GPSTimeStamp
    )
    
    if not gps_date:
        return
    
    # Calcular diferencia en segundos
    diff_seconds = abs((gps_date - selected_date).total_seconds())
    
    # GPS debe estar dentro de ±24 horas de DateTimeOriginal
    if diff_seconds > 86400:  # 24 horas en segundos
        diff_hours = diff_seconds / 3600
        _logger.warning(
            f"GPS DateStamp ({gps_date.strftime('%Y-%m-%d %H:%M:%S')}) difiere "
            f"significativamente de DateTimeOriginal ({selected_date.strftime('%Y-%m-%d %H:%M:%S')}). "
            f"Diferencia: {diff_hours:.1f} horas. "
            f"Posible problema de zona horaria o GPS incorrecto."
        )


def _validate_date_coherence(file_metadata: 'FileMetadata') -> DateCoherenceResult:
    """
    Valida coherencia entre fechas y detecta anomalías en metadatos.
    
    MÉTODO INTERNO usado exclusivamente por select_best_date_from_file().
    
    Esta función aplica varias reglas de validación para detectar metadatos corruptos,
    archivos editados, o transferencias recientes que pueden afectar la confiabilidad
    de las fechas.

    Args:
        metadata: FileMetadata con los metadatos del archivo

    Returns:
        Dict con resultado de validación:
        {
            'is_valid': bool,              # True si pasa todas las validaciones críticas
            'warnings': list[str],         # Lista de códigos de advertencia
            'confidence': str              # 'high', 'medium', 'low'
        }
        
    Códigos de advertencia:
        - 'EXIF_AFTER_MTIME': EXIF posterior a modification_date (sospechoso)
        - 'EXIF_DIVERGENCE': Más de 1 año entre campos EXIF (probable corrupción)
        - 'DIGITIZED_BEFORE_ORIGINAL': DateTimeDigitized anterior a DateTimeOriginal (imposible)
        - 'RECENT_TRANSFER': Más de 7 días entre creation_date y EXIF (transferencia)
        - 'SOFTWARE_DETECTED': Campo Software presente (archivo editado)
        - 'GPS_DIVERGENCE': GPS date muy diferente de EXIF (más de 1 día)
    """
    from datetime import timedelta
    
    # Nota: _parse_exif_date y _parse_gps_datetime están definidos a nivel de módulo
    
    warnings = []
    is_valid = True
    
    # Extraer fechas relevantes del FileMetadata
    exif_date_time_original = _parse_exif_date(file_metadata.exif_DateTimeOriginal)
    exif_create_date = _parse_exif_date(file_metadata.exif_DateTime)
    exif_date_digitized = _parse_exif_date(file_metadata.exif_DateTimeDigitized)
    
    # GPS Date: Combinar GPSDateStamp y GPSTimeStamp usando helper global
    exif_gps_date = _parse_gps_datetime(
        file_metadata.exif_GPSDateStamp,
        file_metadata.exif_GPSTimeStamp
    )
    
    exif_software = file_metadata.exif_Software
    fs_mtime_date = datetime.fromtimestamp(file_metadata.fs_mtime) if file_metadata.fs_mtime else None
    fs_ctime_date = datetime.fromtimestamp(file_metadata.fs_ctime) if file_metadata.fs_ctime else None
    
    # Validación 1: EXIF posterior a modification_date (sospechoso)
    if exif_date_time_original and fs_mtime_date:
        if exif_date_time_original > fs_mtime_date:
            warnings.append('EXIF_AFTER_MTIME')
            is_valid = False
    
    # Validación 2: Divergencia entre campos EXIF (más de 1 año)
    exif_dates = [d for d in [exif_date_time_original, exif_create_date, exif_date_digitized] if d is not None]
    if len(exif_dates) >= 2:
        min_exif = min(exif_dates)
        max_exif = max(exif_dates)
        if (max_exif - min_exif) > timedelta(days=365):
            warnings.append('EXIF_DIVERGENCE')
            is_valid = False
    
    # Validación 3: DateTimeDigitized anterior a DateTimeOriginal (imposible)
    if exif_date_time_original and exif_date_digitized:
        if exif_date_digitized < exif_date_time_original:
            warnings.append('DIGITIZED_BEFORE_ORIGINAL')
            is_valid = False
    
    # Validación 4: Transferencia reciente (creation_date muy diferente de EXIF)
    if exif_date_time_original and fs_ctime_date:
        diff = abs((fs_ctime_date - exif_date_time_original).days)
        if diff > 7:
            warnings.append('RECENT_TRANSFER')
            # No marca como inválido, solo advertencia
    
    # Validación 5: Software detectado (archivo editado)
    if exif_software:
        warnings.append('SOFTWARE_DETECTED')
        # No marca como inválido, solo informativo
    
    # Validación 6: GPS date muy diferente de EXIF
    if exif_gps_date and exif_date_time_original:
        diff = abs((exif_gps_date - exif_date_time_original).days)
        if diff > 1:
            warnings.append('GPS_DIVERGENCE')
            # No marca como inválido, puede ser zona horaria
    
    # Determinar nivel de confianza
    if not is_valid:
        confidence = 'low'
    elif len(warnings) >= 2:
        confidence = 'medium'
    elif len(warnings) == 1:
        confidence = 'medium'
    else:
        confidence = 'high'
    
    return DateCoherenceResult(
        is_valid=is_valid,
        warnings=tuple(warnings),
        confidence=confidence
    )
