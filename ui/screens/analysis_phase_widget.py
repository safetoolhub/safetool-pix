# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Widget que muestra el progreso de cada fase del análisis (STAGE 2)
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget

from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from services.initial_scanner import InitialScanner
from utils.i18n import tr


class AnalysisPhaseWidget(QFrame):
    """
    Widget que muestra las diferentes fases del análisis
    con indicadores de estado numerados y diseño moderno.
    
    Estados visuales:
    - Pendiente: Número gris, texto secundario
    - En proceso: Número azul con fondo, texto destacado
    - Completado: Check verde, texto verde
    - Error: X roja, texto rojo
    - Omitido: Número gris tachado
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase_items = {}  # phase_id -> dict con widgets
        self.phase_original_texts = {}  # Textos originales
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura la interfaz del widget"""
        self.setStyleSheet(DesignSystem.get_analysis_phase_frame_style())
        
        layout = QVBoxLayout(self)
        layout.setSpacing(DesignSystem.SPACE_4)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Definir las fases con sus IDs y textos
        phases = [
            (InitialScanner.PHASE_FILE_CLASSIFICATION, tr("analysis_phase.phase1"), 1),
            (InitialScanner.PHASE_FILESYSTEM_METADATA, tr("analysis_phase.phase2"), 2),
            (InitialScanner.PHASE_HASH, tr("analysis_phase.phase3"), 3),
            (InitialScanner.PHASE_EXIF_IMAGES, tr("analysis_phase.phase4"), 4),
            (InitialScanner.PHASE_EXIF_VIDEOS, tr("analysis_phase.phase5"), 5),
            (InitialScanner.PHASE_BEST_DATE, tr("analysis_phase.phase6"), 6),
        ]
        
        for phase_id, phase_text, phase_num in phases:
            phase_widget = self._create_phase_item(phase_id, phase_text, phase_num)
            layout.addWidget(phase_widget)
            self.phase_original_texts[phase_id] = phase_text
    
    def _create_phase_item(self, phase_id: str, text: str, number: int) -> QFrame:
        """
        Crea un item de fase con número circular + texto + contador.
        
        Args:
            phase_id: ID de la fase
            text: Texto descriptivo
            number: Número de la fase
        
        Returns:
            QFrame con el item de fase
        """
        container = QFrame()
        container.setStyleSheet(DesignSystem.get_phase_item_style('pending'))
        
        item_layout = QHBoxLayout(container)
        item_layout.setSpacing(DesignSystem.SPACE_12)
        item_layout.setContentsMargins(0, 0, 0, 0)
        
        # Indicador numérico circular
        number_label = QLabel(str(number))
        number_label.setStyleSheet(DesignSystem.get_phase_number_style('pending'))
        number_label.setFixedSize(24, 24)
        item_layout.addWidget(number_label)
        
        # Texto de la fase
        text_label = QLabel(text)
        text_label.setStyleSheet(DesignSystem.get_phase_title_style('pending'))
        item_layout.addWidget(text_label)
        
        item_layout.addStretch()
        
        # Contador de progreso (oculto por defecto)
        counter_label = QLabel("")
        counter_label.setStyleSheet(DesignSystem.get_phase_progress_text_style())
        counter_label.hide()
        item_layout.addWidget(counter_label)
        
        # Icono de estado (para completado/error)
        status_icon = QLabel()
        status_icon.hide()
        item_layout.addWidget(status_icon)
        
        # Guardar referencias
        self.phase_items[phase_id] = {
            'container': container,
            'number': number_label,
            'number_value': number,
            'text': text_label,
            'counter': counter_label,
            'status_icon': status_icon,
        }
        
        return container
    
    def set_phase_status(self, phase_id: str, status: str):
        """
        Actualiza el estado visual de una fase.
        
        Args:
            phase_id: ID de la fase
            status: 'pending', 'running', 'completed', 'alert-circle', 'skipped'
        """
        if phase_id not in self.phase_items:
            return
        
        items = self.phase_items[phase_id]
        container = items['container']
        number_label = items['number']
        text_label = items['text']
        counter_label = items['counter']
        status_icon = items['status_icon']
        number_value = items['number_value']
        original_text = self.phase_original_texts.get(phase_id, "")
        
        if status == 'completed':
            # Actualizar contenedor
            container.setStyleSheet(DesignSystem.get_phase_item_style('completed'))
            
            # Mostrar check en lugar de número
            icon_manager.set_label_icon(
                number_label,
                'check',
                color='white',
                size=14
            )
            number_label.setStyleSheet(DesignSystem.get_phase_number_style('completed'))
            
            # Texto verde con "OK"
            text_label.setText(f"{original_text}")
            text_label.setStyleSheet(DesignSystem.get_phase_title_style('completed'))
            
            # Ocultar contador, mostrar icono de estado
            counter_label.hide()
            icon_manager.set_label_icon(
                status_icon,
                'check-circle',
                color=DesignSystem.COLOR_SUCCESS,
                size=16
            )
            status_icon.show()
        
        elif status == 'running':
            # Actualizar contenedor con fondo destacado
            container.setStyleSheet(DesignSystem.get_phase_item_style('running'))
            
            # Número destacado
            number_label.setText(str(number_value))
            number_label.setStyleSheet(DesignSystem.get_phase_number_style('running'))
            
            # Texto principal
            text_label.setText(original_text)
            text_label.setStyleSheet(DesignSystem.get_phase_title_style('running'))
            
            # Mostrar contador
            counter_label.show()
            status_icon.hide()
        
        elif status == 'alert-circle':
            # Estado de error
            container.setStyleSheet(DesignSystem.get_phase_item_style('error'))
            
            # X en número
            icon_manager.set_label_icon(
                number_label,
                'close',
                color='white',
                size=14
            )
            number_label.setStyleSheet(DesignSystem.get_phase_number_style('error'))
            
            # Texto rojo
            text_label.setStyleSheet(DesignSystem.get_phase_title_style('error'))
            
            # Ocultar contador
            counter_label.hide()
            status_icon.hide()
        
        elif status == 'skipped':
            # Fase omitida (por falta de herramientas o configuración)
            container.setStyleSheet(DesignSystem.get_phase_item_style('skipped'))
            
            number_label.setText(str(number_value))
            number_label.setStyleSheet(DesignSystem.get_phase_number_style('skipped'))
            
            text_label.setStyleSheet(DesignSystem.get_phase_title_style('skipped'))
            
            # Mostrar texto indicando que se saltó
            counter_label.setText(tr("analysis_phase.skipped"))
            counter_label.setStyleSheet(f"""
                font-size: {DesignSystem.FONT_SIZE_XS}px;
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                font-style: italic;
            """)
            counter_label.show()
            status_icon.hide()
        
        else:  # pending
            container.setStyleSheet(DesignSystem.get_phase_item_style('pending'))
            
            number_label.setText(str(number_value))
            number_label.setStyleSheet(DesignSystem.get_phase_number_style('pending'))
            
            text_label.setText(original_text)
            text_label.setStyleSheet(DesignSystem.get_phase_title_style('pending'))
            
            counter_label.hide()
            status_icon.hide()
    
    def reset_all_phases(self):
        """Resetea todas las fases a estado pendiente"""
        for phase_id in self.phase_items.keys():
            self.set_phase_status(phase_id, 'pending')
    
    def update_phase_progress(self, phase_id: str, current: int, total: int):
        """
        Actualiza el contador de progreso de una fase.
        
        Args:
            phase_id: ID de la fase
            current: Número de archivos procesados
            total: Total de archivos
        """
        if phase_id not in self.phase_items:
            return
        
        counter_label = self.phase_items[phase_id]['counter']
        counter_label.setText(f"{current:,} / {total:,}")
        counter_label.setStyleSheet(DesignSystem.get_phase_progress_text_style())
    
    def update_phase_text(self, phase_id: str, text: str):
        """
        Actualiza el texto descriptivo de una fase (temporalmente).
        
        Args:
            phase_id: ID de la fase
            text: Nuevo texto a mostrar
        """
        if phase_id not in self.phase_items:
            return
        
        text_label = self.phase_items[phase_id]['text']
        text_label.setText(text)
