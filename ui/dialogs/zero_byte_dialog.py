# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Diálogo para gestionar archivos de 0 bytes.
Usa QTreeWidget con carpetas como nodos padre para consistencia con otros diálogos.
"""
from pathlib import Path
from collections import defaultdict
from typing import List

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
    QWidget, QDialogButtonBox
)
from PyQt6.QtCore import Qt

from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from ui.tools_definitions import TOOL_ZERO_BYTE
from utils.format_utils import format_file_count
from utils.i18n import tr
from services.result_types import ZeroByteAnalysisResult
from .base_dialog import BaseDialog
from .dialog_utils import (
    show_file_context_menu, show_file_details_dialog,
    create_groups_tree_widget, handle_tree_item_double_click, apply_group_item_style
)


class ZeroByteDialog(BaseDialog):
    """
    Diálogo para gestionar archivos de 0 bytes.
    Muestra archivos agrupados por carpeta y permite eliminarlos.
    """
    
    # Constantes para carga progresiva
    INITIAL_LOAD = 50
    LOAD_INCREMENT = 50

    def __init__(self, analysis_result: ZeroByteAnalysisResult, parent=None):
        super().__init__(parent)
        self.analysis_result = analysis_result
        self.accepted_plan = {}
        
        # Organizar archivos por carpeta
        self.all_files = list(analysis_result.files)
        self.all_groups = []  # Lista de (folder_path, files)
        self.loaded_groups = 0
        
        # Track de archivos seleccionados (todos seleccionados por defecto)
        self.selected_files = set(self.all_files)
        
        self.init_ui()
        self._organize_by_folders()
        self._load_initial_groups()
        
    def init_ui(self):
        self.setWindowTitle(TOOL_ZERO_BYTE.title)
        self.resize(900, 650)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(int(DesignSystem.SPACE_12))
        main_layout.setContentsMargins(0, 0, 0, int(DesignSystem.SPACE_20))
        
        # Header compacto
        self.header_frame = self._create_compact_header_with_metrics(
            icon_name=TOOL_ZERO_BYTE.icon_name,
            title=TOOL_ZERO_BYTE.title,
            description=TOOL_ZERO_BYTE.short_description,
            metrics=[
                {
                    'value': str(len(self.analysis_result.files)),
                    'label': tr("dialogs.zero_byte.metric_files"),
                    'color': DesignSystem.COLOR_ERROR
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
        
        # TreeWidget de archivos
        self.tree_widget = self._create_tree_widget()
        content_layout.addWidget(self.tree_widget)
        
        # Barra de carga progresiva
        self.pagination_bar = self._create_progressive_loading_bar(
            on_load_more=self._load_more_groups,
            on_load_all=self._load_all_groups
        )
        content_layout.addWidget(self.pagination_bar)
        
        # Botones de selección
        selection_layout = QHBoxLayout()
        
        select_all_btn = QPushButton(tr("dialogs.zero_byte.button_select_all"))
        select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_all_btn.clicked.connect(self._select_all)
        select_all_btn.setStyleSheet(f"color: {DesignSystem.COLOR_PRIMARY}; border: none; font-weight: bold;")
        
        select_none_btn = QPushButton(tr("dialogs.zero_byte.button_select_none"))
        select_none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_none_btn.clicked.connect(self._select_none)
        select_none_btn.setStyleSheet(f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; border: none;")
        
        # Contador de selección
        self.selection_label = QLabel()
        self.selection_label.setStyleSheet(f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; font-size: {DesignSystem.FONT_SIZE_SM}px;")
        
        selection_layout.addWidget(select_all_btn)
        selection_layout.addWidget(select_none_btn)
        selection_layout.addStretch()
        selection_layout.addWidget(self.selection_label)
        
        content_layout.addLayout(selection_layout)
        
        # Opciones de seguridad
        options_group = self._create_security_options_section(
            show_backup=True,
            show_dry_run=True,
            backup_label=tr("dialogs.zero_byte.option_backup"),
            dry_run_label=tr("dialogs.zero_byte.option_dry_run")
        )
        content_layout.addWidget(options_group)
        
        # Botones de acción
        self.buttons = self.make_ok_cancel_buttons(
            ok_enabled=True,
            button_style='danger'
        )
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._update_button_text()
        
        content_layout.addWidget(self.buttons)
    
    def _create_tree_widget(self) -> QTreeWidget:
        """Crea el widget de árbol para mostrar archivos agrupados por carpeta."""
        headers = [tr("dialogs.zero_byte.tree_header.folder_file"), tr("dialogs.zero_byte.tree_header.location")]
        column_widths = [450, 350]
        
        tree = create_groups_tree_widget(
            headers=headers,
            column_widths=column_widths,
            double_click_handler=self._on_item_double_clicked,
            context_menu_handler=self._show_context_menu
        )
        
        # Conectar cambios en checkboxes
        tree.itemChanged.connect(self._on_item_changed)
        
        return tree
    
    # ========================================================================
    # ORGANIZACIÓN Y CARGA
    # ========================================================================
    
    def _organize_by_folders(self):
        """Organiza los archivos por carpeta."""
        folders = defaultdict(list)
        for file_path in self.all_files:
            folder = file_path.parent
            folders[folder].append(file_path)
        
        self.all_groups = sorted(folders.items(), key=lambda x: str(x[0]))
    
    def _load_initial_groups(self):
        """Carga los grupos iniciales en el árbol."""
        self.loaded_groups = 0
        self.tree_widget.clear()
        self._load_more_groups()
    
    def _load_more_groups(self):
        """Carga más grupos (carpetas) en el árbol."""
        start = self.loaded_groups
        end = min(start + self.LOAD_INCREMENT, len(self.all_groups))
        
        groups_to_load = self.all_groups[start:end]
        
        self.tree_widget.setUpdatesEnabled(False)
        self.tree_widget.blockSignals(True)  # Evitar signals durante carga
        
        for folder_path, files in groups_to_load:
            self._add_folder_group(folder_path, files)
        
        self.tree_widget.blockSignals(False)
        self.tree_widget.setUpdatesEnabled(True)
        
        self.loaded_groups = end
        self._update_pagination_ui()
    
    def _add_folder_group(self, folder_path: Path, files: List[Path]):
        """Añade un grupo de carpeta con sus archivos al árbol."""
        # Crear nodo de carpeta
        folder_item = QTreeWidgetItem(self.tree_widget)
        folder_name = str(folder_path.relative_to(folder_path.anchor)) if folder_path.anchor else str(folder_path)
        folder_item.setText(0, tr("dialogs.zero_byte.tree.folder_label", name=folder_name, count=len(files)))
        folder_item.setExpanded(True)
        
        # Checkbox para la carpeta (tri-state)
        folder_item.setFlags(folder_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
        folder_item.setCheckState(0, Qt.CheckState.Checked)
        
        # Aplicar estilo de grupo
        apply_group_item_style(folder_item, num_columns=2)
        
        folder_item.setToolTip(0, tr("dialogs.zero_byte.tooltip.folder", path=str(folder_path), count=len(files)))
        
        # Añadir archivos como hijos
        for file_path in files:
            self._add_file_item(folder_item, file_path)
    
    def _add_file_item(self, parent_item: QTreeWidgetItem, file_path: Path):
        """Añade un archivo como hijo de una carpeta."""
        file_item = QTreeWidgetItem(parent_item)
        
        # Columna 0: Nombre del archivo con checkbox
        file_item.setText(0, file_path.name)
        file_item.setData(0, Qt.ItemDataRole.UserRole, file_path)
        file_item.setFlags(file_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        
        # Estado del checkbox según selección
        is_selected = file_path in self.selected_files
        file_item.setCheckState(0, Qt.CheckState.Checked if is_selected else Qt.CheckState.Unchecked)
        
        # Icono de archivo
        file_item.setIcon(0, icon_manager.get_icon('file', size=16))
        
        # Columna 1: Ubicación completa
        file_item.setText(1, str(file_path))
        
        file_item.setToolTip(0, tr("dialogs.zero_byte.tooltip.file", path=str(file_path)))
    
    def _load_all_groups(self):
        """Carga todos los grupos restantes."""
        while self.loaded_groups < len(self.all_groups):
            self._load_more_groups()
    
    def _update_pagination_ui(self):
        """Actualiza la UI de la barra de carga progresiva."""
        loaded_files = sum(len(files) for _, files in self.all_groups[:self.loaded_groups])
        total_files = len(self.all_files)
        
        if self.pagination_bar:
            self._update_progressive_loading_ui(
                pagination_bar=self.pagination_bar,
                loaded_count=loaded_files,
                filtered_count=total_files,
                total_count=total_files,
                load_increment=self.LOAD_INCREMENT
            )
    
    # ========================================================================
    # SELECCIÓN
    # ========================================================================
    
    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Maneja cambios en los checkboxes."""
        if column != 0:
            return
        
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path and isinstance(file_path, Path):
            # Es un archivo
            if item.checkState(0) == Qt.CheckState.Checked:
                self.selected_files.add(file_path)
            else:
                self.selected_files.discard(file_path)
            
            self._update_button_text()
    
    def _select_all(self):
        """Selecciona todos los archivos."""
        self.selected_files = set(self.all_files)
        self._update_all_checkboxes(Qt.CheckState.Checked)
        self._update_button_text()
    
    def _select_none(self):
        """Deselecciona todos los archivos."""
        self.selected_files.clear()
        self._update_all_checkboxes(Qt.CheckState.Unchecked)
        self._update_button_text()
    
    def _update_all_checkboxes(self, state: Qt.CheckState):
        """Actualiza todos los checkboxes al estado dado."""
        self.tree_widget.blockSignals(True)
        
        for i in range(self.tree_widget.topLevelItemCount()):
            folder_item = self.tree_widget.topLevelItem(i)
            folder_item.setCheckState(0, state)
            
            for j in range(folder_item.childCount()):
                file_item = folder_item.child(j)
                file_item.setCheckState(0, state)
        
        self.tree_widget.blockSignals(False)
    
    def _update_button_text(self):
        """Actualiza el texto del botón con el conteo de archivos seleccionados."""
        count = len(self.selected_files)
        self.ok_button.setText(f"{tr('common.delete')} {format_file_count(count)}")
        self.ok_button.setEnabled(count > 0)
        self.selection_label.setText(tr("dialogs.zero_byte.selection_count", selected=count, total=len(self.all_files)))
    
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
        """Muestra detalles del archivo."""
        additional_info = {
            'metadata': {
                tr("dialogs.zero_byte.details.size_key"): tr("dialogs.zero_byte.details.size_value"),
                tr("dialogs.zero_byte.details.status_key"): tr("dialogs.zero_byte.details.status_value"),
            }
        }
        show_file_details_dialog(file_path, self, additional_info)
        
    def accept(self):
        # Validar que hay archivos seleccionados
        if not self.selected_files:
            self.show_no_items_message(tr("dialogs.zero_byte.no_items_type"))
            return
        
        # Construir analysis con los archivos seleccionados
        analysis = ZeroByteAnalysisResult(
            files=list(self.selected_files),
            items_count=len(self.selected_files)
        )
            
        self.accepted_plan = {
            'analysis': analysis,
            'create_backup': self.is_backup_enabled(),
            'dry_run': self.is_dry_run_enabled()
        }
        
        super().accept()
