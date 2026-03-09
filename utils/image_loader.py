# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Utilidad para cargar imágenes con soporte multiplataforma para HEIC/HEIF.

Este módulo proporciona funciones para cargar imágenes en QPixmap, con soporte
automático para formatos HEIC/HEIF usando pillow-heif cuando sea necesario.

Incluye caché LRU para thumbnails para mejorar performance.
"""

from pathlib import Path
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt
from typing import Optional
from functools import lru_cache
from utils.logger import get_logger

logger = get_logger('ImageLoader')

# Flag para registrar pillow-heif solo una vez
_heif_registered = False


def _ensure_heif_support():
    """
    Registra soporte HEIC/HEIF en Pillow (solo se ejecuta una vez).
    
    Esto permite que PIL.Image.open() pueda abrir archivos .heic y .heif.
    """
    global _heif_registered
    if not _heif_registered:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
            _heif_registered = True
            logger.debug("HEIC/HEIF support registered successfully")
        except ImportError:
            logger.warning("pillow-heif not available, HEIC files will not be supported")
        except Exception as e:
            logger.warning(f"Error registering HEIC support: {e}")


def _pil_to_qpixmap_fast(pil_image) -> QPixmap:
    """
    Conversión optimizada de PIL Image a QPixmap.
    
    Usa el formato más eficiente según el modo de la imagen.
    
    Args:
        pil_image: PIL Image object
        
    Returns:
        QPixmap convertido
    """
    # Convertir a RGB si no es RGB/RGBA (más eficiente)
    if pil_image.mode not in ('RGB', 'RGBA'):
        pil_image = pil_image.convert('RGB')
    
    # Conversión optimizada según modo
    if pil_image.mode == 'RGB':
        # Para RGB, usar Format_RGB888 (más rápido)
        data = pil_image.tobytes('raw', 'RGB')
        qimage = QImage(
            data,
            pil_image.width,
            pil_image.height,
            pil_image.width * 3,
            QImage.Format.Format_RGB888
        )
    else:  # RGBA
        # Para RGBA, usar Format_RGBA8888
        data = pil_image.tobytes('raw', 'RGBA')
        qimage = QImage(
            data,
            pil_image.width,
            pil_image.height,
            pil_image.width * 4,
            QImage.Format.Format_RGBA8888
        )
    
    # Copiar datos para evitar problemas de memoria
    qimage = qimage.copy()
    
    return QPixmap.fromImage(qimage)


@lru_cache(maxsize=256)
def _load_thumbnail_cached(file_path_str: str, max_w: int, max_h: int) -> Optional[bytes]:
    """
    Carga y cachea thumbnails de imágenes HEIC/other usando Pillow.
    
    Esta función está cacheada con LRU para evitar regenerar thumbnails.
    Los parámetros deben ser hashables (por eso file_path es str).
    
    Args:
        file_path_str: Ruta del archivo como string
        max_w: Ancho máximo del thumbnail
        max_h: Alto máximo del thumbnail
        
    Returns:
        Bytes del thumbnail en formato PNG, o None si falla
    """
    try:
        from PIL import Image
        import io
        
        _ensure_heif_support()
        
        file_path = Path(file_path_str)
        pil_image = Image.open(file_path)
        
        # Redimensionar manteniendo aspect ratio
        pil_image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        
        # Convertir a RGB si es necesario
        if pil_image.mode not in ('RGB', 'RGBA'):
            pil_image = pil_image.convert('RGB')
        
        # Guardar en buffer como PNG (compacto y rápido de decodificar)
        buffer = io.BytesIO()
        pil_image.save(buffer, format='PNG', optimize=True)
        
        return buffer.getvalue()
        
    except Exception as e:
        logger.debug(f"Error loading thumbnail for {file_path_str}: {e}")
        return None


def load_image_as_qpixmap(
    file_path: Path,
    max_size: Optional[tuple] = None
) -> Optional[QPixmap]:
    """
    Carga una imagen como QPixmap, con soporte para HEIC/HEIF y otros formatos.
    
    Intenta primero cargar con QPixmap nativo (JPG, PNG, etc.). Si falla,
    usa Pillow con soporte HEIC/HEIF para formatos especiales.
    
    OPTIMIZADO: Usa caché LRU para thumbnails de imágenes HEIC/especiales.
    
    Args:
        file_path: Ruta al archivo de imagen
        max_size: Tupla (width, height) para limitar tamaño. Si se especifica,
                 la imagen se redimensionará manteniendo la relación de aspecto.
                 None = sin límite de tamaño
        
    Returns:
        QPixmap con la imagen cargada, o None si falla la carga
        
    Examples:
        >>> # Cargar imagen sin límite de tamaño
        >>> pixmap = load_image_as_qpixmap(Path("foto.heic"))
        >>> 
        >>> # Cargar imagen limitada a 800x600
        >>> pixmap = load_image_as_qpixmap(Path("foto.heic"), max_size=(800, 600))
    """
    try:
        # Intentar cargar directamente con QPixmap (formatos nativos: JPG, PNG, etc.)
        pixmap = QPixmap(str(file_path))
        
        if not pixmap.isNull():
            # Si se especifica max_size, redimensionar
            if max_size:
                pixmap = pixmap.scaled(
                    max_size[0], max_size[1],
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            return pixmap
        
        # Si QPixmap falla, usar Pillow con caché (HEIC, HEIF, y otros formatos)
        if max_size:
            # Para thumbnails, usar caché
            png_bytes = _load_thumbnail_cached(str(file_path), max_size[0], max_size[1])
            if png_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(png_bytes, 'PNG')
                return pixmap if not pixmap.isNull() else None
        else:
            # Para imágenes completas, cargar sin caché
            _ensure_heif_support()
            from PIL import Image
            pil_image = Image.open(file_path)
            return _pil_to_qpixmap_fast(pil_image)
        
        return None
        
    except FileNotFoundError:
        logger.warning(f"File not found: {file_path}")
        return None
    except Exception as e:
        logger.debug(f"Could not load image {file_path.name}: {e}")
        return None


