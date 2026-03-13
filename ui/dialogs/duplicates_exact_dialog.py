# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Diálogo de gestión de copias exactas.

Muestra archivos que son IDÉNTICOS bit a bit (mismo SHA256), 
incluso si tienen nombres diferentes.

Diseño homogeneizado con VisualIdenticalDialog para consistencia.
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QFrame, QTreeWidget, QTreeWidgetItem, QLineEdit,
    QMessageBox, QWidget, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent

from services.result_types import ExactDuplicateGroup
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from utils.format_utils import format_size
from utils.file_utils import is_image_file, is_video_file
from utils.logger import get_logger
from utils.i18n import tr
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from ui.tools_definitions import TOOL_DUPLICATES_EXACT
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


class DuplicatesExactDialog(BaseDialog):
    """
    Diálogo para gestionar copias exactas.
    
    Muestra fotos y vídeos idénticos digitalmente (mismo SHA256),
    incluso si tienen nombres diferentes. Permite eliminar duplicados
    con diferentes estrategias de conservación.
    """
    
    # Constantes para paginación
    INITIAL_LOAD = 100
    LOAD_INCREMENT = 100
    WARNING_THRESHOLD = 500
    
    def __init__(self, analysis, parent=None):
        super().__init__(parent)
        self.logger = get_logger('ExactCopiesDialog')
        self.analysis = analysis
        self.repo = FileInfoRepositoryCache.get_instance()
        
        # Estrategia de conservación por defecto: mantener más antiguo
        self.keep_strategy = 'oldest'
        self.accepted_plan = None
        
        # Estado de grupos
        self.all_groups = analysis.groups
        self.filtered_groups = analysis.groups
        self.loaded_count = 0
        
        # Estado del filtro de tipo
        
        # Estado del filtro de origen de fecha
        self.current_source_filter = 'all'  # 'all' or specific source
        
        # Referencias a widgets
        self.tree_widget = None
        self.search_input = None
        self.filter_combo = None
        self.type_combo = None  # Combo de filtro de tipo
        self.status_chip = None  # Chip único de estado (X/Y)
        self.source_combo = None  # Filtro de origen de fecha
        self.filter_bar = None  # Barra de filtros unificada
        self.load_more_btn = None
        self.load_all_btn = None
        self.progress_indicator = None
        self.progress_bar_container = None
        self.progress_bar_fill = None
        self.delete_btn = None
        
        self._init_ui()
    
    # ========================================================================
    # MÉTODOS DE ACCESO A DATOS
    # ========================================================================
    
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
            
            keep_file = self._get_file_to_keep(group)
            
            for file_path in group.files:
                if file_path != keep_file:
                    total_recoverable += self._get_file_size(file_path)
        
        return total_recoverable
    
    def _get_file_to_keep(self, group: ExactDuplicateGroup) -> Path:
        """Determina qué archivo conservar según la estrategia."""
        if not group.files:
            return None
        
        if self.keep_strategy == 'oldest':
            return min(group.files, key=lambda f: self._get_best_date_timestamp(f))
        else:  # newest
            return max(group.files, key=lambda f: self._get_best_date_timestamp(f))
    
    # ========================================================================
    # CONSTRUCCIÓN DE UI
    # ========================================================================
    
    def _init_ui(self):
        """Configura la interfaz del diálogo."""
        self.setWindowTitle(TOOL_DUPLICATES_EXACT.title)
        self.setModal(True)
        self.resize(1200, 900)
        self.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(int(DesignSystem.SPACE_12))
        layout.setContentsMargins(0, 0, 0, int(DesignSystem.SPACE_20))
        
        # Header compacto con métricas
        self.header_frame = self._create_compact_header_with_metrics(
            icon_name=TOOL_DUPLICATES_EXACT.icon_name,
            title=TOOL_DUPLICATES_EXACT.title,
            description=TOOL_DUPLICATES_EXACT.short_description,
            metrics=[
                {
                    'value': str(self.analysis.total_groups),
                    'label': tr("dialogs.duplicates_exact.metric_groups"),
                    'color': DesignSystem.COLOR_PRIMARY
                },
                {
                    'value': str(self.analysis.total_duplicates),
                    'label': tr("dialogs.duplicates_exact.metric_copies"),
                    'color': DesignSystem.COLOR_WARNING
                },
                {
                    'value': format_size(self._calculate_recoverable_space()),
                    'label': tr("dialogs.duplicates_exact.metric_recoverable"),
                    'color': DesignSystem.COLOR_SUCCESS
                }
            ]
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
                tr("dialogs.duplicates_exact.warning_many_groups",
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
        
        # Paginación con explicación clara
        pagination_card = self._create_pagination_bar()
        content_layout.addWidget(pagination_card)
        
        # Opciones de seguridad
        security_options = self._create_security_options_section(
            show_backup=True,
            show_dry_run=True,
            backup_label=tr("dialogs.duplicates_exact.option_backup"),
            dry_run_label=tr("dialogs.duplicates_exact.option_dry_run")
        )
        content_layout.addWidget(security_options)
        
        # Botones de acción
        button_box = self.make_ok_cancel_buttons(
            ok_text=tr("dialogs.duplicates_exact.button_delete"),
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
            ('oldest', 'clock-outline', tr("dialogs.duplicates_exact.strategy.oldest_title"), tr("dialogs.duplicates_exact.strategy.oldest_desc")),
            ('newest', 'clock-fast', tr("dialogs.duplicates_exact.strategy.newest_title"), tr("dialogs.duplicates_exact.strategy.newest_desc")),
        ]
        
        frame = self._create_compact_strategy_selector(
            title=tr("dialogs.duplicates_exact.strategy.title"),
            description=tr("dialogs.duplicates_exact.strategy.description"),
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
        
        # Diccionario de etiquetas para el DesignSystem.get_filter_label_style()
        labels = {
            'search': tr("dialogs.duplicates_exact.filter.search"),
            'size': tr("dialogs.duplicates_exact.filter.size"),
            'groups': tr("dialogs.duplicates_exact.filter.groups"),
            'source': tr("dialogs.duplicates_exact.filter.source"),
            'type': tr("dialogs.duplicates_exact.filter.type")
        }
        
        # Configuración de filtros expandibles
        expandable_filters = [
            {
                'id': 'source',
                'type': 'combo',
                'label': labels['source'],
                'tooltip': tr("dialogs.duplicates_exact.filter.source_tooltip"),
                'options': source_options,
                'on_change': self._on_source_filter_changed,
                'default_index': 0,
                'min_width': 200
            },
            {
                'id': 'type',
                'type': 'combo',
                'label': labels['type'],
                'tooltip': tr("dialogs.duplicates_exact.filter.type_tooltip"),
                'options': [tr("common.filter.all"), tr("common.filter.photos"), tr("common.filter.videos")],
                'on_change': self._on_type_filter_changed,
                'default_index': 0,
                'min_width': 120
            }
        ]
        
        filter_bar = self._create_unified_filter_bar(
            on_search_changed=self._on_search_changed,
            on_size_filter_changed=self._on_filter_changed,
            expandable_filters=expandable_filters,
            is_files_mode=False,
            labels=labels
        )
        
        # Guardar referencias a los widgets
        self.search_input = filter_bar.search_input
        self.filter_combo = filter_bar.size_filter_combo
        self.status_chip = filter_bar.status_chip
        self.type_combo = filter_bar.filter_widgets.get('type')
        self.source_combo = filter_bar.filter_widgets.get('source')
        
        return filter_bar
    
    def _get_combo_style(self) -> str:
        """Retorna el estilo CSS para los ComboBox."""
        return f"""
            QComboBox {{
                background-color: {DesignSystem.COLOR_BG_1};
                border: 2px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_6}px {DesignSystem.SPACE_10}px;
                font-size: {DesignSystem.FONT_SIZE_SM}px;
                color: {DesignSystem.COLOR_TEXT};
                min-width: 90px;
            }}
            QComboBox:hover {{
                border-color: {DesignSystem.COLOR_PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
        """
    
    def _create_tree_widget(self) -> QTreeWidget:
        """Crea el widget de árbol para mostrar grupos."""
        headers = [tr("common.tree_header.groups_files"), tr("common.tree_header.size"), tr("common.tree_header.date"), tr("common.tree_header.origin"), tr("common.tree_header.location"), tr("common.tree_header.status")]
        column_widths = [300, 90, 130, 120, 200, 100]
        
        return create_groups_tree_widget(
            headers=headers,
            column_widths=column_widths,
            double_click_handler=self._on_item_double_clicked,
            context_menu_handler=self._show_context_menu
        )
    
    def _create_pagination_bar(self) -> QFrame:
        """
        Crea la barra de paginación con explicación clara del estado de carga.
        
        La carga progresiva funciona así:
        1. Inicialmente se cargan INITIAL_LOAD grupos (100 por defecto)
        2. El usuario puede cargar más grupos con "Cargar más"
        3. O cargar todos de una vez con "Cargar todos"
        
        Esto mejora el rendimiento en datasets grandes evitando
        renderizar miles de elementos de golpe.
        """
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
        
        # Indicador de progreso textual
        self.progress_indicator = QLabel()
        self.progress_indicator.setStyleSheet(f"""
            QLabel {{
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                font-size: {DesignSystem.FONT_SIZE_SM}px;
            }}
        """)
        self.progress_indicator.setToolTip(
            tr("dialogs.duplicates_exact.pagination.tooltip")
        )
        pagination_layout.addWidget(self.progress_indicator)
        
        # Barra de progreso visual
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
        self.load_all_btn.setToolTip(tr("dialogs.duplicates_exact.pagination.load_all_tooltip"))
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
            QPushButton:disabled {{
                background-color: {DesignSystem.COLOR_SURFACE_DISABLED};
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
            }}
        """)
        pagination_layout.addWidget(self.load_more_btn)
        
        return pagination_card
    
    # ========================================================================
    # LÓGICA DE CARGA PROGRESIVA
    # ========================================================================
    
    def _load_initial_groups(self):
        """
        Carga los grupos iniciales en el árbol.
        
        Este método reinicia el estado de carga y muestra los primeros
        INITIAL_LOAD grupos. Los grupos restantes se pueden cargar
        bajo demanda con _load_more_groups().
        """
        self.loaded_count = 0
        self.tree_widget.clear()
        self._load_groups_batch(self.INITIAL_LOAD)
    
    def _load_more_groups(self):
        """
        Carga el siguiente lote de grupos.
        
        Añade LOAD_INCREMENT grupos más a la lista, partiendo desde
        donde se quedó la carga anterior.
        """
        self._load_groups_batch(self.LOAD_INCREMENT)
    
    def _load_all_groups(self):
        """
        Carga todos los grupos restantes.
        
        Muestra confirmación si hay muchos grupos pendientes,
        ya que puede afectar al rendimiento.
        """
        remaining = len(self.filtered_groups) - self.loaded_count
        
        if remaining > 500:
            reply = QMessageBox.question(
                self,
                tr("common.dialog.load_all_groups_title"),
                tr("dialogs.duplicates_exact.pagination.load_all_msg",
                   count=remaining),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self._load_groups_batch(remaining)
    
    def _load_groups_batch(self, count: int):
        """
        Carga un lote de grupos en el árbol.
        
        Args:
            count: Número de grupos a cargar
        """
        start = self.loaded_count
        end = min(start + count, len(self.filtered_groups))
        
        for i in range(start, end):
            group = self.filtered_groups[i]
            self._add_group_to_tree(group, i + 1)
        
        self.loaded_count = end
        self._update_pagination_ui()
    
    def _add_group_to_tree(self, group: ExactDuplicateGroup, group_num: int):
        """Añade un grupo al árbol con estilo Material Design."""
        # Determinar archivo a conservar
        keep_file = self._get_file_to_keep(group)
        file_count = len(group.files)
        
        # Crear item de grupo
        group_item = QTreeWidgetItem()
        group_item.setText(0, tr("common.tree.group_label", num=group_num, count=file_count))
        
        # Aplicar estilo unificado de grupo
        apply_group_item_style(group_item, num_columns=6)
        
        # Tooltip informativo
        group_item.setToolTip(0, create_group_tooltip(
            group_num,
            tr("dialogs.duplicates_exact.tooltip.group_desc", count=file_count),
            tr("dialogs.duplicates_exact.tooltip.total_size", size=format_size(group.total_size))
        ))
        
        group_item.setData(0, Qt.ItemDataRole.UserRole, group)
        group_item.setExpanded(True)
        
        # Añadir archivos del grupo
        for file_path in group.files:
            file_size = self._get_file_size(file_path)
            is_keep = file_path == keep_file
            self._add_file_to_group(group_item, file_path, file_size, is_keep)
        
        self.tree_widget.addTopLevelItem(group_item)
    
    def _add_file_to_group(self, parent_item: QTreeWidgetItem, file_path: Path, 
                           file_size: int, is_keep: bool):
        """Añade un archivo a un grupo en el árbol."""
        file_item = QTreeWidgetItem()
        
        # Icono según tipo de archivo
        icon_name = get_file_icon_name(file_path)
        file_item.setIcon(0, icon_manager.get_icon(icon_name, size=18))
        
        # Nombre del archivo
        file_item.setText(0, file_path.name)
        
        # Tamaño
        file_item.setText(1, format_size(file_size))
        
        # Fecha y origen
        best_date, date_source = self.repo.get_best_date(file_path) if self.repo else (None, None)
        if best_date:
            file_item.setText(2, best_date.strftime("%d/%m/%Y %H:%M"))
            file_item.setText(3, date_source or "-")
        else:
            file_item.setText(2, "-")
            file_item.setText(3, "-")
        
        # Ubicación
        file_item.setText(4, str(file_path.parent))
        
        # Estado (conservar/eliminar)
        apply_file_item_status(file_item, is_keep, status_column=5)
        
        file_item.setData(0, Qt.ItemDataRole.UserRole, file_path)
        parent_item.addChild(file_item)
    
    def _update_pagination_ui(self):
        """Actualiza la UI de paginación con estado claro."""
        filtered_count = len(self.filtered_groups)
        loaded = self.loaded_count
        all_total = len(self.all_groups)
        
        # Usar método unificado para actualizar chip
        self._update_filter_chip(
            self.status_chip,
            filtered_count,
            all_total,
            loaded,
            is_files_mode=False
        )
        
        # Texto de progreso claro
        if filtered_count > 0:
            percent = (loaded / filtered_count) * 100
            self.progress_indicator.setText(
                tr("dialogs.duplicates_exact.pagination.progress_text",
                   percent=f"{percent:.0f}", loaded=loaded, total=filtered_count)
            )
            
            # Actualizar barra
            bar_width = self.progress_bar_container.width()
            fill_width = int(bar_width * loaded / filtered_count) if bar_width > 0 else 0
            self.progress_bar_fill.setGeometry(0, 0, fill_width, 8)
        else:
            self.progress_indicator.setText(tr("common.pagination.no_groups"))
            self.progress_bar_fill.setGeometry(0, 0, 0, 8)
        
        # Mostrar/ocultar botones según estado
        has_more = loaded < filtered_count
        self.load_more_btn.setVisible(has_more)
        self.load_more_btn.setEnabled(has_more)
        self.load_all_btn.setVisible(has_more and (filtered_count - loaded) > self.LOAD_INCREMENT)
        
        if has_more:
            remaining = filtered_count - loaded
            to_load = min(self.LOAD_INCREMENT, remaining)
            self.load_more_btn.setText(tr("common.pagination.load_n_more", count=to_load))
            self.load_more_btn.setToolTip(tr("dialogs.duplicates_exact.pagination.load_more_tooltip", count=to_load, remaining=remaining))
        else:
            self.load_more_btn.setText(tr("dialogs.duplicates_exact.pagination.all_loaded"))
    
    # ========================================================================
    # MANEJADORES DE EVENTOS
    # ========================================================================
    
    def _on_strategy_changed(self, strategy: str):
        """Maneja el cambio de estrategia de conservación."""
        if strategy == self.keep_strategy:
            return
        
        self.keep_strategy = strategy
        
        # Actualizar botones
        for s, btn in self.strategy_buttons.items():
            btn.setChecked(s == strategy)
        
        # Recargar árbol para reflejar nueva estrategia
        self._load_initial_groups()
        
        # Actualizar métrica de espacio recuperable
        self._update_header_metric(
            self.header_frame, 
            tr("dialogs.duplicates_exact.metric_recoverable"), 
            format_size(self._calculate_recoverable_space())
        )
    
    def _on_search_changed(self, text: str):
        """Maneja cambios en la búsqueda."""
        self._apply_filters()
    
    def _on_filter_changed(self, index: int):
        """Maneja cambios en cualquier filtro."""
        self._apply_filters()
    
    def _on_type_filter_changed(self, index: int):
        """Maneja cambios en el filtro de tipo de archivo."""
        self._apply_filters()
    
    def _on_source_filter_changed(self, index: int):
        """Maneja cambios en el filtro de origen de fecha."""
        self._apply_filters()
    
    def _group_matches_type_filter(self, group: ExactDuplicateGroup) -> bool:
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
    
    def _group_matches_source_filter(self, group: ExactDuplicateGroup) -> bool:
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
    
    def _apply_filters(self):
        """Aplica todos los filtros activos (búsqueda, tipo, tamaño, origen)."""
        search_text = self.search_input.text().lower()
        size_filter_index = self.filter_combo.currentIndex()
        
        filtered = []
        
        for group in self.all_groups:
            # Filtro por tipo de archivo (imágenes/vídeos)
            if not self._group_matches_type_filter(group):
                continue
            
            # Filtro por origen de fecha
            if not self._group_matches_source_filter(group):
                continue
            
            # Filtro de búsqueda por texto
            if search_text:
                matches = False
                for f in group.files:
                    if search_text in str(f).lower():
                        matches = True
                        break
                if not matches:
                    continue
            
            # Filtro por tamaño/cantidad
            if size_filter_index == 1:  # >10 MB
                if group.total_size < 10 * 1024 * 1024:
                    continue
            elif size_filter_index == 2:  # >50 MB
                if group.total_size < 50 * 1024 * 1024:
                    continue
            elif size_filter_index == 3:  # >100 MB
                if group.total_size < 100 * 1024 * 1024:
                    continue
            elif size_filter_index == 4:  # 3+ copias
                if len(group.files) < 3:
                    continue
            elif size_filter_index == 5:  # 5+ copias
                if len(group.files) < 5:
                    continue
            
            filtered.append(group)
        
        self.filtered_groups = filtered
        
        # Actualizar métrica de espacio recuperable
        self._update_header_metric(
            self.header_frame, 
            tr("dialogs.duplicates_exact.metric_recoverable"), 
            format_size(self._calculate_recoverable_space())
        )
        
        # Recargar árbol con grupos filtrados
        self._load_initial_groups()
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Maneja doble clic: expande grupos o abre archivos."""
        handle_tree_item_double_click(item, column, self)
    
    def _show_context_menu(self, pos):
        """Muestra menú contextual para archivos."""
        show_file_context_menu(
            self.tree_widget, pos, self, 
            details_callback=self._show_file_details
        )
    
    def _show_file_details(self, file_path: Path):
        """Muestra diálogo con detalles del archivo."""
        status_info = None
        
        for group in self.filtered_groups:
            if file_path in group.files:
                keep_file = self._get_file_to_keep(group)
                is_keep = file_path == keep_file
                
                status_info = {
                    'metadata': {
                        tr("common.details.status"): tr("common.status.will_keep") if is_keep else tr("common.status.will_delete"),
                        tr("common.groups"): tr("dialogs.duplicates_exact.details.group_desc", count=len(group.files)),
                        tr("common.details.group_space"): format_size(group.total_size),
                        tr("common.details.strategy"): self._strategy_name()
                    }
                }
                break
        
        show_file_details_dialog(file_path, self, status_info)
    
    def _strategy_name(self) -> str:
        """Devuelve el nombre legible de la estrategia."""
        names = {
            'oldest': tr("common.strategy_name.oldest"),
            'newest': tr("common.strategy_name.newest")
        }
        return names.get(self.keep_strategy, self.keep_strategy)
    
    # ========================================================================
    # EVENTOS DE DIÁLOGO
    # ========================================================================
    
    def showEvent(self, event: QShowEvent):
        """Actualiza la barra de progreso cuando el diálogo se muestra."""
        super().showEvent(event)
        self._update_pagination_ui()
    
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
        
        # Guardar plan para ejecución
        self.accepted_plan = {
            'analysis': self.analysis,
            'groups': self.filtered_groups,
            'files_to_delete': files_to_delete,
            'keep_strategy': self.keep_strategy,
            'create_backup': self.is_backup_enabled(),
            'dry_run': self.is_dry_run_enabled()
        }
        
        super().accept()
