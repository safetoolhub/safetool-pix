# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Diálogo modal para mostrar vista previa ampliada de una imagen con diseño moderno.
"""

from pathlib import Path
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QDialog, QScrollArea, QWidget
from PyQt6.QtCore import Qt
from utils.image_loader import load_image_as_qpixmap
from utils.i18n import tr
from ui.styles.design_system import DesignSystem


class ImagePreviewDialog(QDialog):
    """Diálogo modal para mostrar vista previa ampliada de una imagen con diseño moderno."""

    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialogs.image_preview.window_title", filename=image_path.name))
        self.setModal(True)
        self.resize(1000, 800)
        self.setStyleSheet(
            f"background-color: {DesignSystem.COLOR_BACKGROUND};"
            + DesignSystem.get_tooltip_style()
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar superior
        toolbar = QFrame()
        toolbar.setStyleSheet(f"background-color: {DesignSystem.COLOR_SURFACE}; border-bottom: 1px solid {DesignSystem.COLOR_BORDER};")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(DesignSystem.SPACE_16, DesignSystem.SPACE_8, DesignSystem.SPACE_16, DesignSystem.SPACE_8)

        file_info = QLabel(f"{image_path.name}")
        file_info.setStyleSheet(f"font-weight: {DesignSystem.FONT_WEIGHT_BOLD}; font-size: {DesignSystem.FONT_SIZE_MD}px; color: {DesignSystem.COLOR_TEXT};")
        toolbar_layout.addWidget(file_info)
        toolbar_layout.addStretch()

        layout.addWidget(toolbar)

        # Scroll area para la imagen
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setStyleSheet(f"background-color: {DesignSystem.COLOR_BACKGROUND}; border: none;")

        # Label con imagen
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Calcular tamaño máximo
        screen_size = self.screen().availableSize()
        max_w = int(screen_size.width() * 0.8)
        max_h = int(screen_size.height() * 0.8)

        # Cargar imagen con soporte HEIC/HEIF
        pixmap = load_image_as_qpixmap(image_path, max_size=(max_w, max_h))

        if pixmap and not pixmap.isNull():
            image_label.setPixmap(pixmap)
        else:
            image_label.setText(tr("dialogs.image_preview.error_loading"))
            image_label.setStyleSheet(f"""
                font-size: {DesignSystem.FONT_SIZE_LG}px;
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                padding: {DesignSystem.SPACE_40}px;
            """)

        scroll.setWidget(image_label)
        layout.addWidget(scroll)

        # Botón cerrar en la parte inferior
        button_container = QWidget()
        button_container.setStyleSheet(f"background-color: {DesignSystem.COLOR_SURFACE}; border-top: 1px solid {DesignSystem.COLOR_BORDER};")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(
            DesignSystem.SPACE_16, DesignSystem.SPACE_12,
            DesignSystem.SPACE_16, DesignSystem.SPACE_12
        )

        close_btn = QPushButton(tr("dialogs.image_preview.button_close"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        close_btn.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)

        layout.addWidget(button_container)