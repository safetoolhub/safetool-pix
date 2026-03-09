# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Utilidad para generar thumbnails de videos.

Extrae fotogramas representativos de archivos de video usando OpenCV,
con caché LRU para mejorar performance.
"""

from pathlib import Path
from PyQt6.QtGui import QPixmap, QImage
from typing import Optional
from functools import lru_cache
from utils.logger import get_logger

logger = get_logger('VideoThumbnail')


@lru_cache(maxsize=128)
def _extract_video_frame_cached(video_path_str: str, max_w: int, max_h: int, frame_position: float = 0.25) -> Optional[bytes]:
    """
    Extrae y cachea un fotograma de un video.
    
    Args:
        video_path_str: Ruta del video como string (para ser hashable)
        max_w: Ancho máximo del thumbnail
        max_h: Alto máximo del thumbnail
        frame_position: Posición del frame a extraer (0.0-1.0, default 0.25 = 25% del video)
        
    Returns:
        Bytes del fotograma en formato PNG, o None si falla
    """
    try:
        import cv2
        from PIL import Image
        import io
        
        video_path = Path(video_path_str)
        
        # Abrir video
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            logger.debug(f"Could not open video: {video_path.name}")
            return None
        
        try:
            # Obtener información del video
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames <= 0:
                logger.debug(f"Video has no valid frames: {video_path.name}")
                return None
            
            # Calcular frame a extraer (evitar el primero que suele ser negro)
            target_frame = max(1, int(total_frames * frame_position))
            
            # Posicionarse en el frame deseado
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            
            # Leer frame
            ret, frame = cap.read()
            
            if not ret or frame is None:
                logger.debug(f"Could not read frame {target_frame} from {video_path.name}")
                return None
            
            # Convertir BGR (OpenCV) a RGB (PIL)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convertir a PIL Image
            pil_image = Image.fromarray(frame_rgb)
            
            # Redimensionar manteniendo aspect ratio
            pil_image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            
            # Guardar en buffer como PNG
            buffer = io.BytesIO()
            pil_image.save(buffer, format='PNG', optimize=True)
            
            logger.debug(f"Video thumbnail extracted: {video_path.name} (frame {target_frame}/{total_frames})")
            
            return buffer.getvalue()
            
        finally:
            cap.release()
        
    except ImportError:
        logger.warning("OpenCV (cv2) not available, cannot generate video thumbnails")
        return None
    except Exception as e:
        logger.debug(f"Error extracting frame from {video_path_str}: {e}")
        return None


def get_video_thumbnail(video_path: Path, max_size: tuple = (280, 280), frame_position: float = 0.25) -> Optional[QPixmap]:
    """
    Obtiene un thumbnail de un video como QPixmap.
    
    Args:
        video_path: Ruta al archivo de video
        max_size: Tupla (width, height) para el tamaño máximo
        frame_position: Posición del frame a extraer (0.0-1.0)
                       0.0 = primer frame, 0.25 = 25% del video, 0.5 = mitad, etc.
        
    Returns:
        QPixmap con el fotograma, o None si falla
        
    Examples:
        >>> # Extraer fotograma al 25% del video
        >>> pixmap = get_video_thumbnail(Path("video.mov"))
        >>> 
        >>> # Extraer fotograma a la mitad del video
        >>> pixmap = get_video_thumbnail(Path("video.mov"), frame_position=0.5)
    """
    try:
        png_bytes = _extract_video_frame_cached(
            str(video_path),
            max_size[0],
            max_size[1],
            frame_position
        )
        
        if png_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(png_bytes, 'PNG')
            return pixmap if not pixmap.isNull() else None
        
        return None
        
    except Exception as e:
        logger.debug(f"Error getting video thumbnail for {video_path.name}: {e}")
        return None


