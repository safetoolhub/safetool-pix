# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Widget de Summary Card - Resumen del directorio analizado (ESTADO 3)
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

from ui.styles.design_system import DesignSystem
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from utils.i18n import tr
from utils.settings_manager import settings_manager
from pathlib import Path


class SummaryCard(QFrame):
    """
    Card compacta que muestra el resumen del análisis completado
    
    Incluye:
    - Header con icono de carpeta
    - Ruta del directorio + botón "Cambiar..."
    - Estadísticas: archivos totales, tamaño, etc.
    - Espacio optimizable + botón "Reanalizar"
    """
    
    # Señales
    change_folder_requested = pyqtSignal()  # Cuando se hace clic en "Cambiar..."
    reanalyze_requested = pyqtSignal()  # Cuando se hace clic en "Reanalizar"
    
    def __init__(self, directory_path: str, parent=None):
        super().__init__(parent)
        self.directory_path = directory_path
        self.total_files = 0
        self.total_size = 0
        self.num_images = 0
        self.num_videos = 0
        self.num_others = 0
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura la interfaz de la card"""
        self.setStyleSheet(DesignSystem.get_card_style_compact())
        
        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_6)
        
        # Header unificado: Icono + "Carpeta:" + Ruta + Botón "Cambiar"
        header_layout = QHBoxLayout()
        header_layout.setSpacing(DesignSystem.SPACE_8)
        
        # 1. Icono
        header_icon = QLabel()
        icon_manager.set_label_icon(
            header_icon,
            'folder-open',
            color=DesignSystem.COLOR_TEXT,
            size=16
        )
        header_layout.addWidget(header_icon)
        
        # 2. Etiqueta "Carpeta:"
        header_text = QLabel(tr("summary_card.label_folder"))
        header_text.setStyleSheet(DesignSystem.get_label_secondary_style())
        header_layout.addWidget(header_text)
        
        # 3. Ruta del directorio (mono)
        self.path_label = QLabel(self.directory_path)
        self.path_label.setProperty("class", "mono")
        self.path_label.setStyleSheet(DesignSystem.get_label_mono_style())
        header_layout.addWidget(self.path_label)
        
        # 4. Espaciador
        header_layout.addStretch()
        
        # 5. Botón "Cambiar"
        self.btn_change = QPushButton(tr("summary_card.button_change"))
        self.btn_change.setProperty("class", "secondary-small")
        self.btn_change.setToolTip(tr("summary_card.tooltip_change"))
        self.btn_change.clicked.connect(self._on_change_clicked)
        self.btn_change.setStyleSheet(DesignSystem.get_small_button_style("secondary"))
        header_layout.addWidget(self.btn_change)
        
        layout.addLayout(header_layout)
        
        # Actualizar visualización según configuración
        self.update_path_display()
        
        # Línea única: Estadísticas completas + Botón Reanalizar
        info_layout = QHBoxLayout()
        info_layout.setSpacing(DesignSystem.SPACE_8)
        
        # 0. Icono estadísticas
        stats_icon = QLabel()
        icon_manager.set_label_icon(
            stats_icon,
            'chart-bar',
            color=DesignSystem.COLOR_TEXT_SECONDARY,
            size=16
        )
        info_layout.addWidget(stats_icon)
        
        # 1. Estadísticas (Archivos totales y Tamaño)
        self.stats_label = QLabel(tr("summary_card.stats_calculating"))
        self.stats_label.setStyleSheet(DesignSystem.get_stats_label_style())
        info_layout.addWidget(self.stats_label)
        
        # 2. Separador vertical
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.VLine)
        separator1.setStyleSheet(f"background-color: {DesignSystem.COLOR_BORDER}; margin: 4px 0;")
        separator1.setFixedWidth(1)
        info_layout.addWidget(separator1)
        
        # 3. Desglose de tipos de archivo
        self.breakdown_label = QLabel("...")
        self.breakdown_label.setStyleSheet(DesignSystem.get_stats_label_style())
        info_layout.addWidget(self.breakdown_label)
        
        info_layout.addStretch()
        
        # Barra de desglose visual (NUEVO)
        self.bar_container = QFrame()
        self.bar_container.setFixedHeight(8) # Más delgado para look premium
        self.bar_container.setStyleSheet(DesignSystem.get_visual_bar_container_style())
        self.bar_layout = QHBoxLayout(self.bar_container)
        self.bar_layout.setContentsMargins(0, 0, 0, 0)
        self.bar_layout.setSpacing(0)
        
        layout.addWidget(self.bar_container)
        layout.addSpacing(DesignSystem.SPACE_8)
        
        # Botón "Reanalizar" (Restaurado)
        self.btn_reanalyze = QPushButton()
        icon_manager.set_button_icon(
            self.btn_reanalyze,
            'refresh',
            color=DesignSystem.COLOR_TEXT_SECONDARY,
            size=14
        )
        self.btn_reanalyze.setText(tr("summary_card.button_reanalyze"))
        self.btn_reanalyze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reanalyze.setStyleSheet(DesignSystem.get_small_button_style("link"))
        self.btn_reanalyze.clicked.connect(self._on_reanalyze_clicked)
        info_layout.addWidget(self.btn_reanalyze)
        
        layout.addLayout(info_layout)
    
    def update_stats(self, total_files: int, total_size: int = 0, num_images: int = 0, num_videos: int = 0, num_others: int = 0):
        """
        Actualiza las estadísticas mostradas
        
        Args:
            total_files: Número total de archivos
            total_size: Tamaño total en bytes
            num_images: Número de imágenes
            num_videos: Número de videos
            num_others: Número de archivos no soportados
        """
        self.total_files = total_files
        self.total_size = total_size
        self.num_images = num_images
        self.num_videos = num_videos
        self.num_others = num_others
        
        # Formatear estadísticas
        from utils.format_utils import format_file_count, format_size
        
        # Asegurar que total_size no sea None
        size_value = total_size if total_size is not None else 0
        stats_text = tr("summary_card.stats_total", count=format_file_count(total_files), size=format_size(size_value))
        
        self.stats_label.setText(stats_text)
        
        # Actualizar desglose de tipos
        breakdown_parts = []
        if num_images > 0:
            breakdown_parts.append(tr("summary_card.stats_images", count=format_file_count(num_images)))
        if num_videos > 0:
            breakdown_parts.append(tr("summary_card.stats_videos", count=format_file_count(num_videos)))
        if num_others > 0:
            breakdown_parts.append(tr("summary_card.stats_unsupported", count=format_file_count(num_others)))
        
        if breakdown_parts:
            self.breakdown_label.setText(" • ".join(breakdown_parts))
        else:
            self.breakdown_label.setText(tr("summary_card.stats_empty"))
            
        # Actualizar barra visual
        self._update_visual_bar()

    def _update_visual_bar(self):
        """Actualiza el tamaño de los segmentos en la barra visual"""
        if self.total_files == 0:
            if hasattr(self, 'img_segment'):
                self.img_segment.hide()
            if hasattr(self, 'vid_segment'):
                self.vid_segment.hide()
            if hasattr(self, 'other_segment'):
                self.other_segment.hide()
            return
            
        # Calcular porcentajes
        img_pct = (self.num_images / self.total_files) * 100
        vid_pct = (self.num_videos / self.total_files) * 100
        other_pct = (self.num_others / self.total_files) * 100
        
        # Limpiar barra
        while self.bar_layout.count():
            item = self.bar_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                
        # Añadir segmentos si tienen valor
        if self.num_images > 0:
            self.img_segment = QFrame()
            self.img_segment.setStyleSheet(f"background-color: {DesignSystem.COLOR_PRIMARY}; border-top-left-radius: 6px; border-bottom-left-radius: 6px;")
            self.bar_layout.addWidget(self.img_segment, int(img_pct))
            
        if self.num_videos > 0:
            self.vid_segment = QFrame()
            self.vid_segment.setStyleSheet(f"background-color: {DesignSystem.COLOR_WARNING};")
            # Redondear esquinas si es el único o el último
            if self.num_images == 0:
                self.vid_segment.setStyleSheet(self.vid_segment.styleSheet() + "border-top-left-radius: 6px; border-bottom-left-radius: 6px;")
            if self.num_others == 0:
                self.vid_segment.setStyleSheet(self.vid_segment.styleSheet() + "border-top-right-radius: 6px; border-bottom-right-radius: 6px;")
            self.bar_layout.addWidget(self.vid_segment, int(vid_pct))
            
        if self.num_others > 0:
            self.other_segment = QFrame()
            self.other_segment.setStyleSheet(f"background-color: {DesignSystem.COLOR_SECONDARY}; border-top-right-radius: 6px; border-bottom-right-radius: 6px;")
            if self.num_images == 0 and self.num_videos == 0:
                self.other_segment.setStyleSheet(self.other_segment.styleSheet() + "border-top-left-radius: 6px; border-bottom-left-radius: 6px;")
            self.bar_layout.addWidget(self.other_segment, int(other_pct))
    

    
    def _on_change_clicked(self):
        """Maneja el clic en "Cambiar..." """
        self.change_folder_requested.emit()
    
    def _on_reanalyze_clicked(self):
        """Maneja el clic en "Reanalizar" """
        self.reanalyze_requested.emit()

    def update_path_display(self):
        """Actualiza la visualización de la ruta según la configuración"""
        show_full = settings_manager.get_show_full_path()
        
        if show_full:
            self.path_label.setText(self.directory_path)
        else:
            # Mostrar solo el nombre de la carpeta
            folder_name = Path(self.directory_path).name
            self.path_label.setText(folder_name)
