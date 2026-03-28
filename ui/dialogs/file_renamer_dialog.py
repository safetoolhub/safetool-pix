# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Diálogo de renombrado de archivos
Incluye filtrado, búsqueda, estadísticas detalladas y mejor UX
Usa QTreeWidget con carpetas como nodos padre para consistencia con otros diálogos
"""
from pathlib import Path
from collections import defaultdict
from PyQt6.QtWidgets import (
    QVBoxLayout, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QDialogButtonBox, QLabel, QWidget
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from utils.format_utils import format_size
from utils.settings_manager import settings_manager
from utils.file_utils import get_file_type, is_image_file, is_video_file
from services.result_types import RenamePlanItem
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from ui.tools_definitions import TOOL_FILE_RENAMER
from utils.logger import get_logger
from utils.i18n import tr
from .base_dialog import BaseDialog
from .dialog_utils import (
    open_file, show_file_context_menu, show_file_details_dialog,
    create_groups_tree_widget, handle_tree_item_double_click, apply_group_item_style
)


class FileRenamerDialog(BaseDialog):
    """Diálogo de preview para renombrado con funcionalidades avanzadas"""
    
    # Constantes para carga progresiva
    INITIAL_LOAD = 100
    LOAD_INCREMENT = 100
    WARNING_THRESHOLD = 500

    def __init__(self, analysis_results, parent=None):
        super().__init__(parent)
        self.logger = get_logger('RenamingPreviewDialog')
        self.analysis_results = analysis_results  # RenameAnalysisResult (dataclass)
        self.accepted_plan = None
        
        # Datos de archivos
        try:
            self.all_items = list(analysis_results.renaming_plan)
            self.filtered_plan = list(analysis_results.renaming_plan)
        except AttributeError as e:
            self.logger.error(f"Error accediendo a renaming_plan: {e}")
            self.all_items = []
            self.filtered_plan = []
        
        # Carga progresiva (por grupos/carpetas)
        self.loaded_groups = 0
        self.all_groups = []  # Lista de (folder_path, files)
        self.filtered_groups = []
        self.pagination_bar = None
        
        self.init_ui()
        self._organize_by_folders()
        self._load_initial_groups()

    def update_statistics(self, results):
        """Actualiza las estadísticas después del renombrado
        
        Args:
            results: RenameExecutionResult (dataclass)
        """
        if hasattr(self, 'stats_labels'):
            self.stats_labels['renamed'].setText(str(results.files_renamed))
            self.stats_labels['conflicts'].setText(str(results.conflicts_resolved))
            self.stats_labels['errors'].setText(str(len(results.errors)))

    def init_ui(self):
        self.setWindowTitle(TOOL_FILE_RENAMER.title)
        self.setModal(True)
        self.resize(1200, 800)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, int(DesignSystem.SPACE_20))
        
        # Header compacto integrado con métricas inline
        header = self._create_compact_header_with_metrics(
            icon_name=TOOL_FILE_RENAMER.icon_name,
            title=TOOL_FILE_RENAMER.title,
            description=TOOL_FILE_RENAMER.short_description,
            metrics=[
                {
                    'value': str(self.analysis_results.items_count),
                    'label': tr("dialogs.file_renamer.metric_total"),
                    'color': DesignSystem.COLOR_PRIMARY
                },
                {
                    'value': str(self.analysis_results.already_renamed),
                    'label': tr("dialogs.file_renamer.metric_ok"),
                    'color': DesignSystem.COLOR_SUCCESS
                },
                {
                    'value': str(self.analysis_results.need_renaming),
                    'label': tr("dialogs.file_renamer.metric_rename"),
                    'color': DesignSystem.COLOR_WARNING
                },
                {
                    'value': str(self.analysis_results.conflicts),
                    'label': tr("dialogs.file_renamer.metric_conflicts"),
                    'color': DesignSystem.COLOR_ERROR
                }
            ]
        )
        main_layout.addWidget(header)
        
        # Contenedor con margen para el resto del contenido
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setSpacing(int(DesignSystem.SPACE_16))
        content_layout.setContentsMargins(
            int(DesignSystem.SPACE_24),
            int(DesignSystem.SPACE_12),
            int(DesignSystem.SPACE_24),
            0
        )
        main_layout.addWidget(content_container)
        
        # Sección de información y advertencias
        info_section = self._create_info_section()
        content_layout.addWidget(info_section)
        
        # Barra de filtros unificada
        self.filter_bar = self._create_filter_bar()
        content_layout.addWidget(self.filter_bar)
        
        # TreeWidget de cambios propuestos (reemplaza QTableWidget)
        self.tree_widget = self._create_tree_widget()
        content_layout.addWidget(self.tree_widget)
        
        # Barra de carga progresiva
        self.pagination_bar = self._create_progressive_loading_bar(
            on_load_more=self._load_more_groups,
            on_load_all=self._load_all_groups
        )
        content_layout.addWidget(self.pagination_bar)
        
        # Panel de problemas (si hay) - colapsable al final
        if self.analysis_results.issues:
            problems_widget = self._create_problems_section()
            content_layout.addWidget(problems_widget)
        
        # Opciones de seguridad
        options_group = self._create_options_group()
        content_layout.addWidget(options_group)
        
        # Botones con estilo Material Design
        ok_enabled = self.analysis_results.need_renaming > 0
        ok_text = tr("dialogs.file_renamer.button_proceed", count=self.analysis_results.need_renaming) if ok_enabled else None
        buttons = self.make_ok_cancel_buttons(
            ok_text=ok_text,
            ok_enabled=ok_enabled,
            button_style='primary'
        )
        self.buttons = buttons
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        content_layout.addWidget(buttons)

    def _create_info_section(self):
        """Crea sección de información y advertencias"""
        message = tr("dialogs.file_renamer.info.message")
        
        return self._create_info_banner(
            title=tr("dialogs.file_renamer.info.title"),
            message=message
        )

    def _create_filter_bar(self) -> QWidget:
        """Crea barra de filtros unificada usando método base"""
        # Preparar opciones para filtros dinámicos
        file_types = sorted(list(set(
            get_file_type(item.original_path.name) 
            for item in self.analysis_results.renaming_plan
        )))
        date_sources = sorted(list(set(
            item.date_source or tr("common.unknown") 
            for item in self.analysis_results.renaming_plan
        )))
        years = [str(year) for year in sorted(self.analysis_results.files_by_year.keys(), reverse=True)]
        
        # Diccionario de etiquetas
        labels = {
            'search': tr("dialogs.file_renamer.filter.search"),
            'groups': tr("dialogs.file_renamer.filter.groups"),
            'conflict': tr("dialogs.file_renamer.filter.conflict"),
            'file_type': tr("dialogs.file_renamer.filter.file_type"),
            'source': tr("dialogs.file_renamer.filter.source"),
            'year': tr("dialogs.file_renamer.filter.year")
        }
        
        # Configuración de filtros expandibles
        expandable_filters = [
            {
                'id': 'conflict',
                'type': 'combo',
                'label': labels['conflict'],
                'tooltip': tr("dialogs.file_renamer.filter.conflict_tooltip"),
                'options': [tr("common.filter.all"), tr("dialogs.file_renamer.filter.only_conflicts"), tr("dialogs.file_renamer.filter.no_conflicts")],
                'on_change': lambda idx: self._apply_filters(),
                'default_index': 0,
                'min_width': 150
            },
            {
                'id': 'file_type',
                'type': 'combo',
                'label': labels['file_type'],
                'tooltip': tr("dialogs.file_renamer.filter.type_tooltip"),
                'options': [tr("common.filter.all")] + file_types,
                'on_change': lambda idx: self._apply_filters(),
                'default_index': 0,
                'min_width': 120
            },
            {
                'id': 'source',
                'type': 'combo',
                'label': labels['source'],
                'tooltip': tr("dialogs.file_renamer.filter.source_tooltip"),
                'options': [tr("common.filter.all")] + date_sources,
                'on_change': lambda idx: self._apply_filters(),
                'default_index': 0,
                'min_width': 180
            },
            {
                'id': 'year',
                'type': 'combo',
                'label': labels['year'],
                'tooltip': tr("dialogs.file_renamer.filter.year_tooltip"),
                'options': [tr("common.filter.all")] + years,
                'on_change': lambda idx: self._apply_filters(),
                'default_index': 0,
                'min_width': 100
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
        
        # Referencias a filtros expandibles
        self.filter_combo = filter_bar.filter_widgets.get('conflict')
        self.type_combo = filter_bar.filter_widgets.get('file_type')
        self.source_combo = filter_bar.filter_widgets.get('source')
        self.year_combo = filter_bar.filter_widgets.get('year')
        
        return filter_bar
    
    def _create_tree_widget(self) -> QTreeWidget:
        """Crea el widget de árbol para mostrar archivos agrupados por carpeta."""
        headers = [tr("dialogs.file_renamer.tree_header.folder_file"), tr("dialogs.file_renamer.tree_header.new_name"), tr("common.tree_header.date"), tr("dialogs.file_renamer.tree_header.source"), tr("common.tree_header.type")]
        column_widths = [350, 250, 140, 120, 80]
        
        return create_groups_tree_widget(
            headers=headers,
            column_widths=column_widths,
            double_click_handler=self._on_item_double_clicked,
            context_menu_handler=self._show_context_menu
        )

    def _create_problems_section(self):
        """Crea sección colapsable de problemas"""
        group = QGroupBox(tr("dialogs.file_renamer.problems.title", count=len(self.analysis_results.issues)))
        group.setCheckable(True)
        group.setChecked(False)  # Colapsado por defecto
        group.setMaximumHeight(150)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                margin-top: {DesignSystem.SPACE_12}px;
                padding-top: {DesignSystem.SPACE_12}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {DesignSystem.SPACE_12}px;
                padding: 0 {DesignSystem.SPACE_4}px;
            }}
        """)
        
        layout = QVBoxLayout()
        
        info = QLabel(tr("dialogs.file_renamer.problems.description"))
        info.setStyleSheet(f"color: {DesignSystem.COLOR_WARNING}; font-size: {DesignSystem.FONT_SIZE_SM}px;")
        layout.addWidget(info)
        
        # Lista simple de problemas
        problems_text = "\n".join(self.analysis_results.issues[:10])
        if len(self.analysis_results.issues) > 10:
            problems_text += tr("dialogs.file_renamer.problems.and_more", count=len(self.analysis_results.issues) - 10)
        
        problems_label = QLabel(problems_text)
        problems_label.setWordWrap(True)
        problems_label.setStyleSheet(f"font-size: {DesignSystem.FONT_SIZE_SM}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        layout.addWidget(problems_label)
        
        group.setLayout(layout)
        return group

    def _create_options_group(self):
        """Crea el grupo de opciones de seguridad usando método centralizado"""
        return self._create_security_options_section(
            show_backup=True,
            show_dry_run=True,
            backup_label=tr("dialogs.file_renamer.option_backup"),
            dry_run_label=tr("dialogs.file_renamer.option_dry_run")
        )

    # ========================================================================
    # ORGANIZACIÓN Y FILTRADO
    # ========================================================================

    def _organize_by_folders(self):
        """Organiza los archivos por carpeta para el TreeWidget."""
        folders = defaultdict(list)
        for item in self.filtered_plan:
            folder = item.original_path.parent
            folders[folder].append(item)
        
        # Ordenar carpetas y crear lista de grupos
        self.all_groups = sorted(folders.items(), key=lambda x: str(x[0]))
        self.filtered_groups = list(self.all_groups)

    def _apply_filters(self):
        """Aplica los filtros y reorganiza por carpetas"""
        search_text = self.search_input.text().lower() if self.search_input else ""
        filter_option = self.filter_combo.currentText() if self.filter_combo else tr("common.filter.all")
        year_filter = self.year_combo.currentText() if self.year_combo else tr("common.filter.all")
        type_filter = self.type_combo.currentText() if self.type_combo else tr("common.filter.all")
        source_filter = self.source_combo.currentText() if self.source_combo else tr("common.filter.all")
        
        self.filtered_plan = []
        
        for item in self.all_items:
            # Filtro de búsqueda
            if search_text and search_text not in item.original_path.name.lower():
                continue
            
            # Filtro por conflicto
            if filter_option == tr("dialogs.file_renamer.filter.only_conflicts") and not item.has_conflict:
                continue
            elif filter_option == tr("dialogs.file_renamer.filter.no_conflicts") and item.has_conflict:
                continue
            
            # Filtro por año
            if year_filter != tr("common.filter.all") and str(item.date.year) != year_filter:
                continue
            
            # Filtro por tipo de archivo
            if type_filter != tr("common.filter.all"):
                file_type = get_file_type(item.original_path.name)
                if file_type != type_filter:
                    continue
            
            # Filtro por fuente de fecha
            if source_filter != tr("common.filter.all"):
                item_source = item.date_source or tr("common.unknown")
                if item_source != source_filter:
                    continue
            
            self.filtered_plan.append(item)
        
        # Reorganizar por carpetas y recargar
        self._organize_by_folders()
        self._load_initial_groups()

    # ========================================================================
    # LÓGICA DE CARGA PROGRESIVA
    # ========================================================================
    
    def _load_initial_groups(self):
        """Carga los grupos iniciales en el árbol."""
        self.loaded_groups = 0
        self.tree_widget.clear()
        self._load_more_groups()
    
    def _load_more_groups(self):
        """Carga más grupos (carpetas) en el árbol."""
        start = self.loaded_groups
        end = min(start + self.LOAD_INCREMENT, len(self.filtered_groups))
        
        groups_to_load = self.filtered_groups[start:end]
        
        # Optimización: desactivar updates durante la carga
        self.tree_widget.setUpdatesEnabled(False)
        
        for folder_path, files in groups_to_load:
            self._add_folder_group(folder_path, files)
        
        # Reactivar updates
        self.tree_widget.setUpdatesEnabled(True)
        
        self.loaded_groups = end
        self._update_pagination_ui()
    
    def _add_folder_group(self, folder_path: Path, files: list):
        """Añade un grupo de carpeta con sus archivos al árbol."""
        # Crear nodo de carpeta
        folder_item = QTreeWidgetItem(self.tree_widget)
        folder_name = str(folder_path.relative_to(folder_path.anchor)) if folder_path.anchor else str(folder_path)
        folder_item.setText(0, tr("dialogs.file_renamer.tree.folder_label", name=folder_name, count=len(files)))
        folder_item.setExpanded(True)
        
        # Aplicar estilo de grupo
        apply_group_item_style(folder_item, num_columns=5)
        
        # Tooltip del grupo
        conflicts_in_folder = sum(1 for f in files if f.has_conflict)
        tooltip = tr("dialogs.file_renamer.tree.folder_tooltip", path=folder_path, count=len(files))
        if conflicts_in_folder:
            tooltip += "\n" + tr("dialogs.file_renamer.tree.conflicts_tooltip", count=conflicts_in_folder)
        folder_item.setToolTip(0, tooltip)
        
        # Añadir archivos como hijos
        for file_info in files:
            self._add_file_item(folder_item, file_info)
    
    def _add_file_item(self, parent_item: QTreeWidgetItem, file_info: RenamePlanItem):
        """Añade un archivo como hijo de una carpeta."""
        file_path = file_info.original_path
        has_conflict = file_info.has_conflict
        
        file_item = QTreeWidgetItem(parent_item)
        
        # Columna 0: Nombre original
        file_item.setText(0, file_path.name)
        file_item.setData(0, Qt.ItemDataRole.UserRole, file_path)  # Para menú contextual
        
        # Icono según tipo
        icon_name = 'image' if is_image_file(file_path) else 'video' if is_video_file(file_path) else 'file'
        file_item.setIcon(0, icon_manager.get_icon(icon_name, size=16))
        
        # Columna 1: Nuevo nombre
        file_item.setText(1, file_info.new_name)
        
        # Columna 2: Fecha
        file_item.setText(2, file_info.date.strftime('%Y-%m-%d %H:%M:%S'))
        
        # Columna 3: Fuente de fecha
        file_item.setText(3, file_info.date_source or tr("common.unknown"))
        
        # Columna 4: Tipo
        file_item.setText(4, get_file_type(file_path.name))
        
        # Resaltar conflictos
        if has_conflict:
            conflict_color = QColor(255, 200, 200)
            for col in range(5):
                file_item.setBackground(col, conflict_color)
            file_item.setToolTip(0, tr("dialogs.file_renamer.tree.conflict_file_tooltip"))
    
    def _load_all_groups(self):
        """Carga todos los grupos restantes."""
        from PyQt6.QtWidgets import QMessageBox
        
        total_files = len(self.filtered_plan)
        if total_files > 1000:
            reply = QMessageBox.question(
                self,
                tr("dialogs.file_renamer.dialog_load_all_title"),
                tr("dialogs.file_renamer.dialog_load_all_msg",
                   count=total_files, folders=len(self.filtered_groups)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        while self.loaded_groups < len(self.filtered_groups):
            self._load_more_groups()
    
    def _update_pagination_ui(self):
        """Actualiza la UI de la barra de carga progresiva."""
        # Contar archivos cargados
        loaded_files = sum(len(files) for _, files in self.filtered_groups[:self.loaded_groups])
        total_files = len(self.filtered_plan)
        
        if self.pagination_bar:
            self._update_progressive_loading_ui(
                pagination_bar=self.pagination_bar,
                loaded_count=loaded_files,
                filtered_count=total_files,
                total_count=len(self.all_items),
                load_increment=self.LOAD_INCREMENT
            )
        
        # Actualizar chip de estado
        self._update_filter_chip(
            status_chip=self.status_chip,
            filtered_count=total_files,
            total_count=len(self.all_items),
            loaded_count=loaded_files,
            is_files_mode=True
        )

    # ========================================================================
    # EVENTOS
    # ========================================================================
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Maneja doble clic: expande grupos o abre archivos."""
        handle_tree_item_double_click(item, column, self)
    
    def _show_context_menu(self, position):
        """Muestra menú contextual estándar para archivos."""
        show_file_context_menu(
            tree_widget=self.tree_widget,
            position=position,
            parent_widget=self,
            details_callback=self._show_file_details
        )
    
    def _show_file_details(self, file_path: Path):
        """Muestra un diálogo con detalles completos del archivo"""
        # Buscar información del archivo en filtered_plan
        file_info = None
        for plan_item in self.filtered_plan:
            if plan_item.original_path == file_path:
                file_info = plan_item
                break
        
        if not file_info:
            show_file_details_dialog(file_path, self)
            return
        
        file_type = tr("common.file_type.image") if is_image_file(file_path) else tr("common.file_type.video") if is_video_file(file_path) else tr("common.unknown")
        
        additional_info = {
            'original_name': file_path.name,
            'new_name': file_info.new_name,
            'file_type': file_type,
            'conflict': file_info.has_conflict,
            'metadata': {
                tr("dialogs.file_renamer.details.detected_date"): file_info.date.strftime('%Y-%m-%d %H:%M:%S'),
                tr("dialogs.file_renamer.details.date_source"): file_info.date_source or tr("common.unknown"),
                tr("dialogs.file_renamer.details.year"): str(file_info.date.year),
            }
        }
        
        if file_info.has_conflict:
            additional_info['metadata'][tr("dialogs.file_renamer.details.conflict_key")] = tr("dialogs.file_renamer.details.conflict_value")
            if file_info.sequence:
                additional_info['metadata'][tr("dialogs.file_renamer.details.sequence")] = f"#{file_info.sequence}"
        
        show_file_details_dialog(file_path, self, additional_info)

    def accept(self):
        # Validar que hay archivos para renombrar
        if not self.analysis_results or not self.analysis_results.renaming_plan:
            self.show_no_items_message(tr("dialogs.file_renamer.no_items_type"))
            return
        
        self.accepted_plan = {
            'analysis': self.analysis_results,
            'create_backup': self.is_backup_enabled(),
            'dry_run': self.is_dry_run_enabled()
        }
        super().accept()
