# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Diálogo de Organización de Archivos
Permite elegir el tipo de organización en tiempo real y ver los resultados dinámicamente
"""
from pathlib import Path
from collections import defaultdict
from typing import Optional

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QDialogButtonBox, QLabel,
    QTreeWidget, QTreeWidgetItem, QPushButton, QFrame,
    QWidget, QProgressBar, QStackedWidget, QGridLayout
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt

from utils.format_utils import format_size
from utils.file_utils import is_whatsapp_file
from utils.i18n import tr
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from ui.tools_definitions import TOOL_FILE_ORGANIZER
from utils.logger import get_logger
from services.file_organizer_service import FileOrganizerService, OrganizationType
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from services.result_types import OrganizationAnalysisResult
from ui.workers import FileOrganizerAnalysisWorker
from .base_dialog import BaseDialog
from .dialog_utils import open_file, show_file_context_menu, show_file_details_dialog


class FileOrganizerDialog(BaseDialog):
    """
    Diálogo profesional para organización de archivos con:
    - Selector de tipo de organización en tiempo real
    - Análisis dinámico al cambiar tipo
    - UX profesional siguiendo DesignSystem
    - Sin emojis, usando Icon Manager
    """
    
    # Constantes para carga progresiva
    INITIAL_LOAD = 100
    LOAD_INCREMENT = 2000
    WARNING_THRESHOLD = 500

    def __init__(self, initial_analysis: Optional[OrganizationAnalysisResult], parent=None):
        super().__init__(parent)
        self.logger = get_logger("FileOrganizationDialog")
        self.repo = FileInfoRepositoryCache.get_instance()
        
        # Obtener root_directory desde initial_analysis o desde Stage 3
        if initial_analysis:
            self.root_directory = Path(initial_analysis.root_directory)
        else:
            # Si no hay análisis inicial, obtener desde el parent (MainWindow -> Stage3 -> selected_folder)
            if hasattr(parent, 'current_stage') and hasattr(parent.current_stage, 'selected_folder'):
                self.root_directory = Path(parent.current_stage.selected_folder)
            else:
                raise ValueError(tr("dialogs.file_organizer.error_no_root"))
        
        # Datos principales
        self.initial_analysis = initial_analysis  # Puede ser None
        self.analysis = None  # Se llenará cuando el usuario seleccione
        self.current_organization_type = None
        self.accepted_plan = None
        
        # Datos de archivos
        self.all_moves = []
        self.filtered_moves = []
        self.loaded_count = 0
        self._paginated_groups = []
        self._current_group_index = 0
        
        # Worker para análisis
        self.worker: Optional[FileOrganizerAnalysisWorker] = None
        self.is_analyzing = False
        
        # Flag para evitar disparar eventos durante la construcción de la UI
        self.ui_initialized = False
        
        # Referencia a la barra de paginación
        self.pagination_bar = None
        
        # Estado del dialog: 'selection' (pantalla inicial) o 'preview' (vista previa)
        self.dialog_state = 'selection'
        
        self.init_ui()

    def init_ui(self):
        """Inicializa la interfaz"""
        self.setWindowTitle(TOOL_FILE_ORGANIZER.title)
        self.setModal(True)
        self.resize(1200, 720)  # Más ancho para cards horizontales con ejemplos
        
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked widget para cambiar entre pantalla de selección y preview
        self.main_stack = QStackedWidget()
        main_layout.addWidget(self.main_stack)
        
        # === PÁGINA 0: PANTALLA DE SELECCIÓN INICIAL ===
        self.selection_page = self._create_selection_page()
        self.main_stack.addWidget(self.selection_page)
        
        # === PÁGINA 1: PANTALLA DE PREVIEW Y CONFIGURACIÓN ===
        self.preview_page = self._create_preview_page()
        self.main_stack.addWidget(self.preview_page)
        
        # Marcar UI como inicializada
        self.ui_initialized = True
        
        # Mostrar página de selección inicial
        self.main_stack.setCurrentIndex(0)
        
        # NO actualizar vista inicial - dejar vacío hasta que el usuario seleccione
        # self._update_all_ui()
        
        # Marcar UI como inicializada para permitir eventos
        self.ui_initialized = True
    
    def _go_back_to_selection(self):
        """Vuelve a la pantalla de selección inicial"""
        # Cancelar análisis si está en curso
        if self.is_analyzing and self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        
        # Limpiar datos
        self.analysis = None
        self.all_moves = []
        self.filtered_moves = []
        self.is_analyzing = False
        
        # Cambiar a página de selección
        self.dialog_state = 'selection'
        self.main_stack.setCurrentIndex(0)
        self.resize(1100, 700)
    
    def _create_selection_page(self) -> QWidget:
        """Crea la página inicial de selección de estrategia"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header simple
        header = QFrame()
        header.setStyleSheet(DesignSystem.get_organizer_header_style())
        header_layout = QVBoxLayout(header)
        header_layout.setSpacing(DesignSystem.SPACE_8)
        
        # Título
        title = QLabel(tr("dialogs.file_organizer.selection.title"))
        title.setStyleSheet(DesignSystem.get_organizer_header_title_style())
        header_layout.addWidget(title)
        
        # Subtítulo
        subtitle = QLabel(tr("dialogs.file_organizer.selection.subtitle"))
        subtitle.setStyleSheet(DesignSystem.get_organizer_header_subtitle_style())
        header_layout.addWidget(subtitle)
        
        layout.addWidget(header)
        
        # Contenido con las tarjetas
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(DesignSystem.SPACE_32, DesignSystem.SPACE_32, DesignSystem.SPACE_32, DesignSystem.SPACE_32)
        content_layout.setSpacing(DesignSystem.SPACE_20)
        
        # Grid de estrategias (2x2)
        grid = QGridLayout()
        grid.setSpacing(DesignSystem.SPACE_16)
        
        # Definir estrategias con descripciones detalladas y ejemplo visual
        strategies = [
            {
                'key': 'date',
                'icon': 'calendar-month',
                'title': tr("dialogs.file_organizer.strategy.date.title"),
                'description': tr("dialogs.file_organizer.strategy.date.desc"),
                'hint': tr("dialogs.file_organizer.strategy.date.hint"),
                'example': '2024_01/\n2024_02/\n2024_03/\n2025_12/',
                'row': 0, 'col': 0
            },
            {
                'key': 'type',
                'icon': 'image',
                'title': tr("dialogs.file_organizer.strategy.type.title"),
                'description': tr("dialogs.file_organizer.strategy.type.desc"),
                'hint': tr("dialogs.file_organizer.strategy.type.hint"),
                'example': 'Photos/\nVideos/\nOthers/',
                'row': 0, 'col': 1
            },
            {
                'key': 'source',
                'icon': 'devices',
                'title': tr("dialogs.file_organizer.strategy.source.title"),
                'description': tr("dialogs.file_organizer.strategy.source.desc"),
                'hint': tr("dialogs.file_organizer.strategy.type.hint"),
                'example': 'Camera/\nWhatsApp/\nInstagram/\nOthers/',
                'row': 1, 'col': 0
            },
            {
                'key': 'cleanup',
                'icon': 'folder-open',
                'title': tr("dialogs.file_organizer.strategy.cleanup.title"),
                'description': tr("dialogs.file_organizer.strategy.cleanup.desc"),
                'hint': '',
                'example': 'IMG_001.jpg\nVID_002.mp4\nphoto.heic\n(no subfolders)',
                'row': 1, 'col': 1
            }
        ]
        
        for strategy in strategies:
            card = self._create_strategy_selection_card(
                strategy['key'],
                strategy['icon'],
                strategy['title'],
                strategy['description'],
                strategy['example'],
                strategy.get('hint', '')
            )
            grid.addWidget(card, strategy['row'], strategy['col'])
        
        content_layout.addLayout(grid)
        content_layout.addStretch()
        
        # Botón cancelar al final
        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedWidth(120)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        content_layout.addLayout(btn_layout)
        
        layout.addWidget(content, 1)
        
        return page
    
    def _create_strategy_selection_card(self, key: str, icon_name: str, title: str, description: str, example: str, hint: str = '') -> QFrame:
        """Crea una tarjeta con layout horizontal: info izquierda, ejemplo derecha"""
        card = QFrame()
        card.setProperty("strategy_key", key)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setMinimumHeight(190)
        card.setObjectName("strategyCard")
        card.setStyleSheet(DesignSystem.get_strategy_card_style())
        
        # Layout horizontal principal
        main_layout = QHBoxLayout(card)
        main_layout.setContentsMargins(DesignSystem.SPACE_20, DesignSystem.SPACE_16, DesignSystem.SPACE_16, DesignSystem.SPACE_16)
        main_layout.setSpacing(DesignSystem.SPACE_20)
        
        # === LADO IZQUIERDO: Icono + Título + Descripción + Hint ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(DesignSystem.SPACE_8)
        
        # Icono
        icon_label = QLabel()
        icon_manager.set_label_icon(icon_label, icon_name, size=36, color=DesignSystem.COLOR_PRIMARY)
        left_layout.addWidget(icon_label)
        
        # Título
        title_label = QLabel(title)
        title_label.setStyleSheet(DesignSystem.get_strategy_card_title_style())
        left_layout.addWidget(title_label)
        
        # Descripción
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(DesignSystem.get_strategy_card_description_style())
        left_layout.addWidget(desc_label)
        
        # Hint de opciones adicionales (si existe)
        if hint:
            hint_icon = QLabel()
            icon_manager.set_label_icon(hint_icon, 'cog', size=12, color=DesignSystem.COLOR_PRIMARY)
            hint_text = QLabel(hint)
            hint_text.setStyleSheet(DesignSystem.get_strategy_card_hint_style())
            hint_container = QHBoxLayout()
            hint_container.setContentsMargins(0, int(DesignSystem.SPACE_4), 0, 0)
            hint_container.setSpacing(int(DesignSystem.SPACE_4))
            hint_container.addWidget(hint_icon)
            hint_container.addWidget(hint_text)
            hint_container.addStretch()
            left_layout.addLayout(hint_container)
        
        left_layout.addStretch()
        
        main_layout.addWidget(left_widget, 1)  # Stretch factor 1
        
        # === LADO DERECHO: Ejemplo visual con fondo ===
        example_container = QFrame()
        example_container.setObjectName("exampleContainer")
        example_container.setFixedWidth(200)  # Un poco más ancho
        example_container.setStyleSheet(DesignSystem.get_example_container_style())
        example_layout = QVBoxLayout(example_container)
        example_layout.setContentsMargins(DesignSystem.SPACE_12, DesignSystem.SPACE_12, DesignSystem.SPACE_12, DesignSystem.SPACE_12)
        
        # Título del ejemplo
        example_title = QLabel(tr("dialogs.file_organizer.example_title"))
        example_title.setStyleSheet(DesignSystem.get_example_title_style())
        example_layout.addWidget(example_title)
        
        # Contenido del ejemplo
        example_label = QLabel(example)
        example_label.setStyleSheet(DesignSystem.get_example_content_style())
        example_layout.addWidget(example_label)
        example_layout.addStretch()
        
        main_layout.addWidget(example_container)
        
        # Click handler
        card.mousePressEvent = lambda e: self._on_strategy_selection(key)
        
        return card
    
    def _on_strategy_selection(self, key: str):
        """Maneja la selección de una estrategia desde la pantalla inicial"""
        self.logger.info(f"Strategy selected: {key}")
        
        # Mapear key a tipo de organización y página de opciones
        strategy_config = {
            'date': {'org_type': OrganizationType.BY_MONTH, 'page': 0},
            'type': {'org_type': OrganizationType.BY_TYPE, 'page': 1},
            'source': {'org_type': OrganizationType.BY_SOURCE, 'page': 2},
            'cleanup': {'org_type': OrganizationType.TO_ROOT, 'page': 3}
        }
        
        config = strategy_config.get(key, strategy_config['date'])
        
        # Cambiar a página de preview
        self.dialog_state = 'preview'
        self.main_stack.setCurrentIndex(1)
        self.resize(1400, 800)
        
        # Guardar estrategia seleccionada
        self.selected_strategy_key = key
        
        # Cambiar página de opciones correspondiente
        self.options_stack.setCurrentIndex(config['page'])
        
        # Iniciar análisis con configuración por defecto
        self._start_analysis(config['org_type'], group_by_source=False, group_by_type=False, date_grouping_type=None)
    
    def _configure_preview_for_strategy(self, key: str):
        """Configura la página de preview según la estrategia seleccionada"""
        # Actualizar indicador de estrategia
        self._update_strategy_indicator(key)
    
    def _create_preview_page(self) -> QWidget:
        """Crea la página de preview con configuración y vista de archivos"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, DesignSystem.SPACE_20)
        
        # Inicializar progress bar temprano
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # === HEADER COMPACTO CON MÉTRICAS ===
        self.header_frame = self._create_compact_header_with_metrics(
            icon_name=TOOL_FILE_ORGANIZER.icon_name,
            title=TOOL_FILE_ORGANIZER.title,
            description=TOOL_FILE_ORGANIZER.short_description,
            metrics=[
                {'label': tr("dialogs.file_organizer.metric_total"), 'value': '0'},
                {'label': tr("dialogs.file_organizer.metric_organize"), 'value': '0'},
                {'label': tr("dialogs.file_organizer.metric_size"), 'value': '0 B'}
            ]
        )
        layout.addWidget(self.header_frame)
        
        # Contenedor con márgenes para el resto del contenido
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setSpacing(DesignSystem.SPACE_12)
        content_layout.setContentsMargins(
            DesignSystem.SPACE_24,
            DesignSystem.SPACE_12,
            DesignSystem.SPACE_24,
            0
        )
        layout.addWidget(content_container)
        
        # === OPCIONES DE ORGANIZACIÓN (con botón volver + estrategia + personalización) ===
        self.options_panel = self._create_organization_options_panel()
        content_layout.addWidget(self.options_panel)
        
        # === INFORMACIÓN DE CARPETAS ===
        self.folders_info_widget = self._create_folders_info()
        if self.folders_info_widget:
            content_layout.addWidget(self.folders_info_widget)
        
        # === BARRA DE FILTROS UNIFICADA ===
        self.filter_bar = self._create_filter_bar()
        content_layout.addWidget(self.filter_bar)
        
        # === TREE WIDGET ===
        self.files_tree = self._create_tree_widget()
        content_layout.addWidget(self.files_tree, 1)  # Stretch factor 1
        
        # === BARRA DE CARGA PROGRESIVA ===
        self.pagination_bar = self._create_progressive_loading_bar(
            on_load_more=self._load_more_items,
            on_load_all=self._load_all_items
        )
        content_layout.addWidget(self.pagination_bar)

        # === PROGRESS BAR (inicialmente oculto) ===
        self.progress_bar.setStyleSheet(DesignSystem.get_organizer_progressbar_style())
        content_layout.addWidget(self.progress_bar)
        
        # === OPCIONES ===
        options_group = self._create_options_group()
        content_layout.addWidget(options_group)
        
        # === BOTONES ===
        self.buttons = self._create_action_buttons()
        content_layout.addWidget(self.buttons)
        
        return page
    
    def _create_organization_options_panel(self) -> QWidget:
        """Crea panel de opciones compacto: [Volver] | Estrategia | Opciones - todo en una línea"""
        container = QFrame()
        container.setStyleSheet(DesignSystem.get_options_panel_container_style())
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(DesignSystem.SPACE_12, DesignSystem.SPACE_10, DesignSystem.SPACE_16, DesignSystem.SPACE_10)
        layout.setSpacing(DesignSystem.SPACE_12)
        
        # Botón volver (izquierda)
        back_btn = QPushButton(tr("dialogs.file_organizer.button_back"))
        back_btn.setStyleSheet(DesignSystem.get_organizer_back_button_style())
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setToolTip(tr("dialogs.file_organizer.button_back_tooltip"))
        back_btn.clicked.connect(self._go_back_to_selection)
        layout.addWidget(back_btn)
        
        # Separador vertical
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(DesignSystem.get_vertical_separator_style())
        layout.addWidget(sep)
        
        # Stacked widget para opciones según estrategia (ocupa el resto del espacio)
        self.options_stack = QStackedWidget()
        
        # Página 0: Opciones para "Por Fecha"
        date_page = self._create_date_options()
        self.options_stack.addWidget(date_page)
        
        # Página 1: Opciones para "Por Tipo"
        type_page = self._create_type_options()
        self.options_stack.addWidget(type_page)
        
        # Página 2: Opciones para "Por Fuente"
        source_page = self._create_source_options()
        self.options_stack.addWidget(source_page)
        
        # Página 3: Opciones para "Al Raíz"
        cleanup_page = self._create_cleanup_options()
        self.options_stack.addWidget(cleanup_page)
        
        layout.addWidget(self.options_stack, 1)  # Stretch factor 1
        
        return container
    
    def _create_chip_button(self, text: str, group_name: str, value: any, is_selected: bool = False) -> QPushButton:
        """Crea un botón chip para selección de opciones"""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(is_selected)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("group", group_name)
        btn.setProperty("value", value)
        btn.setStyleSheet(self._get_chip_style(is_selected))
        return btn
    
    def _get_chip_style(self, selected: bool = False) -> str:
        """Estilo para chips de selección"""
        return DesignSystem.get_chip_style(selected)
    
    def _get_secondary_chip_style(self, selected: bool = False) -> str:
        """Estilo para chips de opciones secundarias (más sutiles)"""
        return DesignSystem.get_secondary_chip_style(selected)
    
    def _create_date_options(self) -> QWidget:
        """Opciones para organización por fecha - diseño compacto horizontal"""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_8)
        
        # Icono + Título de estrategia
        icon_label = QLabel()
        icon_manager.set_label_icon(icon_label, 'calendar-month', size=20, color=DesignSystem.COLOR_PRIMARY)
        layout.addWidget(icon_label)
        
        strategy_label = QLabel(tr("dialogs.file_organizer.options.date_label"))
        strategy_label.setStyleSheet(DesignSystem.get_organizer_strategy_label_style())
        layout.addWidget(strategy_label)
        
        # Opción principal: Granularidad (con fondo sutil para destacar)
        gran_container = QFrame()
        gran_container.setStyleSheet(DesignSystem.get_granularity_container_style())
        gran_layout = QHBoxLayout(gran_container)
        gran_layout.setContentsMargins(8, 4, 8, 4)
        gran_layout.setSpacing(6)
        
        gran_label = QLabel(tr("dialogs.file_organizer.options.granularity_label"))
        gran_label.setStyleSheet(DesignSystem.get_granularity_label_style())
        gran_layout.addWidget(gran_label)
        
        self.date_granularity_buttons = []
        granularities = [(tr("dialogs.file_organizer.options.month"), 0), (tr("dialogs.file_organizer.options.year"), 1), (tr("dialogs.file_organizer.options.year_month"), 2)]
        for text, value in granularities:
            btn = self._create_chip_button(text, "date_granularity", value, value == 0)
            btn.clicked.connect(lambda checked, v=value: self._on_date_granularity_changed(v))
            self.date_granularity_buttons.append(btn)
            gran_layout.addWidget(btn)
        
        layout.addWidget(gran_container)
        
        # Espacio entre grupos
        layout.addSpacing(8)
        
        # Opciones secundarias: Subcarpetas (más sutiles)
        sub_label = QLabel(tr("dialogs.file_organizer.options.subfolders_label"))
        sub_label.setStyleSheet(DesignSystem.get_subcarpetas_label_style())
        layout.addWidget(sub_label)
        
        self.chk_date_source_btn = QPushButton(tr("dialogs.file_organizer.options.add_source"))
        self.chk_date_source_btn.setCheckable(True)
        self.chk_date_source_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_date_source_btn.setToolTip(tr("dialogs.file_organizer.options.add_source_tooltip"))
        self.chk_date_source_btn.setStyleSheet(self._get_secondary_chip_style(False))
        self.chk_date_source_btn.clicked.connect(self._on_date_extra_changed)
        layout.addWidget(self.chk_date_source_btn)
        
        self.chk_date_type_btn = QPushButton(tr("dialogs.file_organizer.options.add_type"))
        self.chk_date_type_btn.setCheckable(True)
        self.chk_date_type_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_date_type_btn.setToolTip(tr("dialogs.file_organizer.options.add_type_tooltip"))
        self.chk_date_type_btn.setStyleSheet(self._get_secondary_chip_style(False))
        self.chk_date_type_btn.clicked.connect(self._on_date_extra_changed)
        layout.addWidget(self.chk_date_type_btn)
        
        layout.addStretch()
        return page
    
    def _create_type_options(self) -> QWidget:
        """Opciones para organización por tipo - diseño compacto horizontal"""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_8)
        
        # Icono + Título de estrategia
        icon_label = QLabel()
        icon_manager.set_label_icon(icon_label, 'image', size=20, color=DesignSystem.COLOR_PRIMARY)
        layout.addWidget(icon_label)
        
        strategy_label = QLabel(tr("dialogs.file_organizer.options.type_label"))
        strategy_label.setStyleSheet(DesignSystem.get_organizer_strategy_label_style())
        layout.addWidget(strategy_label)
        
        # Opciones secundarias: Subcarpetas por fecha
        sub_label = QLabel(tr("dialogs.file_organizer.options.subfolders_by_date_label"))
        sub_label.setStyleSheet(DesignSystem.get_subcarpetas_label_style())
        layout.addWidget(sub_label)
        
        self.type_date_buttons = []
        options = [(tr("dialogs.file_organizer.options.none"), None), (tr("dialogs.file_organizer.options.month"), "month"), (tr("dialogs.file_organizer.options.year"), "year"), (tr("dialogs.file_organizer.options.year_month"), "year_month")]
        for text, value in options:
            btn = self._create_chip_button(text, "type_date", value, value is None)
            btn.clicked.connect(lambda checked, v=value: self._on_type_date_changed(v))
            self.type_date_buttons.append(btn)
            layout.addWidget(btn)
        
        layout.addStretch()
        return page
    
    def _create_source_options(self) -> QWidget:
        """Opciones para organización por fuente - diseño compacto horizontal"""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_8)
        
        # Icono + Título de estrategia
        icon_label = QLabel()
        icon_manager.set_label_icon(icon_label, 'devices', size=20, color=DesignSystem.COLOR_PRIMARY)
        layout.addWidget(icon_label)
        
        strategy_label = QLabel(tr("dialogs.file_organizer.options.source_label"))
        strategy_label.setStyleSheet(DesignSystem.get_organizer_strategy_label_style())
        layout.addWidget(strategy_label)
        
        # Subcarpetas por fecha
        sub_label = QLabel(tr("dialogs.file_organizer.options.subfolders_by_date_label"))
        sub_label.setStyleSheet(DesignSystem.get_subcarpetas_label_style())
        layout.addWidget(sub_label)
        
        self.source_date_buttons = []
        options = [(tr("dialogs.file_organizer.options.none"), None), (tr("dialogs.file_organizer.options.month"), "month"), (tr("dialogs.file_organizer.options.year"), "year"), (tr("dialogs.file_organizer.options.year_month"), "year_month")]
        for text, value in options:
            btn = self._create_chip_button(text, "source_date", value, value is None)
            btn.clicked.connect(lambda checked, v=value: self._on_source_date_changed(v))
            self.source_date_buttons.append(btn)
            layout.addWidget(btn)
        
        layout.addStretch()
        return page
    
    def _create_cleanup_options(self) -> QWidget:
        """Opciones para mover al raíz - diseño compacto horizontal"""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_8)
        
        # Icono + Título de estrategia
        icon_label = QLabel()
        icon_manager.set_label_icon(icon_label, 'folder-open', size=20, color=DesignSystem.COLOR_PRIMARY)
        layout.addWidget(icon_label)
        
        strategy_label = QLabel(tr("dialogs.file_organizer.options.cleanup_label"))
        strategy_label.setStyleSheet(DesignSystem.get_organizer_strategy_label_style())
        layout.addWidget(strategy_label)
        
        # Descripción
        info_label = QLabel(tr("dialogs.file_organizer.options.cleanup_desc"))
        info_label.setStyleSheet(DesignSystem.get_subcarpetas_label_style())
        layout.addWidget(info_label)
        
        layout.addStretch()
        return page
    
    def _update_chip_group(self, buttons: list, selected_value):
        """Actualiza el estado visual de un grupo de chips"""
        for btn in buttons:
            is_selected = btn.property("value") == selected_value
            btn.setChecked(is_selected)
            btn.setStyleSheet(self._get_chip_style(is_selected))
    
    def _on_date_granularity_changed(self, value: int):
        """Maneja cambio de granularidad temporal en fecha"""
        self._update_chip_group(self.date_granularity_buttons, value)
        self._trigger_date_analysis()
    
    def _on_date_extra_changed(self):
        """Maneja cambio en opciones extras de fecha"""
        # Actualizar estilos de los botones toggle
        self.chk_date_source_btn.setStyleSheet(self._get_secondary_chip_style(self.chk_date_source_btn.isChecked()))
        self.chk_date_type_btn.setStyleSheet(self._get_secondary_chip_style(self.chk_date_type_btn.isChecked()))
        self._trigger_date_analysis()
    
    def _trigger_date_analysis(self):
        """Dispara análisis con las opciones de fecha actuales"""
        if not self.ui_initialized or self.dialog_state != 'preview':
            return
        
        # Obtener granularidad seleccionada
        granularity_value = 0
        for btn in self.date_granularity_buttons:
            if btn.isChecked():
                granularity_value = btn.property("value")
                break
        
        org_type = OrganizationType.BY_MONTH
        if granularity_value == 0:
            org_type = OrganizationType.BY_MONTH
        elif granularity_value == 1:
            org_type = OrganizationType.BY_YEAR
        elif granularity_value == 2:
            org_type = OrganizationType.BY_YEAR_MONTH
        
        group_by_source = self.chk_date_source_btn.isChecked()
        group_by_type = self.chk_date_type_btn.isChecked()
        
        self._start_analysis(org_type, group_by_source, group_by_type, None)
    
    def _on_type_date_changed(self, value):
        """Maneja cambio de suborganización temporal en tipo"""
        self._update_chip_group(self.type_date_buttons, value)
        if not self.ui_initialized or self.dialog_state != 'preview':
            return
        self._start_analysis(OrganizationType.BY_TYPE, False, False, value)
    
    def _on_source_date_changed(self, value):
        """Maneja cambio de suborganización temporal en fuente"""
        self._update_chip_group(self.source_date_buttons, value)
        if not self.ui_initialized or self.dialog_state != 'preview':
            return
        self._start_analysis(OrganizationType.BY_SOURCE, False, False, value)
    
    def _create_strategy_indicator(self) -> QWidget:
        """Crea un indicador simple de la estrategia seleccionada"""
        container = QFrame()
        container.setStyleSheet(DesignSystem.get_strategy_indicator_container_style())
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_12)
        
        # Icono
        self.indicator_icon = QLabel()
        icon_manager.set_label_icon(self.indicator_icon, 'calendar-month', size=DesignSystem.ICON_SIZE_MD, color=DesignSystem.COLOR_PRIMARY)
        layout.addWidget(self.indicator_icon)
        
        # Texto
        self.indicator_text = QLabel(tr("dialogs.file_organizer.indicator.date"))
        self.indicator_text.setStyleSheet(DesignSystem.get_strategy_indicator_text_style())
        layout.addWidget(self.indicator_text, 1)
        
        layout.addStretch()
        
        return container
    
    def _update_strategy_indicator(self, key: str):
        """Actualiza el indicador de estrategia"""
        strategy_info = {
            'date': {'icon': 'calendar-month', 'text': tr("dialogs.file_organizer.indicator.date")},
            'type': {'icon': 'image', 'text': tr("dialogs.file_organizer.indicator.type")},
            'source': {'icon': 'devices', 'text': tr("dialogs.file_organizer.indicator.source")},
            'cleanup': {'icon': 'folder-open', 'text': tr("dialogs.file_organizer.indicator.cleanup")}
        }
        
        info = strategy_info.get(key, strategy_info['date'])
        icon_manager.set_label_icon(self.indicator_icon, info['icon'], size=DesignSystem.ICON_SIZE_MD, color=DesignSystem.COLOR_PRIMARY)
        self.indicator_text.setText(info['text'])

    def is_move_unsupported_enabled(self) -> bool:
        """Devuelve True si el checkbox de mover no soportados está marcado."""
        if not hasattr(self, 'move_unsupported_checkbox') or not self.move_unsupported_checkbox:
            return False
        if hasattr(self.move_unsupported_checkbox, '_checkbox'):
            return self.move_unsupported_checkbox._checkbox.isChecked()
        return self.move_unsupported_checkbox.isChecked()

    def _on_move_unsupported_changed(self):
        """Maneja el cambio en la opción de mover archivos no soportados.
        Re-lanza el análisis actual con la nueva configuración."""
        if not self.ui_initialized or self.dialog_state != 'preview':
            return
        # Re-disparar el análisis actual con la nueva configuración
        self._retrigger_current_analysis()

    def _retrigger_current_analysis(self):
        """Re-ejecuta el análisis con la configuración actual del panel de opciones."""
        if not hasattr(self, 'selected_strategy_key'):
            return
        key = self.selected_strategy_key
        if key == 'date':
            self._trigger_date_analysis()
        elif key == 'type':
            # Obtener valor actual del filtro de tipo
            value = None
            for btn in self.type_date_buttons:
                if btn.isChecked():
                    value = btn.property("value")
                    break
            self._start_analysis(OrganizationType.BY_TYPE, False, False, value)
        elif key == 'source':
            value = None
            for btn in self.source_date_buttons:
                if btn.isChecked():
                    value = btn.property("value")
                    break
            self._start_analysis(OrganizationType.BY_SOURCE, False, False, value)
        elif key == 'cleanup':
            self._start_analysis(OrganizationType.TO_ROOT, False, False, None)

    def _start_analysis(self, org_type: OrganizationType, group_by_source=False, group_by_type=False, date_grouping_type: Optional[str] = None):
        """Inicia análisis en background"""
        if self.is_analyzing and self.worker and self.worker.isRunning():
            # Cancelar worker anterior si es posible o esperar
            # Por simplicidad, bloqueamos nueva solicitud si ya hay una (pero idealmente deberíamos cancelar)
            # En este caso, permitiremos que termine y el usuario tendrá que esperar un poco
            self.logger.warning("Analysis already in progress")
            return
        
        # CRÍTICO: Guardar el tipo de organización actual para los treeviews
        self.current_organization_type = org_type
        
        self.is_analyzing = True
        self._set_ui_loading_state(True)
        
        # Crear y configurar worker
        self.worker = FileOrganizerAnalysisWorker(
            directory=self.root_directory,
            organization_type=org_type,
            group_by_source=group_by_source,
            group_by_type=group_by_type,
            date_grouping_type=date_grouping_type,
            move_unsupported_to_other=self.is_move_unsupported_enabled()
        )
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.progress_update.connect(self._on_analysis_progress)
        self.worker.error.connect(self._on_analysis_error)
        
        # Iniciar
        self.worker.start()
    
    def _on_analysis_finished(self, result: OrganizationAnalysisResult):
        """Maneja la finalización del análisis"""
        self.logger.info(f"Analysis completed: {result.items_count} files (type: {result.organization_type})")
        self.analysis = result
        
        # Actualizar chip de estado
        self._update_filter_chip(
            status_chip=self.status_chip,
            filtered_count=len(result.move_plan),
            total_count=len(result.move_plan),
            is_files_mode=True
        )
        
        # Actualizar opciones de filtros basadas en los datos
        self._update_filter_options()
        
        self.filtered_moves = list(result.move_plan)
        self.current_page = 0
        
        # IMPORTANTE: Establecer is_analyzing=False ANTES de actualizar UI
        # para que el botón OK se habilite correctamente
        self.is_analyzing = False
        
        self._set_ui_loading_state(False)
        self._update_all_ui()
    
    def _on_analysis_progress(self, current: int, total: int, message: str):
        """Maneja el progreso del análisis"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{message} - {current}/{total}")
    
    def _on_analysis_error(self, error_msg: str):
        """Maneja errores en el análisis"""
        from PyQt6.QtWidgets import QMessageBox
        self.logger.error(f"Analysis error: {error_msg}")
        self._set_ui_loading_state(False)
        self.is_analyzing = False
        QMessageBox.critical(self, tr("common.error"), tr("dialogs.file_organizer.error_analysis_failed", error=error_msg))
    
    def _set_ui_loading_state(self, loading: bool):
        """Activa/desactiva el estado de carga"""
        self.progress_bar.setVisible(loading)
        self.files_tree.setEnabled(not loading)
        # NO actualizar ok_button aquí - se hace en _update_ok_button() con datos frescos
        
        # Deshabilitar opciones de tipo durante análisis
        if hasattr(self, 'type_selector'):
            button_group = self.type_selector.property("button_group")
            if button_group:
                for button in button_group.buttons():
                    button.setEnabled(not loading)
    
    def _update_all_ui(self):
        """Actualiza toda la UI con los datos actuales"""
        
        # Actualizar header con métricas
        self._update_header_metrics()
        
        # Actualizar info de carpetas
        self._update_folders_info()
        
        # Actualizar datos de archivos
        if self.analysis:
            self.all_moves = list(self.analysis.move_plan)
            self.filtered_moves = list(self.analysis.move_plan)
            self._load_initial_items()
        
        # Actualizar botón OK
        self._update_ok_button()
        
        # Re-aplicar estilos a las cards de selección
        # Actualizar botón OK
        self._update_ok_button()
    

    
    def _update_header_metrics(self):
        """Actualiza las métricas del header compacto"""
        # Buscar y actualizar los QLabel de las métricas existentes
        main_layout = self.header_frame.layout()
        if not main_layout:
            return

        # El layout tiene: left_container, spacer, metrics_container
        # metrics_container es el último QHBoxLayout
        metrics_layout = None
        for i in range(main_layout.count() - 1, -1, -1):  # Buscar desde el final
            item = main_layout.itemAt(i)
            if item and item.layout() and isinstance(item.layout(), QHBoxLayout):
                metrics_layout = item.layout()
                break
        
        if not metrics_layout:
            return
        
        # Actualizar cada métrica (son QWidget con QVBoxLayout conteniendo value_label y label_widget)
        # Datos de las métricas
        if not self.analysis:
            metrics_data = ["0", "0", "0 B"]
        else:
            metrics_data = [
                str(self.analysis.items_count),
                str(self.analysis.files_to_move),
                format_size(self.analysis.bytes_total)
            ]
        
        for idx, new_value in enumerate(metrics_data):
            if idx < metrics_layout.count():
                metric_widget = metrics_layout.itemAt(idx).widget()
                if metric_widget and metric_widget.layout():
                    # El primer hijo del layout es el value_label
                    value_label = metric_widget.layout().itemAt(0).widget()
                    if value_label and isinstance(value_label, QLabel):
                        value_label.setText(new_value)
    
    def _get_icon_name_for_type(self, org_type: OrganizationType) -> str:
        """Devuelve el nombre del icono para un tipo de organización"""
        icon_map = {
            OrganizationType.TO_ROOT: "folder-open",
            OrganizationType.BY_MONTH: "calendar-month",
            OrganizationType.BY_YEAR: "calendar-today",
            OrganizationType.BY_YEAR_MONTH: "calendar-range",
            OrganizationType.BY_TYPE: "image",
            OrganizationType.BY_SOURCE: "devices"
        }
        return icon_map.get(org_type, "folder")

    

    
    def _create_folders_info(self) -> Optional[QWidget]:
        """Crea sección de información de carpetas a crear con estilo Material Design"""
        # Inicializar atributos siempre
        self.folders_info_container = None
        self.folders_info_label = None
        
        if not self.analysis or not self.analysis.folders_to_create:
            return None
        
        self.folders_info_container = QFrame()
        self.folders_info_container.setStyleSheet(DesignSystem.get_folders_info_container_style())
        
        layout = QHBoxLayout(self.folders_info_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignSystem.SPACE_12)
        
        # Icono
        icon_label = QLabel()
        icon_manager.set_label_icon(icon_label, 'folder-multiple', color=DesignSystem.COLOR_INFO, size=DesignSystem.ICON_SIZE_MD)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        
        self.folders_info_label = QLabel()
        self.folders_info_label.setWordWrap(True)
        self.folders_info_label.setTextFormat(Qt.TextFormat.RichText)
        self.folders_info_label.setStyleSheet(DesignSystem.get_folders_info_label_style())
        layout.addWidget(self.folders_info_label, 1)
        
        self._update_folders_info()
        return self.folders_info_container
    
    def _update_folders_info(self):
        """Actualiza la información de carpetas"""
        if not self.folders_info_label:
            return
        
        folders = sorted(self.analysis.folders_to_create)
        count = len(folders)
        
        if count == 0:
            if self.folders_info_container:
                self.folders_info_container.setVisible(False)
            return
        
        if self.folders_info_container:
            self.folders_info_container.setVisible(True)
        
        if count <= 10:
            folders_text = ", ".join(folders)
        else:
            folders_text = ", ".join(folders[:10]) + tr("dialogs.file_organizer.folders_info_more", count=count - 10)
        
        self.folders_info_label.setText(tr("dialogs.file_organizer.folders_info_label", count=count, list=folders_text))
    
    def _create_filter_bar(self) -> QWidget:
        """Crea barra de filtros unificada usando método base"""
        # Diccionario de etiquetas
        labels = {
            'search': tr("dialogs.file_organizer.filter.search"),
            'groups': tr("dialogs.file_organizer.filter.groups"),
            'category': tr("dialogs.file_organizer.filter.category"),
            'status': tr("dialogs.file_organizer.filter.status"),
            'source': tr("dialogs.file_organizer.filter.source")
        }
        
        # Configuración de filtros expandibles
        expandable_filters = [
            {
                'id': 'source',
                'type': 'combo',
                'label': labels['source'],
                'tooltip': tr("dialogs.file_organizer.filter.source_tooltip"),
                'options': self.DATE_SOURCE_FILTER_OPTIONS,
                'on_change': self._on_source_filter_changed,
                'default_index': 0,
                'min_width': 200
            },
            {
                'id': 'category',
                'type': 'combo',
                'label': labels['category'],
                'tooltip': tr("dialogs.file_organizer.filter.category_tooltip"),
                'options': [tr("common.filter.all")],  # Se actualiza dinámicamente
                'on_change': lambda idx: self._apply_filters(),
                'default_index': 0,
                'min_width': 120
            },
            {
                'id': 'status',
                'type': 'combo',
                'label': labels['status'],
                'tooltip': tr("dialogs.file_organizer.filter.status_tooltip"),
                'options': [tr("common.filter.all")],  # Se actualiza dinámicamente
                'on_change': lambda idx: self._apply_filters(),
                'default_index': 0,
                'min_width': 150
            }
        ]
        
        # Crear barra unificada (sin filtro de tamaño)
        filter_bar = self._create_unified_filter_bar(
            on_search_changed=self._apply_filters,
            on_size_filter_changed=None,
            expandable_filters=expandable_filters,
            size_filter_options=None,
            is_files_mode=True,
            labels=labels
        )
        
        # Guardar referencias a componentes
        self.search_input = filter_bar.search_input
        self.status_chip = filter_bar.status_chip
        self.expand_button = filter_bar.expand_btn
        self.source_combo = filter_bar.filter_widgets.get('source')
        self.category_combo = filter_bar.filter_widgets.get('category')
        self.status_combo = filter_bar.filter_widgets.get('status')
        
        return filter_bar
    
    def _create_tree_widget(self) -> QTreeWidget:
        """Crea TreeWidget con configuración dinámica"""
        tree = QTreeWidget()
        
        # Configurar columnas según tipo
        self._configure_tree_columns(tree)
        
        tree.setAlternatingRowColors(True)
        tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._show_context_menu)
        tree.setStyleSheet(DesignSystem.get_tree_widget_style())
        tree.setToolTip(
            tr("dialogs.file_organizer.tree_tooltip")
        )
        
        return tree
    
    def _configure_tree_columns(self, tree: QTreeWidget):
        """Configura las columnas del tree de forma estandarizada"""
        # Estándar: Nombre Original, Nuevo Nombre, Fecha, Origen, Tamaño
        headers = [tr("dialogs.file_organizer.tree_header.original_name"), tr("dialogs.file_organizer.tree_header.new_name"), tr("common.tree_header.date"), tr("common.tree_header.date_source"), tr("common.tree_header.size")]
        tree.setHeaderLabels(headers)
        
        # Ajustar anchos
        tree.setColumnWidth(0, 400) # Nombre Original (más ancho para path completo)
        tree.setColumnWidth(1, 300) # Nuevo Nombre
        tree.setColumnWidth(2, 160) # Fecha
        tree.setColumnWidth(3, 180) # Origen
        tree.setColumnWidth(4, 80)  # Tamaño
    
    def _create_options_group(self) -> QFrame:
        """Crea grupo de opciones con sección de seguridad + opción de limpieza específica."""
        from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        # Crear contenedor principal con estilo consistente
        container = QFrame()
        container.setObjectName("options-container")
        container.setStyleSheet(DesignSystem.get_options_container_style())
        
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(int(DesignSystem.SPACE_8))
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # === Fila 1: Opciones de seguridad + cleanup (todo inline) ===
        options_row = QHBoxLayout()
        options_row.setSpacing(int(DesignSystem.SPACE_12))
        options_row.setContentsMargins(0, 0, 0, 0)
        
        # Label "Opciones:"
        options_label = QLabel(tr("dialogs.file_organizer.options.label"))
        options_label.setStyleSheet(DesignSystem.get_options_label_style())
        options_row.addWidget(options_label)
        
        # Obtener configuración de backup
        from utils.settings_manager import settings_manager
        from config import Config
        
        backup_dir = settings_manager.get_backup_directory(Config.DEFAULT_BACKUP_DIR)
        backup_path_str = str(backup_dir) if backup_dir else str(Config.DEFAULT_BACKUP_DIR)
        
        # Chip de backup
        backup_checked = settings_manager.get_auto_backup_enabled()
        
        self.backup_checkbox = self._create_inline_chip_checkbox(
            icon_name='content-save',
            label=tr("dialogs.file_organizer.options.backup_label"),
            checked=backup_checked,
            tooltip=tr("dialogs.file_organizer.options.backup_tooltip", path=backup_path_str)
        )
        options_row.addWidget(self.backup_checkbox)
        
        # Chip de dry-run
        dry_run_default = settings_manager.get(settings_manager.KEY_DRY_RUN_DEFAULT, False)
        if isinstance(dry_run_default, str):
            dry_run_default = dry_run_default.lower() in ('true', '1', 'yes')
        
        self.dry_run_checkbox = self._create_inline_chip_checkbox(
            icon_name='eye',
            label=tr("dialogs.file_organizer.options.dry_run_label"),
            checked=bool(dry_run_default),
            tooltip=tr("dialogs.file_organizer.options.dry_run_tooltip")
        )
        options_row.addWidget(self.dry_run_checkbox)
        
        # Separador visual (línea vertical)
        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setStyleSheet(f"background-color: {DesignSystem.COLOR_BORDER};")
        options_row.addWidget(separator)
        
        # Chip de cleanup carpetas vacías (específico de organización)
        self.cleanup_checkbox = self._create_inline_chip_checkbox(
            icon_name='folder-remove',
            label=tr("dialogs.file_organizer.options.cleanup_empty_label"),
            checked=True,  # Default habilitado para dejar estructura limpia
            tooltip=tr("dialogs.file_organizer.options.cleanup_empty_tooltip")
        )
        options_row.addWidget(self.cleanup_checkbox)
        
        # Chip de mover archivos no soportados a 'other/' (específico de organización)
        self.move_unsupported_checkbox = self._create_inline_chip_checkbox(
            icon_name='folder-move',
            label=tr("dialogs.file_organizer.options.move_unsupported_label"),
            checked=True,  # Default habilitado para dejar estructura limpia
            tooltip=tr("dialogs.file_organizer.options.move_unsupported_tooltip")
        )
        self.move_unsupported_checkbox._checkbox.toggled.connect(self._on_move_unsupported_changed)
        options_row.addWidget(self.move_unsupported_checkbox)
        
        options_row.addStretch()
        container_layout.addLayout(options_row)
        
        # === Fila 2: Ruta de backup (siempre presente para mantener tamaño fijo) ===
        # Truncar path si es muy largo
        max_display_len = 60
        display_path = backup_path_str
        if len(display_path) > max_display_len:
            display_path = "..." + display_path[-(max_display_len - 3):]
        
        # Contenedor para la ruta (mantiene espacio fijo)
        self._backup_path_widget = QWidget()
        # Reservar espacio incluso cuando está oculto para evitar saltos en la interfaz
        sp = self._backup_path_widget.sizePolicy()
        if hasattr(sp, 'setRetainSizeWhenHidden'):
            sp.setRetainSizeWhenHidden(True)
            self._backup_path_widget.setSizePolicy(sp)

        path_layout = QHBoxLayout(self._backup_path_widget)
        path_layout.setSpacing(int(DesignSystem.SPACE_6))
        path_layout.setContentsMargins(0, 0, 0, 0)
        
        self._backup_folder_icon = QLabel()
        icon_manager.set_label_icon(
            self._backup_folder_icon, 'folder', 
            size=DesignSystem.ICON_SIZE_SM, 
            color=DesignSystem.COLOR_TEXT_SECONDARY
        )
        path_layout.addWidget(self._backup_folder_icon)
        
        self._backup_path_label = QLabel(tr("dialogs.file_organizer.options.backup_path_label", path=display_path))
        self._backup_path_label.setStyleSheet(DesignSystem.get_backup_path_label_style())
        self._backup_path_label.setToolTip(
            tr("dialogs.file_organizer.options.backup_path_tooltip", path=backup_path_str)
        )
        path_layout.addWidget(self._backup_path_label)
        path_layout.addStretch()
        
        container_layout.addWidget(self._backup_path_widget)
        
        # Actualizar visibilidad inicial (solo contenido, no espacio)
        self._update_backup_path_visibility(self.is_backup_enabled())
        
        # Configurar lógica de interacción dry-run/backup (actualiza visibilidad de ruta)
        self._setup_dry_run_backup_logic()
        
        return container
    
    def _create_action_buttons(self) -> QDialogButtonBox:
        """Crea botones de acción con estilo Material Design"""
        # Determinar si el botón OK debe estar habilitado
        ok_enabled = bool(self.analysis and self.analysis.files_to_move > 0)
        
        if ok_enabled:
            size_formatted = format_size(self.analysis.bytes_to_move)
            ok_text = tr("dialogs.file_organizer.button.organize", count=self.analysis.files_to_move, size=size_formatted)
        else:
            ok_text = tr("dialogs.file_organizer.button.select_option")
        
        buttons = self.make_ok_cancel_buttons(
            ok_text=ok_text,
            ok_enabled=ok_enabled,
            button_style='primary'
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        
        return buttons
    
    def _update_ok_button(self):
        """Actualiza el texto y estado del botón OK"""
        if not hasattr(self, 'ok_button') or not self.ok_button:
            return
        
        # Verificar si tenemos análisis disponible
        if not self.analysis:
            self.ok_button.setEnabled(False)
            self.ok_button.setText(tr("dialogs.file_organizer.button.waiting"))
            return
        
        ok_enabled = self.analysis.files_to_move > 0
        final_enabled = ok_enabled and not self.is_analyzing
        
        self.ok_button.setEnabled(final_enabled)
        
        if ok_enabled:
            size_formatted = format_size(self.analysis.bytes_to_move)
            ok_text = tr("dialogs.file_organizer.button.organize", count=self.analysis.files_to_move, size=size_formatted)
        else:
            ok_text = tr("dialogs.file_organizer.button.no_files")
        
        self.ok_button.setText(ok_text)
    
    # === FILTROS ===
    
    def _update_filter_options(self):
        """Actualiza las opciones de los filtros basándose en los datos actuales"""
        if not self.analysis or not self.analysis.move_plan:
            return

        # 1. Categorías
        type_map = {'PHOTO': tr("common.filter.photos"), 'VIDEO': tr("common.filter.videos")}
        categories = set()
        for move in self.analysis.move_plan:
            categories.add(type_map.get(move.file_type, tr("common.filter.others")))
        
        current_cat = self.category_combo.currentText()
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItems([tr("common.filter.all")] + sorted(list(categories)))
        if current_cat in [tr("common.filter.all")] + sorted(list(categories)):
            self.category_combo.setCurrentText(current_cat)
        else:
            self.category_combo.setCurrentIndex(0)
        self.category_combo.blockSignals(False)



        # 3. Estado (Conflictos)
        has_conflicts = any(move.has_conflict for move in self.analysis.move_plan)
        
        current_status = self.status_combo.currentText()
        self.status_combo.blockSignals(True)
        self.status_combo.clear()
        status_items = [tr("common.filter.all")]
        if has_conflicts:
            status_items.extend([tr("dialogs.file_organizer.filter.with_conflicts"), tr("dialogs.file_organizer.filter.without_conflicts")])
        
        self.status_combo.addItems(status_items)
        if current_status in status_items:
            self.status_combo.setCurrentText(current_status)
        else:
            self.status_combo.setCurrentIndex(0)
        self.status_combo.blockSignals(False)

    def _on_source_filter_changed(self, index: int):
        """Maneja cambios en el filtro de origen de fecha."""
        self._apply_filters()
    
    def _apply_filters(self):
        """Aplica filtros a la lista de movimientos"""
        if not self.analysis:
            return
            
        search_text = self.search_input.text().lower() if self.search_input else ""
        source_filter = self.source_combo.currentText() if self.source_combo else self.DATE_SOURCE_FILTER_ALL
        category_filter = self.category_combo.currentText() if self.category_combo else tr("common.filter.all")
        status_filter = self.status_combo.currentText() if self.status_combo else tr("common.filter.all")
        
        self.filtered_moves = []
        
        # Mapeo de categorías
        type_map = {'PHOTO': tr("common.filter.photos"), 'VIDEO': tr("common.filter.videos")}
        
        for move in self.all_moves:
            # Filtro de búsqueda
            if search_text and search_text not in move.original_name.lower():
                continue
            
            # Filtro por origen de fecha
            if source_filter != self.DATE_SOURCE_FILTER_ALL:
                file_path = Path(move.current_path)
                _, date_source = self.repo.get_best_date(file_path) if self.repo else (None, None)
                if not self._matches_source_filter(date_source, source_filter):
                    continue
            
            # Filtro por Categoría
            if category_filter != tr("common.filter.all"):
                move_cat = type_map.get(move.file_type, tr("common.filter.others"))
                if move_cat != category_filter:
                    continue
            
            # Filtro por Estado
            if status_filter == tr("dialogs.file_organizer.filter.with_conflicts") and not move.has_conflict:
                continue
            if status_filter == tr("dialogs.file_organizer.filter.without_conflicts") and move.has_conflict:
                continue
            
            self.filtered_moves.append(move)
        
        # Reiniciar carga progresiva
        self._load_initial_items()
    
    def _clear_filters(self):
        """Limpia todos los filtros"""
        if self.search_input:
            self.search_input.clear()
        if self.source_combo:
            self.source_combo.setCurrentIndex(0)
        if self.category_combo:
            self.category_combo.setCurrentIndex(0)
        if self.status_combo:
            self.status_combo.setCurrentIndex(0)
    
    # ========================================================================
    # LÓGICA DE CARGA PROGRESIVA
    # ========================================================================
    
    def _load_initial_items(self):
        """Carga los items iniciales en el árbol."""
        self.loaded_count = 0
        self._current_group_index = 0
        self._paginated_groups = []
        self.files_tree.clear()
        
        # Reconfigurar columnas si cambió el tipo
        self._configure_tree_columns(self.files_tree)
        
        self._load_more_items()
    
    def _load_more_items(self):
        """Carga más items en el árbol usando paginación por grupos."""
        if not self.filtered_moves:
            self._update_pagination_ui()
            return
        
        org_type = self.current_organization_type
        
        # En la primera carga, preparar los grupos ordenados
        if self.loaded_count == 0:
            self._prepare_groups_for_pagination(org_type)
        
        # Cargar siguiente bloque de grupos
        groups_loaded = 0
        items_loaded = 0
        
        self.files_tree.setUpdatesEnabled(False)
        
        while self._current_group_index < len(self._paginated_groups) and items_loaded < self.LOAD_INCREMENT:
            folder, moves_in_folder = self._paginated_groups[self._current_group_index]
            
            if org_type == OrganizationType.TO_ROOT:
                self._add_tree_group_to_root(folder, moves_in_folder)
            elif org_type in (OrganizationType.BY_MONTH, OrganizationType.BY_YEAR, OrganizationType.BY_YEAR_MONTH):
                self._add_tree_group_temporal(folder, moves_in_folder)
            elif org_type in (OrganizationType.BY_TYPE, OrganizationType.BY_SOURCE):
                self._add_tree_group_category(folder, moves_in_folder)
            
            items_loaded += len(moves_in_folder)
            groups_loaded += 1
            self._current_group_index += 1
        
        self.files_tree.setUpdatesEnabled(True)
        
        self.loaded_count += items_loaded
        self._update_pagination_ui()
    
    def _load_all_items(self):
        """Carga todos los items restantes."""
        from PyQt6.QtWidgets import QMessageBox
        
        if len(self.filtered_moves) > 1000:
            reply = QMessageBox.question(
                self,
                tr("dialogs.file_organizer.dialog_load_all_title"),
                tr("dialogs.file_organizer.dialog_load_all_msg", count=len(self.filtered_moves)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        while self.loaded_count < len(self.filtered_moves):
            self._load_more_items()
    
    def _prepare_groups_for_pagination(self, org_type):
        """Prepara los grupos ordenados para paginación incremental."""
        self._paginated_groups = []
        self._current_group_index = 0
        
        if org_type == OrganizationType.TO_ROOT:
            by_subdir = defaultdict(list)
            for move in self.filtered_moves:
                by_subdir[move.subdirectory].append(move)
            self._paginated_groups = sorted(by_subdir.items(), key=lambda x: str(x[0]))
            
        elif org_type in (OrganizationType.BY_MONTH, OrganizationType.BY_YEAR, OrganizationType.BY_YEAR_MONTH):
            by_folder = defaultdict(list)
            for move in self.filtered_moves:
                folder = move.target_folder or tr("dialogs.file_organizer.tree.no_date")
                by_folder[folder].append(move)
            self._paginated_groups = sorted(by_folder.items(), key=lambda x: x[0], reverse=True)
            
        elif org_type in (OrganizationType.BY_TYPE, OrganizationType.BY_SOURCE):
            by_category = defaultdict(list)
            for move in self.filtered_moves:
                category = move.target_folder or tr("dialogs.file_organizer.tree.no_category")
                by_category[category].append(move)
            
            def category_sort_key(item):
                cat = item[0]
                if cat == "Unknown":
                    return (1, cat)
                return (0, cat)
            self._paginated_groups = sorted(by_category.items(), key=category_sort_key)
    
    def _add_tree_group_to_root(self, subdir: str, moves_in_subdir: list):
        """Añade un grupo de subdirectorio al tree para TO_ROOT."""
        total_size = sum(m.size for m in moves_in_subdir)
        
        subdir_node = QTreeWidgetItem()
        subdir_node.setText(0, tr("dialogs.file_organizer.tree.from_subdir", subdir=subdir, count=len(moves_in_subdir)))
        subdir_node.setText(1, "")
        subdir_node.setText(2, "")
        subdir_node.setText(3, "")
        subdir_node.setText(4, format_size(total_size))
        
        subdir_font = QFont()
        subdir_font.setBold(True)
        subdir_node.setFont(0, subdir_font)
        subdir_node.setForeground(0, QColor(DesignSystem.COLOR_PRIMARY))
        
        self.files_tree.addTopLevelItem(subdir_node)
        
        for move in sorted(moves_in_subdir, key=lambda m: m.original_name):
            child = self._create_file_tree_item(move)
            subdir_node.addChild(child)
    
    def _add_tree_group_temporal(self, folder: str, moves_in_folder: list):
        """Añade un grupo temporal (mes/año) al tree."""
        total_size = sum(m.size for m in moves_in_folder)
        
        parent = QTreeWidgetItem()
        parent.setText(0, tr("dialogs.file_organizer.tree.folder_group", folder=folder, count=len(moves_in_folder)))
        parent.setText(1, "")
        parent.setText(2, "")
        parent.setText(3, "")
        parent.setText(4, format_size(total_size))
        
        parent_font = QFont()
        parent_font.setBold(True)
        parent.setFont(0, parent_font)
        parent.setForeground(0, QColor(DesignSystem.COLOR_PRIMARY))
        
        self.files_tree.addTopLevelItem(parent)
        
        for move in sorted(moves_in_folder, key=lambda m: m.original_name):
            child = self._create_file_tree_item(move)
            parent.addChild(child)
    
    def _add_tree_group_category(self, category: str, moves_in_category: list):
        """Añade un grupo de categoría al tree."""
        total_size = sum(m.size for m in moves_in_category)
        
        parent = QTreeWidgetItem()
        parent.setText(0, tr("dialogs.file_organizer.tree.folder_group", folder=category, count=len(moves_in_category)))
        parent.setText(1, "")
        parent.setText(2, "")
        parent.setText(3, "")
        parent.setText(4, format_size(total_size))
        
        parent_font = QFont()
        parent_font.setBold(True)
        parent.setFont(0, parent_font)
        
        # Colores especiales para categorías conocidas
        if category == "WhatsApp":
            parent.setForeground(0, QColor("#25d366"))
        elif category in ("iPhone", "Android"):
            parent.setForeground(0, QColor("#2196f3"))
        elif category in ("Camera", "Scanner"):
            parent.setForeground(0, QColor("#ff9800"))
        elif category == "Screenshot":
            parent.setForeground(0, QColor("#9c27b0"))
        elif category in ("Photos", "Videos"):
            parent.setForeground(0, QColor(DesignSystem.COLOR_PRIMARY))
        else:
            parent.setForeground(0, QColor(DesignSystem.COLOR_TEXT_SECONDARY))
        
        self.files_tree.addTopLevelItem(parent)
        
        for move in sorted(moves_in_category, key=lambda m: m.original_name):
            child = self._create_file_tree_item(move)
            parent.addChild(child)
    
    def _create_file_tree_item(self, move) -> QTreeWidgetItem:
        """Crea un QTreeWidgetItem para un archivo individual."""
        child = QTreeWidgetItem()
        child.setText(0, f"  {move.source_path}")
        
        if move.has_conflict:
            child.setText(1, move.new_name)
            child.setForeground(1, QColor(DesignSystem.COLOR_ERROR))
        else:
            child.setText(1, tr("dialogs.file_organizer.tree.unchanged"))
            child.setForeground(1, QColor(DesignSystem.COLOR_TEXT_SECONDARY))
        
        file_date = getattr(move, 'best_date', None)
        date_source = getattr(move, 'best_date_source', None)
        if file_date:
            child.setText(2, file_date.strftime("%Y-%m-%d %H:%M:%S"))
            child.setText(3, date_source if date_source else "-")
        else:
            child.setText(2, "-")
            child.setText(3, "-")
        
        child.setText(4, format_size(move.size))
        
        if move.has_conflict:
            child.setForeground(0, QColor(DesignSystem.COLOR_ERROR))
        
        child.setData(0, Qt.ItemDataRole.UserRole, move.source_path)
        return child
    
    def _update_pagination_ui(self):
        """Actualiza la UI de la barra de carga progresiva."""
        if self.pagination_bar and self.analysis:
            self._update_progressive_loading_ui(
                pagination_bar=self.pagination_bar,
                loaded_count=self.loaded_count,
                filtered_count=len(self.filtered_moves),
                total_count=len(self.all_moves),
                load_increment=self.LOAD_INCREMENT
            )
        
        # Actualizar chip de estado (independiente del loaded_count)
        self._update_filter_chip(
            status_chip=self.status_chip,
            filtered_count=len(self.filtered_moves),
            total_count=len(self.all_moves),
            loaded_count=self.loaded_count,
            is_files_mode=True
        )
    
    # === EVENTOS ===
    
    def _on_file_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Abre el archivo con doble clic"""
        from .dialog_utils import handle_tree_item_double_click
        handle_tree_item_double_click(item, column, self)
    
    def _show_context_menu(self, position):
        """Muestra menú contextual estándar para archivos."""
        show_file_context_menu(
            tree_widget=self.files_tree,
            position=position,
            parent_widget=self,
            details_callback=self._show_file_details
        )
    
    def _show_file_details(self, file_path: Path):
        """Muestra detalles del archivo"""
        # Buscar el move correspondiente al file_path
        move = self._find_move_by_path(file_path)
        
        if not move:
            show_file_details_dialog(file_path, self)
            return
        
        additional_info = {
            'original_name': move.original_name,
            'new_name': move.new_name,
            'file_type': move.file_type,
            'target_path': move.target_path,
            'conflict': move.has_conflict,
            'sequence': move.sequence if move.has_conflict else None,
            'metadata': {
                tr('dialogs.file_organizer.details.subdir'): move.subdirectory,
            }
        }
        
        if move.target_folder:
            additional_info['metadata'][tr('dialogs.file_organizer.details.target_folder')] = move.target_folder
        
        show_file_details_dialog(file_path, self, additional_info)
    
    def _find_move_by_path(self, file_path: Path):
        """Busca el move correspondiente a un file_path."""
        for m in self.filtered_moves:
            if m.source_path == file_path:
                return m
        return None
    
    def accept(self):
        """Acepta el diálogo y construye el plan"""
        # Validar que hay archivos para mover
        if not self.analysis or not self.analysis.move_plan:
            self.show_no_items_message(tr("dialogs.file_organizer.no_items_type"))
            return
        
        # Pasar el analysis completo + parámetros por separado
        self.accepted_plan = {
            'analysis': self.analysis,  # Ya es OrganizationAnalysisResult dataclass
            'cleanup_empty_dirs': self.is_cleanup_enabled(),
            'create_backup': self.is_backup_enabled(),
            'dry_run': self.is_dry_run_enabled()
        }
        super().accept()
