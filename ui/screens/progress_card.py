# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Widget de card de progreso para el análisis (ESTADO 2)
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget
from PyQt6.QtCore import pyqtSignal

from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from utils.settings_manager import settings_manager
from pathlib import Path
from ui.screens.analysis_phase_widget import AnalysisPhaseWidget
from utils.i18n import tr


class ProgressCard(QFrame):
    """
    Card que muestra el progreso del análisis de directorio.
    
    Diseño moderno con:
    - Header con badge de carpeta
    - Indicador de estado visual con fondo coloreado
    - Barra de progreso elegante
    - Widget de fases detallado
    """
    
    # Señales
    cancel_requested = pyqtSignal()  # Cuando el usuario cancela el análisis
    
    def __init__(self, directory_path: str, parent=None):
        super().__init__(parent)
        self.directory_path = directory_path
        self.phase_widget = None
        self.current_status = 'running'  # running, completed, error
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura la interfaz de la card"""
        self.setStyleSheet(DesignSystem.get_progress_card_style())
        
        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_16)
        layout.setContentsMargins(
            DesignSystem.SPACE_20, 
            DesignSystem.SPACE_20, 
            DesignSystem.SPACE_20, 
            DesignSystem.SPACE_20
        )
        
        # ===== HEADER: Título + Botón Cancelar =====
        header_layout = QHBoxLayout()
        header_layout.setSpacing(DesignSystem.SPACE_12)
        
        # Icono de análisis
        header_icon = QLabel()
        icon_manager.set_label_icon(
            header_icon, 
            'magnify', 
            color=DesignSystem.COLOR_PRIMARY, 
            size=24
        )
        header_layout.addWidget(header_icon)
        
        # Título
        header_title = QLabel(tr("progress_card.header_title"))
        header_title.setStyleSheet(DesignSystem.get_progress_header_style())
        header_layout.addWidget(header_title)
        
        header_layout.addStretch()
        
        # Botón cancelar (discreto)
        self.cancel_btn = QPushButton(tr("common.cancel"))
        icon_manager.set_button_icon(self.cancel_btn, 'close', size=14)
        self.cancel_btn.setStyleSheet(DesignSystem.get_cancel_button_discrete_style())
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        header_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(header_layout)
        
        # ===== BADGE DE CARPETA =====
        folder_badge = QFrame()
        folder_badge.setStyleSheet(DesignSystem.get_folder_path_badge_style())
        badge_layout = QHBoxLayout(folder_badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(DesignSystem.SPACE_8)
        
        folder_icon = QLabel()
        icon_manager.set_label_icon(
            folder_icon, 
            'folder-open', 
            color=DesignSystem.COLOR_TEXT_SECONDARY, 
            size=16
        )
        badge_layout.addWidget(folder_icon)
        
        self.path_label = QLabel(self.directory_path)
        self.path_label.setProperty("class", "mono")
        self.path_label.setToolTip(self.directory_path)
        self.path_label.setStyleSheet(f"""
            font-family: {DesignSystem.FONT_FAMILY_MONO};
            font-size: {DesignSystem.FONT_SIZE_SM}px;
            color: {DesignSystem.COLOR_TEXT};
        """)
        badge_layout.addWidget(self.path_label)
        badge_layout.addStretch()
        
        layout.addWidget(folder_badge)
        self.update_path_display()
        
        # ===== INDICADOR DE ESTADO =====
        self.status_container = QFrame()
        self.status_container.setStyleSheet(DesignSystem.get_progress_status_style('running'))
        status_inner_layout = QHBoxLayout(self.status_container)
        status_inner_layout.setContentsMargins(0, 0, 0, 0)
        status_inner_layout.setSpacing(DesignSystem.SPACE_10)
        
        self.status_icon = QLabel()
        icon_manager.set_label_icon(
            self.status_icon, 
            'progress-clock', 
            color=DesignSystem.COLOR_PRIMARY, 
            size=20
        )
        status_inner_layout.addWidget(self.status_icon)
        
        self.status_label = QLabel(tr("progress_card.status_analyzing"))
        self.status_label.setStyleSheet(DesignSystem.get_progress_status_text_style('running'))
        status_inner_layout.addWidget(self.status_label)
        status_inner_layout.addStretch()
        
        layout.addWidget(self.status_container)
        
        # ===== BARRA DE PROGRESO =====
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Modo indeterminado
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(DesignSystem.get_modern_progressbar_style())
        layout.addWidget(self.progress_bar)
        
        # ===== SEPARADOR =====
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {DesignSystem.COLOR_BORDER_LIGHT};")
        separator.setFixedHeight(1)
        layout.addWidget(separator)
        
        # ===== WIDGET DE FASES =====
        self.phase_widget = AnalysisPhaseWidget()
        layout.addWidget(self.phase_widget)
    
    def _update_status_style(self, status: str):
        """Actualiza los estilos del indicador de estado"""
        self.current_status = status
        self.status_container.setStyleSheet(DesignSystem.get_progress_status_style(status))
        self.status_label.setStyleSheet(DesignSystem.get_progress_status_text_style(status))
    
    def mark_completed(self):
        """Marca el análisis como completado"""
        # Ocultar botón de cancelar
        self.cancel_btn.hide()
        
        # Actualizar estilo a completado
        self._update_status_style('completed')
        
        # Cambiar icono
        icon_manager.set_label_icon(
            self.status_icon,
            'check-circle',
            color=DesignSystem.COLOR_SUCCESS,
            size=20
        )
        
        # Cambiar texto
        self.status_label.setText(tr("progress_card.status_completed"))
        
        # Completar barra de progreso
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(100)
    
    def stop_progress(self):
        """Detiene la barra de progreso (por error o cancelación)"""
        self._update_status_style('error')
        
        # Detener animación
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        
        # Mostrar botón de cancelar
        self.cancel_btn.show()
    
    def get_phase_widget(self):
        """Retorna el widget de fases para acceso externo"""
        return self.phase_widget
    
    def set_phase_status(self, phase_id: str, status: str):
        """Delegar llamada al widget de fases"""
        if self.phase_widget:
            self.phase_widget.set_phase_status(phase_id, status)
    
    def update_phase_progress(self, phase_id: str, current: int, total: int):
        """Delegar actualización de progreso al widget de fases"""
        if self.phase_widget:
            self.phase_widget.update_phase_progress(phase_id, current, total)
    
    def update_phase_text(self, phase_id: str, text: str):
        """Delegar actualización de texto al widget de fases"""
        if self.phase_widget:
            self.phase_widget.update_phase_text(phase_id, text)
    
    def reset_phases(self):
        """Delegar llamada al widget de fases"""
        if self.phase_widget:
            self.phase_widget.reset_all_phases()
    
    def reset(self):
        """Resetea el estado del análisis para reinicio"""
        # Resetear barra de progreso a modo indeterminado
        self.progress_bar.setMaximum(0)
        self.progress_bar.setValue(0)
        
        # Resetear estilo y estado
        self._update_status_style('running')
        
        # Resetear icono
        icon_manager.set_label_icon(
            self.status_icon,
            'progress-clock',
            color=DesignSystem.COLOR_PRIMARY,
            size=20
        )
        
        # Resetear texto
        self.status_label.setText(tr("progress_card.status_analyzing"))
        
        # Mostrar botón cancelar
        self.cancel_btn.show()
        
        # Resetear fases
        self.reset_phases()

    def update_path_display(self):
        """Actualiza la visualización de la ruta según la configuración"""
        show_full = settings_manager.get_show_full_path()
        
        if show_full:
            self.path_label.setText(self.directory_path)
        else:
            # Mostrar solo el nombre de la carpeta
            folder_name = Path(self.directory_path).name
            self.path_label.setText(folder_name)
