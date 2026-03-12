# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Icon Manager - Sistema centralizado de gestión de iconos con QtAwesome.

Este módulo proporciona una interfaz unificada para gestionar iconos Material Design
en toda la aplicación usando QtAwesome.

Características:
- Diccionario centralizado de mapeo de iconos (ICON_MAP)
- Métodos helper para aplicar iconos a botones, labels y QToolButtons
- Soporte para diferentes tamaños y colores con caché integrado
- Sistema de caché para optimizar rendimiento
- Soporte HiDPI con devicePixelRatio automático
- Totalmente multiplataforma (Windows, Linux, macOS)

Uso básico:
    from ui.styles.icons import icon_manager
    
    # Aplicar icono a un botón
    icon_manager.set_button_icon(button, 'cog', color='#2563eb', size=20)
    
    # Aplicar icono a un label
    icon_manager.set_label_icon(label, 'information', size=16, color='#1e40af')
    
    # Obtener un QIcon directamente
    icon = icon_manager.get_icon('folder', color='#2563eb')
    
    # Crear un QToolButton con icono
    icon_button = icon_manager.create_icon_label('alert', size=18)

Categorías de iconos disponibles:
- Configuración y sistema: cog, information, devices, monitor, etc.
- Estados y notificaciones: alert, check, close, shield, etc.
- Archivos y carpetas: folder, file, open-in-new, magnify, view-grid, etc.
- Operaciones: delete, content-save, backup-restore, refresh, etc.
- Multimedia: image, video, camera, eye, etc.
- Duplicados: content-copy
- Renombrado: rename-box, rename-box-outline
- Tiempo y progreso: clock-outline, loading, progress-clock, etc.
- Navegación: chevron-left, chevron-right, skip-previous, skip-next, etc.
- Metadatos: ruler, fingerprint, map-marker, palette, etc.
- Almacenamiento: database, database-refresh, database-check, etc.
"""

import qtawesome as qta
from typing import Optional, Dict, Any
from PyQt6.QtGui import QIcon, QPixmap, QColor, QGuiApplication
from PyQt6.QtWidgets import QPushButton, QLabel, QToolButton
from PyQt6.QtCore import QSize, Qt


class IconManager:
    """Gestor centralizado de iconos Material Design usando QtAwesome.
    
    Proporciona un sistema de caché y métodos convenientes para aplicar
    iconos a widgets sin afectar las fuentes de texto de la aplicación.
    """
    
    # Mapping dictionary: logical name -> Material Design icon name in QtAwesome
    # Iconos organizados por categorías funcionales
    ICON_MAP = {
        # === CONFIGURACIÓN Y SISTEMA ===
        'cog': 'mdi6.cog',
        'settings': 'mdi6.cog',  # alias for cog for UI sections
        'auto-fix': 'mdi6.auto-fix',
        'information': 'mdi6.information',
        'information-outline': 'mdi6.information-outline',
        'devices': 'mdi6.devices',
        'monitor': 'mdi6.monitor',
        'harddisk': 'mdi6.harddisk',
        'speedometer': 'mdi6.speedometer',
        'code': 'mdi6.xml',
        
        # === ESTADOS Y NOTIFICACIONES ===
        'alert': 'mdi6.alert',
        'alert-circle': 'mdi6.alert-circle',
        'check': 'mdi6.check',
        'check-circle': 'mdi6.check-circle',
        'close': 'mdi6.close',
        'close-circle': 'mdi6.close-circle',
        'pause-circle': 'mdi6.pause-circle',
        'plus-circle': 'mdi6.plus-circle',
        'shield': 'mdi6.shield',
        'target': 'mdi6.target',
        
        # === ARCHIVOS Y CARPETAS ===
        'folder': 'mdi6.folder',
        'folder-open': 'mdi6.folder-open',
        'folder-cog': 'mdi6.folder-cog',
        'folder-remove': 'mdi6.folder-remove',
        'folder-multiple': 'mdi6.folder-multiple',
        'folder-move': 'mdi6.folder-move',
        'folder-zip': 'mdi6.folder-zip',
        'file': 'mdi6.file',
        'file-x': 'mdi6.file-remove',
        'file-image': 'mdi6.file-image',
        'file-video': 'mdi6.file-video',
        'file-document-outline': 'mdi6.file-document-outline',
        'file-check': 'mdi6.file-check',
        'file-plus': 'mdi6.file-plus',
        'file-edit': 'mdi6.file-edit',
        'file-jpg-box': 'mdi6.file-jpg-box',
        'view-grid': 'mdi6.view-grid',
        
        # === OPERACIONES DE ARCHIVOS ===
        'open-in-new': 'mdi6.open-in-new',
        'magnify': 'mdi6.magnify',
        'refresh': 'mdi6.refresh',
        'download': 'mdi6.download',
        'delete': 'mdi6.delete',
        'delete-sweep': 'mdi6.delete-sweep',
        'trash-alt': 'fa5s.trash-alt',
        'content-save': 'mdi6.content-save',
        'backup-restore': 'mdi6.backup-restore',
        'history': 'mdi6.history',
        'filter-variant': 'mdi6.filter-variant',
        'filter-variant-remove': 'mdi6.filter-variant-remove',
        
        # === TIEMPO Y ESTADÍSTICAS ===
        'chart-bar': 'mdi6.chart-bar',
        'clock-outline': 'mdi6.clock-outline',
        'clock-fast': 'mdi6.clock-fast',
        'clock-time-four': 'mdi6.clock-time-four',
        'timer-sand': 'mdi6.timer-sand',
        'update': 'mdi6.update',
        'calendar-month': 'mdi6.calendar-month',
        'calendar-check': 'mdi6.calendar-check',
        'arrow-expand-all': 'mdi6.arrow-expand-all',
        'arrow-collapse-all': 'mdi6.arrow-collapse-all',
        
        # === MULTIMEDIA ===
        'image': 'mdi6.image',
        'image-multiple': 'mdi6.image-multiple',
        'image-album': 'mdi6.image-album',
        'image-search': 'mdi6.image-search',
        'camera': 'mdi6.camera',
        'camera-burst': 'mdi6.camera-burst',
        'video': 'mdi6.video',
        'eye': 'mdi6.eye',
        'eye-off': 'mdi6.eye-off',
        'movie-open': 'mdi6.movie-open',
        'play-circle': 'mdi6.play-circle',
        'mail': 'mdi6.email',
        'email-outline': 'mdi6.email-outline',
        
        # === DUPLICADOS Y COPIAS ===
        'content-copy': 'mdi6.content-copy',
        
        # === RENOMBRADO ===
        'rename-box': 'mdi6.rename-box',
        'rename-box-outline': 'mdi6.rename-box-outline',
        
        # === PROGRESO Y LOADING ===
        'loading': 'mdi6.loading',
        'progress-clock': 'mdi6.progress-clock',
        
        # === NAVEGACIÓN ===
        'skip-previous': 'mdi6.skip-previous',
        'skip-next': 'mdi6.skip-next',
        'chevron-left': 'mdi6.chevron-left',
        'chevron-right': 'mdi6.chevron-right',
        'numeric-1-circle': 'mdi6.numeric-1-circle',
        
        # === METADATOS Y PROPIEDADES ===
        'ruler': 'mdi6.ruler',
        'fingerprint': 'mdi6.fingerprint',
        'map-marker': 'mdi6.map-marker',
        'palette': 'mdi6.palette',
        
        # === ALMACENAMIENTO Y BASE DE DATOS ===
        'database': 'mdi6.database',
        'database-refresh': 'mdi6.database-refresh',
        'database-check': 'mdi6.database-check',
        
        # === CONECTIVIDAD ===
        'wifi-off': 'mdi6.wifi-off',
    }
    
    def __init__(self):
        """Inicializa el gestor con un sistema de caché vacío."""
        self._cache: Dict[str, QIcon] = {}
    
    def get_icon(
        self, 
        name: str, 
        color: Optional[str] = None,
        size: Optional[int] = None,
        scale_factor: float = 1.0
    ) -> QIcon:
        """Obtiene un icono Material Design por nombre lógico.
        
        Args:
            name: Nombre lógico del icono (ej: 'settings', 'folder')
            color: Color del icono en formato hex (ej: '#2563eb'). Por defecto None (negro)
            size: Tamaño del icono en píxeles. Por defecto None (usa tamaño del widget)
            scale_factor: Factor de escala adicional (1.0 = tamaño normal)
        
        Returns:
            QIcon con el icono Material Design solicitado
        
        Raises:
            ValueError: Si el nombre de icono no existe en el mapeo
        """
        # Validar que el icono existe
        if name not in self.ICON_MAP:
            raise ValueError(
                f"Icon '{name}' not found. "
                f"Available icons: {', '.join(sorted(self.ICON_MAP.keys()))}"
            )
        
        # Crear clave de caché única
        cache_key = f"{name}_{color}_{size}_{scale_factor}"
        
        # Retornar desde caché si existe
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Obtener nombre real del icono en QtAwesome
        icon_name = self.ICON_MAP[name]
        
        # Preparar opciones para qtawesome
        options: Dict[str, Any] = {}
        if color:
            options['color'] = color
        if scale_factor != 1.0:
            options['scale_factor'] = scale_factor
        
        # Crear icono con qtawesome
        icon = qta.icon(icon_name, **options)
        
        # Guardar en caché
        self._cache[cache_key] = icon
        
        return icon
    
    def set_button_icon(
        self,
        button: QPushButton,
        icon_name: str,
        color: Optional[str] = None,
        size: int = 16
    ) -> None:
        """Aplica un icono Material Design a un botón.
        
        Args:
            button: QPushButton al que aplicar el icono
            icon_name: Nombre lógico del icono
            color: Color del icono en formato hex
            size: Tamaño del icono en píxeles
        """
        icon = self.get_icon(icon_name, color=color)
        button.setIcon(icon)
        button.setIconSize(QSize(size, size))
    
    def set_label_icon(
        self,
        label: QLabel,
        icon_name: str,
        color: Optional[str] = None,
        size: int = 16
    ) -> None:
        """Aplica un icono Material Design a un label.
        
        Este método convierte el icono en un QPixmap y lo establece en el label,
        evitando cualquier interferencia con la fuente del texto.
        
        Args:
            label: QLabel al que aplicar el icono
            icon_name: Nombre lógico del icono
            color: Color del icono en formato hex
            size: Tamaño del icono en píxeles
            
        Note:
            No establece el tamaño del label automáticamente para permitir
            que el layout y las políticas de tamaño del label se respeten.
            El pixmap se genera con devicePixelRatio para pantallas HiDPI.
        """
        icon = self.get_icon(icon_name, color=color)

        # Detectar device pixel ratio de la pantalla (HiDPI)
        try:
            screen = label.screen() if hasattr(label, 'screen') else QGuiApplication.primaryScreen()
            dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
        except Exception:
            dpr = 1.0

        # Crear pixmap con resolución física adecuada
        physical_size = QSize(max(1, int(size * dpr)), max(1, int(size * dpr)))
        pixmap = icon.pixmap(physical_size)

        # Si no conseguimos un pixmap a tamaño físico, intentar tamaño lógico
        if pixmap.isNull():
            pixmap = icon.pixmap(QSize(size, size))

        # Si sigue siendo nulo, crear un pixmap transparente de respaldo
        if pixmap.isNull():
            fallback = QPixmap(QSize(size, size))
            fallback.fill(QColor(0, 0, 0, 0))
            label.setPixmap(fallback)
            return

        # Algunos entornos/Qt pueden manejar devicePixelRatio internamente, pero
        # para evitar inconsistencias con QLabel.setScaledContents y distintos
        # backends, escalamos explícitamente el pixmap a su tamaño lógico
        # (size x size) usando SmoothTransformation.
        try:
            logical_pixmap = pixmap.scaled(QSize(size, size), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        except Exception:
            # En caso de que la API difiera, fallback a scaled without enums
            logical_pixmap = pixmap.scaled(size, size)

        # Asegurar DPR 1.0 en el pixmap final para evitar re-escalados inesperados
        try:
            logical_pixmap.setDevicePixelRatio(1.0)
        except Exception:
            pass

        label.setPixmap(logical_pixmap)
        # NO hacer setFixedSize aquí - permitir que el label controle su propio tamaño
    
    def create_icon_label(
        self,
        icon_name: str,
        color: Optional[str] = None,
        size: int = 16
    ) -> QToolButton:
        """Crea un QToolButton con un icono Material Design.
        
        Utiliza QToolButton en lugar de QLabel para aprovechar el renderizado
        nativo de QIcon, lo que garantiza consistencia con pestañas y mejora
        el soporte HiDPI en todas las plataformas.
        
        Args:
            icon_name: Nombre lógico del icono
            color: Color del icono en formato hex
            size: Tamaño del icono en píxeles
        
        Returns:
            QToolButton configurado con el icono y estilo plano transparente
        """
        # Para evitar inconsistencias de rasterizado en HiDPI, creamos un
        # QToolButton plano que usa QIcon internamente. Esto permite que Qt
        # rasterice el icono a la resolución correcta (igual que en pestañas).
        btn = QToolButton()
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn.setIconSize(QSize(size, size))
        btn.setFixedSize(QSize(max(24, size + 6), max(24, size + 6)))
        btn.setStyleSheet("QToolButton { background: transparent; border: none; padding: 0px; }")
        # Aplicar icono usando la canalización de QIcon/QToolButton
        self.set_button_icon(btn, icon_name, color=color, size=size)
        return btn


# Instancia global del gestor de iconos
icon_manager = IconManager()