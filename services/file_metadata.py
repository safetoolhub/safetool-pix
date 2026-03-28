# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
File Metadata Model

Dataclass que representa los metadatos completos de un archivo.
Separada en módulo propio para reutilización y claridad.

Preparada para serialización/deserialización desde/hacia base de datos.
"""
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class FileMetadata:
    """
    Metadatos completos de un archivo.
    
    Estructura de datos pura que contiene toda la información de un archivo:
    - Metadatos del filesystem (prefijo fs_)
    - Hash SHA256 (cálculo costoso, lazy loaded)
    - Metadatos EXIF (prefijo exif_)
    
    Esta clase es agnóstica de la fuente de datos (memoria, SQLite, MySQL, etc.)
    y puede ser serializada/deserializada fácilmente.
    
    Attributes:
        path: Ruta absoluta del archivo
        fs_size: Tamaño en bytes
        fs_ctime: Creation time (timestamp)
        fs_mtime: Modification time (timestamp)
        fs_atime: Access time (timestamp)
        sha256: Hash SHA256 en hexadecimal (opcional, lazy loaded)
        exif_*: Campos EXIF específicos (opcionales)
    """
    # Identificador único
    path: Path
    
    # Metadatos del filesystem (siempre presentes)
    fs_size: int
    fs_ctime: float
    fs_mtime: float
    fs_atime: float
    
    # Hash SHA256 (opcional, cálculo costoso)
    sha256: Optional[str] = None
    
    # Best date available (fecha más representativa calculada)
    # Calculada en Phase 5 del InitialScanner usando select_best_date_from_file()
    best_date: Optional[datetime] = None
    best_date_source: Optional[str] = None  # Fuente de la fecha (ej: 'EXIF DateTimeOriginal', 'mtime')
    
    # Metadatos EXIF (opcionales)
    exif_ImageWidth: Optional[int] = None
    exif_ImageLength: Optional[int] = None
    exif_DateTime: Optional[str] = None
    exif_GPSTimeStamp: Optional[str] = None
    exif_GPSDateStamp: Optional[str] = None
    exif_DateTimeOriginal: Optional[str] = None
    exif_DateTimeDigitized: Optional[str] = None
    exif_ExifVersion: Optional[str] = None
    exif_SubSecTimeOriginal: Optional[str] = None
    exif_OffsetTimeOriginal: Optional[str] = None
    exif_Software: Optional[str] = None
    exif_VideoDurationSeconds: Optional[float] = None
    
    @property
    def video_duration_formatted(self) -> Optional[str]:
        """
        Duración del video formateada como string con precisión adaptativa.
        
        Formato según duración:
        - < 10 segundos: "1.2 seg" (con decimales para precisión)
        - 10-59 segundos: "45 seg" (sin decimales)
        - >= 60 segundos: "1:23 min" (minutos:segundos)
        
        Generado dinámicamente desde exif_VideoDurationSeconds.
        
        Returns:
            String formateado o None si no hay duración disponible
        """
        if self.exif_VideoDurationSeconds is None:
            return None
        
        seconds = self.exif_VideoDurationSeconds
        
        if seconds < 10:
            # Duración muy corta: mostrar con 1 decimal para precisión
            return f"{seconds:.1f} seg"
        elif seconds < 60:
            # Menos de un minuto: mostrar segundos enteros
            return f"{int(seconds)} seg"
        else:
            # Un minuto o más: formato mm:ss
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}:{secs:02d} min"
    
    @property
    def extension(self) -> str:
        """Extensión del archivo en minúsculas"""
        return self.path.suffix.lower()
    
    @property
    def has_exif(self) -> bool:
        """Verifica si tiene algún campo EXIF poblado"""
        return any([
            self.exif_ImageWidth is not None,
            self.exif_ImageLength is not None,
            self.exif_DateTime is not None,
            self.exif_GPSTimeStamp is not None,
            self.exif_GPSDateStamp is not None,
            self.exif_DateTimeOriginal is not None,
            self.exif_DateTimeDigitized is not None,
            self.exif_ExifVersion is not None,
            self.exif_SubSecTimeOriginal is not None,
            self.exif_OffsetTimeOriginal is not None,
            self.exif_Software is not None,
            self.exif_VideoDurationSeconds is not None
        ])
    
    @property
    def has_hash(self) -> bool:
        """Verifica si tiene el hash calculado"""
        return self.sha256 is not None
    
    @property
    def has_best_date(self) -> bool:
        """Verifica si tiene la mejor fecha calculada"""
        return self.best_date is not None
    
    @property
    def is_image(self) -> bool:
        """Verifica si es un archivo de imagen"""
        from utils.file_utils import is_image_file
        return is_image_file(self.path)
    
    @property
    def is_video(self) -> bool:
        """Verifica si es un archivo de video"""
        from utils.file_utils import is_video_file
        return is_video_file(self.path)
    
    @property
    def file_type(self) -> str:
        """
        Obtiene el tipo de archivo.
        
        Returns:
            'PHOTO', 'VIDEO', u 'OTHER'
        """
        from utils.file_utils import get_file_type
        return get_file_type(self.path)
    
    def get_exif_dates(self) -> dict[str, str]:
        """
        Obtiene solo las fechas EXIF (filtradas).
        
        Returns:
            Dict con fechas EXIF presentes
        """
        dates = {}
        if self.exif_DateTime:
            dates['DateTime'] = self.exif_DateTime
        if self.exif_DateTimeOriginal:
            dates['DateTimeOriginal'] = self.exif_DateTimeOriginal
        if self.exif_DateTimeDigitized:
            dates['DateTimeDigitized'] = self.exif_DateTimeDigitized
        if self.exif_GPSDateStamp:
            dates['GPSDateStamp'] = self.exif_GPSDateStamp
        if self.exif_GPSTimeStamp:
            dates['GPSTimeStamp'] = self.exif_GPSTimeStamp
        return dates
    
    def to_dict(self) -> dict:
        """
        Convierte a diccionario para serialización.
        
        Útil para exportar a JSON, BBDD, etc.
        
        Returns:
            Dict con todos los campos, path convertido a str
        """
        return {
            'path': str(self.path),
            'fs_size': self.fs_size,
            'fs_ctime': self.fs_ctime,
            'fs_mtime': self.fs_mtime,
            'fs_atime': self.fs_atime,
            'sha256': self.sha256,
            'best_date': self.best_date.isoformat() if self.best_date else None,
            'best_date_source': self.best_date_source,
            'exif_ImageWidth': self.exif_ImageWidth,
            'exif_ImageLength': self.exif_ImageLength,
            'exif_DateTime': self.exif_DateTime,
            'exif_GPSTimeStamp': self.exif_GPSTimeStamp,
            'exif_GPSDateStamp': self.exif_GPSDateStamp,
            'exif_DateTimeOriginal': self.exif_DateTimeOriginal,
            'exif_DateTimeDigitized': self.exif_DateTimeDigitized,
            'exif_ExifVersion': self.exif_ExifVersion,
            'exif_SubSecTimeOriginal': self.exif_SubSecTimeOriginal,
            'exif_OffsetTimeOriginal': self.exif_OffsetTimeOriginal,
            'exif_Software': self.exif_Software,
            'exif_VideoDurationSeconds': self.exif_VideoDurationSeconds,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FileMetadata':
        """
        Crea instancia desde diccionario.
        
        Útil para deserialización desde JSON, BBDD, etc.
        
        Args:
            data: Diccionario con los campos
            
        Returns:
            FileMetadata: Instancia creada
        """
        # Parse best_date from ISO format string
        best_date_str = data.get('best_date')
        best_date = None
        if best_date_str:
            try:
                best_date = datetime.fromisoformat(best_date_str)
            except (ValueError, TypeError):
                pass
        
        return cls(
            path=Path(data['path']),
            fs_size=data['fs_size'],
            fs_ctime=data['fs_ctime'],
            fs_mtime=data['fs_mtime'],
            fs_atime=data['fs_atime'],
            sha256=data.get('sha256'),
            best_date=best_date,
            best_date_source=data.get('best_date_source'),
            exif_ImageWidth=data.get('exif_ImageWidth'),
            exif_ImageLength=data.get('exif_ImageLength'),
            exif_DateTime=data.get('exif_DateTime'),
            exif_GPSTimeStamp=data.get('exif_GPSTimeStamp'),
            exif_GPSDateStamp=data.get('exif_GPSDateStamp'),
            exif_DateTimeOriginal=data.get('exif_DateTimeOriginal'),
            exif_DateTimeDigitized=data.get('exif_DateTimeDigitized'),
            exif_ExifVersion=data.get('exif_ExifVersion'),
            exif_SubSecTimeOriginal=data.get('exif_SubSecTimeOriginal'),
            exif_OffsetTimeOriginal=data.get('exif_OffsetTimeOriginal'),
            exif_Software=data.get('exif_Software'),
            exif_VideoDurationSeconds=data.get('exif_VideoDurationSeconds'),
        )
    
    def get_summary(self, verbose: bool = False) -> str:
        """
        Genera resumen de metadatos para logging.
        
        Args:
            verbose: Si True, incluye todos los campos EXIF
            
        Returns:
            str: Línea de texto con información del archivo
        """
        try:
            hash_val = self.sha256[:8] + '...' if self.sha256 else 'pending'
            
            # Timestamps del filesystem
            ctime_str = datetime.fromtimestamp(self.fs_ctime).strftime('%Y-%m-%d %H:%M:%S')
            mtime_str = datetime.fromtimestamp(self.fs_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            # EXIF info
            if verbose:
                exif_items = []
                for field in ['ImageWidth', 'ImageLength', 'DateTime', 'GPSTimeStamp', 
                             'GPSDateStamp', 'DateTimeOriginal', 'DateTimeDigitized', 'ExifVersion']:
                    value = getattr(self, f'exif_{field}', None)
                    if value is not None:
                        exif_items.append(f"{field}={value}")
                exif_info = f"exif_fields={len(exif_items)}"
                if exif_items:
                    exif_info += f" [{', '.join(exif_items)}]"
            else:
                dates = self.get_exif_dates()
                if dates:
                    exif_info = f"exif_dates={len(dates)}"
                else:
                    exif_info = "exif=none"
            
            # Best date info
            if self.best_date:
                best_date_str = self.best_date.strftime('%Y-%m-%d %H:%M:%S')
                best_date_info = f"best_date={best_date_str} ({self.best_date_source or 'unknown'})"
            else:
                best_date_info = "best_date=pending"
            
            return (
                f"path={self.path.name} | "
                f"size={self.fs_size}b | "
                f"ext={self.extension} | "
                f"sha256={hash_val} | "
                f"{best_date_info} | "
                f"mtime={mtime_str} | "
                f"ctime={ctime_str} | "
                f"{exif_info}"
            )
        except Exception as e:
            # Fallback seguro si algo falla
            return f"path={self.path.name if hasattr(self.path, 'name') else str(self.path)} | error_generating_summary: {e}"
