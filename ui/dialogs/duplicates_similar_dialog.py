# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Diálogo de gestión de archivos similares (70-95% similitud).

Este diálogo está diseñado para archivos SIMILARES pero NO idénticos.
Para copias visuales idénticas (100%), usar el diálogo Visual Identical.

Flujo:
1. Los hashes perceptuales ya están calculados (DuplicatesSimilarAnalysis)
2. El diálogo se muestra con estado de carga
3. El clustering se ejecuta después de que el diálogo sea visible
4. El usuario ajusta sensibilidad con slider (regenera en tiempo real)
"""

from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QDialogButtonBox, QCheckBox, QScrollArea, QWidget,
    QGridLayout, QProgressBar, QMenu, QSpinBox
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QCursor, QPainter, QColor
from services.duplicates_similar_service import DuplicatesSimilarAnalysis
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from services.result_types import SimilarDuplicateGroup
from utils.format_utils import format_size
from utils.image_loader import load_image_as_qpixmap
from utils.video_thumbnail import get_video_thumbnail
from utils.platform_utils import open_file_with_default_app
from utils.file_utils import is_image_file, is_video_file
from utils.logger import get_logger
from utils.i18n import tr
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtCore import QRect
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from ui.tools_definitions import TOOL_DUPLICATES_SIMILAR
from .base_dialog import BaseDialog
from .dialog_utils import show_file_details_dialog
from .image_preview_dialog import ImagePreviewDialog


L_DUPLICATES_SIMILAR = get_logger('DuplicatesSimilarDialog')


class DualRangeSlider(QWidget):
    """Widget de slider con rango dual (min-max) para filtrar similitud.
    
    Permite seleccionar un rango de valores con dos handles independientes.
    Diseñado con estilo moderno y profesional usando DesignSystem.
    """
    
    def __init__(self, minimum=0, maximum=100, parent=None):
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        self.lower_value = minimum
        self.upper_value = maximum
        self.handle_radius = 9
        self.handle_hover_radius = 11
        self.track_height = 6
        self.active_handle = None  # 'lower', 'upper', or None
        self.hover_handle = None   # 'lower', 'upper', or None
        
        self.setMinimumHeight(40)  # Reduced height since labels are removed
        self.setMinimumWidth(200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    valueChanged = pyqtSignal(int, int)  # Signal emitting (lower, upper)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Calcular posiciones
        track_y = height // 2
        track_x_start = self.handle_radius + 5
        track_x_end = width - self.handle_radius - 5
        track_width = track_x_end - track_x_start
        
        lower_pos = track_x_start + (self.lower_value - self.minimum) / (self.maximum - self.minimum) * track_width
        upper_pos = track_x_start + (self.upper_value - self.minimum) / (self.maximum - self.minimum) * track_width
        
        # Dibujar track de fondo
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(DesignSystem.hex_to_qcolor(DesignSystem.COLOR_BORDER_LIGHT))
        track_rect = QRect(track_x_start, track_y - self.track_height // 2, track_width, self.track_height)
        painter.drawRoundedRect(track_rect, self.track_height // 2, self.track_height // 2)
        
        # Dibujar track activo (rango seleccionado)
        painter.setBrush(DesignSystem.hex_to_qcolor(DesignSystem.COLOR_PRIMARY))
        active_width = int(upper_pos - lower_pos)
        active_rect = QRect(int(lower_pos), track_y - self.track_height // 2, active_width, self.track_height)
        painter.drawRoundedRect(active_rect, self.track_height // 2, self.track_height // 2)
        
        # Dibujar handles
        for handle_type in ['lower', 'upper']:
            pos = lower_pos if handle_type == 'lower' else upper_pos
            is_hover = self.hover_handle == handle_type
            is_active = self.active_handle == handle_type
            radius = self.handle_hover_radius if (is_hover or is_active) else self.handle_radius
            
            # Sombra del handle
            shadow_color = DesignSystem.hex_to_qcolor("#000000")
            shadow_color.setAlpha(30)
            painter.setBrush(shadow_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(pos - radius + 1), track_y - radius + 2, radius * 2, radius * 2)
            
            # Handle principal
            handle_color = DesignSystem.COLOR_PRIMARY_HOVER if (is_hover or is_active) else DesignSystem.COLOR_PRIMARY
            painter.setBrush(DesignSystem.hex_to_qcolor(handle_color))
            pen = QPen(DesignSystem.hex_to_qcolor(DesignSystem.COLOR_SURFACE))
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawEllipse(int(pos - radius), track_y - radius, radius * 2, radius * 2)
        
        # Labels removed as they are redundant with SpinBoxes and to improve alignment
    
    def mousePressEvent(self, event):
        pos = event.pos().x()
        width = self.width()
        track_x_start = self.handle_radius + 5
        track_x_end = width - self.handle_radius - 5
        track_width = track_x_end - track_x_start
        
        lower_pos = track_x_start + (self.lower_value - self.minimum) / (self.maximum - self.minimum) * track_width
        upper_pos = track_x_start + (self.upper_value - self.minimum) / (self.maximum - self.minimum) * track_width
        
        # Determinar cuál handle está más cerca
        dist_lower = abs(pos - lower_pos)
        dist_upper = abs(pos - upper_pos)
        
        if dist_lower < dist_upper and dist_lower < 20:
            self.active_handle = 'lower'
        elif dist_upper < dist_lower and dist_upper < 20:
            self.active_handle = 'upper'
        elif dist_upper == dist_lower and dist_lower < 20:
             # Handles are overlapping or very close at the click point
             # Determine direction based on click relative to handles center or just default to moving the one that expands/contracts logically
             # Simpler approach: if clicking exactly on them, check if we are closer to left or right bound of track to decide?
             # Or just check which direction user drags. For now, let's pick 'upper' if moving right, 'lower' if moving left? 
             # Initial click doesn't have direction yet.
             # Strategy: Default to 'upper' if value is expanding, but here we are just selecting the handle.
             # Let's pick the one that allows moving towards the mouse cursor if they were slightly separate?
             # Actually if they are at same spot, standard logic might fail.
             # If pos > lower_pos (calculated), pick upper. If pos < lower_pos, pick lower
             if pos > lower_pos:
                 self.active_handle = 'upper'
             else:
                 self.active_handle = 'lower'
        else:
            # Click on track - move closest handle
            if dist_lower < dist_upper:
                self.active_handle = 'lower'
            else:
                self.active_handle = 'upper'
            self._update_value_from_pos(pos)
        
        self.update()
    
    def mouseMoveEvent(self, event):
        pos = event.pos().x()
        
        if self.active_handle:
            self._update_value_from_pos(pos)
        else:
            # Detectar hover
            width = self.width()
            track_x_start = self.handle_radius + 5
            track_x_end = width - self.handle_radius - 5
            track_width = track_x_end - track_x_start
            
            lower_pos = track_x_start + (self.lower_value - self.minimum) / (self.maximum - self.minimum) * track_width
            upper_pos = track_x_start + (self.upper_value - self.minimum) / (self.maximum - self.minimum) * track_width
            
            if abs(pos - lower_pos) < 15:
                self.hover_handle = 'lower'
            elif abs(pos - upper_pos) < 15:
                self.hover_handle = 'upper'
            else:
                self.hover_handle = None
            
            self.update()
    
    def mouseReleaseEvent(self, event):
        self.active_handle = None
        self.update()
    
    def leaveEvent(self, event):
        self.hover_handle = None
        self.active_handle = None
        self.update()
    
    def _update_value_from_pos(self, pos):
        width = self.width()
        track_x_start = self.handle_radius + 5
        track_x_end = width - self.handle_radius - 5
        track_width = track_x_end - track_x_start
        
        # Calcular valor
        ratio = (pos - track_x_start) / track_width
        value = int(self.minimum + ratio * (self.maximum - self.minimum))
        value = max(self.minimum, min(self.maximum, value))
        
        if self.active_handle == 'lower':
            self.lower_value = min(value, self.upper_value)  # Allow equal values
        elif self.active_handle == 'upper':
            self.upper_value = max(value, self.lower_value)  # Allow equal values
        
        self.update()
        self.valueChanged.emit(self.lower_value, self.upper_value)
    
    def get_range(self):
        """Retorna tupla (lower_value, upper_value)."""
        return (self.lower_value, self.upper_value)
    
    def set_range(self, lower, upper):
        """Establece el rango de valores."""
        self.lower_value = max(self.minimum, min(lower, self.maximum))
        self.upper_value = max(self.minimum, min(upper, self.maximum))
        if self.lower_value > self.upper_value:
             # Swap if crossed, or enforce constraint? usually enforce lower <= upper
             self.upper_value = self.lower_value
             # Or just swap them? default implementation often clamps.
             # Let's trust the input slightly but ensure order.
             # If lower > upper, valid behavior is lower=upper.
             pass
        self.update()
        self.valueChanged.emit(self.lower_value, self.upper_value)


class DuplicatesSimilarDialog(BaseDialog):
    """
    Diálogo para gestionar archivos similares (70-95% de similitud).
    
    IMPORTANTE: Este diálogo es para archivos SIMILARES, no idénticos.
    Para copias idénticas, usar el diálogo "Copias Visuales Idénticas".
    """
    
    DEFAULT_SENSITIVITY = 70
    
    def __init__(self, analysis: DuplicatesSimilarAnalysis, parent=None):
        super().__init__(parent)
        
        self.logger = get_logger('DuplicatesSimilarDialog')
        self.analysis = analysis
        self.repo = FileInfoRepositoryCache.get_instance()
        
        self.current_sensitivity = self.DEFAULT_SENSITIVITY
        self.current_result = None
        self.all_groups = []
        self.current_group_index = 0
        self.selections = {}
        self.accepted_plan = None
        self._is_loading = True
        self.keep_strategy = None  # Ninguna estrategia por defecto
        self.strategy_buttons = {}
        
        # Referencias a widgets de filtros
        self.search_input = None
        self.filter_combo = None
        self.type_combo = None
        self.source_combo = None
        self.similarity_range_slider = None  # Cambiado de combo a slider de rango
        self.status_chip = None
        self.filter_bar = None
        self.filtered_groups = []  # Grupos filtrados
        
        self._setup_ui()
        self._show_loading_state()
        
        # Cargar grupos DESPUÉS de que el diálogo sea visible
        QTimer.singleShot(100, self._initial_load)
    
    def _setup_ui(self):
        """Configura la interfaz del diálogo."""
        self.setWindowTitle(TOOL_DUPLICATES_SIMILAR.title)
        self.setModal(True)
        self.resize(1280, 900)
        self.setMinimumSize(1100, 750)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header con tip integrado
        self.header_frame = self._create_compact_header_with_metrics(
            icon_name=TOOL_DUPLICATES_SIMILAR.icon_name,
            title=TOOL_DUPLICATES_SIMILAR.title,
            description=TOOL_DUPLICATES_SIMILAR.short_description,
            metrics=[
                {'value': '-', 'label': tr("dialogs.duplicates_similar.metric_groups"), 'color': DesignSystem.COLOR_PRIMARY},
                {'value': '-', 'label': tr("dialogs.duplicates_similar.metric_similar"), 'color': DesignSystem.COLOR_WARNING},
                {'value': '-', 'label': tr("dialogs.duplicates_similar.metric_recoverable"), 'color': DesignSystem.COLOR_SUCCESS}
            ],
            tip_message=tr("dialogs.duplicates_similar.tip_message")
        )
        main_layout.addWidget(self.header_frame)
        
        # Contenedor principal
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setSpacing(DesignSystem.SPACE_16)
        content_layout.setContentsMargins(
            DesignSystem.SPACE_24, DesignSystem.SPACE_20,
            DesignSystem.SPACE_24, DesignSystem.SPACE_20
        )
        
        # Barra de acciones globales (antes sensibilidad)
        self.global_actions_bar = self._create_global_actions_bar()
        content_layout.addWidget(self.global_actions_bar)
        
        # Barra de filtros (debajo de la sensibilidad, para coherencia)
        self.filter_bar = self._create_filter_bar()
        content_layout.addWidget(self.filter_bar)
        
        # Área de trabajo (workspace_card)
        workspace_card = QFrame()
        workspace_card.setObjectName("workspace_card")
        workspace_card.setStyleSheet(DesignSystem.get_workspace_card_style())
        workspace_layout = QVBoxLayout(workspace_card)
        workspace_layout.setSpacing(0)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar del grupo: navegación + info de similitud + estrategias
        self.workspace_toolbar = self._create_group_toolbar()
        workspace_layout.addWidget(self.workspace_toolbar)
        
        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(DesignSystem.get_horizontal_separator_style())
        workspace_layout.addWidget(separator)
        
        # Contenedor de grupos (grid de imágenes)
        self.group_container = QWidget()
        self.group_layout = QVBoxLayout(self.group_container)
        self.group_layout.setContentsMargins(
            DesignSystem.SPACE_20, DesignSystem.SPACE_20,
            DesignSystem.SPACE_20, DesignSystem.SPACE_20
        )
        self.group_layout.setSpacing(DesignSystem.SPACE_16)
        
        workspace_layout.addWidget(self.group_container, stretch=1)
        content_layout.addWidget(workspace_card, stretch=1)
        
        main_layout.addWidget(content_wrapper, stretch=1)
        
        # Opciones de seguridad
        security_options = self._create_security_options_section(
            show_backup=True,
            show_dry_run=True,
            backup_label=tr("dialogs.duplicates_similar.option_backup"),
            dry_run_label=tr("dialogs.duplicates_similar.option_dry_run")
        )
        content_layout.addWidget(security_options)
        
        # Botones
        button_box = self.make_ok_cancel_buttons(
            ok_text=tr("dialogs.duplicates_similar.button_delete"),
            ok_enabled=False,
            button_style='danger'
        )
        self.delete_btn: Optional[QPushButton] = button_box.button(QDialogButtonBox.StandardButton.Ok)
        content_layout.addWidget(button_box)
        
        # Maximizar el diálogo para aprovechar el espacio
        self.showMaximized()

    def _create_global_actions_bar(self) -> QFrame:
        """Crea la barra de acciones globales con estilo unificado (Chips)."""
        strategies = [
            ('keep_largest', 'arrow-expand-all', tr("dialogs.duplicates_similar.strategy.auto_title"), tr("dialogs.duplicates_similar.strategy.auto_tooltip"))
        ]
        
        frame = self._create_compact_strategy_selector(
            title=tr("dialogs.duplicates_similar.strategy.title"),
            description=tr("dialogs.duplicates_similar.strategy.description"),
            strategies=strategies,
            current_strategy=self.keep_strategy,
            on_strategy_changed=self._on_global_strategy_changed
        )
        
        # Guardar referencia a botones globales
        self.global_strategy_buttons = getattr(frame, 'strategy_buttons', {})
        
        return frame
    
    def _create_filter_bar(self) -> QFrame:
        """Crea la barra de filtros unificada para buscar y filtrar grupos."""
        # Opciones para filtro de origen de fecha (usar constantes de BaseDialog)
        source_options = self.DATE_SOURCE_FILTER_OPTIONS
        
        # Diccionario de etiquetas
        labels = {
            'search': tr("dialogs.duplicates_similar.filter.search"),
            'size': tr("dialogs.duplicates_similar.filter.size"),
            'groups': tr("dialogs.duplicates_similar.filter.groups"),
            'source': tr("dialogs.duplicates_similar.filter.source"),
            'type': tr("dialogs.duplicates_similar.filter.type")
        }
        
        # Opciones de filtro de tamaño específicas para este diálogo
        size_options = [
            tr("common.filter.all"),
            tr("common.filter.gt_10mb"),
            tr("common.filter.gt_50mb"),
            tr("common.filter.3_plus_copies"),
            tr("common.filter.5_plus_copies")
        ]
        
        # Configuración de filtros expandibles (similitud eliminada de aquí, va arriba)
        expandable_filters = [
            {
                'id': 'source',
                'type': 'combo',
                'label': labels['source'],
                'tooltip': tr("dialogs.duplicates_similar.filter.source_tooltip"),
                'options': source_options,
                'on_change': self._on_source_filter_changed,
                'default_index': 0,
                'min_width': 200
            },
            {
                'id': 'type',
                'type': 'combo',
                'label': labels['type'],
                'tooltip': tr("dialogs.duplicates_similar.filter.type_tooltip"),
                'options': [tr("common.filter.all"), tr("common.filter.photos"), tr("common.filter.videos")],
                'on_change': self._on_type_filter_changed,
                'default_index': 0,
                'min_width': 120
            }
        ]
        
        filter_bar = self._create_unified_filter_bar(
            on_search_changed=self._on_search_changed,
            on_size_filter_changed=self._on_size_filter_changed,
            expandable_filters=expandable_filters,
            size_filter_options=size_options,
            is_files_mode=False,
            labels=labels
        )
        
        # Inject Similarity Slider into Primary Bar
        # Get Primary Bar layout (it is the first item in the main layout of filter_bar)
        main_layout = filter_bar.layout() # QVBoxLayout
        if main_layout and main_layout.count() > 0:
            primary_bar = main_layout.itemAt(0).layout() # QHBoxLayout
            if primary_bar:
                # Create the widget
                similarity_widget = self._create_similarity_range_widget()
                
                # Insert at index 1 (after Search, before Stretch which is at index 1 before insertion)
                # Primary Bar structure: Search | Stretch | Status | Expand
                primary_bar.insertWidget(1, similarity_widget)
                
                # Note: The widget itself should have a fixed width or max width to avoid taking too much space
                similarity_widget.setFixedWidth(320)
                
                # Save reference (the widget inside is already self.range_slider)
                self.similarity_range_slider = similarity_widget
        
        # Guardar referencias a los widgets
        self.search_input = filter_bar.search_input
        self.filter_combo = filter_bar.size_filter_combo
        self.status_chip = filter_bar.status_chip
        self.source_combo = filter_bar.filter_widgets.get('source')
        self.type_combo = filter_bar.filter_widgets.get('type')
        
        return filter_bar
    
    # ================= FILTER HANDLERS =================
    
    def _on_search_changed(self, text: str):
        """Maneja cambios en la búsqueda."""
        self._apply_filters()
    
    def _on_size_filter_changed(self, index: int):
        """Maneja cambios en el filtro de tamaño."""
        self._apply_filters()
    
    def _on_type_filter_changed(self, index: int):
        """Maneja cambios en el filtro de tipo de archivo."""
        self._apply_filters()
    
    def _on_source_filter_changed(self, index: int):
        """Maneja cambios en el filtro de origen de fecha."""
        self._apply_filters()
    
    def _create_similarity_range_widget(self) -> QWidget:
        """Crea el widget de rango dual para filtro de similitud con spinboxes y etiqueta."""
        from ui.styles.design_system import DesignSystem
        
        # Container principal (Vertical para incluir etiqueta)
        container = QWidget()
        v_layout = QVBoxLayout(container)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(2)
        
        # Etiqueta consistente con el sistema de filtros
        label = QLabel(tr("dialogs.duplicates_similar.filter.sensitivity_label"))
        label.setStyleSheet(DesignSystem.get_filter_label_style())
        v_layout.addWidget(label)
        
        # Frame del control
        frame = QFrame()
        frame.setObjectName("similarity_range_control")
        frame.setStyleSheet(DesignSystem.get_similarity_range_control_style())
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(DesignSystem.SPACE_8, 2, DesignSystem.SPACE_8, 2)
        layout.setSpacing(DesignSystem.SPACE_4)
        
        # SpinBox Min
        self.min_spin = QSpinBox()
        self.min_spin.setRange(70, 100)
        self.min_spin.setSuffix("%")
        self.min_spin.setFixedWidth(55)
        self.min_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.min_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons) # Cleaner look
        self.min_spin.setToolTip(tr("dialogs.duplicates_similar.filter.min_tooltip"))
        
        # Slider
        self.range_slider = DualRangeSlider(minimum=70, maximum=100, parent=self)
        self.range_slider.set_range(70, 100)
        
        # SpinBox Max
        self.max_spin = QSpinBox()
        self.max_spin.setRange(70, 100)
        self.max_spin.setSuffix("%")
        self.max_spin.setFixedWidth(55)
        self.max_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.max_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons) # Cleaner look
        self.max_spin.setToolTip(tr("dialogs.duplicates_similar.filter.max_tooltip"))
        
        # Valores iniciales
        self.min_spin.setValue(70)
        self.max_spin.setValue(100)
        
        layout.addWidget(self.min_spin)
        layout.addWidget(self.range_slider, stretch=1) # Give slider stretch
        layout.addWidget(self.max_spin)
        
        v_layout.addWidget(frame)
        
        # Conexiones bidireccionales
        
        # Slider -> SpinBoxes
        def on_slider_change(lower, upper):
            self.min_spin.blockSignals(True)
            self.max_spin.blockSignals(True)
            self.min_spin.setValue(lower)
            self.max_spin.setValue(upper)
            self.min_spin.blockSignals(False)
            self.max_spin.blockSignals(False)
            
        self.range_slider.valueChanged.connect(on_slider_change)
        
        # SpinBoxes -> Slider
        def on_spins_change():
            low = self.min_spin.value()
            high = self.max_spin.value()
            
            # Validar cruces
            if low > high:
                if self.sender() == self.min_spin:
                    high = low  # Empujar el max si subimos el min
                    self.max_spin.setValue(high)
                else:
                    low = high  # Empujar el min si bajamos el max
                    self.min_spin.setValue(low)
            
            self.range_slider.set_range(low, high)
            
            # Aplicar filtro
            if hasattr(self, '_apply_filters'):
                self._apply_filters()
                
        self.min_spin.valueChanged.connect(on_spins_change)
        self.max_spin.valueChanged.connect(on_spins_change)
        
        # Guardar callback para aplicar filtros cuando se suelte el mouse del slider
        # (para no filtrar excesivamente mientras se arrastra)
        original_release = self.range_slider.mouseReleaseEvent
        def on_release(event):
            original_release(event)
            if hasattr(self, '_apply_filters'):
                self._apply_filters()
        self.range_slider.mouseReleaseEvent = on_release
        
        return container
    
    def _on_similarity_filter_changed(self, index: int):
        """Maneja cambios en el filtro de similitud (legacy - ahora usa slider)."""
        self._apply_filters()
    
    def _group_matches_similarity_filter(self, group: SimilarDuplicateGroup) -> bool:
        """Verifica si un grupo coincide con el filtro de similitud.
        
        Filtra grupos según su porcentaje de similitud usando el rango del slider.
        """
        if not hasattr(self, 'range_slider') or not self.range_slider:
            return True
        
        score = group.similarity_score
        lower, upper = self.range_slider.get_range()
        
        # El grupo debe estar dentro del rango [lower, upper]
        return lower <= score <= upper
    
    def _group_matches_type_filter(self, group: SimilarDuplicateGroup) -> bool:
        """
        Verifica si un grupo coincide con el filtro de tipo de archivo.
        
        Un grupo coincide si AL MENOS UN archivo del grupo es del tipo seleccionado.
        """
        if not self.type_combo:
            return True
            
        type_filter = self.type_combo.currentText()
        if type_filter == "Todos":
            return True
        
        for file_path in group.files:
            if type_filter == 'Fotos' and is_image_file(file_path):
                return True
            elif type_filter == 'Videos' and is_video_file(file_path):
                return True
        
        return False
    
    def _group_matches_source_filter(self, group: SimilarDuplicateGroup) -> bool:
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
        """Aplica todos los filtros activos y actualiza la vista."""
        if not self.all_groups or self._is_loading:
            return
        
        search_text = self.search_input.text().lower() if self.search_input else ""
        filter_index = self.filter_combo.currentIndex() if self.filter_combo else 0
        
        filtered = []
        
        for group in self.all_groups:
            # Filtro por similitud
            if not self._group_matches_similarity_filter(group):
                continue
            
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
            if filter_index == 1:  # >10 MB
                if group.total_size < 10 * 1024 * 1024:
                    continue
            elif filter_index == 2:  # >50 MB
                if group.total_size < 50 * 1024 * 1024:
                    continue
            elif filter_index == 3:  # 3+ copias
                if len(group.files) < 3:
                    continue
            elif filter_index == 4:  # 5+ copias
                if len(group.files) < 5:
                    continue
            
            filtered.append(group)
        
        self.filtered_groups = filtered
        
        # Actualizar el chip de estado
        self._update_filter_chip(
            self.status_chip, 
            len(self.filtered_groups), 
            len(self.all_groups)
        )
        
        # Actualizar métricas del header
        self._update_header_metrics_for_filtered()
        
        # Actualizar estado de botones de selección automática (deshabilitar si no hay grupos)
        self._update_global_buttons_enabled_state()
        
        # Recargar la vista con grupos filtrados
        if self.filtered_groups:
            self.current_group_index = 0
            self._load_group(0)
        else:
            self._show_no_groups_message()

    def _update_header_metrics_for_filtered(self):
        """Actualiza las métricas del header basadas en los grupos filtrados.
        
        IMPORTANTE: Si no hay grupos filtrados, muestra 0 en todas las métricas,
        NO los valores del total de all_groups.
        """
        # Usar filtered_groups directamente, NO fallback a all_groups
        groups_to_use = self.filtered_groups
        
        total_groups = len(groups_to_use)
        total_similar = sum(len(g.files) - 1 for g in groups_to_use)
        space_potential = sum(
            (len(g.files) - 1) * (g.total_size // len(g.files))
            for g in groups_to_use if g.files
        )
        
        self._update_header_metric(self.header_frame, tr("dialogs.duplicates_similar.metric_groups"), str(total_groups))
        self._update_header_metric(self.header_frame, tr("dialogs.duplicates_similar.metric_similar"), str(total_similar))
        self._update_header_metric(self.header_frame, tr("dialogs.duplicates_similar.metric_recoverable"), format_size(space_potential))
    
    # ================= STRATEGY BUTTONS =================
    
    def _create_strategy_buttons(self, parent_layout: QHBoxLayout):
        """Crea los botones de estrategia inline para la toolbar."""
        self.strategy_buttons = {}
        
        strategies = [
            ('keep_largest', 'arrow-expand-all', tr("dialogs.duplicates_similar.strategy.keep_largest_title"), tr("dialogs.duplicates_similar.strategy.keep_largest_tooltip")),
        ]
        
        for strategy_id, icon_name, label, tooltip in strategies:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(False)  # Ninguno seleccionado por defecto
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            icon_manager.set_button_icon(btn, icon_name, size=16)
            btn.setStyleSheet(DesignSystem.get_strategy_button_style())
            btn.clicked.connect(lambda checked, s=strategy_id: self._on_strategy_changed(s))
            parent_layout.addWidget(btn)
            self.strategy_buttons[strategy_id] = btn
    
    def _on_strategy_changed(self, strategy_id: str):
        """Maneja el cambio de estrategia de conservación."""
        self.keep_strategy = strategy_id
        
        # Actualizar estado visual de botones
        for btn_id, btn in self.strategy_buttons.items():
            btn.setChecked(btn_id == strategy_id)
        
        # Aplicar estrategia al grupo actual
        self._apply_strategy(strategy_id)
    
    def _reset_strategy_buttons(self):
        """Resetea los botones de estrategia (ninguno seleccionado)."""
        self.keep_strategy = None
        for btn in self.strategy_buttons.values():
            btn.setChecked(False)
    
    def _on_global_strategy_changed(self, strategy: str):
        """Maneja cambios en la estrategia global (selección automática).
        
        IMPORTANTE: Solo aplica a los grupos actualmente filtrados (visibles).
        Los grupos que no coinciden con los filtros actuales conservan su selección.
        """
        # Verificar que hay grupos filtrados disponibles
        filtered_count = len(self.filtered_groups)
        if filtered_count == 0:
            # No hay grupos filtrados, no hacer nada
            self.logger.info("No filtered groups available for automatic selection")
            return
        
        # Primero reseteamos visualmente para que no parezca activado hasta que confirmen
        self._update_global_buttons_state(None) # Uncheck all temporarily
        
        from PyQt6.QtWidgets import QMessageBox
        
        strategy_name = tr("dialogs.duplicates_similar.auto_select.strategy_name")
        total_count = len(self.all_groups)
        
        # Diálogo de confirmación
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(tr("dialogs.duplicates_similar.auto_select.title", name=strategy_name))
        
        if filtered_count < total_count:
            # Hay filtros aplicados
            msg.setText(
                tr("dialogs.duplicates_similar.auto_select.text_filtered",
                   name=strategy_name, count=filtered_count)
            )
            msg.setInformativeText(
                tr("dialogs.duplicates_similar.auto_select.info_filtered",
                   filtered=filtered_count, remaining=total_count - filtered_count)
            )
        else:
            # No hay filtros, se aplica a todos
            msg.setText(
                tr("dialogs.duplicates_similar.auto_select.text_all",
                   name=strategy_name, count=total_count)
            )
            msg.setInformativeText(
                tr("dialogs.duplicates_similar.auto_select.info_all")
            )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        msg.setStyleSheet(DesignSystem.get_stylesheet())
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.keep_strategy = strategy
            self._apply_strategy_to_filtered_groups(strategy)
            self._update_global_buttons_state(strategy)
        else:
            # Si cancela, restauramos el estado visual anterior
            self._update_global_buttons_state(self.keep_strategy)

    def _update_global_buttons_state(self, current_strategy):
        """Actualiza el estado visual de los botones globales."""
        if hasattr(self, 'global_strategy_buttons'):
            for s, btn in self.global_strategy_buttons.items():
                btn.setChecked(s == current_strategy)
    
    def _update_global_buttons_enabled_state(self):
        """Actualiza el estado habilitado/deshabilitado de los botones de selección automática.
        
        Deshabilita los botones cuando no hay grupos filtrados disponibles.
        """
        has_filtered_groups = len(self.filtered_groups) > 0
        
        if hasattr(self, 'global_strategy_buttons'):
            for btn in self.global_strategy_buttons.values():
                btn.setEnabled(has_filtered_groups)
                if not has_filtered_groups:
                    btn.setToolTip(tr("dialogs.duplicates_similar.strategy.disabled_tooltip"))
                else:
                    btn.setToolTip(tr("dialogs.duplicates_similar.strategy.auto_tooltip"))
    
    def _on_auto_select_click(self, strategy: str):
        """DEPRECATED: Mantenido por si acaso, redirige a _on_global_strategy_changed."""
        self._on_global_strategy_changed(strategy)

    def _create_group_toolbar(self) -> QWidget:
        """
        Crea la barra de grupo unificada con:
        - Navegación (anterior/siguiente)
        - Info de similitud del grupo actual
        - Estrategias de conservación
        - Contador de selección
        
        Todo junto en una toolbar compacta y profesional.
        """
        container = QWidget()
        container.setObjectName("group_toolbar")
        container.setStyleSheet(DesignSystem.get_group_toolbar_style())
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            DesignSystem.SPACE_16, DesignSystem.SPACE_12,
            DesignSystem.SPACE_16, DesignSystem.SPACE_12
        )
        layout.setSpacing(DesignSystem.SPACE_12)
        
        # === SECCIÓN IZQUIERDA: Navegación ===
        nav_frame = QFrame()
        nav_frame.setStyleSheet(DesignSystem.get_nav_frame_style())
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(4, 4, 4, 4)
        nav_layout.setSpacing(4)
        
        self.prev_btn = QPushButton()
        icon_manager.set_button_icon(self.prev_btn, 'chevron-left', size=18)
        self.prev_btn.setToolTip(tr("dialogs.duplicates_similar.nav.prev_tooltip"))
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.clicked.connect(self._previous_group)
        self.prev_btn.setEnabled(False)
        self.prev_btn.setStyleSheet(DesignSystem.get_nav_button_style())
        nav_layout.addWidget(self.prev_btn)
        
        self.group_counter_label = QLabel(tr("dialogs.duplicates_similar.loading.counter"))
        self.group_counter_label.setMinimumWidth(100)
        self.group_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.group_counter_label.setStyleSheet(DesignSystem.get_group_counter_label_style())
        nav_layout.addWidget(self.group_counter_label)
        
        self.next_btn = QPushButton()
        icon_manager.set_button_icon(self.next_btn, 'chevron-right', size=18)
        self.next_btn.setToolTip(tr("dialogs.duplicates_similar.nav.next_tooltip"))
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.clicked.connect(self._next_group)
        self.next_btn.setEnabled(False)
        self.next_btn.setStyleSheet(DesignSystem.get_nav_button_style())
        nav_layout.addWidget(self.next_btn)
        
        layout.addWidget(nav_frame)
        
        # Separador
        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setFixedHeight(28)
        sep1.setStyleSheet(DesignSystem.get_vertical_separator_style())
        layout.addWidget(sep1)
        
        # === SECCIÓN CENTRO: Similitud del grupo actual ===
        self.similarity_container = QWidget()
        sim_layout = QHBoxLayout(self.similarity_container)
        sim_layout.setContentsMargins(0, 0, 0, 0)
        sim_layout.setSpacing(DesignSystem.SPACE_8)
        
        # Badge de similitud
        self.similarity_badge = QLabel("-")
        self.similarity_badge.setStyleSheet(DesignSystem.get_similarity_badge_style())
        sim_layout.addWidget(self.similarity_badge)
        
        # Info de archivos del grupo
        self.group_files_info = QLabel("-")
        self.group_files_info.setStyleSheet(DesignSystem.get_group_files_info_style())
        sim_layout.addWidget(self.group_files_info)
        
        layout.addWidget(self.similarity_container)
        
        # Separador
        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(28)
        sep2.setStyleSheet(DesignSystem.get_vertical_separator_style())
        layout.addWidget(sep2)
        
        # === SECCIÓN DERECHA: Estrategias y acciones ===
        strategy_label = QLabel(tr("dialogs.duplicates_similar.toolbar.keep_label"))
        strategy_label.setStyleSheet(DesignSystem.get_strategy_label_style())
        layout.addWidget(strategy_label)
        
        self._create_strategy_buttons(layout)
        
        layout.addStretch()
        
        # Contador de selección global
        self.global_summary_label = QLabel(tr("dialogs.duplicates_similar.summary.none_selected"))
        self.global_summary_label.setMinimumWidth(120)
        self.global_summary_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.global_summary_label.setStyleSheet(DesignSystem.get_global_summary_label_style())
        layout.addWidget(self.global_summary_label)
        
        return container
    
    def _update_group_similarity_display(self, group):
        """Actualiza los indicadores de similitud del grupo actual."""
        if not group:
            self.similarity_badge.setText("-")
            self.group_files_info.setText("-")
            return
        
        score = group.similarity_score
        
        # Determinar color según el nivel de similitud (colores sólidos más elegantes)
        if score >= 95:
            bg_color = "#10b981"  # Verde elegante
        elif score >= 85:
            bg_color = DesignSystem.COLOR_PRIMARY  # Azul primary
        else:
            bg_color = "#f59e0b"  # Ámbar/naranja elegante
        
        # Actualizar badge con texto abreviado
        self.similarity_badge.setText(tr("dialogs.duplicates_similar.badge.similarity", score=score))
        self.similarity_badge.setStyleSheet(DesignSystem.get_similarity_badge_with_color_style(bg_color))
        
        # Actualizar info de archivos
        self.group_files_info.setText(tr("dialogs.duplicates_similar.badge.files_info", count=len(group.files), size=format_size(group.total_size)))

    # ================= LOADING STATE =================

    def _show_loading_state(self):
        """Muestra estado de carga con barra de progreso real.
        
        Usa QProgressBar con rango determinado para mostrar porcentaje real
        del proceso de clustering, manteniendo la UI responsiva mediante
        callbacks que llaman a processEvents().
        """
        for i in reversed(range(self.group_layout.count())):
            item = self.group_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)  # type: ignore[union-attr]
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(DesignSystem.SPACE_16)
        
        # Icono de búsqueda (estático, no animado)
        icon_label = icon_manager.create_icon_label(
            'image-search', size=48, color=DesignSystem.COLOR_PRIMARY
        )
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Mensaje principal (se actualiza dinámicamente)
        self.loading_label = QLabel(tr("dialogs.duplicates_similar.loading.preparing"))
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet(DesignSystem.get_loading_label_style())
        layout.addWidget(self.loading_label)
        
        # Barra de progreso con porcentaje real
        total_files = len(self.analysis.perceptual_hashes)
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, total_files)
        self.loading_progress.setValue(0)
        self.loading_progress.setFixedWidth(350)
        self.loading_progress.setFixedHeight(8)
        self.loading_progress.setTextVisible(False)
        self.loading_progress.setStyleSheet(DesignSystem.get_loading_progressbar_style())
        layout.addWidget(self.loading_progress, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Porcentaje y contador
        self.loading_percent = QLabel("0%")
        self.loading_percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_percent.setStyleSheet(DesignSystem.get_loading_percent_style())
        layout.addWidget(self.loading_percent)
        
        # Submensaje con detalle de la fase actual
        self.loading_submsg = QLabel(
            tr("dialogs.duplicates_similar.loading.submessage",
               sensitivity=self.current_sensitivity, count=f"{total_files:,}")
        )
        self.loading_submsg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_submsg.setStyleSheet(DesignSystem.get_loading_submessage_style())
        layout.addWidget(self.loading_submsg)
        
        self.group_layout.addWidget(container)
        
        # Deshabilitar controles durante carga
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)

    def _update_loading_progress(self, current: int, total: int, message: str) -> bool:
        """Callback para actualizar la barra de progreso durante el clustering.
        
        Args:
            current: Archivo actual siendo procesado
            total: Total de archivos
            message: Mensaje descriptivo de la fase actual
            
        Returns:
            True para continuar, False para cancelar (no implementado)
        """
        from PyQt6.QtWidgets import QApplication
        from PyQt6.sip import isdeleted
        
        # Verificar que los widgets existen antes de usarlos
        if (hasattr(self, 'loading_progress') and 
            self.loading_progress is not None and 
            not isdeleted(self.loading_progress)):
            self.loading_progress.setValue(current)
            
            # Actualizar porcentaje
            percent = (current / total * 100) if total > 0 else 0
            if (hasattr(self, 'loading_percent') and 
                self.loading_percent is not None and 
                not isdeleted(self.loading_percent)):
                self.loading_percent.setText(f"{percent:.0f}%")
            
            # Actualizar mensaje de fase
            if (hasattr(self, 'loading_label') and 
                self.loading_label is not None and 
                not isdeleted(self.loading_label)):
                self.loading_label.setText(message)
            
            # Procesar eventos para mantener UI responsiva
            QApplication.processEvents()
        
        return True  # Continuar procesando

    def _initial_load(self):
        """Carga inicial de grupos (llamada después de mostrar el diálogo)."""
        from PyQt6.QtWidgets import QApplication
        
        # Procesar eventos para asegurar que el diálogo está visible
        QApplication.processEvents()
        
        self._regenerate_groups()
        self._is_loading = False

    # ================= LÓGICA =================



    def _regenerate_groups(self):
        """Regenera los grupos con la sensibilidad actual.
        
        Usa callback de progreso para mantener la UI responsiva
        y mostrar el avance real del clustering.
        """
        from PyQt6.QtWidgets import QApplication
        from PyQt6.sip import isdeleted
        
        self.logger.info(f"Regenerating groups with sensitivity {self.current_sensitivity}%...")
        
        # Actualizar info de sensibilidad (verificar que el widget existe)
        if (hasattr(self, 'loading_submsg') and 
            self.loading_submsg is not None and 
            not isdeleted(self.loading_submsg)):
            total_files = len(self.analysis.perceptual_hashes)
            self.loading_submsg.setText(
                tr("dialogs.duplicates_similar.loading.submessage",
                   sensitivity=self.current_sensitivity, count=f"{total_files:,}")
            )
            QApplication.processEvents()
        
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # Ejecutar clustering con callback de progreso
            result = self.analysis.get_groups(
                self.current_sensitivity,
                progress_callback=self._update_loading_progress
            )
            
            self.current_result = result
            self.all_groups = result.groups.copy()
            self.filtered_groups = self.all_groups.copy()  # Inicialmente todos los grupos están filtrados
            
            self.logger.info(f"Found {len(self.all_groups)} groups")
            
            self.selections.clear()
            self._update_header_metrics()
            
            # Actualizar el chip de estado de filtros
            self._update_filter_chip(
                self.status_chip,
                len(self.filtered_groups),
                len(self.all_groups)
            )
            
            # Actualizar estado de botones de selección automática
            self._update_global_buttons_enabled_state()
            
            if self.all_groups:
                self.current_group_index = 0
                self._load_group(0)
            else:
                self._show_no_groups_message()
                
        finally:
            QApplication.restoreOverrideCursor()

    def _update_header_metrics(self):
        """Actualiza las métricas del header."""
        total_groups = len(self.all_groups)
        total_similar = sum(len(g.files) - 1 for g in self.all_groups)
        space_potential = sum(
            (len(g.files) - 1) * (g.total_size // len(g.files))
            for g in self.all_groups if g.files
        )
        
        self._update_header_metric(self.header_frame, tr("dialogs.duplicates_similar.metric_groups"), str(total_groups))
        self._update_header_metric(self.header_frame, tr("dialogs.duplicates_similar.metric_similar"), str(total_similar))
        self._update_header_metric(self.header_frame, tr("dialogs.duplicates_similar.metric_recoverable"), format_size(space_potential))

    def _show_no_groups_message(self):
        """Muestra mensaje cuando no hay grupos (ya sea por filtros o sin coincidencias)."""
        for i in reversed(range(self.group_layout.count())):
            item = self.group_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)  # type: ignore[union-attr]
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(DesignSystem.SPACE_16)
        
        icon_label = icon_manager.create_icon_label('check-circle', size=64, color=DesignSystem.COLOR_SUCCESS)
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Mensaje diferente según si hay grupos totales o no
        if self.all_groups and not self.filtered_groups:
            # Hay grupos pero los filtros los ocultaron
            msg_text = tr("dialogs.duplicates_similar.no_groups.filtered")
        else:
            # No hay grupos en absoluto
            msg_text = tr("dialogs.duplicates_similar.no_groups.none_found",
                         pct=self.current_sensitivity)
        
        msg = QLabel(msg_text)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet(f"font-size: {DesignSystem.FONT_SIZE_MD}px; color: {DesignSystem.COLOR_TEXT_SECONDARY};")
        layout.addWidget(msg)
        
        self.group_layout.addWidget(container)
        
        self.group_counter_label.setText(tr("dialogs.duplicates_similar.nav.counter_empty"))
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        
        # Resetear indicadores de similitud
        self._update_group_similarity_display(None)

    def _load_group(self, index: int):
        """Carga y muestra un grupo específico de los grupos filtrados.
        
        NOTA: El índice se refiere a filtered_groups. Las selecciones se almacenan
        usando el índice real en all_groups para persistir entre cambios de filtro.
        """
        groups_to_show = self.filtered_groups if self.filtered_groups else self.all_groups
        
        if not 0 <= index < len(groups_to_show):
            return
        
        self.current_group_index = index
        group = groups_to_show[index]
        
        # Obtener el índice real en all_groups para acceder a selections
        real_index = self._get_real_group_index(index)
        
        # Actualizar contador de navegación
        self.group_counter_label.setText(tr("dialogs.duplicates_similar.nav.counter", index=index + 1, total=len(groups_to_show)))
        
        # Habilitar navegación cíclica si hay más de un grupo
        has_multiple_groups = len(groups_to_show) > 1
        self.prev_btn.setEnabled(has_multiple_groups)
        self.next_btn.setEnabled(has_multiple_groups)
        
        # Actualizar indicadores de similitud en la toolbar
        self._update_group_similarity_display(group)
        
        # Resetear botones de estrategia (ninguno seleccionado)
        self._reset_strategy_buttons()
        
        # Limpiar contenedor de grupo
        for i in reversed(range(self.group_layout.count())):
            item = self.group_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)  # type: ignore[union-attr]
        
        # Grid de imágenes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(DesignSystem.SPACE_16)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # Usar el índice real para obtener la selección
        current_selection = self.selections.get(real_index, []) if real_index is not None else []
        
        cols = 3
        # Determinar qué archivos se van a conservar (los NO seleccionados cuando hay selección)
        has_selection = len(current_selection) > 0
        for i, file_path in enumerate(group.files):
            is_selected = file_path in current_selection
            will_be_kept = has_selection and not is_selected
            card = self._create_file_card(file_path, is_selected, will_be_kept)
            grid_layout.addWidget(card, i // cols, i % cols)
        
        scroll.setWidget(grid_widget)
        self.group_layout.addWidget(scroll)

    def _create_file_card(self, file_path: Path, is_selected: bool, will_be_kept: bool = False) -> QFrame:
        """Crea tarjeta para un archivo."""
        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mouseDoubleClickEvent = lambda e: show_file_details_dialog(file_path, self)  # type: ignore[assignment]
        card.setStyleSheet(self._get_card_style(is_selected, will_be_kept))
        
        layout = QVBoxLayout(card)
        layout.setSpacing(DesignSystem.SPACE_8)
        layout.setContentsMargins(DesignSystem.SPACE_8, DesignSystem.SPACE_8, DesignSystem.SPACE_8, DesignSystem.SPACE_8)
        
        # Header
        header = QHBoxLayout()
        
        checkbox = QCheckBox(tr("dialogs.duplicates_similar.card.checkbox_delete"))
        checkbox.setChecked(is_selected)
        checkbox.setStyleSheet(f"QCheckBox {{ color: {DesignSystem.COLOR_DANGER}; font-weight: {DesignSystem.FONT_WEIGHT_BOLD}; }}")
        checkbox.toggled.connect(lambda checked, f=file_path: self._toggle_selection(f, checked))
        header.addWidget(checkbox)
        
        header.addStretch()
        
        info_badge = self._create_info_badge(file_path)
        header.addWidget(info_badge)
        
        try:
            size_text = format_size(file_path.stat().st_size)
        except:
            size_text = "?"
        size_lbl = QLabel(size_text)
        size_lbl.setStyleSheet(f"color: {DesignSystem.COLOR_TEXT_SECONDARY}; font-size: {DesignSystem.FONT_SIZE_XS}px; border: none; background: transparent;")
        header.addWidget(size_lbl)
        
        layout.addLayout(header)
        
        # Thumbnail
        thumb_lbl, is_video = self._create_thumbnail(file_path)
        if thumb_lbl:
            thumb_lbl.mousePressEvent = lambda e, f=file_path, v=is_video: self._handle_thumbnail_click(f, v)  # type: ignore[assignment]
            layout.addWidget(thumb_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Nombre
        name_lbl = QLabel(file_path.name)
        name_lbl.setWordWrap(True)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet(f"font-size: {DesignSystem.FONT_SIZE_SM}px; color: {DesignSystem.COLOR_TEXT}; border: none; background: transparent;")
        layout.addWidget(name_lbl)
        
        # Fecha
        date_info = self._get_file_date_info(file_path)
        if date_info:
            date_lbl = QLabel(date_info)
            date_lbl.setWordWrap(True)
            date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            date_lbl.setStyleSheet(f"font-size: {DesignSystem.FONT_SIZE_XS}px; color: {DesignSystem.COLOR_TEXT_SECONDARY}; border: none; background: transparent;")
            layout.addWidget(date_lbl)
        
        card.setProperty("file_path", str(file_path))
        card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos, f=file_path: self._show_context_menu(f))
        
        return card

    def _create_info_badge(self, file_path: Path) -> QLabel:
        """Crea badge de info."""
        badge = QLabel()
        info_icon = icon_manager.get_icon('information-outline', size=16, color=DesignSystem.COLOR_PRIMARY)
        badge.setPixmap(info_icon.pixmap(16, 16))
        badge.setFixedSize(20, 20)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(DesignSystem.get_info_badge_style())
        badge.setCursor(Qt.CursorShape.PointingHandCursor)
        badge.mousePressEvent = lambda e, f=file_path: show_file_details_dialog(f, self)  # type: ignore[assignment]
        return badge

    def _get_card_style(self, is_selected: bool, will_be_kept: bool = False) -> str:
        """Retorna el estilo de la tarjeta según su estado.
        
        - is_selected (rojo): archivo marcado para eliminación
        - will_be_kept (verde): archivo que se conservará (no seleccionado cuando hay selección en el grupo)
        - neutro (blanco): sin selección en el grupo
        """
        if is_selected:
            border_color = DesignSystem.COLOR_DANGER
            bg_color = DesignSystem.COLOR_DANGER_BG
            width = 2
        elif will_be_kept:
            border_color = DesignSystem.COLOR_SUCCESS
            bg_color = DesignSystem.COLOR_SUCCESS_SOFT_BG
            width = 2
        else:
            border_color = DesignSystem.COLOR_BORDER
            bg_color = DesignSystem.COLOR_SURFACE
            width = 1
        
        return f"""
            QFrame {{
                background-color: {bg_color};
                border: {width}px solid {border_color};
                border-radius: {DesignSystem.RADIUS_MD}px;
            }}
            QFrame:hover {{ border-color: {DesignSystem.COLOR_PRIMARY}; }}
        """

    def _toggle_selection(self, file_path: Path, checked: bool):
        """Toggle selección de un archivo para eliminación.
        
        Usa el índice real en all_groups para almacenar la selección,
        permitiendo persistencia entre cambios de filtro.
        """
        # Obtener índice real para almacenar selección
        real_index = self._get_real_group_index(self.current_group_index)
        if real_index is None:
            return
        
        if real_index not in self.selections:
            self.selections[real_index] = []
        
        if checked and file_path not in self.selections[real_index]:
            self.selections[real_index].append(file_path)
        elif not checked and file_path in self.selections[real_index]:
            self.selections[real_index].remove(file_path)
        
        self._update_summary()
        
        # Refrescar TODAS las tarjetas del grupo para actualizar estados verde/rojo/blanco
        groups_to_show = self.filtered_groups if self.filtered_groups else self.all_groups
        group = groups_to_show[self.current_group_index]
        for file in group.files:
            is_selected = file in self.selections[real_index]
            self._update_card_visual(file, is_selected)

    def _update_card_visual(self, file_path: Path, is_selected: bool):
        """Actualiza visual de tarjeta."""
        scroll_area: Optional[QScrollArea] = None
        for i in range(self.group_layout.count()):
            item = self.group_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QScrollArea):
                scroll_area = item.widget()  # type: ignore[assignment]
                break
        
        if not scroll_area or not scroll_area.widget():
            return
        
        inner_widget = scroll_area.widget()
        if not inner_widget:
            return
        grid_layout = inner_widget.layout()
        if not grid_layout:
            return
        
        # Determinar si hay selección en el grupo actual para calcular will_be_kept
        # Usar índice real para acceder a selections
        real_index = self._get_real_group_index(self.current_group_index)
        current_selection = self.selections.get(real_index, []) if real_index is not None else []
        has_selection = len(current_selection) > 0
        will_be_kept = has_selection and not is_selected
        
        target = str(file_path)
        for i in range(grid_layout.count()):
            item = grid_layout.itemAt(i)
            card = item.widget() if item else None
            if card and card.property("file_path") == target:
                card.setStyleSheet(self._get_card_style(is_selected, will_be_kept))
                checkbox = card.findChild(QCheckBox)
                if checkbox:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(is_selected)
                    checkbox.blockSignals(False)
                break

    def _update_summary(self):
        """Actualiza resumen."""
        total_files = sum(len(l) for l in self.selections.values())
        total_bytes = sum(
            f.stat().st_size for files in self.selections.values() for f in files if f.exists()
        )
        
        self.global_summary_label.setText(tr("dialogs.duplicates_similar.summary.selected", count=total_files, size=format_size(total_bytes)))
        if self.delete_btn:
            self.delete_btn.setEnabled(total_files > 0)
            self.delete_btn.setText(tr("dialogs.duplicates_similar.button_delete_n", count=total_files))

    def _previous_group(self):
        """Navega al grupo anterior (ciclíco)."""
        groups_to_show = self.filtered_groups if self.filtered_groups else self.all_groups
        if not groups_to_show:
            return
            
        new_index = self.current_group_index - 1
        if new_index < 0:
            new_index = len(groups_to_show) - 1  # Ir al último
            
        self._load_group(new_index)

    def _next_group(self):
        """Navega al grupo siguiente (ciclíco)."""
        groups_to_show = self.filtered_groups if self.filtered_groups else self.all_groups
        if not groups_to_show:
            return
            
        new_index = self.current_group_index + 1
        if new_index >= len(groups_to_show):
            new_index = 0  # Ir al primero
            
        self._load_group(new_index)

    def _apply_strategy(self, strategy: str):
        """Aplica estrategia al grupo actual."""
        groups_to_show = self.filtered_groups if self.filtered_groups else self.all_groups
        if not groups_to_show:
            return
        
        group = groups_to_show[self.current_group_index]
        files = group.files
        if len(files) < 2:
            return
        
        if strategy == 'keep_largest':
            # Conservar el de mayor tamaño
            to_delete = self._get_files_to_delete_by_size(files, keep_largest=True)
        else:
            to_delete = []
        
        # Obtener el índice real en all_groups
        real_index = self._get_real_group_index(self.current_group_index)
        if real_index is not None:
            self.selections[real_index] = list(to_delete)
        
        self._load_group(self.current_group_index)
        self._update_summary()
    
    def _get_file_size(self, file_path: Path) -> int:
        """Obtiene el tamaño del archivo desde el repositorio o fallback."""
        if self.repo:
            meta = self.repo.get_file_metadata(file_path)
            if meta and meta.fs_size is not None:
                return meta.fs_size
        
        # Fallback: leer del filesystem directamente
        self.logger.warning(f"Size not found in cache, reading from filesystem: {file_path}")
        try:
            return file_path.stat().st_size if file_path.exists() else 0
        except Exception:
            return 0
    
    def _get_file_best_date(self, file_path: Path) -> float:
        """Obtiene la mejor fecha del archivo desde el repositorio o fallback."""
        if self.repo:
            best_date, _ = self.repo.get_best_date(file_path)
            if best_date:
                return best_date.timestamp()
        
        # Fallback: leer mtime del filesystem directamente
        self.logger.warning(f"Best_date not found in cache, using mtime: {file_path}")
        try:
            return file_path.stat().st_mtime if file_path.exists() else float('inf')
        except Exception:
            return float('inf')
    
    def _get_files_to_delete_by_size(self, files: list, keep_largest: bool = True) -> list:
        """Determina qué archivos eliminar según tamaño."""
        sizes = [(f, self._get_file_size(f)) for f in files]
        sorted_files = sorted(sizes, key=lambda x: x[1], reverse=keep_largest)
        return [f for f, _ in sorted_files[1:]]
    
    def _get_files_to_delete_by_date(self, files: list, keep_oldest: bool = True) -> list:
        """Determina qué archivos eliminar según fecha."""
        dates = [(f, self._get_file_best_date(f)) for f in files]
        sorted_files = sorted(dates, key=lambda x: x[1], reverse=not keep_oldest)
        return [f for f, _ in sorted_files[1:]]
    
    def _get_real_group_index(self, filtered_index: int) -> Optional[int]:
        """Obtiene el índice real en all_groups a partir del índice en filtered_groups.
        
        Esto es necesario porque self.selections usa índices de all_groups para
        persistir selecciones entre cambios de filtro.
        
        Args:
            filtered_index: Índice del grupo en filtered_groups
            
        Returns:
            Índice correspondiente en all_groups, o None si no se encuentra
        """
        groups_to_show = self.filtered_groups if self.filtered_groups else self.all_groups
        
        if not 0 <= filtered_index < len(groups_to_show):
            return None
        
        # Si no hay filtros, el índice es el mismo
        if not self.filtered_groups or self.filtered_groups == self.all_groups:
            return filtered_index
        
        # Buscar el grupo en all_groups
        target_group = groups_to_show[filtered_index]
        for idx, group in enumerate(self.all_groups):
            if id(group) == id(target_group):
                return idx
        
        return None
    
    def _apply_strategy_to_filtered_groups(self, strategy: str):
        """Aplica estrategia SOLO a los grupos filtrados actualmente.
        
        Los grupos que no están en filtered_groups conservan su selección previa.
        Esto permite al usuario:
        1. Filtrar por sensibilidad/tipo
        2. Aplicar selección automática solo a esos grupos
        3. Cambiar filtros y repetir para otros grupos
        
        IMPORTANTE: Si filtered_groups está vacío, NO hace nada (no usa all_groups como fallback).
        """
        # Si no hay grupos filtrados, no hacer nada
        if not self.filtered_groups:
            self.logger.info("No filtered groups, no changes applied")
            return
        
        groups_to_apply = self.filtered_groups
        
        self.logger.info(
            f"Applying strategy '{strategy}' to {len(groups_to_apply)} filtered groups "
            f"(of {len(self.all_groups)} total)"
        )
        
        # Crear un set de los grupos filtrados para búsqueda rápida
        filtered_groups_set = set(id(g) for g in groups_to_apply)
        
        for idx, group in enumerate(self.all_groups):
            # Solo procesar si este grupo está en los filtrados
            if id(group) not in filtered_groups_set:
                # Grupo no filtrado: conservar selección existente (no hacer nada)
                continue
            
            files = group.files
            if len(files) < 2:
                continue
            
            to_delete = []
            if strategy == 'keep_largest':
                to_delete = self._get_files_to_delete_by_size(files, keep_largest=True)
            
            if to_delete:
                self.selections[idx] = list(to_delete)
            else:
                # Si no hay archivos para eliminar, limpiar selección previa
                if idx in self.selections:
                    del self.selections[idx]
        
        # Recargar grupo actual y actualizar resumen
        self._load_group(self.current_group_index)
        self._update_summary()

    def _show_context_menu(self, file_path: Path):
        """Muestra menú contextual."""
        menu = QMenu(self)
        menu.setStyleSheet(DesignSystem.get_context_menu_style())
        
        action = menu.addAction(icon_manager.get_icon('information-outline'), tr("dialogs.duplicates_similar.context_view_details"))
        if action:
            action.triggered.connect(lambda: show_file_details_dialog(file_path, self))
        
        menu.exec(QCursor.pos())

    def accept(self):
        """Construye plan de eliminación: pasa grupos completos y lista de archivos a eliminar."""
        # Recopilar todos los archivos a eliminar de todas las selecciones
        files_to_delete = []
        
        for idx, selected_files in self.selections.items():
            if selected_files and idx < len(self.all_groups):
                files_to_delete.extend(selected_files)

        # Validar que hay archivos seleccionados
        if not files_to_delete:
            self.show_no_items_message(tr("dialogs.duplicates_similar.no_items_type"))
            return

        # Usar el current_result que contiene los grupos completos (>=2 archivos)
        # Esto permite que el servicio pase las validaciones de grupos
        self.accepted_plan = {
            'analysis': self.current_result,  # DuplicateAnalysisResult con grupos completos
            'files_to_delete': files_to_delete,  # Lista plana de archivos a eliminar
            'keep_strategy': 'manual',
            'create_backup': self.is_backup_enabled(),
            'dry_run': self.is_dry_run_enabled()
        }
        super().accept()

    def _get_file_date_info(self, file_path: Path) -> str:
        """Obtiene info de fecha."""
        try:
            from utils.date_utils import select_best_date_from_file, get_all_metadata_from_file
            
            file_metadata = get_all_metadata_from_file(file_path)
            selected_date, source = select_best_date_from_file(file_metadata)
            
            if not selected_date:
                return ""
            
            date_str = selected_date.strftime('%Y-%m-%d %H:%M:%S')
            if source:
                source_short = 'EXIF' if 'EXIF' in source else 'Nombre' if 'Filename' in source else 'Mod.' if 'mtime' in source else source[:10]
            else:
                source_short = '?'
            return f"{date_str}\n({source_short})"
        except Exception:
            return ""

    def _create_thumbnail(self, file_path: Path):
        """Crea thumbnail."""
        try:
            from utils.file_utils import is_video_file
            is_video = is_video_file(str(file_path))
            
            if is_video:
                pixmap = get_video_thumbnail(file_path, max_size=(280, 280), frame_position=0.25)
                if pixmap and not pixmap.isNull():
                    pixmap = self._add_play_overlay(pixmap)
                else:
                    return None, True
            else:
                pixmap = load_image_as_qpixmap(file_path, max_size=(280, 280))
                if not pixmap or pixmap.isNull():
                    return None, False
            
            lbl = QLabel()
            lbl.setPixmap(pixmap)
            lbl.setFixedSize(280, 280)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"background-color: {DesignSystem.COLOR_BACKGROUND}; border-radius: 4px;")
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            
            return lbl, is_video
        except Exception as e:
            self.logger.debug(f"Error thumbnail: {e}")
            return None, False

    def _add_play_overlay(self, pixmap: QPixmap) -> QPixmap:
        """Agrega overlay de play."""
        result = QPixmap(pixmap.size())
        result.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(0, 0, pixmap)
        painter.fillRect(result.rect(), QColor(0, 0, 0, 60))
        
        play_icon = icon_manager.get_icon('play-circle', color=DesignSystem.COLOR_SURFACE)
        icon_pixmap = play_icon.pixmap(QSize(64, 64))
        x = (pixmap.width() - 64) // 2
        y = (pixmap.height() - 64) // 2
        painter.drawPixmap(x, y, icon_pixmap)
        painter.end()
        
        return result

    def _handle_thumbnail_click(self, file_path: Path, is_video: bool):
        """Maneja click en thumbnail."""
        if is_video:
            open_file_with_default_app(file_path)
        else:
            ImagePreviewDialog(file_path, self).exec()
