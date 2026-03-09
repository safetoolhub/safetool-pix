# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Diálogo de eliminación de duplicados HEIC/JPG
Grupos expandibles con archivos HEIC y JPG individuales, diseño Material Design
"""
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QVBoxLayout, QDialogButtonBox, 
    QTreeWidgetItem,
    QFrame, QWidget
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from utils.format_utils import format_size
from utils.i18n import tr
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from ui.tools_definitions import TOOL_HEIC
from .base_dialog import BaseDialog


class HeicDialog(BaseDialog):
    """Diálogo para eliminación de duplicados HEIC/JPG con vista de grupos expandibles"""
    
    # Constantes para carga progresiva
    INITIAL_LOAD = 100
    LOAD_INCREMENT = 100
    WARNING_THRESHOLD = 500

    def __init__(self, analysis, parent=None):
        super().__init__(parent)
        self.analysis = analysis
        self.selected_format = 'jpg'
        self.accepted_plan = None
        
        # Datos de grupos
        self.all_pairs = list(analysis.duplicate_pairs)
        self.filtered_pairs = list(analysis.duplicate_pairs)
        self.loaded_count = 0
        
        # Referencias a widgets
        self.tree_widget = None
        self.search_input = None
        self.filter_combo = None
        self.status_chip = None
        self.source_combo = None
        self.dir_combo = None
        self.filter_bar = None
        self.pagination_bar = None
        
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(TOOL_HEIC.title)
        self.setModal(True)
        self.resize(1200, 800)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(int(DesignSystem.SPACE_12))
        main_layout.setContentsMargins(0, 0, 0, int(DesignSystem.SPACE_20))
        
        # Header compacto integrado con métricas inline
        initial_recoverable = self.analysis.potential_savings_keep_jpg if self.selected_format == 'jpg' else self.analysis.potential_savings_keep_heic
        
        self.header_frame = self._create_compact_header_with_metrics(
            icon_name=TOOL_HEIC.icon_name,
            title=TOOL_HEIC.title,
            description=TOOL_HEIC.short_description,
            metrics=[
                {
                    'value': str(self.analysis.items_count),
                    'label': tr("dialogs.heic.metric_groups"),
                    'color': DesignSystem.COLOR_PRIMARY
                },
                {
                    'value': format_size(initial_recoverable),
                    'label': tr("dialogs.heic.metric_recoverable"),
                    'color': DesignSystem.COLOR_SUCCESS
                }
            ]
        )
        main_layout.addWidget(self.header_frame)
        
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
        
        # Selector de formato con cards
        self.format_selector = self._create_format_selector()
        content_layout.addWidget(self.format_selector)
        
        # Barra de filtros unificada
        self.filter_bar = self._create_filter_bar()
        content_layout.addWidget(self.filter_bar)
        
        # TreeWidget de grupos expandibles
        self.tree_widget = self._create_files_tree()
        content_layout.addWidget(self.tree_widget)
        
        # Barra de carga progresiva
        self.pagination_bar = self._create_progressive_loading_bar(
            on_load_more=self._load_more_groups,
            on_load_all=self._load_all_groups
        )
        content_layout.addWidget(self.pagination_bar)
        
        # Opciones de seguridad
        options_group = self._create_options_group()
        content_layout.addWidget(options_group)
        
        # Botones con estilo Material Design
        ok_enabled = self.analysis.items_count > 0
        self.buttons = self.make_ok_cancel_buttons(
            ok_enabled=ok_enabled,
            button_style='danger'
        )
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_enabled:
            self._update_button_text()
        content_layout.addWidget(self.buttons)
        
        # Cargar grupos iniciales
        self._load_initial_groups()

    def _create_format_selector(self) -> QFrame:
        """Crea selector de formato usando el diseño compacto horizontal."""
        formats = [
            ('jpg', 'file-jpg-box', tr("dialogs.heic.strategy.jpg_title"), 
             tr("dialogs.heic.strategy.jpg_desc", size=format_size(self.analysis.potential_savings_keep_jpg))),
            ('heic', 'file-image', tr("dialogs.heic.strategy.heic_title"), 
             tr("dialogs.heic.strategy.heic_desc", size=format_size(self.analysis.potential_savings_keep_heic)))
        ]
        
        frame = self._create_compact_strategy_selector(
            title=tr("dialogs.heic.strategy.title"),
            description=tr("dialogs.heic.strategy.description"),
            strategies=formats,
            current_strategy=self.selected_format,
            on_strategy_changed=self._on_format_changed
        )
        
        # Guardar referencia a los botones para actualizarlos posteriormente
        self.format_buttons = frame.strategy_buttons
        
        return frame
    
    def _on_format_changed(self, new_format: str) -> None:
        """Maneja el cambio de formato seleccionado.
        
        Args:
            new_format: Nuevo formato seleccionado ('jpg' o 'heic')
        """
        if new_format == self.selected_format:
            return
        
        self.selected_format = new_format
        
        # Actualizar estilos de los botones
        if hasattr(self, 'format_buttons'):
            for fmt, btn in self.format_buttons.items():
                btn.setChecked(fmt == new_format)
        
        # Actualizar métrica de espacio recuperable en el header
        recoverable_space = self.analysis.potential_savings_keep_jpg if new_format == 'jpg' else self.analysis.potential_savings_keep_heic
        self._update_header_metric(self.header_frame, tr("dialogs.heic.metric_recoverable"), format_size(recoverable_space))
        
        # Actualizar texto del botón OK
        self._update_button_text()
        
        # Recargar árbol con nuevo formato
        self._load_initial_groups()
    
    def _create_filter_bar(self) -> QFrame:
        """Crea la barra de filtros unificada."""
        # Extraer directorios únicos
        directories = sorted(list(set(
            str(pair.directory) for pair in self.analysis.duplicate_pairs
        )))
        dir_options = [tr("common.filter.all_directories")] + directories
        
        # Opciones para filtro de origen de fecha (usar constantes de BaseDialog)
        source_options = self.DATE_SOURCE_FILTER_OPTIONS
        
        # Diccionario de etiquetas
        labels = {
            'search': tr("dialogs.heic.filter.search"),
            'size': tr("dialogs.heic.filter.size"),
            'groups': tr("dialogs.heic.filter.groups"),
            'source': tr("dialogs.heic.filter.source"),
            'directory': tr("dialogs.heic.filter.directory")
        }
        
        # Configuración de filtros expandibles
        expandable_filters = [
            {
                'id': 'source',
                'type': 'combo',
                'label': labels['source'],
                'tooltip': tr("dialogs.heic.filter.source_tooltip"),
                'options': source_options,
                'on_change': self._on_source_filter_changed,
                'default_index': 0,
                'min_width': 200
            },
            {
                'id': 'directory',
                'type': 'combo',
                'label': labels['directory'],
                'tooltip': tr("dialogs.heic.filter.dir_tooltip"),
                'options': dir_options,
                'on_change': self._on_dir_filter_changed,
                'default_index': 0,
                'min_width': 200
            }
        ]
        
        filter_bar = self._create_unified_filter_bar(
            on_search_changed=self._on_search_changed,
            on_size_filter_changed=self._on_size_filter_changed,
            expandable_filters=expandable_filters,
            is_files_mode=False,
            labels=labels
        )
        
        # Guardar referencias
        self.search_input = filter_bar.search_input
        self.filter_combo = filter_bar.size_filter_combo
        self.status_chip = filter_bar.status_chip
        self.source_combo = filter_bar.filter_widgets.get('source')
        self.dir_combo = filter_bar.filter_widgets.get('directory')
        
        return filter_bar
    
    def _on_search_changed(self, text: str):
        """Maneja cambios en la búsqueda."""
        self._apply_filters()
    
    def _on_size_filter_changed(self, index: int):
        """Maneja cambios en el filtro de tamaño."""
        self._apply_filters()
    
    def _on_source_filter_changed(self, index: int):
        """Maneja cambios en el filtro de origen de fecha."""
        self._apply_filters()
    
    def _on_dir_filter_changed(self, index: int):
        """Maneja cambios en el filtro de directorio."""
        self._apply_filters()
    
    def _create_files_tree(self):
        """Crea TreeWidget con grupos expandibles estilo Material Design"""
        from .dialog_utils import create_groups_tree_widget
        
        return create_groups_tree_widget(
            headers=[tr("common.tree_header.groups_files"), tr("common.tree_header.size"), tr("common.tree_header.type"), tr("common.tree_header.date"), tr("common.tree_header.date_source"), tr("common.tree_header.status")],
            column_widths=[300, 100, 80, 160, 150, 120],
            double_click_handler=self._on_item_double_clicked,
            context_menu_handler=self._show_context_menu
        )
    
    def _create_options_group(self):
        """Crea grupo de opciones de seguridad usando método centralizado"""
        return self._create_security_options_section(
            show_backup=True,
            show_dry_run=True,
            backup_label=tr("dialogs.heic.option_backup"),
            dry_run_label=tr("dialogs.heic.option_dry_run")
        )
    
    def _apply_filters(self):
        """Aplica filtros a la lista de grupos"""
        search_text = self.search_input.text().lower()
        size_filter_index = self.filter_combo.currentIndex()
        
        # Obtener valores de filtros expandibles
        dir_filter = self.dir_combo.currentText() if self.dir_combo else tr("common.filter.all_directories")
        source_filter = self.source_combo.currentText() if self.source_combo else self.DATE_SOURCE_FILTER_ALL
        
        self.filtered_pairs = []
        
        for pair in self.all_pairs:
            # Filtro de búsqueda
            if search_text and search_text not in pair.base_name.lower():
                continue
            
            # Filtro por directorio
            if dir_filter != tr("common.filter.all_directories") and str(pair.directory) != dir_filter:
                continue
            
            # Filtro por origen de fecha
            if not self._matches_source_filter(pair.date_source, source_filter):
                continue
            
            # Filtro por tamaño
            if size_filter_index == 1:  # >10 MB
                if pair.total_size < 10 * 1024 * 1024:
                    continue
            elif size_filter_index == 2:  # >50 MB
                if pair.total_size < 50 * 1024 * 1024:
                    continue
            elif size_filter_index == 3:  # >100 MB
                if pair.total_size < 100 * 1024 * 1024:
                    continue
            
            self.filtered_pairs.append(pair)
        
        # Reiniciar carga progresiva
        self._load_initial_groups()
    
    # ========================================================================
    # LÓGICA DE CARGA PROGRESIVA
    # ========================================================================
    
    def _load_initial_groups(self):
        """Carga los grupos iniciales en el árbol."""
        self.loaded_count = 0
        self.tree_widget.clear()
        self._load_more_groups()
    
    def _load_more_groups(self):
        """Carga más grupos en el árbol."""
        start = self.loaded_count
        end = min(start + self.LOAD_INCREMENT, len(self.filtered_pairs))
        
        # Determinar qué se conservará y eliminará según formato seleccionado
        format_to_keep = "JPG" if self.selected_format == 'jpg' else "HEIC"
        format_to_delete = "HEIC" if self.selected_format == 'jpg' else "JPG"
        
        for i in range(start, end):
            pair = self.filtered_pairs[i]
            self._add_group_to_tree(pair, i + 1, format_to_keep, format_to_delete)
        
        self.loaded_count = end
        self._update_pagination_ui()
    
    def _load_all_groups(self):
        """Carga todos los grupos restantes."""
        from PyQt6.QtWidgets import QMessageBox
        
        if len(self.filtered_pairs) > 1000:
            reply = QMessageBox.question(
                self,
                tr("common.dialog.load_all_groups_title"),
                tr("common.dialog.load_all_groups_msg", count=len(self.filtered_pairs)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        while self.loaded_count < len(self.filtered_pairs):
            self._load_more_groups()
    
    def _update_pagination_ui(self):
        """Actualiza la UI de la barra de carga progresiva."""
        if self.pagination_bar:
            self._update_progressive_loading_ui(
                pagination_bar=self.pagination_bar,
                loaded_count=self.loaded_count,
                filtered_count=len(self.filtered_pairs),
                total_count=len(self.all_pairs),
                load_increment=self.LOAD_INCREMENT
            )
        
        # Actualizar chip de estado
        if self.status_chip:
            self._update_filter_chip(
                self.status_chip,
                len(self.filtered_pairs),
                len(self.all_pairs),
                self.loaded_count,
                is_files_mode=False
            )
    
    def _add_group_to_tree(self, pair, group_number, format_to_keep, format_to_delete):
        """Añade un grupo como nodo padre expandible con archivos HEIC y JPG"""
        from .dialog_utils import apply_group_item_style, create_group_tooltip
        
        # Nodo padre del grupo
        group_item = QTreeWidgetItem(self.tree_widget)
        
        # Texto del grupo - Solo columna 0
        group_item.setText(0, tr("dialogs.heic.tree.group_label", num=group_number, name=pair.base_name))
        
        # Fecha y origen en el grupo
        group_date = pair.heic_date or pair.jpg_date
        if group_date:
            group_item.setText(3, group_date.strftime('%d/%m/%Y %H:%M:%S'))
        group_item.setText(4, pair.date_source or "")
        
        # Aplicar estilo unificado de grupo
        apply_group_item_style(group_item, num_columns=6)
        
        # Tooltip informativo
        extra_info = ""
        if pair.date_source:
            extra_info = tr("dialogs.heic.tooltip.common_date", source=pair.date_source)
            if pair.date_difference is not None:
                extra_info += "\n" + tr("dialogs.heic.tooltip.date_diff", diff=pair.date_difference)
        
        group_item.setToolTip(0, create_group_tooltip(
            group_number, 
            tr("dialogs.heic.tooltip.group_desc", name=pair.base_name),
            extra_info
        ))
        
        # Añadir archivo HEIC como hijo
        heic_item = QTreeWidgetItem(group_item)
        heic_item.setIcon(0, icon_manager.get_icon('camera', size=16))
        heic_item.setText(0, pair.heic_path.name)
        heic_item.setText(1, format_size(pair.heic_size))
        heic_item.setText(2, "HEIC")
        if pair.heic_date:
            heic_item.setText(3, pair.heic_date.strftime('%d/%m/%Y %H:%M:%S'))
        heic_item.setText(4, pair.date_source or "")
        
        if format_to_delete == "HEIC":
            heic_item.setText(5, tr("common.status.mark_delete"))
            heic_item.setForeground(5, QColor(DesignSystem.COLOR_ERROR))
        else:
            heic_item.setText(5, tr("common.status.mark_keep"))
            heic_item.setForeground(5, QColor(DesignSystem.COLOR_SUCCESS))
        
        # Guardar referencia al archivo HEIC
        heic_item.setData(0, Qt.ItemDataRole.UserRole, pair.heic_path)
        
        # Tooltip para HEIC
        heic_mtime = datetime.fromtimestamp(pair.heic_path.stat().st_mtime)
        heic_tooltip = (f"<b>{pair.heic_path.name}</b><br>"
                       f"{tr('common.tooltip.folder')} {pair.heic_path.parent}<br>"
                       f"{tr('common.tooltip.size')} {format_size(pair.heic_size)}<br>"
                       f"{tr('common.tooltip.date')} {heic_mtime.strftime('%d/%m/%Y %H:%M:%S')}<br>")
        
        if pair.date_source:
             heic_tooltip += f"{tr('common.tooltip.date_source')} {pair.date_source}<br>"
             
        heic_tooltip += f"{tr('common.tooltip.will_keep') if format_to_delete == 'JPG' else tr('common.tooltip.will_delete')}"
        heic_item.setToolTip(0, heic_tooltip)
        
        # Añadir archivo JPG como hijo
        jpg_item = QTreeWidgetItem(group_item)
        jpg_item.setIcon(0, icon_manager.get_icon('image', size=16))
        jpg_item.setText(0, pair.jpg_path.name)
        jpg_item.setText(1, format_size(pair.jpg_size))
        jpg_item.setText(2, "JPG")
        if pair.jpg_date:
            jpg_item.setText(3, pair.jpg_date.strftime('%d/%m/%Y %H:%M:%S'))
        jpg_item.setText(4, pair.date_source or "")
        
        if format_to_delete == "JPG":
            jpg_item.setText(5, tr("common.status.mark_delete"))
            jpg_item.setForeground(5, QColor(DesignSystem.COLOR_ERROR))
        else:
            jpg_item.setText(5, tr("common.status.mark_keep"))
            jpg_item.setForeground(5, QColor(DesignSystem.COLOR_SUCCESS))
        
        # Guardar referencia al archivo JPG
        jpg_item.setData(0, Qt.ItemDataRole.UserRole, pair.jpg_path)
        
        # Tooltip para JPG
        jpg_mtime = datetime.fromtimestamp(pair.jpg_path.stat().st_mtime)
        jpg_tooltip = (f"<b>{pair.jpg_path.name}</b><br>"
                       f"{tr('common.tooltip.folder')} {pair.jpg_path.parent}<br>"
                       f"{tr('common.tooltip.size')} {format_size(pair.jpg_size)}<br>"
                       f"{tr('common.tooltip.date')} {jpg_mtime.strftime('%d/%m/%Y %H:%M:%S')}<br>")
        
        if pair.date_source:
             jpg_tooltip += f"{tr('common.tooltip.date_source')} {pair.date_source}<br>"
             
        jpg_tooltip += f"{tr('common.tooltip.will_keep') if format_to_delete == 'HEIC' else tr('common.tooltip.will_delete')}"
        jpg_item.setToolTip(0, jpg_tooltip)
    
    def _on_item_double_clicked(self, item, column):
        """Maneja doble click: expande grupos o abre archivos"""
        from .dialog_utils import handle_tree_item_double_click
        handle_tree_item_double_click(item, column, self)
    
    def _show_context_menu(self, position):
        """Muestra menú contextual para archivos individuales"""
        from .dialog_utils import show_file_context_menu
        show_file_context_menu(self.tree_widget, position, self)
    
    def _update_button_text(self):
        """Actualiza el texto del botón según el formato seleccionado"""
        if self.analysis.items_count > 0:
            if self.selected_format == 'jpg':
                savings = self.analysis.potential_savings_keep_jpg
            else:
                savings = self.analysis.potential_savings_keep_heic

            space_formatted = format_size(savings)
            self.ok_button.setText(
                tr("dialogs.heic.button_delete", count=self.analysis.items_count, size=space_formatted)
            )

    def accept(self):
        # Validar que hay pares para procesar
        if not self.analysis.duplicate_pairs:
            self.show_no_items_message(tr("dialogs.heic.no_items_type"))
            return
        
        # Pasar el analysis completo + parámetros por separado
        self.accepted_plan = {
            'analysis': self.analysis,  # Ya es un HeicAnalysisResult dataclass
            'keep_format': self.selected_format,
            'create_backup': self.is_backup_enabled(),
            'dry_run': self.is_dry_run_enabled(),
        }
        super().accept()
