# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Dropzone Widget - Área para arrastrar y soltar carpetas
"""
from pathlib import Path
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from utils.i18n import tr


class DropzoneWidget(QFrame):
    """
    Widget que acepta arrastrar y soltar carpetas
    Muestra área visual con instrucciones
    """
    
    # Señales
    folder_dropped = pyqtSignal(str)  # Emite la ruta de la carpeta
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._is_dragging = False
        self._setup_ui()
        self._apply_styles()
        
        # Configurar iconos después de que QApplication esté corriendo
        QTimer.singleShot(0, self._setup_icons)
    
    def _setup_ui(self):
        """Configura la interfaz del dropzone"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            DesignSystem.SPACE_24, 
            DesignSystem.SPACE_20, 
            DesignSystem.SPACE_24, 
            DesignSystem.SPACE_20
        )
        layout.setSpacing(DesignSystem.SPACE_12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icono de carpeta usando icon_manager (configurado después)
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setMinimumSize(DesignSystem.ICON_SIZE_XL, DesignSystem.ICON_SIZE_XL)
        self.icon_label.setContentsMargins(0, 0, 0, 0)
        self.icon_label.setStyleSheet("padding: 0px; margin: 0px; border: none; background-color: transparent;")
        layout.addWidget(self.icon_label)
        
        # Texto principal (más corto)
        self.main_text = QLabel(tr("dropzone.main_text"))
        self.main_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_text.setFixedWidth(250)  # Ancho fijo para evitar movimiento del layout al cambiar texto
        self.main_text.setStyleSheet(DesignSystem.get_dropzone_main_text_style())
        layout.addWidget(self.main_text)
        
        # Texto secundario (hint sutil, más corto)
        self.hint_text = QLabel(tr("dropzone.hint_text"))
        self.hint_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_text.setStyleSheet(DesignSystem.get_dropzone_hint_text_style())
        # Mantener referencia a un efecto de opacidad para poder ocultarlo
        # visualmente sin cambiar el tamaño del layout (opacity=0 mantiene
        # el espacio ocupado por el QLabel)
        opacity_effect = QGraphicsOpacityEffect(self.hint_text)
        opacity_effect.setOpacity(1.0)
        self.hint_text.setGraphicsEffect(opacity_effect)
        self._hint_opacity_effect = opacity_effect
        layout.addWidget(self.hint_text)
        
        # Tamaño mínimo (usando las dimensiones definidas en DesignSystem)
        self.setMinimumSize(
            DesignSystem.DROPZONE_WIDTH,
            DesignSystem.DROPZONE_HEIGHT
        )
    
    def _setup_icons(self):
        """Configura los iconos después de que QApplication esté corriendo"""
        icon_manager.set_label_icon(
            self.icon_label, 
            'folder-open', 
            color=DesignSystem.COLOR_PRIMARY, 
            size=DesignSystem.ICON_SIZE_XL
        )
        # No necesitamos update() ya que Qt repinta automáticamente
    
    def _apply_styles(self):
        """Aplica estilos al widget"""
        self._update_appearance(dragging=False)
    
    def _update_appearance(self, dragging=False):
        """Actualiza la apariencia según el estado"""
        if dragging:
            self.setStyleSheet(DesignSystem.get_dropzone_style(dragging=True))
            self.main_text.setText(tr("dropzone.drop_text"))
            # No ocultar el hint_text ya que provoca que el layout se encoja
            # (al ocultarlo quedan solo 2 QLabel). En su lugar dejamos el
            # texto original pero lo hacemos invisible mediante opacidad=0.
            # De este modo mantiene la misma anchura y evita redimensionado.
            if hasattr(self, '_hint_opacity_effect'):
                self._hint_opacity_effect.setOpacity(0.0)
            # No necesitamos update() ya que Qt repinta automáticamente con los cambios de texto
        else:
            self.setStyleSheet(DesignSystem.get_dropzone_style(dragging=False))
            self.main_text.setText(tr("dropzone.main_text"))
            # Restaurar la visibilidad del hint estableciendo opacidad a 1
            if hasattr(self, '_hint_opacity_effect'):
                self._hint_opacity_effect.setOpacity(1.0)
            # Icono ya está configurado correctamente desde _setup_icons()
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Maneja cuando se arrastra algo sobre el widget"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                path = Path(urls[0].toLocalFile())
                if path.is_dir():
                    event.acceptProposedAction()
                    self._is_dragging = True
                    self._update_appearance(dragging=True)
                    return
        event.ignore()
    
    def dragLeaveEvent(self, event):
        """Maneja cuando se sale del área de drop"""
        self._is_dragging = False
        self._update_appearance(dragging=False)
    
    def dropEvent(self, event: QDropEvent):
        """Maneja cuando se suelta algo en el widget"""
        self._is_dragging = False
        self._update_appearance(dragging=False)
        
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                path = Path(urls[0].toLocalFile())
                if path.is_dir():
                    event.acceptProposedAction()
                    self.folder_dropped.emit(str(path))
                    return
        event.ignore()
