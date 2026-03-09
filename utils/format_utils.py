# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Utilidades para formateo reutilizables en todo el proyecto.

Contiene funciones puras: format_size, format_number, format_file_count y
format_duration. Estas funciones no dependen de la UI y pueden importarse desde
`utils.format_utils` en cualquier módulo.
"""
from typing import Optional


def format_size(bytes_size: Optional[float]) -> str:
    """Formatea un tamaño en bytes a una cadena legible.

    Soporta B, KB, MB, GB usando potencias de 1024.
    Maneja None y valores inválidos devolviendo '0 B'. Mantiene el signo para
    valores negativos.
    """
    if bytes_size is None:
        return "0 B"
    
    try:
        size = float(bytes_size)
    except (TypeError, ValueError):
        return "0 B"

    if size < 0:
        return f"-{format_size(abs(size))}"

    if size < 1024:
        return f"{int(size)} B"

    kb = size / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"

    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"

    gb = mb / 1024
    return f"{gb:.2f} GB"


def format_number(number: Optional[int]) -> str:
    """Formatea un número con abreviaciones para miles (K, M).
    
    Ejemplos:
    - 0-999: "123"
    - 1000-9999: "1.2K"
    - 10000-999999: "12K"
    - 1000000+: "1.2M"
    
    Args:
        number: Número entero a formatear
    
    Returns:
        String con el número formateado profesionalmente
    """
    if number is None:
        return "0"
    
    try:
        num = int(number)
    except (TypeError, ValueError):
        return "0"
    
    if num < 0:
        return f"-{format_number(abs(num))}"
    
    if num < 1000:
        return str(num)
    elif num < 10000:
        return f"{num / 1000:.1f}K"
    elif num < 1000000:
        return f"{num // 1000}K"
    else:
        return f"{num / 1000000:.1f}M"


def format_file_count(count: Optional[int]) -> str:
    """Formatea un recuento de archivos con separador de miles.

    - Si count es None o inválido devuelve '0'.
    - Mantiene formateo con coma como separador de miles.
    """
    if count is None:
        return "0"
    
    try:
        return f"{int(count):,}"
    except (TypeError, ValueError):
        return "0"


def format_duration(seconds: Optional[float]) -> str:
    """Formatea una duración en segundos a formato legible.
    
    Ejemplos:
    - 0.5s -> "0.5s"
    - 65s -> "1m 5s"
    - 3661s -> "1h 1m 1s"
    - 86400s -> "1d"
    
    Args:
        seconds: Duración en segundos
        
    Returns:
        String formateado con componentes separados por espacios
    """
    if seconds is None:
        return "N/A"
    
    try:
        sec = float(seconds)
    except (TypeError, ValueError):
        return "N/A"
    
    if sec < 0:
        return f"-{format_duration(abs(sec))}"
    
    # Menos de 1 segundo: mostrar con decimales
    if sec < 1:
        return f"{sec:.2f}s"
    
    # Menos de 60 segundos: mostrar segundos enteros
    if sec < 60:
        return f"{int(sec)}s"
    
    # Calcular componentes
    days = int(sec // 86400)
    remaining = sec % 86400
    hours = int(remaining // 3600)
    remaining = remaining % 3600
    minutes = int(remaining // 60)
    secs = int(remaining % 60)
    
    # Construir string con espacios entre componentes
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0:
        parts.append(f"{secs}s")
    
    return " ".join(parts) if parts else "0s"
