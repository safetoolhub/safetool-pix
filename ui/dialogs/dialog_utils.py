# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Utilidades compartidas para diálogos
Funciones comunes para abrir archivos, carpetas y mostrar detalles
"""
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from PyQt6.QtWidgets import QMessageBox, QMenu, QTreeWidget, QWidget
from PyQt6.QtCore import Qt, QSize, QPoint
from utils.format_utils import format_size
from utils.platform_utils import open_file_with_default_app, open_folder_in_explorer
from utils.logger import get_logger
from utils.i18n import tr

# Logger del módulo siguiendo el patrón estándar del proyecto
logger = get_logger('UI.Dialogs.Utils')


def open_file(file_path: Path, parent_widget=None):
    """
    Abre un archivo con la aplicación predeterminada del sistema operativo.
    Wrapper de UI para utils.platform_utils.open_file_with_default_app()
    
    Args:
        file_path: Ruta del archivo a abrir
        parent_widget: Widget padre para mostrar mensajes de error
        
    Returns:
        True si el archivo se abrió correctamente, False si hubo error
    """
    def show_error(error_msg: str):
        """Callback para mostrar errores en QMessageBox"""
        if parent_widget:
            QMessageBox.warning(
                parent_widget,
                tr("dialogs.utils.error_open_file"),
                error_msg
            )
    
    return open_file_with_default_app(file_path, error_callback=show_error)


def open_folder(folder_path: Path, parent_widget=None, select_file: Path = None):
    """
    Abre una carpeta en el explorador de archivos del sistema operativo.
    Wrapper de UI para utils.platform_utils.open_folder_in_explorer()
    
    Args:
        folder_path: Ruta de la carpeta a abrir
        parent_widget: Widget padre para mostrar mensajes de error
        select_file: Archivo opcional dentro de la carpeta a seleccionar
        
    Returns:
        True si la carpeta se abrió correctamente, False si hubo error
    """
    def show_error(error_msg: str):
        """Callback para mostrar errores en QMessageBox"""
        if parent_widget:
            QMessageBox.warning(
                parent_widget,
                tr("dialogs.utils.error_open_folder"),
                error_msg
            )
    
    return open_folder_in_explorer(folder_path, 
                                   select_file=select_file,
                                   error_callback=show_error)


# ============================================================================
# FUNCIONES COMUNES PARA TREEWIDGETS DE DIÁLOGOS
# ============================================================================

def handle_tree_item_double_click(item, column, parent_widget=None) -> None:
    """
    Maneja el doble clic en un item del TreeWidget de forma unificada.
    
    - Si es un archivo (Path en UserRole): lo abre con la app predeterminada
    - Si es un grupo (cualquier otro dato o None): expande/colapsa el nodo
    
    Args:
        item: QTreeWidgetItem que recibió el doble clic
        column: Columna del clic (no usado, pero requerido por la señal)
        parent_widget: Widget padre para mostrar errores
    """
    # Obtener el dato asociado al item
    data = item.data(0, Qt.ItemDataRole.UserRole)
    
    if isinstance(data, Path):
        # Es un archivo - abrirlo
        open_file(data, parent_widget)
    else:
        # Es un grupo - expandir/colapsar
        item.setExpanded(not item.isExpanded())


def apply_group_item_style(group_item, num_columns: int = 5) -> None:
    """
    Aplica estilo Material Design unificado a un nodo de grupo en TreeWidget.
    
    Estilo: Texto en negrita, color primario (azul), fondo sutil.
    
    Args:
        group_item: QTreeWidgetItem del grupo
        num_columns: Número de columnas a las que aplicar el fondo
    """
    from PyQt6.QtGui import QColor, QFont
    from ui.styles.design_system import DesignSystem
    
    # Estilo del texto: Bold + Primary color + tamaño XS
    font = group_item.font(0)
    font.setBold(True)
    font.setPointSize(int(DesignSystem.FONT_SIZE_XS))
    group_item.setFont(0, font)
    group_item.setForeground(0, QColor(DesignSystem.COLOR_PRIMARY))
    
    # Color de fondo sutil Material Design para todas las columnas
    bg_color = QColor(DesignSystem.COLOR_BG_1)
    for col in range(num_columns):
        group_item.setBackground(col, bg_color)


def create_group_tooltip(group_number: int, description: str, extra_info: str = "") -> str:
    """
    Crea un tooltip estándar para nodos de grupo.
    
    Args:
        group_number: Número del grupo
        description: Descripción del contenido (ej: "3 archivos idénticos")
        extra_info: Información adicional opcional (ej: fecha, variación)
        
    Returns:
        Texto del tooltip formateado
    """
    tooltip = (f"{tr('dialogs.utils.group_tooltip_expand')}\n"
               f"{tr('dialogs.utils.group_tooltip_columns')}")
    
    if extra_info:
        tooltip += f"\n{extra_info}"
    
    return f"#{group_number} - {description}\n{tooltip}"


def apply_file_item_status(file_item, is_keep: bool, status_column: int = 4) -> None:
    """
    Aplica el estado (conservar/eliminar) a un item de archivo.
    
    Args:
        file_item: QTreeWidgetItem del archivo
        is_keep: True si se conservará, False si se eliminará
        status_column: Índice de la columna de estado
    """
    from PyQt6.QtGui import QColor
    from ui.styles.design_system import DesignSystem
    
    if is_keep:
        file_item.setText(status_column, tr("dialogs.utils.status_keep"))
        file_item.setForeground(status_column, QColor(DesignSystem.COLOR_SUCCESS))
    else:
        file_item.setText(status_column, tr("dialogs.utils.status_delete"))
        file_item.setForeground(status_column, QColor(DesignSystem.COLOR_ERROR))


def get_file_icon_name(file_path: Path) -> str:
    """
    Determina el nombre del icono según el tipo de archivo.
    
    Args:
        file_path: Ruta del archivo
        
    Returns:
        Nombre del icono ('image', 'video', 'camera', 'file')
    """
    ext = file_path.suffix.lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        return "image"
    elif ext in ['.mov', '.mp4', '.avi', '.mkv', '.m4v']:
        return "video"
    elif ext in ['.heic', '.heif']:
        return "camera"
    else:
        return "file"


def create_groups_tree_widget(
    headers: list[str],
    column_widths: list[int],
    double_click_handler: Callable = None,
    context_menu_handler: Callable = None
) -> QTreeWidget:
    """
    Crea un QTreeWidget configurado para mostrar grupos expandibles.
    
    Configuración unificada con estilo Material Design para todos los diálogos.
    
    Args:
        headers: Lista de nombres de columnas
        column_widths: Lista de anchos de columna (debe tener mismo tamaño que headers)
        double_click_handler: Función a conectar con itemDoubleClicked
        context_menu_handler: Función a conectar con customContextMenuRequested
        
    Returns:
        QTreeWidget configurado y estilizado
    """
    from PyQt6.QtWidgets import QTreeWidget
    from PyQt6.QtCore import Qt
    from ui.styles.design_system import DesignSystem
    
    tree = QTreeWidget()
    tree.setHeaderLabels(headers)
    
    # Configurar anchos de columna
    for i, width in enumerate(column_widths):
        tree.setColumnWidth(i, width)
    
    # Configuración estándar para grupos expandibles
    tree.setAlternatingRowColors(True)
    tree.setRootIsDecorated(True)
    tree.setAnimated(True)
    tree.setIndentation(20)
    tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    
    # Estilo Material Design
    tree.setStyleSheet(DesignSystem.get_tree_widget_style())
    
    # Conectar señales si se proporcionan handlers
    if double_click_handler:
        tree.itemDoubleClicked.connect(double_click_handler)
    if context_menu_handler:
        tree.customContextMenuRequested.connect(context_menu_handler)
    
    return tree


def show_file_context_menu(
    tree_widget: QTreeWidget, 
    position: QPoint, 
    parent_widget: QWidget,
    details_callback: Optional[Callable[[Path], None]] = None
) -> None:
    """
    Muestra menú contextual estándar para archivos en TreeWidgets.
    
    Menú unificado con estilo Material Design para todos los diálogos:
    - Abrir archivo
    - Abrir carpeta contenedora
    - Ver detalles del archivo
    
    Args:
        tree_widget: QTreeWidget donde se muestra el menú
        position: Posición del clic (desde customContextMenuRequested)
        parent_widget: Widget padre para el menú y callbacks
        details_callback: Callback opcional para "Ver detalles" con información adicional.
                         Si es None, usa show_file_details_dialog directamente.
                         La función recibe file_path como parámetro.
    """
    from ui.styles.design_system import DesignSystem
    from ui.styles.icons import icon_manager
    
    item = tree_widget.itemAt(position)
    if not item:
        return
    
    # Obtener el archivo asociado al item
    file_path = item.data(0, Qt.ItemDataRole.UserRole)
    if not file_path:
        return  # Es un grupo padre, no mostrar menú
    
    # Convertir a Path si es string
    if isinstance(file_path, str):
        file_path = Path(file_path)
    elif not isinstance(file_path, Path):
        return
    
    menu = QMenu(parent_widget)
    menu.setStyleSheet(DesignSystem.get_context_menu_style())
    
    # Opción: Abrir archivo
    open_action = menu.addAction(icon_manager.get_icon('open-in-new'), tr("dialogs.utils.menu.open_file"))
    open_action.triggered.connect(lambda: open_file(file_path, parent_widget))
    
    # Opción: Abrir carpeta contenedora
    open_folder_action = menu.addAction(icon_manager.get_icon('folder-open'), tr("dialogs.utils.menu.open_folder"))
    open_folder_action.triggered.connect(lambda: open_folder(file_path.parent, parent_widget))
    
    menu.addSeparator()
    
    # Opción: Ver detalles del archivo
    details_action = menu.addAction(icon_manager.get_icon('information'), tr("dialogs.utils.menu.view_details"))
    if details_callback:
        details_action.triggered.connect(lambda: details_callback(file_path))
    else:
        details_action.triggered.connect(lambda: show_file_details_dialog(file_path, parent_widget))
    
    menu.exec(tree_widget.viewport().mapToGlobal(position))


def show_file_details_dialog(file_path: Path, parent_widget=None, additional_info=None, force_metadata_search=False):
    """
    Muestra un diálogo con detalles completos del archivo usando toda la información
    disponible en FileMetadata desde el FileInfoRepositoryCache.
    
    ÚNICA FUENTE DE VERDAD: FileInfoRepositoryCache.get_file_metadata()
    Esta función obtiene directamente los metadatos del repositorio de caché.
    
    Args:
        file_path: Ruta del archivo a mostrar
        parent_widget: Widget padre para el diálogo
        additional_info: Información adicional contextual (opcional)
        force_metadata_search: Si True, fuerza la extracción completa de metadatos
                              ignorando caché y configuración (hash + EXIF)
    """
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                QPushButton, QFrame, QGroupBox, QWidget, QScrollArea)
    from PyQt6.QtCore import Qt
    from ui.styles.design_system import DesignSystem
    from ui.styles.icons import icon_manager
    from services.file_metadata_repository_cache import FileInfoRepositoryCache
    from utils.date_utils import get_all_metadata_from_file
    
    logger.debug(f"Showing file details: {file_path.name} (force_search={force_metadata_search})")
    
    # === 1. RECOPILACIÓN DE DATOS ===
    
    if force_metadata_search:
        # Búsqueda forzada: extraer TODOS los metadatos disponibles (hash + EXIF)
        logger.info(f"Forced search of complete metadata for: {file_path.name}")
        metadata = get_all_metadata_from_file(file_path, force_search=True)
    else:
        # Búsqueda normal: usar caché primero
        repo = FileInfoRepositoryCache.get_instance()
        metadata = repo.get_file_metadata(file_path)
        
        if metadata is None:
            logger.warning(f"No cached metadata found for {file_path}")
            # Fallback: intentar obtener con get_all_metadata_from_file si no está en caché
            metadata = get_all_metadata_from_file(file_path, force_search=True)
    
    logger.debug(f"Metadata obtained - Size: {metadata.fs_size}, Hash: {metadata.has_hash}, EXIF: {metadata.has_exif}, Best Date: {metadata.has_best_date}")
    if metadata.is_video:
        logger.debug(f"Video metadata EXIF - DateTimeOriginal: {metadata.exif_DateTimeOriginal}, DateTime: {metadata.exif_DateTime}, Width: {metadata.exif_ImageWidth}, Height: {metadata.exif_ImageLength}, Duration: {metadata.video_duration_formatted}, Seconds: {metadata.exif_VideoDurationSeconds}")
    
    # Para videos con force_search, extraer metadatos técnicos adicionales de ffprobe
    video_metadata = None
    if force_metadata_search and metadata.is_video:
        try:
            from utils.file_utils import get_exif_from_video
            video_metadata = get_exif_from_video(file_path)
            if video_metadata:
                logger.debug(f"Technical video metadata obtained via ffprobe: {len(video_metadata)} fields")
        except Exception as e:
            logger.warning(f"Error getting technical video metadata: {e}")
    
    # === 2. CONSTRUCCIÓN DE LA IU ===
    
    dialog = QDialog(parent_widget)
    dialog.setWindowTitle(tr("dialogs.details.title"))
    dialog.setModal(True)
    dialog.setMinimumWidth(900)
    dialog.setMaximumWidth(950)
    dialog.setMinimumHeight(700)
    
    main_layout = QVBoxLayout(dialog)
    main_layout.setContentsMargins(DesignSystem.SPACE_24, DesignSystem.SPACE_20, DesignSystem.SPACE_24, DesignSystem.SPACE_20)
    main_layout.setSpacing(DesignSystem.SPACE_16)
    
    # Header
    header_layout = QHBoxLayout()
    header_layout.setSpacing(DesignSystem.SPACE_12)
    
    file_icon_name = 'image' if metadata.is_image else ('video' if metadata.is_video else 'file')
    header_icon = QLabel()
    icon_manager.set_label_icon(header_icon, file_icon_name, size=DesignSystem.ICON_SIZE_LG, color=DesignSystem.COLOR_PRIMARY)
    header_layout.addWidget(header_icon)
    
    title_label = QLabel(file_path.name)
    title_label.setStyleSheet(f"font-size: {DesignSystem.FONT_SIZE_2XL}px; font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD}; color: {DesignSystem.COLOR_TEXT};")
    header_layout.addWidget(title_label)
    header_layout.addStretch()
    
    # Botón de búsqueda completa de metadatos (solo si no se ha forzado ya)
    if not force_metadata_search:
        refresh_btn = QPushButton()
        refresh_icon = icon_manager.get_icon('database-refresh', size=DesignSystem.ICON_SIZE_MD, color=DesignSystem.COLOR_ACCENT)
        refresh_btn.setIcon(refresh_icon)
        refresh_btn.setIconSize(QSize(DesignSystem.ICON_SIZE_MD, DesignSystem.ICON_SIZE_MD))
        refresh_btn.setFixedSize(DesignSystem.ICON_SIZE_LG + 8, DesignSystem.ICON_SIZE_LG + 8)
        refresh_btn.setToolTip(
            tr("dialogs.details.refresh_tooltip")
        )
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {DesignSystem.COLOR_CARD_BORDER};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: {DesignSystem.SPACE_4}px;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_SECONDARY_LIGHT};
                border-color: {DesignSystem.COLOR_ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {DesignSystem.COLOR_SURFACE};
            }}
        """)
        refresh_btn.clicked.connect(lambda: _reload_with_full_metadata(file_path, parent_widget, additional_info, dialog))
        header_layout.addWidget(refresh_btn)
    else:
        # Indicador de que se realizó búsqueda completa
        search_indicator = QLabel()
        search_icon = icon_manager.get_icon('database-check', size=DesignSystem.ICON_SIZE_MD, color=DesignSystem.COLOR_SUCCESS)
        search_indicator.setPixmap(search_icon.pixmap(DesignSystem.ICON_SIZE_MD, DesignSystem.ICON_SIZE_MD))
        search_indicator.setToolTip(tr("dialogs.details.full_metadata_loaded"))
        header_layout.addWidget(search_indicator)
    
    main_layout.addLayout(header_layout)
    
    # Área de scroll
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setStyleSheet(f"QScrollArea {{ border: 1px solid {DesignSystem.COLOR_CARD_BORDER}; border-radius: {DesignSystem.RADIUS_LG}px; background-color: {DesignSystem.COLOR_SURFACE}; }}")
    
    scroll_widget = QWidget()
    scroll_layout = QVBoxLayout(scroll_widget)
    scroll_layout.setContentsMargins(DesignSystem.SPACE_20, DesignSystem.SPACE_16, DesignSystem.SPACE_20, DesignSystem.SPACE_16)
    scroll_layout.setSpacing(DesignSystem.SPACE_20)
    
    # SECCIÓN: INFORMACIÓN GENERAL
    general_items = [
        (tr("dialogs.details.general.full_path"), str(file_path), tr("dialogs.details.general.full_path_desc"), 'folder-open', DesignSystem.COLOR_INFO),
        (tr("dialogs.details.general.size"), format_size(metadata.fs_size), tr("dialogs.details.general.size_desc"), 'harddisk', DesignSystem.COLOR_INFO),
        (tr("dialogs.details.general.type"), _get_file_type_display(file_path), tr("dialogs.details.general.type_desc"), 'file-check', DesignSystem.COLOR_INFO),
    ]
    if metadata.sha256:
        general_items.append((tr("dialogs.details.general.hash"), metadata.sha256, tr("dialogs.details.general.hash_desc"), 'fingerprint', DesignSystem.COLOR_INFO))
    
    scroll_layout.addWidget(_create_enhanced_section_with_copy(
        tr("dialogs.details.section.general"), 
        general_items,
        copy_field_index=0,
        parent_widget=dialog
    ))
    
    # SECCIÓN: MEJOR FECHA DISPONIBLE (Segunda posición - solo si existe)
    if metadata.best_date:
        scroll_layout.addWidget(_create_best_date_section(metadata))
    
    # SECCIÓN: FECHAS DEL SISTEMA (RAW FileMetadata)
    fs_dates = [
        (tr("dialogs.details.fs_dates.ctime"), datetime.fromtimestamp(metadata.fs_ctime).strftime('%Y-%m-%d %H:%M:%S'), tr("dialogs.details.fs_dates.ctime_desc"), 'file-plus', DesignSystem.COLOR_WARNING),
        (tr("dialogs.details.fs_dates.mtime"), datetime.fromtimestamp(metadata.fs_mtime).strftime('%Y-%m-%d %H:%M:%S'), tr("dialogs.details.fs_dates.mtime_desc"), 'file-edit', DesignSystem.COLOR_WARNING),
        (tr("dialogs.details.fs_dates.atime"), datetime.fromtimestamp(metadata.fs_atime).strftime('%Y-%m-%d %H:%M:%S'), tr("dialogs.details.fs_dates.atime_desc"), 'eye', DesignSystem.COLOR_WARNING),
    ]
    scroll_layout.addWidget(_create_enhanced_section(tr("dialogs.details.section.filesystem_dates"), fs_dates))
    
    # SECCIÓN: CONTEXTO DE LA OPERACIÓN (Si hay información adicional del diálogo)
    if additional_info:
        add_items = []
        for key, val in additional_info.items():
            if key in ['metadata', 'target_path']: continue # Manejados aparte o ignorados
            # Determinar icono y color según el tipo de información
            icon = 'information-outline'
            color = DesignSystem.COLOR_INFO
            if 'name' in key: 
                icon = 'file-edit'
                color = DesignSystem.COLOR_ACCENT
            if 'conflict' in key: 
                icon = 'alert'
                color = DesignSystem.COLOR_ERROR
            
            description = tr("dialogs.details.operation_context.generic_desc")
            add_items.append((key.replace('_', ' ').title(), str(val), description, icon, color))
        
        if add_items:
            scroll_layout.addWidget(_create_enhanced_section(tr("dialogs.details.section.operation_context"), add_items))
    
    # SECCIÓN: METADATOS TÉCNICOS DE VIDEO (desde FileMetadata o ffprobe)
    # Posicionada ANTES de las fechas para mayor visibilidad
    if metadata.is_video:
        video_tech_items = []
        
        # Dimensiones del video (desde FileMetadata)
        if metadata.exif_ImageWidth and metadata.exif_ImageLength:
            resolution = f"{metadata.exif_ImageWidth} × {metadata.exif_ImageLength}"
            video_tech_items.append((
                tr("dialogs.details.video.resolution"),
                resolution,
                tr("dialogs.details.video.resolution_desc"),
                'monitor',
                DesignSystem.COLOR_INFO
            ))
        elif metadata.exif_ImageWidth:
            video_tech_items.append((tr("dialogs.details.video.width"), f"{metadata.exif_ImageWidth} px", tr("dialogs.details.video.width_desc"), 'ruler', DesignSystem.COLOR_INFO))
        elif metadata.exif_ImageLength:
            video_tech_items.append((tr("dialogs.details.video.height"), f"{metadata.exif_ImageLength} px", tr("dialogs.details.video.height_desc"), 'ruler', DesignSystem.COLOR_INFO))
        
        # Duración del video (desde FileMetadata)
        if metadata.video_duration_formatted:
            video_tech_items.append((
                tr("dialogs.details.video.duration"),
                metadata.video_duration_formatted,
                tr("dialogs.details.video.duration_desc"),
                'clock-outline',
                DesignSystem.COLOR_INFO
            ))
        
        # Si hay metadatos adicionales de ffprobe (force_metadata_search)
        if video_metadata:
            # Frame rate
            if 'fps' in video_metadata:
                video_tech_items.append((
                    tr("dialogs.details.video.fps"),
                    video_metadata['fps'],
                    tr("dialogs.details.video.fps_desc"),
                    'speedometer',
                    DesignSystem.COLOR_INFO
                ))
            
            # Códec de video
            if 'video_codec' in video_metadata:
                codec_display = video_metadata['video_codec'].upper()
                if 'video_codec_long' in video_metadata:
                    codec_display = f"{codec_display} ({video_metadata['video_codec_long']})"
                video_tech_items.append((
                    tr("dialogs.details.video.codec"),
                    codec_display,
                    tr("dialogs.details.video.codec_desc"),
                    'file-video',
                    DesignSystem.COLOR_INFO
                ))
            
            # Bitrate
            if 'bitrate' in video_metadata:
                video_tech_items.append((
                    tr("dialogs.details.video.bitrate"),
                    video_metadata['bitrate'],
                    tr("dialogs.details.video.bitrate_desc"),
                    'speedometer',
                    DesignSystem.COLOR_INFO
                ))
            
            # Formato
            if 'format_long' in video_metadata:
                video_tech_items.append((
                    tr("dialogs.details.video.format_container"),
                    video_metadata['format_long'],
                    tr("dialogs.details.video.format_container_desc"),
                    'folder-zip',
                    DesignSystem.COLOR_INFO
                ))
            elif 'format' in video_metadata:
                video_tech_items.append((
                    tr("dialogs.details.video.format"),
                    video_metadata['format'],
                    tr("dialogs.details.video.format_desc"),
                    'folder-zip',
                    DesignSystem.COLOR_INFO
                ))
            
            # Pixel format
            if 'pixel_format' in video_metadata:
                video_tech_items.append((
                    tr("dialogs.details.video.pixel_format"),
                    video_metadata['pixel_format'],
                    tr("dialogs.details.video.pixel_format_desc"),
                    'palette',
                    DesignSystem.COLOR_INFO
                ))
            
            # Encoder
            if 'encoder' in video_metadata:
                video_tech_items.append((
                    tr("dialogs.details.video.encoder"),
                    video_metadata['encoder'],
                    tr("dialogs.details.video.encoder_desc"),
                    'cog',
                    DesignSystem.COLOR_INFO
                ))
        
        if video_tech_items:
            section_title = tr("dialogs.details.section.video_tech")
            if video_metadata:
                section_title += " (ffprobe)"
            scroll_layout.addWidget(_create_enhanced_section(section_title, video_tech_items))
    
    # SECCIÓN: FECHAS EXIF (después de metadatos técnicos de video)
    scroll_layout.addWidget(_create_dates_section(metadata))
    
    # SECCIÓN: METADATOS TÉCNICOS EXIF (Última posición - solo para imágenes)
    if metadata.has_exif and metadata.is_image:
        exif_items = []
        
        # Dimensiones
        if metadata.exif_ImageWidth:
            exif_items.append((tr("dialogs.details.exif_tech.width_desc"), f"{metadata.exif_ImageWidth} px", tr("dialogs.details.exif_tech.width_desc"), 'ruler', DesignSystem.COLOR_ACCENT))
        if metadata.exif_ImageLength:
            exif_items.append((tr("dialogs.details.exif_tech.height_desc"), f"{metadata.exif_ImageLength} px", tr("dialogs.details.exif_tech.height_desc"), 'ruler', DesignSystem.COLOR_ACCENT))
        
        # Versión EXIF
        if metadata.exif_ExifVersion:
            exif_items.append((tr("dialogs.details.exif_tech.version"), str(metadata.exif_ExifVersion), tr("dialogs.details.exif_tech.version_desc"), 'information', DesignSystem.COLOR_ACCENT))
        
        # Software (solo si existe y es relevante - no duplicado)
        if metadata.exif_Software:
            exif_items.append((tr("dialogs.details.exif_tech.software"), metadata.exif_Software, tr("dialogs.details.exif_tech.software_desc"), 'cog', DesignSystem.COLOR_ACCENT))
        
        # Subsegundos
        if metadata.exif_SubSecTimeOriginal:
            exif_items.append((tr("dialogs.details.exif_tech.subseconds"), metadata.exif_SubSecTimeOriginal, tr("dialogs.details.exif_tech.subseconds_desc"), 'timer-sand', DesignSystem.COLOR_ACCENT))
        
        # Timezone
        if metadata.exif_OffsetTimeOriginal:
            exif_items.append((tr("dialogs.details.exif_tech.timezone"), metadata.exif_OffsetTimeOriginal, tr("dialogs.details.exif_tech.timezone_desc"), 'clock-time-four', DesignSystem.COLOR_ACCENT))
        
        if exif_items:
            scroll_layout.addWidget(_create_enhanced_section(tr("dialogs.details.section.exif_tech"), exif_items))

    scroll_layout.addStretch()
    scroll_area.setWidget(scroll_widget)
    main_layout.addWidget(scroll_area)
    
    # Separador
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setFrameShadow(QFrame.Shadow.Sunken)
    separator.setStyleSheet(f"color: {DesignSystem.COLOR_CARD_BORDER};")
    main_layout.addWidget(separator)
    
    # Botones
    buttons_layout = QHBoxLayout()
    buttons_layout.setSpacing(DesignSystem.SPACE_12)
    
    # Botón de abrir archivo
    open_file_btn = QPushButton(tr("dialogs.details.buttons.open_file"))
    open_file_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
    open_file_btn.clicked.connect(lambda: _open_file_and_close(file_path, dialog))
    buttons_layout.addWidget(open_file_btn)
    
    # Botón de abrir carpeta
    open_folder_btn = QPushButton(tr("dialogs.details.buttons.open_folder"))
    open_folder_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
    open_folder_btn.clicked.connect(lambda: _open_folder_and_close(file_path, dialog))
    buttons_layout.addWidget(open_folder_btn)
    
    buttons_layout.addStretch()
    
    # Botón cerrar
    close_btn = QPushButton(tr("common.close"))
    close_btn.setStyleSheet(DesignSystem.get_primary_button_style())
    close_btn.clicked.connect(dialog.accept)
    buttons_layout.addWidget(close_btn)
    
    main_layout.addLayout(buttons_layout)
    
    dialog.exec()


def _create_enhanced_section(title: str, items: list):
    """Crea una sección mejorada con formato unificado (título + valor + descripción)
    
    Args:
        title: Título de la sección
        items: Lista de tuplas (título, valor, descripción, icono, color)
    """
    from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QWidget
    from ui.styles.design_system import DesignSystem
    
    group = QGroupBox(title)
    group.setStyleSheet(f"""
        QGroupBox {{
            font-size: {DesignSystem.FONT_SIZE_LG}px;
            font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
            color: {DesignSystem.COLOR_TEXT};
            border: 1px solid {DesignSystem.COLOR_CARD_BORDER};
            border-radius: {DesignSystem.RADIUS_LG}px;
            padding: {DesignSystem.SPACE_16}px;
            margin: 0;
            background-color: {DesignSystem.COLOR_SURFACE};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {DesignSystem.SPACE_12}px;
            padding: 0 {DesignSystem.SPACE_8}px;
            color: {DesignSystem.COLOR_PRIMARY};
            font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
        }}
    """)
    
    layout = QVBoxLayout()
    layout.setContentsMargins(
        DesignSystem.SPACE_16, DesignSystem.SPACE_24, 
        DesignSystem.SPACE_16, DesignSystem.SPACE_16
    )
    layout.setSpacing(DesignSystem.SPACE_12)
    
    for i, (label_text, value_text, description, icon_name, accent_color) in enumerate(items):
        row = _create_info_row(label_text, value_text, description, icon_name, accent_color)
        layout.addWidget(row)
        
        # Agregar separador entre items (excepto el último)
        if i < len(items) - 1:
            separator = QWidget()
            separator.setFixedHeight(1)
            separator.setStyleSheet(f"background-color: {DesignSystem.COLOR_CARD_BORDER}; margin: {DesignSystem.SPACE_4}px 0;")
            layout.addWidget(separator)
    
    group.setLayout(layout)
    return group


def _create_enhanced_section_with_copy(
    title: str, 
    items: list, 
    copy_field_index: int = 0,
    parent_widget=None
):
    """Crea una sección mejorada con un campo que tiene botón de copiar al portapapeles.
    
    Args:
        title: Título de la sección
        items: Lista de tuplas (título, valor, descripción, icono, color)
        copy_field_index: Índice del campo que tendrá el botón de copiar (default: 0)
        parent_widget: Widget padre para mostrar tooltips/feedback
    """
    from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QWidget
    from ui.styles.design_system import DesignSystem
    
    group = QGroupBox(title)
    group.setStyleSheet(f"""
        QGroupBox {{
            font-size: {DesignSystem.FONT_SIZE_LG}px;
            font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
            color: {DesignSystem.COLOR_TEXT};
            border: 1px solid {DesignSystem.COLOR_CARD_BORDER};
            border-radius: {DesignSystem.RADIUS_LG}px;
            padding: {DesignSystem.SPACE_16}px;
            margin: 0;
            background-color: {DesignSystem.COLOR_SURFACE};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {DesignSystem.SPACE_12}px;
            padding: 0 {DesignSystem.SPACE_8}px;
            color: {DesignSystem.COLOR_PRIMARY};
            font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
        }}
    """)
    
    layout = QVBoxLayout()
    layout.setContentsMargins(
        DesignSystem.SPACE_16, DesignSystem.SPACE_24, 
        DesignSystem.SPACE_16, DesignSystem.SPACE_16
    )
    layout.setSpacing(DesignSystem.SPACE_12)
    
    for i, (label_text, value_text, description, icon_name, accent_color) in enumerate(items):
        if i == copy_field_index:
            # Campo con botón de copiar
            row = _create_info_row_with_copy(
                label_text, value_text, description, icon_name, accent_color, parent_widget
            )
        else:
            row = _create_info_row(label_text, value_text, description, icon_name, accent_color)
        layout.addWidget(row)
        
        # Agregar separador entre items (excepto el último)
        if i < len(items) - 1:
            separator = QWidget()
            separator.setFixedHeight(1)
            separator.setStyleSheet(f"background-color: {DesignSystem.COLOR_CARD_BORDER}; margin: {DesignSystem.SPACE_4}px 0;")
            layout.addWidget(separator)
    
    group.setLayout(layout)
    return group


def _create_dates_section(metadata: 'FileMetadata'):
    """Crea la sección especial de fechas con información detallada usando FileMetadata directamente"""
    from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel, QHBoxLayout, QWidget
    from ui.styles.design_system import DesignSystem
    from ui.styles.icons import icon_manager
    from datetime import datetime
    from utils.date_utils import extract_date_from_filename, _parse_exif_date
    
    group = QGroupBox(tr("dialogs.details.section.exif_dates"))
    group.setStyleSheet(f"""
        QGroupBox {{
            font-size: {DesignSystem.FONT_SIZE_LG}px;
            font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
            color: {DesignSystem.COLOR_TEXT};
            border: 1px solid {DesignSystem.COLOR_CARD_BORDER};
            border-radius: {DesignSystem.RADIUS_LG}px;
            padding: {DesignSystem.SPACE_16}px;
            margin: 0;
            background-color: {DesignSystem.COLOR_SURFACE};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {DesignSystem.SPACE_12}px;
            padding: 0 {DesignSystem.SPACE_8}px;
            color: {DesignSystem.COLOR_PRIMARY};
            font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
        }}
    """)
    
    layout = QVBoxLayout()
    layout.setContentsMargins(
        DesignSystem.SPACE_16, DesignSystem.SPACE_24, 
        DesignSystem.SPACE_16, DesignSystem.SPACE_16
    )
    layout.setSpacing(DesignSystem.SPACE_12)
    
    # === FECHAS EXIF ===
    exif_dates_added = False
    
    logger.debug(f"_create_dates_section - Entrada: DateTimeOriginal={metadata.exif_DateTimeOriginal}, DateTime={metadata.exif_DateTime}, DateTimeDigitized={metadata.exif_DateTimeDigitized}")
    
    # DateTimeOriginal (fecha de captura principal)
    exif_date_time_original = _parse_exif_date(metadata.exif_DateTimeOriginal)
    logger.debug(f"_parse_exif_date(DateTimeOriginal) returned: {exif_date_time_original}")
    if exif_date_time_original:
        tz_info = ""
        if metadata.exif_OffsetTimeOriginal:
            tz_info = f" (Timezone: {metadata.exif_OffsetTimeOriginal})"
        exif_row = _create_date_row(
            "EXIF DateTimeOriginal", 
            exif_date_time_original.strftime("%Y-%m-%d %H:%M:%S"),
            tr("dialogs.details.exif_dates.original_desc") + tz_info,
            'camera',
            DesignSystem.COLOR_ACCENT
        )
        layout.addWidget(exif_row)
        exif_dates_added = True
    
    # CreateDate (DateTime en FileMetadata)
    exif_create_date = _parse_exif_date(metadata.exif_DateTime)
    logger.debug(f"_parse_exif_date(DateTime/CreateDate) returned: {exif_create_date}")
    if exif_create_date:
        exif_row = _create_date_row(
            "EXIF CreateDate", 
            exif_create_date.strftime("%Y-%m-%d %H:%M:%S"),
            tr("dialogs.details.exif_dates.create_desc"),
            'camera',
            DesignSystem.COLOR_ACCENT
        )
        layout.addWidget(exif_row)
        exif_dates_added = True
    
    # DateTimeDigitized
    exif_date_digitized = _parse_exif_date(metadata.exif_DateTimeDigitized)
    if exif_date_digitized:
        exif_row = _create_date_row(
            "EXIF DateTimeDigitized", 
            exif_date_digitized.strftime("%Y-%m-%d %H:%M:%S"),
            tr("dialogs.details.exif_dates.digitized_desc"),
            'camera',
            DesignSystem.COLOR_ACCENT
        )
        layout.addWidget(exif_row)
        exif_dates_added = True
    
    # GPS DateStamp
    exif_gps_date = _parse_exif_date(metadata.exif_GPSDateStamp)
    if exif_gps_date:
        exif_row = _create_date_row(
            "EXIF GPS DateStamp", 
            exif_gps_date.strftime("%Y-%m-%d %H:%M:%S"),
            tr("dialogs.details.exif_dates.gps_desc"),
            'map-marker',
            DesignSystem.COLOR_ACCENT
        )
        layout.addWidget(exif_row)
        exif_dates_added = True
    
    # Separador después de EXIF si se agregó algo
    if exif_dates_added:
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background-color: {DesignSystem.COLOR_CARD_BORDER}; margin: {DesignSystem.SPACE_8}px 0;")
        layout.addWidget(separator)
    
    # === FECHA DEL NOMBRE DE ARCHIVO ===
    filename_date = extract_date_from_filename(metadata.path.name)
    if filename_date:
        filename_row = _create_date_row(
            tr("dialogs.details.exif_dates.filename_label"), 
            filename_date.strftime("%Y-%m-%d %H:%M:%S"),
            tr("dialogs.details.exif_dates.filename_desc"),
            'file-document-outline',
            DesignSystem.COLOR_INFO
        )
        layout.addWidget(filename_row)
    
    # === METADATA DE VIDEO ===
    # Para videos, exif_DateTime contiene la fecha de creación del video
    if metadata.is_video and exif_create_date:
        video_row = _create_date_row(
            tr("dialogs.details.exif_dates.video_metadata"), 
            exif_create_date.strftime("%Y-%m-%d %H:%M:%S"),
            tr("dialogs.details.exif_dates.video_metadata_desc"),
            'video',
            DesignSystem.COLOR_INFO
        )
        layout.addWidget(video_row)
    
    # Separador antes de fechas del sistema
    if filename_date or (metadata.is_video and exif_create_date):
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background-color: {DesignSystem.COLOR_CARD_BORDER};")
        layout.addWidget(separator)
    
    # === FECHAS DEL SISTEMA DE ARCHIVOS ===
    # NOTA: Las fechas del filesystem (ctime, mtime, atime) ya se muestran en la sección "Filesystem (RAW)"
    # por lo que no se repiten aquí para evitar duplicación
    
    group.setLayout(layout)
    return group


def _create_best_date_section(metadata: 'FileMetadata'):
    """Crea la sección especial para mostrar la mejor fecha disponible"""
    from PyQt6.QtWidgets import QGroupBox, QVBoxLayout
    from ui.styles.design_system import DesignSystem
    
    group = QGroupBox(tr("dialogs.details.section.best_date"))
    group.setStyleSheet(f"""
        QGroupBox {{
            font-size: {DesignSystem.FONT_SIZE_LG}px;
            font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
            color: {DesignSystem.COLOR_TEXT};
            border: 2px solid {DesignSystem.COLOR_SUCCESS};
            border-radius: {DesignSystem.RADIUS_LG}px;
            padding: {DesignSystem.SPACE_16}px;
            margin: 0;
            background-color: {DesignSystem.COLOR_SURFACE};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {DesignSystem.SPACE_12}px;
            padding: 0 {DesignSystem.SPACE_8}px;
            color: {DesignSystem.COLOR_SUCCESS};
            font-weight: {DesignSystem.FONT_WEIGHT_BOLD};
        }}
    """)
    
    layout = QVBoxLayout()
    layout.setContentsMargins(
        DesignSystem.SPACE_16, DesignSystem.SPACE_24, 
        DesignSystem.SPACE_16, DesignSystem.SPACE_16
    )
    layout.setSpacing(DesignSystem.SPACE_12)
    
    best_date_row = _create_date_row(
        tr("dialogs.details.best_date.label"), 
        metadata.best_date.strftime("%Y-%m-%d %H:%M:%S"),
        tr("dialogs.details.best_date.description", source=metadata.best_date_source),
        'calendar-check',
        DesignSystem.COLOR_SUCCESS
    )
    layout.addWidget(best_date_row)
    
    group.setLayout(layout)
    return group


def _create_info_row(title: str, value_text: str, description: str, icon_name: str, accent_color: str = None):
    """Crea una fila especializada para mostrar información con icono, título, valor y descripción
    
    Args:
        title: Título del campo
        value_text: Valor a mostrar
        description: Descripción explicativa
        icon_name: Nombre del icono MDI
        accent_color: Color del icono (opcional, por defecto COLOR_ACCENT)
    """
    from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
    from ui.styles.design_system import DesignSystem
    from ui.styles.icons import icon_manager
    
    if accent_color is None:
        accent_color = DesignSystem.COLOR_ACCENT
    
    widget = QWidget()
    main_layout = QHBoxLayout(widget)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(DesignSystem.SPACE_12)
    
    # Icono
    icon = icon_manager.get_icon(icon_name, size=DesignSystem.ICON_SIZE_MD, color=accent_color)
    icon_label = QLabel()
    icon_label.setPixmap(icon.pixmap(DesignSystem.ICON_SIZE_MD, DesignSystem.ICON_SIZE_MD))
    icon_label.setFixedSize(DesignSystem.ICON_SIZE_MD + 4, DesignSystem.ICON_SIZE_MD + 4)
    main_layout.addWidget(icon_label)
    
    # Contenido de información
    content_layout = QVBoxLayout()
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(DesignSystem.SPACE_2)
    
    # Título y valor
    title_label = QLabel(f"{title}: {value_text}")
    title_label.setStyleSheet(f"""
        color: {DesignSystem.COLOR_TEXT};
        font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
        font-size: {DesignSystem.FONT_SIZE_BASE}px;
    """)
    title_label.setWordWrap(True)
    content_layout.addWidget(title_label)
    
    # Descripción
    desc_label = QLabel(description)
    desc_label.setStyleSheet(f"""
        color: {DesignSystem.COLOR_TEXT_SECONDARY};
        font-size: {DesignSystem.FONT_SIZE_SM}px;
    """)
    desc_label.setWordWrap(True)
    content_layout.addWidget(desc_label)
    
    main_layout.addLayout(content_layout, 1)
    
    return widget


def _create_info_row_with_copy(
    title: str, 
    value_text: str, 
    description: str, 
    icon_name: str, 
    accent_color: str = None,
    parent_widget=None
):
    """Crea una fila con información y un botón para copiar el valor al portapapeles.
    
    Args:
        title: Título del campo
        value_text: Valor a mostrar y copiar
        description: Descripción explicativa
        icon_name: Nombre del icono MDI
        accent_color: Color del icono (opcional, por defecto COLOR_ACCENT)
        parent_widget: Widget padre para feedback visual
    """
    from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
    from PyQt6.QtCore import Qt, QSize, QTimer
    from ui.styles.design_system import DesignSystem
    from ui.styles.icons import icon_manager
    from utils.platform_utils import copy_to_clipboard
    
    if accent_color is None:
        accent_color = DesignSystem.COLOR_ACCENT
    
    widget = QWidget()
    main_layout = QHBoxLayout(widget)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(DesignSystem.SPACE_12)
    
    # Icono principal
    icon = icon_manager.get_icon(icon_name, size=DesignSystem.ICON_SIZE_MD, color=accent_color)
    icon_label = QLabel()
    icon_label.setPixmap(icon.pixmap(DesignSystem.ICON_SIZE_MD, DesignSystem.ICON_SIZE_MD))
    icon_label.setFixedSize(DesignSystem.ICON_SIZE_MD + 4, DesignSystem.ICON_SIZE_MD + 4)
    main_layout.addWidget(icon_label)
    
    # Contenido de información
    content_layout = QVBoxLayout()
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(DesignSystem.SPACE_2)
    
    # Título y valor
    title_label = QLabel(f"{title}: {value_text}")
    title_label.setStyleSheet(f"""
        color: {DesignSystem.COLOR_TEXT};
        font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
        font-size: {DesignSystem.FONT_SIZE_BASE}px;
    """)
    title_label.setWordWrap(True)
    content_layout.addWidget(title_label)
    
    # Descripción
    desc_label = QLabel(description)
    desc_label.setStyleSheet(f"""
        color: {DesignSystem.COLOR_TEXT_SECONDARY};
        font-size: {DesignSystem.FONT_SIZE_SM}px;
    """)
    desc_label.setWordWrap(True)
    content_layout.addWidget(desc_label)
    
    main_layout.addLayout(content_layout, 1)
    
    # Botón de copiar
    copy_btn = QPushButton()
    copy_btn.setToolTip("Copiar ruta al portapapeles")
    copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    icon_manager.set_button_icon(copy_btn, 'content-copy', size=16)
    copy_btn.setFixedSize(32, 32)
    copy_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            border: 1px solid {DesignSystem.COLOR_BORDER};
            border-radius: {DesignSystem.RADIUS_SM}px;
            padding: 4px;
        }}
        QPushButton:hover {{
            background-color: {DesignSystem.COLOR_BG_1};
            border-color: {DesignSystem.COLOR_PRIMARY};
        }}
        QPushButton:pressed {{
            background-color: {DesignSystem.COLOR_PRIMARY};
        }}
    """)
    
    def on_copy_clicked():
        """Copia el valor al portapapeles y muestra feedback visual."""
        if copy_to_clipboard(value_text):
            # Feedback visual: cambiar icono temporalmente a check
            icon_manager.set_button_icon(copy_btn, 'check', size=16, color=DesignSystem.COLOR_SUCCESS)
            copy_btn.setToolTip(tr("dialogs.details.copy_success"))
            
            # Restaurar icono original después de 1.5 segundos
            def restore_icon():
                icon_manager.set_button_icon(copy_btn, 'content-copy', size=16)
                copy_btn.setToolTip(tr("dialogs.details.copy_path_tooltip"))
            
            QTimer.singleShot(1500, restore_icon)
        else:
            # Error: mostrar icono de error
            icon_manager.set_button_icon(copy_btn, 'alert-circle', size=16, color=DesignSystem.COLOR_ERROR)
            copy_btn.setToolTip(tr("dialogs.details.copy_error"))
            
            def restore_icon():
                icon_manager.set_button_icon(copy_btn, 'content-copy', size=16)
                copy_btn.setToolTip(tr("dialogs.details.copy_path_tooltip"))
            
            QTimer.singleShot(2000, restore_icon)
    
    copy_btn.clicked.connect(on_copy_clicked)
    main_layout.addWidget(copy_btn)
    
    return widget


def _create_date_row(title: str, date_str: str, description: str, icon_name: str, accent_color: str):
    """Crea una fila especializada para mostrar información de fecha
    
    Alias de _create_info_row para mantener compatibilidad con código existente.
    """
    return _create_info_row(title, date_str, description, icon_name, accent_color)


def _get_file_type_display(file_path: Path) -> str:
    """Obtiene una descripción amigable del tipo de archivo"""
    from config import Config
    
    from utils.file_utils import get_file_type
    file_type = get_file_type(file_path)
    if file_type == 'image':
        return "Imagen"
    elif file_type == 'video':
        return "Video"
    else:
        return f"Archivo {file_path.suffix.upper()}"


def _open_file_and_close(file_path: Path, dialog):
    """Abre el archivo y cierra el diálogo"""
    open_file(file_path)
    dialog.accept()


def _open_folder_and_close(file_path: Path, dialog):
    """Abre la carpeta del archivo y cierra el diálogo"""
    open_folder(file_path.parent)
    dialog.accept()


def _reload_with_full_metadata(file_path: Path, parent_widget, additional_info, current_dialog):
    """Recarga el diálogo con búsqueda completa de metadatos
    
    Args:
        file_path: Ruta del archivo a analizar
        parent_widget: Widget padre
        additional_info: Información adicional
        current_dialog: Diálogo actual a cerrar
    """
    logger.info(f"Reloading dialog with forced metadata search for: {file_path.name}")
    
    # Cerrar el diálogo actual
    current_dialog.accept()
    
    # Reabrir con force_metadata_search=True
    show_file_details_dialog(
        file_path=file_path,
        parent_widget=parent_widget,
        additional_info=additional_info,
        force_metadata_search=True
    )





