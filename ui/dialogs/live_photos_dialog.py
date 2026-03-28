# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Diálogo de limpieza de Live Photos
Grupos expandibles con archivos de imagen y video, diseño Material Design
"""
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QVBoxLayout, QDialogButtonBox, QTreeWidgetItem, QWidget
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from utils.format_utils import format_size
from utils.i18n import tr
from utils.platform_utils import are_video_tools_available
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from ui.tools_definitions import TOOL_LIVE_PHOTOS
from services.result_types import LivePhotosAnalysisResult, LivePhotoGroup
from .base_dialog import BaseDialog


class LivePhotosDialog(BaseDialog):
    """Diálogo para limpieza de Live Photos con vista de grupos expandibles"""
    
    # Constantes para carga progresiva
    INITIAL_LOAD = 100
    LOAD_INCREMENT = 100
    WARNING_THRESHOLD = 500

    def __init__(self, analysis: LivePhotosAnalysisResult, parent=None):
        super().__init__(parent)
        self.analysis = analysis
        self.accepted_plan = None
        
        # Datos de grupos
        self.all_groups = list(analysis.groups)
        self.filtered_groups = list(analysis.groups)
        self.loaded_count = 0
        
        # Referencias a widgets
        self.tree_widget = None
        self.search_input = None
        self.filter_combo = None
        self.status_chip = None
        self.filter_bar = None
        self.expand_button = None
        self.source_combo = None
        self.dir_combo = None
        self.pagination_bar = None
        
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(TOOL_LIVE_PHOTOS.title)
        self.setModal(True)
        self.resize(1200, 800)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(int(DesignSystem.SPACE_12))
        main_layout.setContentsMargins(0, 0, 0, int(DesignSystem.SPACE_20))
        
        # Calcular espacio recuperable (videos a eliminar)
        potential_savings = self.analysis.potential_savings
        
        # Header compacto integrado con métricas inline
        self.header_frame = self._create_compact_header_with_metrics(
            icon_name=TOOL_LIVE_PHOTOS.icon_name,
            title=TOOL_LIVE_PHOTOS.title,
            description=TOOL_LIVE_PHOTOS.short_description,
            metrics=[
                {
                    'value': str(self.analysis.items_count),
                    'label': tr("dialogs.live_photos.metric_groups"),
                    'color': DesignSystem.COLOR_PRIMARY
                },
                {
                    'value': str(self.analysis.total_images),
                    'label': tr("dialogs.live_photos.metric_images"),
                    'color': DesignSystem.COLOR_TEXT_SECONDARY
                },
                {
                    'value': format_size(potential_savings),
                    'label': tr("dialogs.live_photos.metric_recoverable"),
                    'color': DesignSystem.COLOR_SUCCESS
                }
            ]
        )
        main_layout.addWidget(self.header_frame)
        
        # Warning sobre metadata de video no disponible
        # Prioridad: 1) Herramientas no instaladas, 2) Configuración desactivada
        from utils.settings_manager import settings_manager
        video_tools_available = are_video_tools_available()
        video_metadata_enabled = settings_manager.get_precalculate_video_exif()
        
        if not video_tools_available or not video_metadata_enabled:
            warning_container = QWidget()
            warning_container_layout = QVBoxLayout(warning_container)
            warning_container_layout.setContentsMargins(
                int(DesignSystem.SPACE_24),
                int(DesignSystem.SPACE_12),
                int(DesignSystem.SPACE_24),
                0
            )
            warning_container_layout.setSpacing(0)
            
            if not video_tools_available:
                # Herramientas no instaladas - warning más importante
                warning_banner = self._create_warning_banner(
                    title=tr("dialogs.live_photos.warning.tools_unavailable_title"),
                    message=tr("dialogs.live_photos.warning.tools_unavailable_msg"),
                    icon='alert-circle',
                    action_text=tr("dialogs.live_photos.warning.tools_action"),
                    action_callback=self._open_settings,
                    bg_color=DesignSystem.COLOR_DANGER_BG,
                    border_color=DesignSystem.COLOR_ERROR
                )
            else:
                # Herramientas disponibles pero configuración desactivada
                warning_banner = self._create_warning_banner(
                    title=tr("dialogs.live_photos.warning.no_validation_title"),
                    message=tr("dialogs.live_photos.warning.no_validation_msg"),
                    action_text=tr("dialogs.live_photos.warning.no_validation_action"),
                    action_callback=self._open_settings
                )
            warning_container_layout.addWidget(warning_banner)
            main_layout.addWidget(warning_container)
        
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

    def _create_filter_bar(self):
        """Crea barra de filtros unificada usando método base"""
        # Preparar directorios únicos
        directories = sorted(list(set(
            str(group.directory) for group in self.analysis.groups
        )))
        
        # Diccionario de etiquetas
        labels = {
            'search': tr("dialogs.live_photos.filter.search"),
            'size': tr("dialogs.live_photos.filter.size"),
            'groups': tr("dialogs.live_photos.filter.groups"),
            'source': tr("dialogs.live_photos.filter.source"),
            'directory': tr("dialogs.live_photos.filter.directory")
        }
        
        # Configuración de filtros expandibles
        expandable_filters = [
            {
                'id': 'source',
                'type': 'combo',
                'label': labels['source'],
                'tooltip': tr("dialogs.live_photos.filter.source_tooltip"),
                'options': self.DATE_SOURCE_FILTER_OPTIONS,
                'on_change': lambda idx: self._apply_filters(),
                'default_index': 0,
                'min_width': 200
            },
            {
                'id': 'directory',
                'type': 'combo',
                'label': labels['directory'],
                'tooltip': tr("dialogs.live_photos.filter.dir_tooltip"),
                'options': [tr("common.filter.all_directories")] + directories,
                'on_change': lambda idx: self._apply_filters(),
                'default_index': 0,
                'min_width': 200
            }
        ]
        
        # Crear barra unificada
        filter_bar = self._create_unified_filter_bar(
            on_search_changed=self._apply_filters,
            on_size_filter_changed=lambda idx: self._apply_filters(),
            expandable_filters=expandable_filters,
            is_files_mode=False,
            labels=labels
        )
        
        # Guardar referencias a componentes
        self.search_input = filter_bar.search_input
        self.filter_combo = filter_bar.size_filter_combo
        self.status_chip = filter_bar.status_chip
        self.expand_button = filter_bar.expand_btn
        self.source_combo = filter_bar.filter_widgets.get('source')
        self.dir_combo = filter_bar.filter_widgets.get('directory')
        
        return filter_bar
        
        return filter_bar
    
    def _create_files_tree(self):
        """Crea TreeWidget con grupos expandibles estilo Material Design"""
        from .dialog_utils import create_groups_tree_widget
        
        return create_groups_tree_widget(
            headers=[tr("common.tree_header.groups_files"), tr("common.tree_header.size"), tr("common.tree_header.type"), tr("common.tree_header.date"), tr("common.tree_header.date_source"), tr("common.tree_header.status")],
            column_widths=[350, 100, 80, 160, 150, 120],
            double_click_handler=self._on_item_double_clicked,
            context_menu_handler=self._show_context_menu
        )
    
    def _create_options_group(self):
        """Crea grupo de opciones de seguridad usando método centralizado"""
        return self._create_security_options_section(
            show_backup=True,
            show_dry_run=True,
            backup_label=tr("dialogs.live_photos.option_backup"),
            dry_run_label=tr("dialogs.live_photos.option_dry_run")
        )
    
    def _apply_filters(self):
        """Aplica filtros a la lista de grupos"""
        search_text = self.search_input.text().lower() if self.search_input else ""
        size_filter = self.filter_combo.currentText() if self.filter_combo else tr("common.filter.all_sizes")
        dir_filter = self.dir_combo.currentText() if self.dir_combo else tr("common.filter.all_directories")
        source_filter = self.source_combo.currentText() if self.source_combo else self.DATE_SOURCE_FILTER_ALL
        
        self.filtered_groups = []
        
        for group in self.all_groups:
            # Filtro de búsqueda
            if search_text and search_text not in group.base_name.lower():
                continue
            
            # Filtro por tamaño del video
            if not self._matches_size_filter(group.video_size, size_filter):
                continue
            
            # Filtro por directorio
            if dir_filter != tr("common.filter.all_directories") and str(group.directory) != dir_filter:
                continue
            
            # Filtro por origen de fecha
            if not self._matches_source_filter(group.date_source, source_filter):
                continue
            
            self.filtered_groups.append(group)
        
        # Reiniciar carga progresiva
        self._load_initial_groups()
    
    def _matches_size_filter(self, file_size: int, filter_value: str) -> bool:
        """Verifica si el tamaño del archivo coincide con el filtro seleccionado.
        
        Args:
            file_size: Tamaño del archivo en bytes
            filter_value: Valor del filtro seleccionado
            
        Returns:
            True si coincide con el filtro
        """
        if filter_value == tr("common.filter.all_sizes"):
            return True
        
        mb = file_size / (1024 * 1024)
        
        if filter_value == "< 1 MB":
            return mb < 1
        elif filter_value == "1 - 10 MB":
            return 1 <= mb < 10
        elif filter_value == "10 - 100 MB":
            return 10 <= mb < 100
        elif filter_value == "> 100 MB":
            return mb >= 100
        
        return True
    
    def _clear_filters(self):
        """Limpia todos los filtros"""
        if self.search_input:
            self.search_input.clear()
        if self.filter_combo:
            self.filter_combo.setCurrentIndex(0)
        if self.dir_combo:
            self.dir_combo.setCurrentIndex(0)
        if self.source_combo:
            self.source_combo.setCurrentIndex(0)
    
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
        end = min(start + self.LOAD_INCREMENT, len(self.filtered_groups))
        
        for i in range(start, end):
            group = self.filtered_groups[i]
            self._add_group_to_tree(group, i + 1)
        
        self.loaded_count = end
        self._update_pagination_ui()
    
    def _load_all_groups(self):
        """Carga todos los grupos restantes."""
        from PyQt6.QtWidgets import QMessageBox
        
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
    
    def _update_pagination_ui(self):
        """Actualiza la UI de la barra de carga progresiva."""
        if self.pagination_bar:
            self._update_progressive_loading_ui(
                pagination_bar=self.pagination_bar,
                loaded_count=self.loaded_count,
                filtered_count=len(self.filtered_groups),
                total_count=len(self.all_groups),
                load_increment=self.LOAD_INCREMENT
            )
        
        # Actualizar chip de estado (independiente del loaded_count)
        self._update_filter_chip(
            status_chip=self.status_chip,
            filtered_count=len(self.filtered_groups),
            total_count=len(self.all_groups),
            loaded_count=self.loaded_count,
            is_files_mode=False
        )
    
    def _add_group_to_tree(self, group: LivePhotoGroup, group_number: int):
        """Añade un grupo como nodo padre expandible con archivos de imagen y video"""
        from .dialog_utils import apply_group_item_style, create_group_tooltip
        
        # Nodo padre del grupo
        group_item = QTreeWidgetItem(self.tree_widget)
        
        # Texto del grupo - Solo columna 0
        images_info = tr("dialogs.live_photos.tree.image_count_plural", count=group.image_count) if group.image_count > 1 else tr("dialogs.live_photos.tree.image_count_singular", count=group.image_count)
        group_item.setText(0, tr("dialogs.live_photos.tree.group_label", num=group_number, name=group.base_name, images=images_info))
        
        # Fecha y origen en el grupo
        group_date = group.best_date
        if group_date:
            group_item.setText(3, group_date.strftime('%d/%m/%Y %H:%M:%S'))
        group_item.setText(4, group.date_source or "")
        
        # Aplicar estilo unificado de grupo
        apply_group_item_style(group_item, num_columns=6)
        
        # Tooltip informativo
        extra_info = tr("dialogs.live_photos.tooltip.group_desc", count=group.image_count)
        if group.date_source:
            extra_info += "\n" + tr("dialogs.live_photos.tooltip.common_date", source=group.date_source)
            if group.date_difference is not None:
                extra_info += "\n" + tr("dialogs.live_photos.tooltip.date_diff", diff=group.date_difference)
        
        group_item.setToolTip(0, create_group_tooltip(
            group_number,
            f"Live Photo: {group.base_name}",
            extra_info
        ))
        
        # Añadir imágenes como hijos
        for idx, img_info in enumerate(group.images):
            img_item = QTreeWidgetItem(group_item)
            img_item.setIcon(0, icon_manager.get_icon('image', size=16))
            img_item.setText(0, img_info.path.name)
            img_item.setText(1, format_size(img_info.size))
            img_item.setText(2, img_info.path.suffix.upper().lstrip('.'))
            if img_info.date:
                img_item.setText(3, img_info.date.strftime('%d/%m/%Y %H:%M:%S'))
            img_item.setText(4, img_info.date_source or "")
            img_item.setText(5, tr("common.status.mark_keep"))
            img_item.setForeground(5, QColor(DesignSystem.COLOR_SUCCESS))
            
            # Guardar referencia al archivo
            img_item.setData(0, Qt.ItemDataRole.UserRole, img_info.path)
            
            # Tooltip para imagen
            try:
                img_mtime = datetime.fromtimestamp(img_info.path.stat().st_mtime)
                img_tooltip = (f"<b>{img_info.path.name}</b><br>"
                               f"{tr('common.tooltip.folder')} {img_info.path.parent}<br>"
                               f"{tr('common.tooltip.size')} {format_size(img_info.size)}<br>"
                               f"{tr('common.tooltip.date')} {img_mtime.strftime('%d/%m/%Y %H:%M:%S')}<br>")
                if img_info.date_source:
                    img_tooltip += f"{tr('common.tooltip.date_source')} {img_info.date_source}<br>"
                img_tooltip += tr("common.tooltip.will_keep")
                img_item.setToolTip(0, img_tooltip)
            except Exception:
                pass
        
        # Añadir video como hijo
        video_item = QTreeWidgetItem(group_item)
        video_item.setIcon(0, icon_manager.get_icon('video', size=16))
        video_item.setText(0, group.video_path.name)
        video_item.setText(1, format_size(group.video_size))
        video_item.setText(2, "MOV")
        if group.video_date:
            video_item.setText(3, group.video_date.strftime('%d/%m/%Y %H:%M:%S'))
        video_item.setText(4, group.video_date_source or "")
        video_item.setText(5, tr("common.status.mark_delete"))
        video_item.setForeground(5, QColor(DesignSystem.COLOR_ERROR))
        
        # Guardar referencia al video
        video_item.setData(0, Qt.ItemDataRole.UserRole, group.video_path)
        
        # Tooltip para video
        try:
            video_mtime = datetime.fromtimestamp(group.video_path.stat().st_mtime)
            video_tooltip = (f"<b>{group.video_path.name}</b><br>"
                             f"{tr('common.tooltip.folder')} {group.video_path.parent}<br>"
                             f"{tr('common.tooltip.size')} {format_size(group.video_size)}<br>"
                             f"{tr('common.tooltip.date')} {video_mtime.strftime('%d/%m/%Y %H:%M:%S')}<br>")
            if group.video_date_source:
                video_tooltip += f"{tr('common.tooltip.date_source')} {group.video_date_source}<br>"
            video_tooltip += tr("common.tooltip.will_delete")
            video_item.setToolTip(0, video_tooltip)
        except Exception:
            pass
    
    def _on_item_double_clicked(self, item, column):
        """Maneja doble click: expande grupos o abre archivos"""
        from .dialog_utils import handle_tree_item_double_click
        handle_tree_item_double_click(item, column, self)
    
    def _show_context_menu(self, position):
        """Muestra menú contextual para archivos individuales"""
        from .dialog_utils import show_file_context_menu
        show_file_context_menu(self.tree_widget, position, self)
    
    def _update_button_text(self):
        """Actualiza el texto del botón según los grupos"""
        if self.analysis.items_count > 0:
            savings = self.analysis.potential_savings
            space_formatted = format_size(savings)
            self.ok_button.setText(
                tr("dialogs.live_photos.button_delete", count=self.analysis.items_count, size=space_formatted)
            )

    def accept(self):
        """Acepta el diálogo y prepara los datos para la ejecución"""
        # Validar que hay grupos para procesar
        if not self.analysis.groups:
            self.show_no_items_message("Live Photos")
            return
        
        # Pasar el analysis completo + parámetros por separado
        self.accepted_plan = {
            'analysis': self.analysis,  # Ya es un LivePhotosAnalysisResult dataclass
            'create_backup': self.is_backup_enabled(),
            'dry_run': self.is_dry_run_enabled(),
        }
        super().accept()
    
    def _open_settings(self):
        """Abre el diálogo de configuración en la pestaña Análisis inicial"""
        from .settings_dialog import SettingsDialog
        settings_dialog = SettingsDialog(self, initial_tab=1)  # 1 = Análisis inicial tab
        settings_dialog.exec()
