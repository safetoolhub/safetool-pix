# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Diálogo de gestión de copias visuales idénticas.

Muestra archivos que son visualmente IDÉNTICOS al 100% aunque tengan
diferente resolución, compresión o metadatos (fechas, EXIF, etc.).

Diseño similar a DuplicatesExactDialog pero optimizado para el caso
de uso de detección visual (ej: fotos de WhatsApp, copias redimensionadas).
"""

from pathlib import Path


from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QFrame, QTreeWidget, QTreeWidgetItem, QLineEdit,
    QMessageBox, QWidget, QDialogButtonBox
)
from PyQt6.QtCore import Qt

from services.result_types import VisualIdenticalAnalysisResult, VisualIdenticalGroup
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from utils.format_utils import format_size
from utils.file_utils import is_image_file, is_video_file
from utils.logger import get_logger
from utils.i18n import tr
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from ui.tools_definitions import TOOL_VISUAL_IDENTICAL
from .base_dialog import BaseDialog
from .dialog_utils import (
    show_file_details_dialog, 
    create_groups_tree_widget, 
    handle_tree_item_double_click, 
    show_file_context_menu,
    apply_group_item_style,
    create_group_tooltip,
    apply_file_item_status,
    get_file_icon_name
)


class VisualIdenticalDialog(BaseDialog):
    """
    Diálogo para gestionar copias visuales idénticas.
    
    Muestra archivos visualmente idénticos (mismo hash perceptual)
    aunque tengan diferente tamaño, resolución o metadatos.
    Permite eliminar duplicados con estrategias automáticas.
    """
    
    # Constantes para paginación
    INITIAL_LOAD = 100
    LOAD_INCREMENT = 100
    WARNING_THRESHOLD = 500
    
    def __init__(self, analysis: VisualIdenticalAnalysisResult, parent=None):
        super().__init__(parent)
        self.logger = get_logger('VisualIdenticalDialog')
        self.analysis = analysis
        self.repo = FileInfoRepositoryCache.get_instance()
        
        # Estrategia de conservación por defecto: mantener mejor calidad (más grande)
        self.keep_strategy = 'largest'
        self.accepted_plan = None
        
        # Estado de grupos
        self.all_groups = analysis.groups
        self.filtered_groups = analysis.groups
        self.loaded_count = 0
        
        # Referencias a widgets
        self.tree_widget = None
        self.search_input = None
        self.filter_combo = None
        self.type_combo = None  # Combo de filtro de tipo
        self.status_chip = None  # Chip único de estado
        self.source_combo = None  # Filtro de origen de fecha
        self.filter_bar = None  # Barra de filtros unificada
        self.load_more_btn = None
        self.load_all_btn = None
        self.progress_indicator = None
        self.progress_bar_container = None
        self.progress_bar_fill = None
        self.delete_btn = None
        
        self._init_ui()
    
    def _get_best_date_timestamp(self, file_path: Path) -> float:
        """Obtiene el timestamp de la mejor fecha disponible."""
        if self.repo:
            best_date, _ = self.repo.get_best_date(file_path)
            if best_date:
                return best_date.timestamp()
            
            fs_mtime = self.repo.get_filesystem_modification_date(file_path)
            if fs_mtime:
                return fs_mtime.timestamp()
        
        return file_path.stat().st_mtime if file_path.exists() else 0
    
    def _get_file_size(self, file_path: Path) -> int:
        """Obtiene el tamaño del archivo desde caché o disco."""
        if self.repo:
            meta = self.repo.get_file_metadata(file_path)
            if meta:
                return meta.fs_size
        return file_path.stat().st_size if file_path.exists() else 0
    
    def _calculate_recoverable_space(self) -> int:
        """Calcula el espacio total recuperable según la estrategia actual."""
        total_recoverable = 0
        
        for group in self.filtered_groups:
            if len(group.files) < 2:
                continue
                
            # Obtener tamaños
            sizes = []
            for f in group.files:
                sizes.append((f, self._get_file_size(f)))
            
            # Determinar qué archivo mantener según estrategia
            if self.keep_strategy == 'largest':
                keep_file = max(sizes, key=lambda x: x[1])[0]
            elif self.keep_strategy == 'smallest':
                keep_file = min(sizes, key=lambda x: x[1])[0]
            elif self.keep_strategy == 'oldest':
                keep_file = min(group.files, key=lambda f: self._get_best_date_timestamp(f))
            else:  # newest
                keep_file = max(group.files, key=lambda f: self._get_best_date_timestamp(f))
            
            # Sumar tamaños de archivos a eliminar
            for f, size in sizes:
                if f != keep_file:
                    total_recoverable += size
        
        return total_recoverable
    
    def _init_ui(self):
        """Configura la interfaz del diálogo."""
        self.setWindowTitle(TOOL_VISUAL_IDENTICAL.title)
        self.setModal(True)
        self.resize(1350, 900)
        self.setMinimumSize(1150, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(int(DesignSystem.SPACE_12))
        layout.setContentsMargins(0, 0, 0, int(DesignSystem.SPACE_20))
        
        # Header compacto con métricas
        self.header_frame = self._create_compact_header_with_metrics(
            icon_name=TOOL_VISUAL_IDENTICAL.icon_name,
            title=TOOL_VISUAL_IDENTICAL.title,
            description=TOOL_VISUAL_IDENTICAL.short_description,
            metrics=[
                {
                    'value': str(self.analysis.total_groups),
                    'label': tr("dialogs.visual_identical.metric_groups"),
                    'color': DesignSystem.COLOR_PRIMARY
                },
                {
                    'value': str(self.analysis.total_duplicates),
                    'label': tr("dialogs.visual_identical.metric_duplicates"),
                    'color': DesignSystem.COLOR_WARNING
                },
                {
                    'value': format_size(self._calculate_recoverable_space()),
                    'label': tr("dialogs.visual_identical.metric_recoverable"),
                    'color': DesignSystem.COLOR_SUCCESS
                }
            ],
            tip_message=tr("dialogs.visual_identical.tip_message")
        )
        layout.addWidget(self.header_frame)
        
        # Contenedor con margen para el resto
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setSpacing(int(DesignSystem.SPACE_16))
        content_layout.setContentsMargins(
            int(DesignSystem.SPACE_24),
            int(DesignSystem.SPACE_12),
            int(DesignSystem.SPACE_24),
            0
        )
        layout.addWidget(content_container)
        
        # Selector de estrategia
        self.strategy_selector = self._create_strategy_selector()
        content_layout.addWidget(self.strategy_selector)
        
        # Advertencia si hay muchos grupos
        if len(self.all_groups) > self.WARNING_THRESHOLD:
            warning = QLabel(
                tr("dialogs.visual_identical.warning_many_groups", 
                   count=len(self.all_groups), initial=self.INITIAL_LOAD)
            )
            warning.setTextFormat(Qt.TextFormat.RichText)
            warning.setWordWrap(True)
            warning.setStyleSheet(f"""
                QLabel {{
                    background: {DesignSystem.COLOR_INFO_BG};
                    border: 1px solid {DesignSystem.COLOR_INFO};
                    border-radius: {DesignSystem.RADIUS_BASE}px;
                    padding: {DesignSystem.SPACE_12}px;
                    color: {DesignSystem.COLOR_TEXT};
                    font-size: {DesignSystem.FONT_SIZE_SM}px;
                }}
            """)
            content_layout.addWidget(warning)
        
        # Barra de filtros unificada
        self.filter_bar = self._create_filter_bar()
        content_layout.addWidget(self.filter_bar)
        
        # Árbol de grupos
        self.tree_widget = self._create_tree_widget()
        content_layout.addWidget(self.tree_widget)
        
        # Paginación
        pagination_card = self._create_pagination_bar()
        content_layout.addWidget(pagination_card)
        
        # Opciones de seguridad
        security_options = self._create_security_options_section(
            show_backup=True,
            show_dry_run=True,
            backup_label=tr("dialogs.visual_identical.option_backup"),
            dry_run_label=tr("dialogs.visual_identical.option_dry_run")
        )
        content_layout.addWidget(security_options)
        
        # Botones de acción
        button_box = self.make_ok_cancel_buttons(
            ok_text=tr("dialogs.visual_identical.button_delete"),
            ok_enabled=len(self.all_groups) > 0,
            button_style='danger'
        )
        self.delete_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        content_layout.addWidget(button_box)
        
        # Cargar grupos iniciales
        self._load_initial_groups()
    
    def _create_strategy_selector(self) -> QFrame:
        """Crea el selector de estrategia de conservación usando método centralizado."""
        strategies = [
            ('largest', 'arrow-expand-all', tr("dialogs.visual_identical.strategy.largest_title"), tr("dialogs.visual_identical.strategy.largest_desc")),
            ('smallest', 'arrow-collapse-all', tr("dialogs.visual_identical.strategy.smallest_title"), tr("dialogs.visual_identical.strategy.smallest_desc")),
            ('oldest', 'clock-outline', tr("dialogs.visual_identical.strategy.oldest_title"), tr("dialogs.visual_identical.strategy.oldest_desc")),
            ('newest', 'clock-fast', tr("dialogs.visual_identical.strategy.newest_title"), tr("dialogs.visual_identical.strategy.newest_desc")),
        ]
        
        frame = self._create_compact_strategy_selector(
            title=tr("dialogs.visual_identical.strategy.title"),
            description=tr("dialogs.visual_identical.strategy.description"),
            strategies=strategies,
            current_strategy=self.keep_strategy,
            on_strategy_changed=self._on_strategy_changed
        )
        
        # Guardar referencia a los botones para actualizarlos posteriormente
        self.strategy_buttons = frame.strategy_buttons
        
        return frame
    
    def _create_filter_bar(self) -> QFrame:
        """Crea la barra de filtros unificada."""
        # Opciones para filtro de origen de fecha (usar constantes de BaseDialog)
        source_options = self.DATE_SOURCE_FILTER_OPTIONS
        
        # Diccionario de etiquetas
        labels = {
            'search': tr("dialogs.visual_identical.filter.search"),
            'size': tr("dialogs.visual_identical.filter.size"),
            'groups': tr("dialogs.visual_identical.filter.groups"),
            'source': tr("dialogs.visual_identical.filter.source"),
            'type': tr("dialogs.visual_identical.filter.type")
        }
        
        # Configuración de filtros expandibles
        expandable_filters = [
            {
                'id': 'source',
                'type': 'combo',
                'label': labels['source'],
                'tooltip': tr("dialogs.visual_identical.filter.source_tooltip"),
                'options': source_options,
                'on_change': self._on_source_filter_changed,
                'default_index': 0,
                'min_width': 200
            },
            {
                'id': 'type',
                'type': 'combo',
                'label': labels['type'],
                'tooltip': tr("dialogs.visual_identical.filter.type_tooltip"),
                'options': [tr("common.filter.all"), tr("common.filter.photos"), tr("common.filter.videos")],
                'on_change': self._on_type_filter_changed,
                'default_index': 0,
                'min_width': 120
            }
        ]
        
        # Opciones de filtro de tamaño específicas para este diálogo
        size_options = [
            tr("common.filter.all"),
            tr("common.filter.gt_10mb"),
            tr("common.filter.gt_50mb"),
            tr("dialogs.visual_identical.filter.size_variation"),
            tr("common.filter.3_plus_copies"),
            tr("common.filter.5_plus_copies")
        ]
        
        filter_bar = self._create_unified_filter_bar(
            on_search_changed=self._on_search_changed,
            on_size_filter_changed=self._on_filter_changed,
            expandable_filters=expandable_filters,
            size_filter_options=size_options,
            is_files_mode=False,
            labels=labels
        )
        
        # Guardar referencias a los widgets
        self.search_input = filter_bar.search_input
        self.filter_combo = filter_bar.size_filter_combo
        self.status_chip = filter_bar.status_chip
        self.source_combo = filter_bar.filter_widgets.get('source')
        self.type_combo = filter_bar.filter_widgets.get('type')
        
        return filter_bar
    
    def _on_source_filter_changed(self, index: int):
        """Maneja cambios en el filtro de origen de fecha."""
        self._apply_filters()
    
    def _on_type_filter_changed(self, index: int):
        """Maneja cambios en el filtro de tipo de archivo."""
        self._apply_filters()
    
    def _group_matches_type_filter(self, group: VisualIdenticalGroup) -> bool:
        """
        Verifica si un grupo coincide con el filtro de tipo de archivo.
        
        Un grupo coincide si AL MENOS UN archivo del grupo es del tipo seleccionado.
        """
        if not self.type_combo:
            return True
            
        type_filter = self.type_combo.currentText()
        if type_filter == tr("common.filter.all"):
            return True
        
        for file_path in group.files:
            if type_filter == tr("common.filter.photos") and is_image_file(file_path):
                return True
            elif type_filter == tr("common.filter.videos") and is_video_file(file_path):
                return True
        
        return False
    
    def _group_matches_source_filter(self, group: VisualIdenticalGroup) -> bool:
        """Verifica si un grupo coincide con el filtro de origen de fecha."""
        if not self.source_combo:
            return True
        
        source_filter = self.source_combo.currentText()
        if source_filter == self.DATE_SOURCE_FILTER_ALL:
            return True
        
        # Verificar si algún archivo del grupo tiene el origen de fecha seleccionado
        for file_path in group.files:
            _, source = self.repo.get_best_date(file_path) if self.repo else (None, None)
            if source and self._matches_source_filter(source, source_filter):
                return True
        
        return False
    
    def _create_tree_widget(self) -> QTreeWidget:
        """Crea el widget de árbol para mostrar grupos."""
        headers = [tr("common.tree_header.groups_files"), tr("common.tree_header.size"), tr("common.tree_header.date"), tr("common.tree_header.date_source"), tr("common.tree_header.location"), tr("common.tree_header.status")]
        column_widths = [300, 90, 140, 140, 200, 100]
        
        return create_groups_tree_widget(
            headers=headers,
            column_widths=column_widths,
            double_click_handler=self._on_item_double_clicked,
            context_menu_handler=self._show_context_menu
        )
    
    def _create_pagination_bar(self) -> QFrame:
        """Crea la barra de paginación."""
        pagination_card = QFrame()
        pagination_card.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_BG_1};
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_LG}px;
                padding: {DesignSystem.SPACE_12}px {DesignSystem.SPACE_16}px;
            }}
        """)
        
        pagination_layout = QHBoxLayout(pagination_card)
        pagination_layout.setSpacing(int(DesignSystem.SPACE_12))
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        
        # Indicador de progreso
        self.progress_indicator = QLabel()
        self.progress_indicator.setStyleSheet(f"""
            QLabel {{
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                font-size: {DesignSystem.FONT_SIZE_SM}px;
            }}
        """)
        pagination_layout.addWidget(self.progress_indicator)
        
        # Barra de progreso
        self.progress_bar_container = QFrame()
        self.progress_bar_container.setFixedHeight(8)
        self.progress_bar_container.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_BORDER};
                border-radius: 4px;
            }}
        """)
        
        self.progress_bar_fill = QFrame(self.progress_bar_container)
        self.progress_bar_fill.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                border-radius: 4px;
            }}
        """)
        self.progress_bar_fill.setGeometry(0, 0, 0, 8)
        
        pagination_layout.addWidget(self.progress_bar_container, 1)
        
        # Botón cargar todos
        self.load_all_btn = QPushButton(tr("common.pagination.load_all"))
        icon_manager.set_button_icon(self.load_all_btn, 'download', size=16)
        self.load_all_btn.clicked.connect(self._load_all_groups)
        self.load_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {DesignSystem.COLOR_PRIMARY};
                border: 2px solid {DesignSystem.COLOR_PRIMARY};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_8}px {DesignSystem.SPACE_16}px;
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                color: {DesignSystem.COLOR_PRIMARY_TEXT};
            }}
        """)
        self.load_all_btn.hide()
        pagination_layout.addWidget(self.load_all_btn)
        
        # Botón cargar más
        self.load_more_btn = QPushButton(tr("common.pagination.load_more"))
        icon_manager.set_button_icon(self.load_more_btn, 'refresh', size=18)
        self.load_more_btn.clicked.connect(self._load_more_groups)
        self.load_more_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                color: {DesignSystem.COLOR_PRIMARY_TEXT};
                border: none;
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_10}px {DesignSystem.SPACE_20}px;
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_PRIMARY_HOVER};
            }}
        """)
        pagination_layout.addWidget(self.load_more_btn)
        
        return pagination_card
    
    def _load_initial_groups(self):
        """Carga los grupos iniciales en el árbol."""
        self.loaded_count = 0
        self.tree_widget.clear()
        self._load_more_groups()
    
    def _load_more_groups(self):
        """Carga más grupos en el árbol."""
        start = self.loaded_count
        end = min(start + self.LOAD_INCREMENT, len(self.filtered_groups))
        
        for i in range(start, end):
            group = self.filtered_groups[i]
            self._add_group_to_tree(group, i + 1)
        
        self.loaded_count = end
        self._update_pagination_ui()
    
    def _load_all_groups(self):
        """Carga todos los grupos restantes."""
        if len(self.filtered_groups) > 1000:
            reply = QMessageBox.question(
                self,
                tr("common.dialog.load_all_groups_title"),
                tr("common.dialog.load_all_groups_msg", count=len(self.filtered_groups)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        while self.loaded_count < len(self.filtered_groups):
            self._load_more_groups()
    
    def _add_group_to_tree(self, group: VisualIdenticalGroup, group_num: int):
        """Añade un grupo al árbol con estilo Material Design."""
        from .dialog_utils import apply_group_item_style, create_group_tooltip
        
        # Determinar archivo a conservar
        keep_file = self._get_file_to_keep(group)
        file_count = len(group.files)
        
        # Crear item de grupo
        group_item = QTreeWidgetItem()
        group_item.setText(0, tr("common.tree.group_label", num=group_num, count=file_count))
        # Las otras columnas quedan vacías para grupos - solo se usan para archivos
        
        # Aplicar estilo unificado de grupo
        apply_group_item_style(group_item, num_columns=5)
        
        # Tooltip informativo sobre doble click
        extra_info = ""
        if group.size_variation_percent > 10:
            extra_info = tr("dialogs.visual_identical.tooltip.size_variation", pct=group.size_variation_percent)
        
        group_item.setToolTip(0, create_group_tooltip(
            group_num,
            tr("dialogs.visual_identical.tooltip.group_desc", count=file_count),
            extra_info
        ))
        
        group_item.setData(0, Qt.ItemDataRole.UserRole, group)
        group_item.setExpanded(True)
        
        # Añadir archivos del grupo
        for i, file_path in enumerate(group.files):
            file_size = group.file_sizes[i] if i < len(group.file_sizes) else 0
            is_keep = file_path == keep_file
            
            self._add_file_to_group(group_item, file_path, file_size, is_keep)
        
        self.tree_widget.addTopLevelItem(group_item)
    
    def _add_file_to_group(self, parent_item: QTreeWidgetItem, file_path: Path, 
                           file_size: int, is_keep: bool):
        """Añade un archivo a un grupo en el árbol."""
        from .dialog_utils import apply_file_item_status, get_file_icon_name
        from ui.styles.icons import icon_manager
        
        file_item = QTreeWidgetItem()
        
        # Icono según tipo de archivo
        icon_name = get_file_icon_name(file_path)
        file_item.setIcon(0, icon_manager.get_icon(icon_name, size=18))
        
        # Nombre del archivo
        file_item.setText(0, file_path.name)
        
        # Tamaño
        file_item.setText(1, format_size(file_size))
        
        # Fecha
        best_date, source = self.repo.get_best_date(file_path) if self.repo else (None, None)
        if best_date:
            file_item.setText(2, best_date.strftime("%Y-%m-%d %H:%M"))
        else:
            file_item.setText(2, "-")
        
        # Origen Fecha
        if source:
            file_item.setText(3, source)
        else:
            file_item.setText(3, "-")
        
        # Ubicación
        file_item.setText(4, str(file_path.parent))
        
        # Estado (conservar/eliminar) - usar función común
        apply_file_item_status(file_item, is_keep, status_column=5)
        
        file_item.setData(0, Qt.ItemDataRole.UserRole, file_path)
        parent_item.addChild(file_item)
    
    def _get_file_to_keep(self, group: VisualIdenticalGroup) -> Path:
        """Determina qué archivo conservar según la estrategia."""
        if not group.files:
            return None
        
        if self.keep_strategy == 'largest':
            if group.file_sizes:
                max_idx = group.file_sizes.index(max(group.file_sizes))
                return group.files[max_idx]
            return max(group.files, key=lambda f: self._get_file_size(f))
        
        elif self.keep_strategy == 'smallest':
            if group.file_sizes:
                min_idx = group.file_sizes.index(min(group.file_sizes))
                return group.files[min_idx]
            return min(group.files, key=lambda f: self._get_file_size(f))
        
        elif self.keep_strategy == 'oldest':
            return min(group.files, key=lambda f: self._get_best_date_timestamp(f))
        
        else:  # newest
            return max(group.files, key=lambda f: self._get_best_date_timestamp(f))
    
    def _update_pagination_ui(self):
        """Actualiza la UI de paginación."""
        total = len(self.filtered_groups)
        loaded = self.loaded_count
        all_total = len(self.all_groups)
        
        # Usar método unificado para actualizar chip
        self._update_filter_chip(
            self.status_chip,
            total,
            all_total,
            loaded,
            is_files_mode=False
        )
        
        # Progreso
        if total > 0:
            percent = (loaded / total) * 100
            self.progress_indicator.setText(tr("common.pagination.progress_text", percent=f"{percent:.0f}", loaded=loaded, total=total))
            
            # Actualizar barra
            bar_width = self.progress_bar_container.width()
            fill_width = int(bar_width * loaded / total)
            self.progress_bar_fill.setGeometry(0, 0, fill_width, 8)
        else:
            self.progress_indicator.setText(tr("common.pagination.no_groups"))
            self.progress_bar_fill.setGeometry(0, 0, 0, 8)
        
        # Mostrar/ocultar botones
        has_more = loaded < total
        self.load_more_btn.setVisible(has_more)
        self.load_all_btn.setVisible(has_more and total > self.LOAD_INCREMENT * 2)
        
        if has_more:
            remaining = total - loaded
            self.load_more_btn.setText(tr("common.pagination.load_n_more", count=min(self.LOAD_INCREMENT, remaining)))
    
    def _on_strategy_changed(self, strategy: str):
        """Maneja el cambio de estrategia."""
        self.keep_strategy = strategy
        
        # Actualizar botones
        for s, btn in self.strategy_buttons.items():
            btn.setChecked(s == strategy)
        
        # Recargar árbol para reflejar nueva estrategia
        self._load_initial_groups()
        
        # Actualizar métrica de espacio recuperable
        self._update_header_metric(
            self.header_frame, 
            tr("dialogs.visual_identical.metric_recoverable"), 
            format_size(self._calculate_recoverable_space())
        )
    
    def _on_search_changed(self, text: str):
        """Maneja cambios en la búsqueda."""
        self._apply_filters()
    
    def _on_filter_changed(self, index: int):
        """Maneja cambios en el filtro."""
        self._apply_filters()
    
    def _apply_filters(self):
        """Aplica filtros de búsqueda, tamaño, origen y tipo."""
        search_text = self.search_input.text().lower()
        filter_index = self.filter_combo.currentIndex()
        
        filtered = []
        
        for group in self.all_groups:
            # Filtro por tipo de archivo (imágenes/vídeos)
            if not self._group_matches_type_filter(group):
                continue
            
            # Filtro por origen de fecha
            if not self._group_matches_source_filter(group):
                continue
            
            # Filtro de búsqueda
            if search_text:
                matches = False
                for f in group.files:
                    if search_text in str(f).lower():
                        matches = True
                        break
                if not matches:
                    continue
            
            # Filtro por tamaño/cantidad
            if filter_index == 1:  # >10 MB
                if group.total_size < 10 * 1024 * 1024:
                    continue
            elif filter_index == 2:  # >50 MB
                if group.total_size < 50 * 1024 * 1024:
                    continue
            elif filter_index == 3:  # Mucha variación
                if group.size_variation_percent < 50:
                    continue
            elif filter_index == 4:  # 3+ copias
                if len(group.files) < 3:
                    continue
            elif filter_index == 5:  # 5+ copias
                if len(group.files) < 5:
                    continue
            
            filtered.append(group)
        
        self.filtered_groups = filtered
        self._load_initial_groups()
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Maneja doble clic: expande grupos o abre archivos."""
        from .dialog_utils import handle_tree_item_double_click
        handle_tree_item_double_click(item, column, self)
    
    def _show_context_menu(self, pos):
        """Muestra menú contextual para archivos individuales."""
        from .dialog_utils import show_file_context_menu
        show_file_context_menu(self.tree_widget, pos, self, details_callback=self._show_file_details)
    
    def _show_file_details(self, file_path: Path):
        """Muestra diálogo con detalles del archivo."""
        # Determinar el estado del archivo (mantener/eliminar)
        # Buscar en qué grupo está este archivo
        status_info = None
        for group in self.filtered_groups:
            if file_path in group.files:
                # Determinar qué archivo se mantiene
                keep_file = self._get_file_to_keep(group)
                
                is_keep = file_path == keep_file
                status_info = {
                    'metadata': {
                        tr("common.details.status"): tr("common.status.will_keep") if is_keep else tr("common.status.will_delete"),
                        tr("common.details.group_space"): format_size(group.total_size),
                        tr("common.details.strategy"): self._strategy_name()
                    }
                }
                break
        
        show_file_details_dialog(file_path, self, status_info)
    
    def accept(self):
        """Maneja la aceptación del diálogo."""
        # Recopilar archivos a eliminar
        files_to_delete = []
        
        for group in self.filtered_groups:
            keep_file = self._get_file_to_keep(group)
            for f in group.files:
                if f != keep_file:
                    files_to_delete.append(f)
        
        if not files_to_delete:
            self.show_no_items_message(tr("common.files"))
            return
        
        # Guardar plan para ejecución (incluye analysis para consistencia)
        self.accepted_plan = {
            'analysis': self.analysis,  # Añadido para consistencia con otros diálogos
            'groups': self.filtered_groups,  # Grupos para referencia
            'files_to_delete': files_to_delete,
            'keep_strategy': self.keep_strategy,
            'create_backup': self.is_backup_enabled(),
            'dry_run': self.is_dry_run_enabled()
        }
        
        super().accept()
    
    def _strategy_name(self) -> str:
        """Returns human-readable strategy name."""
        names = {
            'largest': tr("common.strategy_name.largest"),
            'smallest': tr("common.strategy_name.smallest"),
            'oldest': tr("common.strategy_name.oldest"),
            'newest': tr("common.strategy_name.newest")
        }
        return names.get(self.keep_strategy, self.keep_strategy)
