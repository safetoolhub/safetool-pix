# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Clases/base utilities para diálogos."""
from typing import Dict, List, Optional, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QWidget,
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QFrame, QRadioButton

from ui.styles.design_system import DesignSystem
from utils.i18n import tr
from utils.settings_manager import settings_manager


class BaseDialog(QDialog):
    """Clase base para diálogos con utilidades comunes.
    
    Signals:
        actions_completed(str): Emitida cuando el diálogo ejecuta acciones que modifican archivos.
                                Argumento: tool_name identificador de la herramienta.
    """
    
    actions_completed = pyqtSignal(str)  # tool_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.backup_checkbox = None
        self._ok_button_ref = None
        
        # Aplicar estilo global a todos los diálogos
        self.setStyleSheet(DesignSystem.get_stylesheet() + DesignSystem.get_tooltip_style())



    def is_backup_enabled(self) -> bool:
        """Devuelve True si el checkbox de backup existe y está marcado."""
        if not self.backup_checkbox:
            return False
        
        # Si es el diseño compacto con contenedor, usar _checkbox interno
        if hasattr(self.backup_checkbox, '_checkbox'):
            return self.backup_checkbox._checkbox.isChecked()
        
        # Si es QCheckBox directo
        return self.backup_checkbox.isChecked()
    
    def is_dry_run_enabled(self) -> bool:
        """Devuelve True si el checkbox de dry-run existe y está marcado."""
        if not self.dry_run_checkbox:
            return False
        
        # Si es el diseño compacto con contenedor, usar _checkbox interno
        if hasattr(self.dry_run_checkbox, '_checkbox'):
            return self.dry_run_checkbox._checkbox.isChecked()
        
        # Si es QCheckBox directo
        return self.dry_run_checkbox.isChecked()
    
    def is_cleanup_enabled(self) -> bool:
        """Devuelve True si el checkbox de cleanup existe y está marcado."""
        if not hasattr(self, 'cleanup_checkbox') or not self.cleanup_checkbox:
            return False
        
        # Si es el diseño compacto con contenedor, usar _checkbox interno
        if hasattr(self.cleanup_checkbox, '_checkbox'):
            return self.cleanup_checkbox._checkbox.isChecked()
        
        # Si es QCheckBox directo
        return self.cleanup_checkbox.isChecked()

    def confirm_destructive_operation(
        self,
        files_count: int,
        total_size: int = 0,
        operation_verb: str = "deleted",
        extra_info: str = ""
    ) -> bool:
        """
        Muestra confirmación antes de operaciones destructivas.
        
        Método común para todos los diálogos que realizan operaciones
        de eliminación, movimiento o renombrado de archivos.
        
        Args:
            files_count: Número de archivos afectados
            total_size: Tamaño total en bytes (opcional)
            operation_verb: Verbo de la operación (eliminarán, moverán, renombrarán)
            extra_info: Información adicional para mostrar (ej: estrategia)
            
        Returns:
            True si el usuario confirma, False en caso contrario
        """
        from utils.format_utils import format_size
        
        # Construir mensaje
        if total_size > 0:
            size_info = f" ({format_size(total_size)})"
        else:
            size_info = ""
        
        message = tr("common.confirm_operation_message", operation_verb=operation_verb, files_count=files_count, size_info=size_info)
        
        if extra_info:
            message += f"\n\n{extra_info}"
        
        message += "\n\n" + tr("common.confirm_continue")
        
        reply = QMessageBox.question(
            self,
            tr("common.confirm_operation_title"),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No  # Default seguro
        )
        return reply == QMessageBox.StandardButton.Yes
    
    def show_no_items_message(self, item_type: str = "files") -> None:
        """
        Muestra mensaje informativo cuando no hay items para procesar.
        
        Args:
            item_type: Tipo de items (archivos, grupos, pares, etc.)
        """
        QMessageBox.information(
            self,
            tr("common.no_items_title"),
            tr("common.no_items_message", item_type=item_type)
        )



    def make_ok_cancel_buttons(
        self, 
        ok_text: Optional[str] = None, 
        ok_enabled: bool = True,
        button_style: str = 'primary'
    ) -> QDialogButtonBox:
        """Crea y devuelve un QDialogButtonBox con Ok/Cancel enlazados a accept/reject.
        
        Aplica automáticamente estilos Material Design consistentes.

        Args:
            ok_text: Texto personalizado para el botón OK (default: "OK")
            ok_enabled: Si el botón OK debe estar habilitado inicialmente
            button_style: Estilo del botón OK: 'primary', 'danger', o 'secondary'

        Returns:
            QDialogButtonBox configurado con estilos Material Design
        """
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = box.button(QDialogButtonBox.StandardButton.Cancel)
        
        # Aplicar textos personalizados
        if ok_text is not None:
            ok_btn.setText(ok_text)
        cancel_btn.setText(tr("common.cancel"))
        
        # Eliminar iconos automáticos de Qt que no respetan los colores personalizados
        from PyQt6.QtGui import QIcon
        ok_btn.setIcon(QIcon())  # Icono vacío
        cancel_btn.setIcon(QIcon())  # Icono vacío
        
        # Aplicar estilos Material Design según el tipo especificado
        if button_style == 'danger':
            ok_btn.setStyleSheet(DesignSystem.get_danger_button_style())
        elif button_style == 'secondary':
            ok_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        else:  # 'primary' por defecto
            ok_btn.setStyleSheet(DesignSystem.get_primary_button_style())
        
        cancel_btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        
        ok_btn.setEnabled(ok_enabled)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        
        # remember ok button for convenience
        self.register_ok_button(ok_btn)
        return box

    def make_styled_button(
        self,
        text: str = "",
        icon_name: str = "",
        button_style: str = 'secondary',
        tooltip: str = "",
        enabled: bool = True,
        custom_style: str = ""
    ) -> QPushButton:
        """Crea un botón estilizado con Material Design.
        
        Args:
            text: Texto del botón
            icon_name: Nombre del icono (opcional)
            button_style: Estilo: 'primary', 'secondary', 'danger'
            tooltip: Tooltip del botón
            enabled: Si está habilitado inicialmente
            custom_style: CSS personalizado (opcional, reemplaza el estilo estándar)
        
        Returns:
            QPushButton configurado
        """
        btn = QPushButton(text)
        if icon_name:
            from ui.styles.icons import icon_manager
            btn.setIcon(icon_manager.get_icon(icon_name))
        if tooltip:
            btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setEnabled(enabled)
        
        # Aplicar estilo
        if custom_style:
            btn.setStyleSheet(custom_style)
        else:
            if button_style == 'danger':
                btn.setStyleSheet(DesignSystem.get_danger_button_style())
            elif button_style == 'primary':
                btn.setStyleSheet(DesignSystem.get_primary_button_style())
            else:  # 'secondary' por defecto
                btn.setStyleSheet(DesignSystem.get_secondary_button_style())
        
        return btn

    def register_ok_button(self, button: Optional[QPushButton]):
        """Register the dialog's primary OK button so helpers can enable/disable it.

        Pass None to clear the registration.
        """
        self._ok_button_ref = button

    def set_ok_enabled(self, enabled: bool):
        """Enable/disable previously registered OK button (no-op if none)."""
        if self._ok_button_ref is not None:
            self._ok_button_ref.setEnabled(enabled)

    def make_table(self, headers: List[str], max_height: Optional[int] = None) -> QTableWidget:
        """Create a QTableWidget with given headers and optional maximum height.

        Caller is responsible for populating rows and adding it to a layout.
        """
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        if max_height is not None:
            table.setMaximumHeight(max_height)
        return table

    def _create_compact_header_with_metrics(
        self,
        icon_name: str,
        title: str,
        description: str,
        metrics: List[Dict[str, str]],
        tip_message: Optional[str] = None
    ) -> 'QFrame':
        """Crea header compacto integrado con métricas inline estilo Material Design.
        
        Combina icono, título, descripción y métricas en un diseño horizontal compacto
        que ahorra espacio vertical. Las métricas aparecen alineadas a la derecha.
        Opcionalmente incluye un botón de tip junto al título.

        Args:
            icon_name: Nombre del icono de icon_manager (ej: 'content-copy')
            title: Título principal (negrita)
            description: Texto descriptivo (1-2 líneas)
            metrics: Lista de diccionarios con formato:
                [
                    {'value': '45', 'label': 'Grupos', 'color': COLOR_PRIMARY},
                    {'value': '120', 'label': 'Copias', 'color': COLOR_WARNING},
                    {'value': '2.5 GB', 'label': 'Espacio', 'color': COLOR_SUCCESS}
                ]
            tip_message: Mensaje HTML opcional para mostrar en un botón de ayuda
                         junto al título. Puede usar etiquetas <b>, <i>, etc.
        
        Returns:
            QFrame con header compacto y profesional
        """
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border-bottom: 1px solid {DesignSystem.COLOR_BORDER};
                padding: 0px;
            }}
        """)
        
        # Layout principal horizontal
        main_layout = QHBoxLayout(frame)
        main_layout.setSpacing(int(DesignSystem.SPACE_16))
        main_layout.setContentsMargins(
            int(DesignSystem.SPACE_20),
            int(DesignSystem.SPACE_12),
            int(DesignSystem.SPACE_20),
            int(DesignSystem.SPACE_12)
        )
        
        # === LADO IZQUIERDO: Icono + Texto ===
        left_container = QHBoxLayout()
        left_container.setSpacing(int(DesignSystem.SPACE_12))
        
        # Icono con fondo circular
        icon_container = QFrame()
        icon_container.setFixedSize(48, 48)
        icon_container.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                border-radius: 24px;
                border: none;
            }}
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel()
        icon_label.setStyleSheet("border: none; background: transparent;")
        icon_manager.set_label_icon(
            icon_label, 
            icon_name, 
            size=DesignSystem.ICON_SIZE_LG,
            color=DesignSystem.COLOR_PRIMARY
        )
        icon_layout.addWidget(icon_label)
        left_container.addWidget(icon_container)
        
        # Contenedor de texto (título + descripción apilados)
        text_container = QVBoxLayout()
        text_container.setSpacing(int(DesignSystem.SPACE_2))
        
        # Título con tip opcional (horizontal)
        title_row = QHBoxLayout()
        title_row.setSpacing(int(DesignSystem.SPACE_8))
        title_row.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_XL}px;
            font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            color: {DesignSystem.COLOR_TEXT};
            border: none;
            background: transparent;
        """)
        title_row.addWidget(title_label)
        
        # Botón de tip junto al título (si se proporciona mensaje)
        if tip_message:
            self._header_tip_btn = self.create_tip_button(tip_message, width=450)
            title_row.addWidget(self._header_tip_btn)
        
        title_row.addStretch()  # Empujar tip al lado del título
        text_container.addLayout(title_row)
        
        # Descripción
        desc_label = QLabel(description)
        desc_label.setWordWrap(False)  # Mantenerlo en una línea
        desc_label.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_SM}px;
            color: {DesignSystem.COLOR_TEXT_SECONDARY};
            border: none;
            background: transparent;
        """)
        text_container.addWidget(desc_label)
        
        left_container.addLayout(text_container)
        main_layout.addLayout(left_container, 0)  # Sin stretch para mantener pegado a la izquierda
        
        # Stretch para empujar métricas a la derecha
        main_layout.addStretch()
        
        # === LADO DERECHO: Métricas inline ===
        metrics_container = QHBoxLayout()
        metrics_container.setSpacing(int(DesignSystem.SPACE_20))
        
        for metric in metrics:
            metric_widget = self._create_inline_metric(
                value=metric['value'],
                label=metric['label'],
                color=metric.get('color', DesignSystem.COLOR_PRIMARY)
            )
            metrics_container.addWidget(metric_widget)
        
        main_layout.addLayout(metrics_container)
        
        return frame
    
    def _create_inline_metric(
        self,
        value: str,
        label: str,
        color: str
    ) -> 'QWidget':
        """Crea métrica inline minimalista para header compacto.
        
        Args:
            value: Valor numérico o texto a mostrar
            label: Etiqueta descriptiva
            color: Color del indicador y valor
        
        Returns:
            QWidget con la métrica formateada
        """
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        from ui.styles.design_system import DesignSystem
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(DesignSystem.SPACE_2))
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Valor (grande y destacado)
        value_label = QLabel(str(value))
        value_label.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_2XL}px;
            font-weight: {DesignSystem.FONT_WEIGHT_BOLD};
            color: {color};
            border: none;
            background: transparent;
        """)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        
        # Label (pequeño y sutil)
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_XS}px;
            color: {DesignSystem.COLOR_TEXT_SECONDARY};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border: none;
            background: transparent;
        """)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_widget)
        
        return widget
    
    def _update_header_metric(self, header_frame: 'QFrame', metric_label: str, new_value: str) -> None:
        """Actualiza dinámicamente el valor de una métrica específica en el header.
        
        Busca la métrica por su etiqueta (label) y actualiza el valor asociado.
        Útil para actualizar métricas cuando el usuario cambia opciones en el diálogo.
        
        Args:
            header_frame: El QFrame retornado por _create_compact_header_with_metrics
            metric_label: El label de la métrica a actualizar (ej: 'Recuperable', 'Grupos')
            new_value: El nuevo valor a mostrar (ej: '2.5 GB', '45')
        
        Example:
            self._update_header_metric(self.header_frame, 'Recuperable', format_size(new_space))
        """
        from PyQt6.QtWidgets import QLabel, QWidget
        
        # Recorrer todos los QWidget del frame para encontrar los contenedores de métricas
        for widget in header_frame.findChildren(QWidget):
            if not widget.layout():
                continue
            
            # Buscar el widget que contiene la métrica (tiene 2 labels: valor y label)
            all_labels = widget.findChildren(QLabel)
            # Filtrar solo hijos directos del widget
            direct_labels = [l for l in all_labels if l.parent() == widget]
            
            if len(direct_labels) == 2:
                # Estructura esperada: [value_label, label_widget]
                value_label, label_widget = direct_labels[0], direct_labels[1]
                
                # Verificar si este es el label que buscamos
                if label_widget.text().lower() == metric_label.lower():
                    value_label.setText(new_value)
                    return

    def _create_selection_card(
        self,
        card_id: str,
        icon_name: str,
        title: str,
        description: str,
        is_selected: bool,
        radio_button: Optional['QRadioButton'] = None
    ) -> 'QFrame':
        """Crea tarjeta de selección clickeable con RadioButton (patrón organization_dialog).

        Args:
            card_id: ID único de la card (ej: 'strategy-oldest')
            icon_name: Nombre del icono de icon_manager
            title: Título de la opción
            description: Descripción de la opción
            is_selected: Si la card está seleccionada
            radio_button: RadioButton a asociar (opcional, se crea si es None)
        
        Returns:
            QFrame con la card de selección
        """
        from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        card = QFrame()
        card.setObjectName(card_id)
        card.setStyleSheet(f"""
            QFrame#{card_id} {{
                background-color: {DesignSystem.COLOR_PRIMARY if is_selected else DesignSystem.COLOR_SURFACE};
                border: 2px solid {DesignSystem.COLOR_PRIMARY if is_selected else DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
            QFrame#{card_id}:hover {{
                border-color: {DesignSystem.COLOR_PRIMARY};
                background-color: {DesignSystem.COLOR_PRIMARY if is_selected else DesignSystem.COLOR_BG_2};
            }}
            QFrame#{card_id} QLabel {{
                color: {DesignSystem.COLOR_PRIMARY_TEXT if is_selected else DesignSystem.COLOR_TEXT};
            }}
            QFrame#{card_id} QLabel#title-label {{
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            }}
            QFrame#{card_id} QLabel#desc-label {{
                color: {DesignSystem.COLOR_PRIMARY_TEXT if is_selected else DesignSystem.COLOR_TEXT_SECONDARY};
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(int(DesignSystem.SPACE_8))
        
        # Header: RadioButton + Icono + Título
        header_layout = QHBoxLayout()
        
        if radio_button is None:
            radio_button = QRadioButton()
            radio_button.setChecked(is_selected)
        
        header_layout.addWidget(radio_button)
        
        icon_label = QLabel()
        icon_manager.set_label_icon(
            icon_label, 
            icon_name, 
            size=DesignSystem.ICON_SIZE_XL,
            color=DesignSystem.COLOR_PRIMARY_TEXT if is_selected else DesignSystem.COLOR_PRIMARY
        )
        icon_label.icon_name = icon_name  # Guardar nombre del icono para actualización posterior
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setObjectName("title-label")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Descripción
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setObjectName("desc-label")
        layout.addWidget(desc_label)
        
        # Hacer la card clickeable
        card.mousePressEvent = lambda event: radio_button.setChecked(True)
        
        # Guardar referencia al radio en la card
        card.setProperty("radio_button", radio_button)
        
        return card
    
    def _create_option_selector(
        self,
        title: str,
        title_icon: Optional[str],
        options: list[tuple],
        selected_value: any,
        on_change_callback: callable
    ) -> 'QFrame':
        """Crea selector de opciones con cards interactivas CENTRALIZADO.
        
        Patrón unificado para todos los dialogs que necesiten radio buttons
        de selección (estrategias, modos, formatos, tipos).
        
        Args:
            title: Título del selector (ej: "Elige qué archivo conservar")
            title_icon: Nombre del icono para el título (ej: 'ruler'). Opcional, si es None no se muestra icono
            options: Lista de tuplas con formato:
                (value, icon_name, title, description)
                donde value es el identificador único de la opción
            selected_value: Valor actualmente seleccionado
            on_change_callback: Función a llamar cuando cambia la selección.
                Recibe el nuevo valor como argumento.
        
        Returns:
            QFrame con el selector completo
        
        Example:
            selector = self._create_option_selector(
                title="Elige qué archivo conservar",
                title_icon='ruler',  # o None para no mostrar icono
                options=[
                    ('oldest', 'clock-outline', 'Más antiguo', 'Conserva el original'),
                    ('newest', 'update', 'Más reciente', 'Conserva la versión editada')
                ],
                selected_value=self.keep_strategy,
                on_change_callback=self._on_strategy_changed
            )
        """
        from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        frame = QFrame()
        frame.setObjectName("option-selector-frame")
        frame.setStyleSheet(f"""
            QFrame#option-selector-frame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_CARD_BORDER};
                border-radius: {DesignSystem.RADIUS_LG}px;
                padding: {DesignSystem.SPACE_16}px;
            }}
        """)
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(int(DesignSystem.SPACE_12))
        
        # Título del selector
        title_layout = QHBoxLayout()
        
        # Solo agregar icono si se proporciona
        if title_icon:
            title_icon_label = QLabel()
            icon_manager.set_label_icon(
                title_icon_label, 
                title_icon, 
                size=int(DesignSystem.ICON_SIZE_LG)
            )
            title_layout.addWidget(title_icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_LG}px;
            font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            color: {DesignSystem.COLOR_TEXT};
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # ButtonGroup para RadioButtons
        button_group = QButtonGroup(frame)
        
        # Cards layout (horizontal)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(int(DesignSystem.SPACE_12))
        
        # Crear una card por cada opción
        for idx, (value, icon_name, opt_title, description) in enumerate(options):
            is_selected = (value == selected_value)
            
            # Usar índice para ID consistente y evitar problemas con caracteres especiales
            card_id = f"option-{idx}"
            
            # Crear RadioButton
            radio = QRadioButton()
            radio.setChecked(is_selected)
            radio.toggled.connect(
                lambda checked, v=value: on_change_callback(v) if checked else None
            )
            button_group.addButton(radio)
            
            # Crear card usando el método de BaseDialog
            card = self._create_selection_card(
                card_id,
                icon_name,
                opt_title,
                description,
                is_selected,
                radio
            )
            # Guardar el valor original en la card para referencia posterior
            card.setProperty("option_value", value)
            cards_layout.addWidget(card)
        
        layout.addLayout(cards_layout)
        
        # Guardar referencia al ButtonGroup para acceso posterior si es necesario
        frame.setProperty("button_group", button_group)
        
        return frame
    
    def _update_option_selector_styles(
        self,
        selector_frame: 'QFrame',
        options_values: list,
        selected_value: any
    ):
        """Actualiza los estilos de las cards en un selector de opciones.
        
        Útil cuando cambia la selección y necesitas actualizar visualmente las cards.
        
        Args:
            selector_frame: QFrame retornado por _create_option_selector
            options_values: Lista de valores de las opciones en el mismo orden que se pasaron a _create_option_selector
            selected_value: Valor actualmente seleccionado
        """
        from PyQt6.QtWidgets import QFrame
        from ui.styles.design_system import DesignSystem
        
        for idx, value in enumerate(options_values):
            card_name = f"option-{idx}"
            card = selector_frame.findChild(QFrame, card_name)
            
            if card:
                is_selected = (value == selected_value)
                card.setStyleSheet(f"""
                    QFrame#{card_name} {{
                        background-color: {DesignSystem.COLOR_PRIMARY if is_selected else DesignSystem.COLOR_SURFACE};
                        border: 2px solid {DesignSystem.COLOR_PRIMARY if is_selected else DesignSystem.COLOR_BORDER};
                        border-radius: {DesignSystem.RADIUS_BASE}px;
                        padding: {DesignSystem.SPACE_12}px;
                    }}
                    QFrame#{card_name}:hover {{
                        border-color: {DesignSystem.COLOR_PRIMARY};
                        background-color: {DesignSystem.COLOR_PRIMARY if is_selected else DesignSystem.COLOR_BG_2};
                    }}
                    QFrame#{card_name} QLabel {{
                        color: {DesignSystem.COLOR_PRIMARY_TEXT if is_selected else DesignSystem.COLOR_TEXT};
                    }}
                    QFrame#{card_name} QLabel#title-label {{
                        font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
                    }}
                    QFrame#{card_name} QLabel#desc-label {{
                        color: {DesignSystem.COLOR_PRIMARY_TEXT if is_selected else DesignSystem.COLOR_TEXT_SECONDARY};
                    }}
                """)
                
                # Actualizar color del icono
                self._update_card_icon_color(card, is_selected)
    
    def _update_card_icon_color(self, card: 'QFrame', is_selected: bool):
        """Actualiza el color del icono en una card de selección.
        
        Args:
            card: QFrame de la card
            is_selected: Si la card está seleccionada
        """
        from PyQt6.QtWidgets import QLabel
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        # Encontrar el icono (segundo QLabel en el header layout)
        layout = card.layout()
        if layout and layout.count() > 0:
            header_layout = layout.itemAt(0).layout()  # Primer item es el header_layout
            if header_layout and header_layout.count() >= 3:  # RadioButton, Icono, Título
                icon_label = header_layout.itemAt(1).widget()  # Segundo widget es el icono
                if isinstance(icon_label, QLabel):
                    # Obtener el icono actual y actualizar su color
                    current_icon = getattr(icon_label, 'icon_name', None)
                    if current_icon:
                        icon_manager.set_label_icon(
                            icon_label,
                            current_icon,
                            size=DesignSystem.ICON_SIZE_XL,
                            color=DesignSystem.COLOR_PRIMARY_TEXT if is_selected else DesignSystem.COLOR_PRIMARY
                        )
                        icon_label.update()  # Forzar repaint
    
    def _create_security_options_section(
        self,
        show_backup: bool = True,
        show_dry_run: bool = False,
        backup_label: str = tr("dialogs.base.backup_label"),
        dry_run_label: str = tr("dialogs.base.dry_run_label")
    ) -> 'QFrame':
        """Crea sección de opciones con diseño Material Design 3.
        
        Diseño profesional con chips inline y ruta de backup visible.
        Consistente en todos los 8 diálogos principales.
        
        Args:
            show_backup: Si se debe mostrar el checkbox de backup
            show_dry_run: Si se debe mostrar el checkbox de dry-run
            backup_label: Texto para el checkbox de backup
            dry_run_label: Texto para el checkbox de dry-run
        
        Returns:
            QFrame con la sección configurada
        """
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QWidget
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        from utils.settings_manager import settings_manager
        from config import Config
        
        frame = QFrame()
        frame.setObjectName("security-options-frame")
        frame.setStyleSheet(f"""
            QFrame#security-options-frame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_12}px {DesignSystem.SPACE_16}px;
            }}
        """)
        
        # Layout principal vertical para chips + ruta
        main_layout = QVBoxLayout(frame)
        main_layout.setSpacing(int(DesignSystem.SPACE_8))
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # === Fila de chips ===
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(int(DesignSystem.SPACE_12))
        chips_layout.setContentsMargins(0, 0, 0, 0)
        
        # Label "Opciones:" inline minimalista
        options_label = QLabel(tr("dialogs.base.options_label"))
        options_label.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_SM}px;
            font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
            color: {DesignSystem.COLOR_TEXT_SECONDARY};
            padding: 0px;
            margin: 0px;
        """)
        chips_layout.addWidget(options_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # Obtener ruta de backup
        backup_dir = settings_manager.get_backup_directory(Config.DEFAULT_BACKUP_DIR)
        backup_path_str = str(backup_dir) if backup_dir else str(Config.DEFAULT_BACKUP_DIR)
        
        # === Checkbox de backup (inline chip style) ===
        if show_backup:
            backup_checked = settings_manager.get_auto_backup_enabled()
            
            self.backup_checkbox = self._create_inline_chip_checkbox(
                icon_name='content-save',
                label=backup_label,
                checked=backup_checked,
                tooltip=tr("dialogs.base.backup_tooltip", path=backup_path_str)
            )
            chips_layout.addWidget(self.backup_checkbox)
        
        # === Checkbox de dry-run (inline chip style) ===
        if show_dry_run:
            dry_run_default = settings_manager.get(settings_manager.KEY_DRY_RUN_DEFAULT, False)
            if isinstance(dry_run_default, str):
                dry_run_default = dry_run_default.lower() in ('true', '1', 'yes')
            
            self.dry_run_checkbox = self._create_inline_chip_checkbox(
                icon_name='eye',
                label=dry_run_label,
                checked=bool(dry_run_default),
                tooltip=tr("dialogs.base.dry_run_tooltip")
            )
            chips_layout.addWidget(self.dry_run_checkbox)
        
        # Spacer para empujar chips a la izquierda
        chips_layout.addStretch()
        main_layout.addLayout(chips_layout)
        
        # === Fila con ruta de backup (siempre presente para mantener tamaño fijo) ===
        if show_backup:
            # Truncar path si es muy largo
            max_display_len = 60
            display_path = backup_path_str
            if len(display_path) > max_display_len:
                display_path = "..." + display_path[-(max_display_len - 3):]
            
            # Contenedor para la ruta (mantiene espacio fijo)
            self._backup_path_widget = QWidget()
            # Reservar espacio incluso cuando está oculto para evitar saltos en la interfaz
            sp = self._backup_path_widget.sizePolicy()
            if hasattr(sp, 'setRetainSizeWhenHidden'):
                sp.setRetainSizeWhenHidden(True)
                self._backup_path_widget.setSizePolicy(sp)

            path_layout = QHBoxLayout(self._backup_path_widget)
            path_layout.setSpacing(int(DesignSystem.SPACE_6))
            path_layout.setContentsMargins(0, 0, 0, 0)
            
            self._backup_folder_icon = QLabel()
            icon_manager.set_label_icon(
                self._backup_folder_icon, 'folder', 
                size=DesignSystem.ICON_SIZE_SM, 
                color=DesignSystem.COLOR_TEXT_SECONDARY
            )
            path_layout.addWidget(self._backup_folder_icon)
            
            self._backup_path_label = QLabel(tr("dialogs.base.backup_path_label", path=display_path))
            self._backup_path_label.setStyleSheet(f"""
                font-size: {DesignSystem.FONT_SIZE_XS}px;
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
            """)
            self._backup_path_label.setToolTip(
                tr("dialogs.base.backup_path_tooltip", path=backup_path_str)
            )
            path_layout.addWidget(self._backup_path_label)
            path_layout.addStretch()
            
            main_layout.addWidget(self._backup_path_widget)
            
            # Actualizar visibilidad inicial del widget completo
            self._backup_path_widget.setVisible(self.is_backup_enabled())
        
        # Configurar lógica de interacción dry-run/backup
        if show_dry_run and show_backup and hasattr(self, 'backup_checkbox'):
            self._setup_dry_run_backup_logic()
        
        return frame
    
    def _update_backup_path_visibility(self, visible: bool):
        """Actualiza la visibilidad de la ruta de backup preservando el espacio en el layout."""
        if hasattr(self, '_backup_path_widget') and self._backup_path_widget:
            self._backup_path_widget.setVisible(visible)
    
    def _create_warning_banner(
        self,
        title: str,
        message: str,
        icon: str = 'alert',
        action_text: Optional[str] = None,
        action_callback: Optional[callable] = None,
        bg_color: str = DesignSystem.COLOR_WARNING_BG,
        border_color: str = DesignSystem.COLOR_WARNING,
        text_color: str = DesignSystem.COLOR_TEXT
    ) -> 'QFrame':
        """Crea un banner de advertencia estandarizado.
        
        Args:
            title: Título en negrita
            message: Mensaje descriptivo (soporta HTML básico)
            icon: Nombre del icono (default: 'alert')
            action_text: Texto del botón de acción (opcional)
            action_callback: Función a llamar al pulsar el botón (opcional)
            bg_color: Color de fondo (default: Warning BG)
            border_color: Color del borde (default: Warning)
            text_color: Color del texto (default: Text)
            
        Returns:
            QFrame configurado con el banner
        """
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
        from PyQt6.QtCore import Qt
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        frame = QFrame()
        frame.setObjectName("warningBanner")
        frame.setStyleSheet(f"""
            QFrame#warningBanner {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
        """)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(
            int(DesignSystem.SPACE_12),
            int(DesignSystem.SPACE_8),
            int(DesignSystem.SPACE_12),
            int(DesignSystem.SPACE_8)
        )
        layout.setSpacing(int(DesignSystem.SPACE_12))
        
        # Icono
        icon_label = QLabel()
        # Usar un tamaño un poco más grande para el icono de advertencia
        icon_manager.set_label_icon(
            icon_label, 
            icon, 
            size=DesignSystem.ICON_SIZE_LG,
            color=DesignSystem.COLOR_TEXT  # El icono suele ser texto/emoji o SVG coloreado
        )
        # Si es un emoji (fallback), asegurar tamaño
        icon_label.setStyleSheet(f"font-size: {DesignSystem.FONT_SIZE_LG}px;")
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        
        # Contenedor de texto
        text_layout = QVBoxLayout()
        text_layout.setSpacing(int(DesignSystem.SPACE_4))
        
        # Mensaje compuesto (Título: Mensaje)
        full_message = f"<b>{title}:</b> {message}" if title else message
        text_label = QLabel(full_message)
        text_label.setWordWrap(True)
        text_label.setStyleSheet(f"""
            color: {text_color};
            font-size: {DesignSystem.FONT_SIZE_SM}px;
        """)
        text_layout.addWidget(text_label)
        
        layout.addLayout(text_layout, 1)
        
        # Botón de acción (opcional)
        if action_text and action_callback:
            action_btn = QPushButton(action_text)
            # Determinar estilo del botón basado en el tipo de alerta
            btn_bg = border_color  # Usar el color del borde como fondo del botón
            btn_hover = border_color # Simplificación, idealmente un tono más oscuro
            
            action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {btn_bg};
                    color: {DesignSystem.COLOR_TEXT};
                    border: none;
                    border-radius: {DesignSystem.RADIUS_SM}px;
                    padding: {DesignSystem.SPACE_6}px {DesignSystem.SPACE_12}px;
                    font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
                    font-size: {DesignSystem.FONT_SIZE_SM}px;
                }}
                QPushButton:hover {{
                    opacity: 0.9;
                }}
            """)
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.clicked.connect(action_callback)
            layout.addWidget(action_btn)
            
        return frame

    def _create_info_banner(
        self,
        title: str,
        message: str,
        icon: str = 'information-outline'
    ) -> 'QFrame':
        """Crea un banner de información (azul) estandarizado.
        
        Wrapper conveniente sobre _create_warning_banner con colores de Info.
        """
        return self._create_warning_banner(
            title=title,
            message=message,
            icon=icon,
            bg_color=DesignSystem.COLOR_INFO_BG,
            border_color=DesignSystem.COLOR_INFO,
            text_color="#055160"  # Color oscuro para texto sobre fondo azul claro
        )
    def _setup_dry_run_backup_logic(self):
        """Configura la lógica de deshabilitación automática entre dry-run y backup.
        
        Cuando dry-run está activo, el backup se deshabilita visualmente Y se desactiva
        automáticamente ya que no se realizarán cambios reales en los archivos.
        Guarda el estado previo para restaurarlo cuando se desactive dry-run.
        """
        # Variable para guardar el estado previo del backup
        self._backup_state_before_dry_run = None
        
        def on_dry_run_changed():
            if not hasattr(self, 'dry_run_checkbox') or not hasattr(self, 'backup_checkbox'):
                return
            
            dry_run_enabled = self.is_dry_run_enabled()
            backup_widget = self.backup_checkbox
            backup_checkbox_internal = backup_widget._checkbox if hasattr(backup_widget, '_checkbox') else backup_widget
            
            if dry_run_enabled:
                # Guardar estado actual del backup antes de deshabilitarlo
                self._backup_state_before_dry_run = backup_checkbox_internal.isChecked()
                
                # Desactivar el checkbox del backup
                backup_checkbox_internal.setChecked(False)
                
                # Deshabilitar visualmente el widget
                backup_widget.setEnabled(False)
                backup_widget.setToolTip(
                    tr("dialogs.base.backup_disabled_tooltip")
                )
                
                # Actualizar el estado visual del chip
                if hasattr(backup_widget, '_update_visual_state'):
                    backup_widget._update_visual_state()
            else:
                # Rehabilitar visualmente el widget PRIMERO
                backup_widget.setEnabled(True)
                
                # Restaurar estado previo del backup si existía
                if self._backup_state_before_dry_run is not None:
                    backup_checkbox_internal.setChecked(self._backup_state_before_dry_run)
                    self._backup_state_before_dry_run = None
                
                # Obtener ruta para el tooltip
                from utils.settings_manager import settings_manager
                from config import Config
                backup_dir = settings_manager.get_backup_directory(Config.DEFAULT_BACKUP_DIR)
                backup_path_str = str(backup_dir) if backup_dir else str(Config.DEFAULT_BACKUP_DIR)
                
                backup_widget.setToolTip(
                    tr("dialogs.base.backup_tooltip", path=backup_path_str)
                )
                
                # Actualizar el estado visual del chip
                if hasattr(backup_widget, '_update_visual_state'):
                    backup_widget._update_visual_state()
            
            # Actualizar visibilidad de la ruta de backup (contenido, no espacio)
            self._update_backup_path_visibility(self.is_backup_enabled())
        
        def on_backup_changed():
            """Actualiza la visibilidad de la ruta cuando cambia el estado del backup."""
            self._update_backup_path_visibility(self.is_backup_enabled())
        
        # Conectar señales
        if hasattr(self.dry_run_checkbox, '_checkbox'):
            self.dry_run_checkbox._checkbox.toggled.connect(on_dry_run_changed)
        else:
            self.dry_run_checkbox.toggled.connect(on_dry_run_changed)
        
        # Conectar cambio de backup para actualizar visibilidad de ruta
        if hasattr(self.backup_checkbox, '_checkbox'):
            self.backup_checkbox._checkbox.toggled.connect(on_backup_changed)
        else:
            self.backup_checkbox.toggled.connect(on_backup_changed)
        
        # Ejecutar lógica inicial
        on_dry_run_changed()
    
    def _create_inline_chip_checkbox(
        self,
        icon_name: str,
        label: str,
        checked: bool,
        tooltip: str
    ) -> QWidget:
        """Crea un checkbox ultra-compacto estilo "chip" Material Design 3.
        
        Diseño inline minimalista profesional con transiciones suaves.
        Inspirado en los filter chips de Material Design 3.
        
        Args:
            icon_name: Nombre del icono de icon_manager
            label: Texto del checkbox
            checked: Estado inicial
            tooltip: Texto del tooltip
        
        Returns:
            QWidget contenedor con el diseño chip inline
        """
        from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QCheckBox
        from PyQt6.QtCore import Qt
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        # Contenedor tipo chip
        container = QWidget()
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            int(DesignSystem.SPACE_10),
            int(DesignSystem.SPACE_6),
            int(DesignSystem.SPACE_10),
            int(DesignSystem.SPACE_6)
        )
        layout.setSpacing(int(DesignSystem.SPACE_6))
        
        # Checkbox real (oculto)
        checkbox = QCheckBox()
        checkbox.setChecked(checked)
        checkbox.setStyleSheet("QCheckBox { margin: 0; padding: 0; } QCheckBox::indicator { width: 0; height: 0; }")
        
        # Establecer tooltip en el contenedor visual (no en el checkbox oculto)
        container.setToolTip(tooltip)
        
        # Icono Material Design con checkmark integrado
        icon_label = QLabel()
        # Quitar tamaño fijo para evitar cortes horizontales
        layout.addWidget(icon_label)
        
        # Texto del chip
        text_label = QLabel(label)
        text_label.setStyleSheet(f"""
            QLabel {{
                font-size: {DesignSystem.FONT_SIZE_SM}px;
                font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
                padding: 0px;
                margin: 0px;
                border: none;
                background: transparent;
            }}
        """)
        layout.addWidget(text_label)
        
        # Función para toggle
        def toggle_checkbox():
            if container.isEnabled():
                checkbox.setChecked(not checkbox.isChecked())
        
        def update_visual_state():
            is_checked = checkbox.isChecked()
            is_enabled = container.isEnabled()
            
            # Determinar colores según estado
            if not is_enabled:
                bg_color = DesignSystem.COLOR_BG_1
                border_color = DesignSystem.COLOR_BORDER
                text_color = DesignSystem.COLOR_TEXT_SECONDARY
                icon_color = DesignSystem.COLOR_TEXT_SECONDARY
                icon_to_show = icon_name
            elif is_checked:
                bg_color = DesignSystem.COLOR_PRIMARY
                border_color = DesignSystem.COLOR_PRIMARY
                text_color = DesignSystem.COLOR_PRIMARY_TEXT
                icon_color = DesignSystem.COLOR_PRIMARY_TEXT
                icon_to_show = 'check-circle'  # Icono de check cuando está seleccionado
            else:
                bg_color = DesignSystem.COLOR_SURFACE
                border_color = DesignSystem.COLOR_BORDER
                text_color = DesignSystem.COLOR_TEXT
                icon_color = DesignSystem.COLOR_TEXT_SECONDARY
                icon_to_show = icon_name
            
            # Actualizar icono
            icon_manager.set_label_icon(
                icon_label,
                icon_to_show,
                color=icon_color
            )
            
            # Actualizar texto
            text_label.setStyleSheet(f"""
                QLabel {{
                    font-size: {DesignSystem.FONT_SIZE_SM}px;
                    font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
                    color: {text_color};
                    padding: 0px;
                    margin: 0px;
                    border: none;
                    background: transparent;
                }}
            """)
            
            # Estilo del contenedor chip con transición suave
            hover_bg = DesignSystem.COLOR_PRIMARY if is_checked else DesignSystem.COLOR_BG_2
            
            if not is_enabled:
                hover_bg = DesignSystem.COLOR_BG_1
            
            container.setStyleSheet(f"""
                QWidget {{
                    background-color: {bg_color};
                    border-radius: 16px;
                }}
                QWidget:hover {{
                    background-color: {hover_bg};
                    border: 1px solid {DesignSystem.COLOR_PRIMARY};
                }}
                QWidget:hover QLabel {{
                    background: transparent;
                }}
            """)
        
        container.mousePressEvent = lambda event: toggle_checkbox()
        update_visual_state()
        
        # Conectar cambios
        checkbox.toggled.connect(update_visual_state)
        
        # Guardar referencias
        container._checkbox = checkbox
        container._update_visual_state = update_visual_state
        
        return container

    def _create_progressive_loading_bar(
        self,
        on_load_more: callable,
        on_load_all: callable
    ) -> 'QFrame':
        """Crea barra de carga progresiva para listas grandes.
        
        La carga progresiva funciona así:
        1. Inicialmente se cargan N items (ej: 100 grupos)
        2. El usuario puede cargar más items con "Cargar más"
        3. O cargar todos de una vez con "Cargar todos"
        
        Esto mejora el rendimiento en datasets grandes evitando
        renderizar miles de elementos de golpe.
        
        Args:
            on_load_more: Callback para cargar el siguiente lote
            on_load_all: Callback para cargar todos los items restantes
            
        Returns:
            QFrame con la barra de paginación progresiva.
            El frame tiene atributos públicos para actualizar el estado:
            - progress_indicator: QLabel con texto de progreso
            - progress_bar_container: QFrame contenedor de la barra
            - progress_bar_fill: QFrame de relleno de la barra
            - load_more_btn: QPushButton para cargar más
            - load_all_btn: QPushButton para cargar todos
        """
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        pagination_card = QFrame()
        pagination_card.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_BG_1};
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_LG}px;
                padding: {DesignSystem.SPACE_12}px {DesignSystem.SPACE_16}px;
            }}
        """)
        
        pagination_layout = QHBoxLayout(pagination_card)
        pagination_layout.setSpacing(int(DesignSystem.SPACE_12))
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        
        # Indicador de progreso textual
        progress_indicator = QLabel()
        progress_indicator.setStyleSheet(f"""
            QLabel {{
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                font-size: {DesignSystem.FONT_SIZE_SM}px;
            }}
        """)
        progress_indicator.setToolTip(
            tr("dialogs.base.progress.indicator_tooltip")
        )
        pagination_layout.addWidget(progress_indicator)
        
        # Barra de progreso visual
        progress_bar_container = QFrame()
        progress_bar_container.setFixedHeight(8)
        progress_bar_container.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_BORDER};
                border-radius: 4px;
            }}
        """)
        
        progress_bar_fill = QFrame(progress_bar_container)
        progress_bar_fill.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                border-radius: 4px;
            }}
        """)
        progress_bar_fill.setGeometry(0, 0, 0, 8)
        
        pagination_layout.addWidget(progress_bar_container, 1)
        
        # Botón cargar todos
        load_all_btn = QPushButton(tr("dialogs.base.progress.load_all"))
        icon_manager.set_button_icon(load_all_btn, 'download', size=16)
        load_all_btn.clicked.connect(on_load_all)
        load_all_btn.setToolTip(tr("dialogs.base.progress.load_all_tooltip"))
        load_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {DesignSystem.COLOR_PRIMARY};
                border: 2px solid {DesignSystem.COLOR_PRIMARY};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_8}px {DesignSystem.SPACE_16}px;
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                color: {DesignSystem.COLOR_PRIMARY_TEXT};
            }}
        """)
        load_all_btn.hide()
        pagination_layout.addWidget(load_all_btn)
        
        # Botón cargar más
        load_more_btn = QPushButton(tr("dialogs.base.progress.load_more"))
        icon_manager.set_button_icon(load_more_btn, 'refresh', size=18)
        load_more_btn.clicked.connect(on_load_more)
        load_more_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DesignSystem.COLOR_PRIMARY};
                color: {DesignSystem.COLOR_PRIMARY_TEXT};
                border: none;
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_10}px {DesignSystem.SPACE_20}px;
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_PRIMARY_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {DesignSystem.COLOR_SURFACE_DISABLED};
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
            }}
        """)
        pagination_layout.addWidget(load_more_btn)
        
        # Guardar referencias en el frame para acceso externo
        pagination_card.progress_indicator = progress_indicator
        pagination_card.progress_bar_container = progress_bar_container
        pagination_card.progress_bar_fill = progress_bar_fill
        pagination_card.load_more_btn = load_more_btn
        pagination_card.load_all_btn = load_all_btn
        
        return pagination_card

    def _update_progressive_loading_ui(
        self,
        pagination_bar: 'QFrame',
        loaded_count: int,
        filtered_count: int,
        total_count: int,
        load_increment: int = 100
    ) -> None:
        """Actualiza la UI de la barra de carga progresiva.
        
        Args:
            pagination_bar: El QFrame retornado por _create_progressive_loading_bar
            loaded_count: Número de elementos ya cargados en la lista
            filtered_count: Número de elementos después de aplicar filtros
            total_count: Número total de elementos sin filtrar
            load_increment: Cuántos elementos se cargan por lote
        """
        # Texto de progreso claro
        if filtered_count > 0:
            percent = (loaded_count / filtered_count) * 100
            pagination_bar.progress_indicator.setText(
                tr("dialogs.base.progress.loaded_text", percent=f"{percent:.0f}", loaded=loaded_count, total=filtered_count)
            )
            
            # Actualizar barra
            bar_width = pagination_bar.progress_bar_container.width()
            fill_width = int(bar_width * loaded_count / filtered_count) if bar_width > 0 else 0
            pagination_bar.progress_bar_fill.setGeometry(0, 0, fill_width, 8)
        else:
            pagination_bar.progress_indicator.setText(tr("dialogs.base.progress.no_items"))
            pagination_bar.progress_bar_fill.setGeometry(0, 0, 0, 8)
        
        # Mostrar/ocultar botones según estado
        has_more = loaded_count < filtered_count
        pagination_bar.load_more_btn.setVisible(has_more)
        pagination_bar.load_more_btn.setEnabled(has_more)
        pagination_bar.load_all_btn.setVisible(has_more and (filtered_count - loaded_count) > load_increment)
        
        if has_more:
            remaining = filtered_count - loaded_count
            to_load = min(load_increment, remaining)
            pagination_bar.load_more_btn.setText(tr("dialogs.base.progress.load_n_more", count=to_load))
            pagination_bar.load_more_btn.setToolTip(tr("dialogs.base.progress.load_n_more_tooltip", count=to_load, remaining=remaining))
        else:
            pagination_bar.load_more_btn.setText(tr("dialogs.base.progress.all_loaded"))

    def _create_compact_strategy_selector(
        self,
        title: str,
        description: str,
        strategies: List[tuple],
        current_strategy: str,
        on_strategy_changed: callable
    ) -> 'QFrame':
        """Crea selector de estrategia compacto en una línea horizontal.
        
        Diseño minimalista que ahorra espacio vertical manteniendo funcionalidad completa.
        
        Args:
            title: Título del selector (ej: "Conservar:")
            description: Descripción breve (ej: "Elige qué archivo mantener")
            strategies: Lista de tuplas (id, icon_name, label, tooltip)
                Ejemplo: [
                    ('oldest', 'clock-outline', 'Más antiguo', 'Conserva el archivo más antiguo'),
                    ('newest', 'clock-fast', 'Más reciente', 'Conserva el archivo más reciente'),
                ]
            current_strategy: ID de la estrategia actualmente seleccionada
            on_strategy_changed: Callback(strategy_id) cuando cambia la selección
            
        Returns:
            QFrame con el selector compacto.
            El frame tiene un atributo 'strategy_buttons' dict[str, QPushButton]
        """
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import Qt
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_LG}px;
                padding: {DesignSystem.SPACE_12}px {DesignSystem.SPACE_16}px;
            }}
        """)
        
        # Layout horizontal único para compactar todo en una línea
        layout = QHBoxLayout(frame)
        layout.setSpacing(int(DesignSystem.SPACE_16))
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Título + Descripción en línea
        title_desc = QLabel(f"<b>{title}</b> {description}")
        title_desc.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_BASE}px;
            color: {DesignSystem.COLOR_TEXT};
        """)
        layout.addWidget(title_desc)
        
        layout.addStretch()
        
        # Botones de estrategia
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(int(DesignSystem.SPACE_8))
        
        strategy_buttons = {}
        
        for strategy_id, icon_name, label, tooltip in strategies:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(strategy_id == current_strategy)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            icon_manager.set_button_icon(btn, icon_name, size=18)
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DesignSystem.COLOR_BG_1};
                    border: 2px solid {DesignSystem.COLOR_BORDER};
                    border-radius: {DesignSystem.RADIUS_BASE}px;
                    padding: {DesignSystem.SPACE_8}px {DesignSystem.SPACE_16}px;
                    font-size: {DesignSystem.FONT_SIZE_SM}px;
                    font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
                    color: {DesignSystem.COLOR_TEXT};
                }}
                QPushButton:hover {{
                    border-color: {DesignSystem.COLOR_PRIMARY};
                    background-color: {DesignSystem.COLOR_SURFACE};
                }}
                QPushButton:checked {{
                    background-color: {DesignSystem.COLOR_PRIMARY};
                    border-color: {DesignSystem.COLOR_PRIMARY};
                    color: {DesignSystem.COLOR_PRIMARY_TEXT};
                }}
                QPushButton:disabled {{
                    background-color: {DesignSystem.COLOR_BG_2}; /* Slightly darker/different bg for disabled */
                    border-color: {DesignSystem.COLOR_BORDER_LIGHT};
                    color: {DesignSystem.COLOR_TEXT_SECONDARY};
                    border-style: dashed; /* Visual cue for disabled */
                }}
            """)
            
            btn.clicked.connect(lambda checked, s=strategy_id: on_strategy_changed(s))
            buttons_layout.addWidget(btn)
            strategy_buttons[strategy_id] = btn
        
        layout.addLayout(buttons_layout)
        
        # Guardar referencia a los botones
        frame.strategy_buttons = strategy_buttons
        
        return frame
    
    # ========================================================================
    # COLLAPSIBLE TIP / HELP POPUP
    # ========================================================================
    
    def create_tip_button(self, tip_message: str, width: int = 450) -> QPushButton:
        """Crea un botón de tip colapsable con popup flotante.
        
        Diseño minimalista que no ocupa espacio permanente en la UI.
        El mensaje aparece en un popup flotante al hacer clic.
        
        Args:
            tip_message: Mensaje HTML a mostrar en el popup (puede usar <b>, <i>, etc.)
            width: Ancho del popup en píxeles (default: 450)
        
        Returns:
            QPushButton configurado con el tip. Guardar referencia para posicionar popup.
            
        Example:
            self.tip_btn = self.create_tip_button(
                "<b>Tip:</b> Esta herramienta detecta imágenes <i>similares</i>..."
            )
            layout.addWidget(self.tip_btn)
        """
        from PyQt6.QtWidgets import QPushButton
        from PyQt6.QtCore import Qt
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        tip_btn = QPushButton()
        tip_btn.setToolTip(tr("dialogs.base.tip_toggle_tooltip"))
        tip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tip_btn.setCheckable(True)
        icon_manager.set_button_icon(tip_btn, 'information-outline', size=22, color=DesignSystem.COLOR_INFO)
        tip_btn.setFixedSize(32, 32)
        tip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid transparent;
                padding: {DesignSystem.SPACE_4}px;
                border-radius: {DesignSystem.RADIUS_FULL}px;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.COLOR_INFO_BG};
            }}
            QPushButton:checked {{
                background-color: {DesignSystem.COLOR_INFO_BG};
                border: 1px solid {DesignSystem.COLOR_INFO};
            }}
        """)
        
        # Guardar mensaje y ancho para uso posterior
        tip_btn._tip_message = tip_message
        tip_btn._tip_width = width
        tip_btn._tip_popup = None
        
        # Conectar eventos
        tip_btn.clicked.connect(lambda: self._toggle_tip_popup(tip_btn))
        
        return tip_btn
    
    def _toggle_tip_popup(self, tip_btn: QPushButton):
        """Muestra/oculta el popup de tip."""
        if tip_btn.isChecked():
            self._show_tip_popup(tip_btn)
        else:
            self._hide_tip_popup(tip_btn)
    
    def _show_tip_popup(self, tip_btn: QPushButton):
        """Muestra el popup con el mensaje de ayuda."""
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import Qt
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        # Si ya existe, solo mostrarlo
        if tip_btn._tip_popup:
            tip_btn._tip_popup.show()
            return
        
        # Crear popup
        popup = QFrame(self)
        popup.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_INFO_BG};
                border: 1px solid {DesignSystem.COLOR_INFO};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
        """)
        
        popup_layout = QHBoxLayout(popup)
        popup_layout.setContentsMargins(
            DesignSystem.SPACE_12, DesignSystem.SPACE_8,
            DesignSystem.SPACE_12, DesignSystem.SPACE_8
        )
        popup_layout.setSpacing(DesignSystem.SPACE_8)
        
        # Icono
        icon = icon_manager.create_icon_label('information-outline', size=18, color=DesignSystem.COLOR_INFO)
        popup_layout.addWidget(icon)
        
        # Texto
        text = QLabel(tip_btn._tip_message)
        text.setWordWrap(True)
        text.setStyleSheet(f"""
            color: {DesignSystem.COLOR_TEXT}; 
            font-size: {DesignSystem.FONT_SIZE_SM}px;
            background: transparent;
            border: none;
        """)
        popup_layout.addWidget(text, stretch=1)
        
        # Botón cerrar
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {DesignSystem.COLOR_TEXT_SECONDARY};
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {DesignSystem.COLOR_TEXT};
            }}
        """)
        close_btn.clicked.connect(lambda: self._hide_tip_popup(tip_btn))
        popup_layout.addWidget(close_btn)
        
        # Configurar tamaño y posición
        popup.setFixedWidth(tip_btn._tip_width)
        popup.adjustSize()
        
        # Posicionar debajo y a la derecha del botón (alineado con el borde izquierdo del botón)
        btn_pos = tip_btn.mapTo(self, tip_btn.rect().bottomLeft())
        popup_x = btn_pos.x()
        popup_y = btn_pos.y() + 8
        
        popup.move(popup_x, popup_y)
        
        # Guardar referencia y mostrar
        tip_btn._tip_popup = popup
        popup.show()
    
    def _hide_tip_popup(self, tip_btn: QPushButton):
        """Oculta el popup de tip."""
        if tip_btn._tip_popup:
            tip_btn._tip_popup.hide()
        tip_btn.setChecked(False)
    
    # ========================================================================
    # UNIFIED FILTER BAR
    # ========================================================================
    
    def _create_unified_filter_bar(
        self,
        on_search_changed: callable,
        on_size_filter_changed: callable,
        expandable_filters: Optional[List[Dict]] = None,
        size_filter_options: Optional[List[str]] = None,
        is_files_mode: bool = False,
        labels: Optional[Dict[str, str]] = None
    ) -> 'QFrame':
        """Crea barra de filtros unificada con diseño consistente para todos los diálogos.
        
        Diseño estándar:
        - Barra principal: Búsqueda, filtro de tamaño/cantidad, chip de estado, botón expandir
        - Barra secundaria (desplegable): Filtros adicionales específicos por diálogo
        
        Args:
            on_search_changed: Callback para cambios en búsqueda
            on_size_filter_changed: Callback para cambios en filtro tamaño/cantidad
            expandable_filters: Lista de filtros para la barra desplegable.
            size_filter_options: Lista personalizada de opciones para el filtro de tamaño.
            is_files_mode: Si True, muestra "Archivos" en vez de "Grupos" en el chip
            labels: Diccionario opcional de etiquetas para los filtros.
                Ej: {'search': 'Buscar:', 'size': 'Tamaño:', 'groups': 'Grupos:'}
            
        Returns:
            QFrame con la barra de filtros.
        """
        from PyQt6.QtWidgets import (
            QFrame, QHBoxLayout, QVBoxLayout, QWidget, QLabel, 
            QLineEdit, QComboBox, QPushButton
        )
        from PyQt6.QtCore import Qt
        from ui.styles.design_system import DesignSystem
        from ui.styles.icons import icon_manager
        
        labels = labels or {}
        
        # Default size filter options
        if size_filter_options is None:
            size_filter_options = [
                tr("common.filter.all"),
                tr("common.filter.gt_10mb"),
                tr("common.filter.gt_50mb"),
                tr("common.filter.gt_100mb"),
                tr("common.filter.3_plus_copies"),
                tr("common.filter.5_plus_copies")
            ]
        
        # Frame principal - más compacto
        main_frame = QFrame()
        main_frame.setObjectName("UnifiedFilterBar")
        main_frame.setStyleSheet(f"""
            QFrame#UnifiedFilterBar {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_LG}px;
                padding: {DesignSystem.SPACE_12}px;
            }}
        """)
        
        main_layout = QVBoxLayout(main_frame)
        main_layout.setSpacing(int(DesignSystem.SPACE_8))
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # === BARRA PRINCIPAL ===
        primary_bar = QHBoxLayout()
        primary_bar.setSpacing(int(DesignSystem.SPACE_12))
        primary_bar.setContentsMargins(0, 0, 0, 0)
        
        # --- BÚSQUEDA ---
        search_vlayout = QVBoxLayout()
        search_vlayout.setSpacing(2)  # Espacio mínimo entre label y control
        search_vlayout.setContentsMargins(0, 0, 0, 0)
        
        if 'search' in labels:
            search_label = QLabel(labels['search'])
            search_label.setStyleSheet(DesignSystem.get_filter_label_style())
            search_vlayout.addWidget(search_label)
            
        search_container = QWidget()
        search_container.setObjectName("SearchContainer")
        search_container.setFixedHeight(36)  # Altura unificada
        search_container.setStyleSheet(f"""
            QWidget#SearchContainer {{
                background-color: {DesignSystem.COLOR_BG_1};
                border: 2px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
            }}
            QWidget#SearchContainer:hover {{
                border-color: {DesignSystem.COLOR_PRIMARY};
            }}
        """)
        
        search_container_layout = QHBoxLayout(search_container)
        search_container_layout.setContentsMargins(10, 6, 10, 6)
        search_container_layout.setSpacing(8)
        
        search_icon = QLabel()
        icon_manager.set_label_icon(search_icon, 'magnify', size=16)
        search_container_layout.addWidget(search_icon)
        
        search_input = QLineEdit()
        search_input.setPlaceholderText(tr("dialogs.base.filter.search_placeholder"))
        search_input.textChanged.connect(on_search_changed)
        search_input.setStyleSheet(f"""
            QLineEdit {{
                border: none;
                background: transparent;
                font-size: {DesignSystem.FONT_SIZE_SM}px;
                color: {DesignSystem.COLOR_TEXT};
                padding: 0px;
            }}
        """)
        search_container_layout.addWidget(search_input, 1)
        
        search_vlayout.addWidget(search_container)
        primary_bar.addLayout(search_vlayout, 3)
        
        # Espaciador flexible
        primary_bar.addStretch()
        
        # --- STATUS CHIP (Grupos:) ---
        status_vlayout = QVBoxLayout()
        status_vlayout.setSpacing(2)  # Espacio mínimo entre label y control
        status_vlayout.setContentsMargins(0, 0, 0, 0)
        
        # Etiqueta de grupos - ahora alineada a la izquierda
        entity_label_text = labels.get('groups', tr("dialogs.base.filter.files_selected") if is_files_mode else tr("dialogs.base.filter.groups_selected"))
        groups_label = QLabel(entity_label_text)
        groups_label.setStyleSheet(DesignSystem.get_filter_label_style())
        groups_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        status_vlayout.addWidget(groups_label)
        
        # El chip en sí
        status_chip = QLabel()
        status_chip.setMinimumWidth(70)
        status_chip.setFixedHeight(36)  # Altura unificada
        status_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # El estilo dinámico se aplica en _update_filter_chip
        status_vlayout.addWidget(status_chip)
        primary_bar.addLayout(status_vlayout)
        
        # Botón expandir filtros (si hay filtros expandibles o filtro de tamaño)
        has_expandable_filters = expandable_filters or (size_filter_options and on_size_filter_changed)
        if has_expandable_filters:
            expand_vlayout = QVBoxLayout()
            expand_vlayout.setSpacing(2)
            expand_vlayout.setContentsMargins(0, 0, 0, 0)
            
            # Label vacío para alinear con otros controles
            if 'search' in labels:
                empty_label = QLabel()
                empty_label.setStyleSheet("font-size: 9px; margin: 0px; padding: 0px;")
                empty_label.setFixedHeight(11)  # Altura aproximada del label
                expand_vlayout.addWidget(empty_label)
            
            expand_btn = QPushButton()
            expand_btn.setCheckable(True)
            expand_btn.setChecked(False)
            expand_btn.setToolTip(tr("dialogs.base.filter.more_filters"))
            icon_manager.set_button_icon(expand_btn, 'filter-variant', size=16)
            expand_btn.setFixedSize(36, 36)  # Altura unificada
            expand_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DesignSystem.COLOR_BG_1};
                    border: 2px solid {DesignSystem.COLOR_BORDER};
                    border-radius: {DesignSystem.RADIUS_BASE}px;
                }}
                QPushButton:hover {{
                    border-color: {DesignSystem.COLOR_PRIMARY};
                }}
                QPushButton:checked {{
                    background-color: {DesignSystem.COLOR_PRIMARY};
                    border-color: {DesignSystem.COLOR_PRIMARY};
                }}
            """)
            expand_vlayout.addWidget(expand_btn)
            primary_bar.addLayout(expand_vlayout)
        else:
            expand_btn = None
            
        main_layout.addLayout(primary_bar)
        
        # === BARRA EXPANDIBLE ===
        expandable_container = None
        filter_widgets = {}
        size_filter_combo = None  # Referencia al combo de tamaño
        
        # Preparar la lista completa de filtros expandibles incluyendo el de tamaño
        all_expandable_filters = []
        
        # Añadir filtro de tamaño como PRIMER filtro expandible
        if size_filter_options and on_size_filter_changed:
            size_filter_config = {
                'id': 'size',
                'type': 'combo',
                'label': labels.get('size', tr("dialogs.base.filter.size_quantity_label")),
                'tooltip': tr("dialogs.base.filter.size_quantity_tooltip"),
                'options': size_filter_options,
                'on_change': on_size_filter_changed,
                'default_index': 0,
                'min_width': 150
            }
            all_expandable_filters.append(size_filter_config)
        
        # Añadir el resto de filtros expandibles
        if expandable_filters:
            all_expandable_filters.extend(expandable_filters)
        
        if all_expandable_filters:
            expandable_container = QWidget()
            expandable_container.setVisible(False)
            expandable_layout = QHBoxLayout(expandable_container)
            expandable_layout.setSpacing(int(DesignSystem.SPACE_12))
            expandable_layout.setContentsMargins(0, int(DesignSystem.SPACE_8), 0, 0)
            
            for filter_config in all_expandable_filters:
                filter_id = filter_config['id']
                filter_type = filter_config.get('type', 'combo')
                filter_label_text = labels.get(filter_id, filter_config.get('label'))
                
                # Layout vertical para cada filtro en la barra expandible
                v_box = QVBoxLayout()
                v_box.setSpacing(2)  # Espacio mínimo entre label y control
                v_box.setContentsMargins(0, 0, 0, 0)
                
                if filter_label_text:
                    f_label = QLabel(filter_label_text)
                    f_label.setStyleSheet(DesignSystem.get_filter_label_style())
                    v_box.addWidget(f_label)
                
                if filter_type == 'combo':
                    combo = QComboBox()
                    combo.addItems(filter_config['options'])
                    combo.setCurrentIndex(filter_config.get('default_index', 0))
                    combo.currentIndexChanged.connect(
                        lambda idx, cb=filter_config['on_change']: cb(idx)
                    )
                    combo.setToolTip(filter_config.get('tooltip', ''))
                    combo.setFixedHeight(36)  # Altura unificada
                    combo.setStyleSheet(self._get_unified_combo_style())
                    combo.setMinimumWidth(filter_config.get('min_width', 150))
                    v_box.addWidget(combo)
                    filter_widgets[filter_id] = combo
                    
                elif filter_type == 'type_buttons':
                    # Botones para filtro de tipo (imágenes/vídeos/todo)
                    type_container = QFrame()
                    type_container.setObjectName("TypeButtonsContainer")
                    type_container.setFixedHeight(36)  # Altura unificada
                    type_container.setStyleSheet(f"""
                        QFrame#TypeButtonsContainer {{
                            background-color: {DesignSystem.COLOR_BG_1};
                            border: 2px solid {DesignSystem.COLOR_BORDER};
                            border-radius: {DesignSystem.RADIUS_BASE}px;
                            padding: 2px;
                        }}
                    """)
                    type_layout = QHBoxLayout(type_container)
                    type_layout.setSpacing(2)
                    type_layout.setContentsMargins(2, 2, 2, 2)
                    
                    type_buttons = {}
                    for btn_id, icon_name, tooltip in filter_config['options']:
                        btn = QPushButton()
                        btn.setCheckable(True)
                        btn.setChecked(btn_id == filter_config.get('default', 'all'))
                        btn.setToolTip(tooltip)
                        btn.setCursor(Qt.CursorShape.PointingHandCursor)
                        icon_manager.set_button_icon(btn, icon_name, size=16)
                        btn.setFixedSize(32, 28)  # Más compacto
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: transparent;
                                border: none;
                                border-radius: {DesignSystem.RADIUS_SM}px;
                                padding: 2px;
                            }}
                            QPushButton:hover {{
                                background-color: {DesignSystem.COLOR_SURFACE};
                            }}
                            QPushButton:checked {{
                                background-color: {DesignSystem.COLOR_PRIMARY};
                            }}
                        """)
                        btn.clicked.connect(
                            lambda checked, bid=btn_id, cb=filter_config['on_change'], btns=type_buttons:
                            self._handle_type_button_click(bid, btns, cb)
                        )
                        type_layout.addWidget(btn)
                        type_buttons[btn_id] = btn
                    
                    v_box.addWidget(type_container)
                    filter_widgets[filter_id] = type_buttons
                
                elif filter_type in ['custom', 'partial_slider']:
                    # Widget personalizado usando factory
                    if 'widget_factory' in filter_config:
                        custom_widget = filter_config['widget_factory']()
                        custom_widget.setToolTip(filter_config.get('tooltip', ''))
                        if 'min_width' in filter_config:
                            custom_widget.setMinimumWidth(filter_config['min_width'])
                        v_box.addWidget(custom_widget)
                        filter_widgets[filter_id] = custom_widget
                
                # Guardar referencia especial al combo de tamaño
                if filter_id == 'size' and filter_type == 'combo':
                    size_filter_combo = filter_widgets.get('size')
                
                expandable_layout.addLayout(v_box)
            
            expandable_layout.addStretch()
            main_layout.addWidget(expandable_container)
            
            # Conectar botón expandir
            def toggle_expandable():
                is_expanded = expand_btn.isChecked()
                expandable_container.setVisible(is_expanded)
                icon_name = 'filter-variant-remove' if is_expanded else 'filter-variant'
                icon_manager.set_button_icon(expand_btn, icon_name, size=16)
                expand_btn.setToolTip(
                    tr("dialogs.base.filter.hide_extra") if is_expanded else tr("dialogs.base.filter.show_extra")
                )
            
            expand_btn.clicked.connect(toggle_expandable)
        
        # Guardar referencias
        main_frame.search_input = search_input
        main_frame.size_filter_combo = size_filter_combo
        main_frame.status_chip = status_chip
        main_frame.expand_btn = expand_btn
        main_frame.expandable_container = expandable_container
        main_frame.filter_widgets = filter_widgets
        main_frame._is_files_mode = is_files_mode
        
        return main_frame
    
    def _handle_type_button_click(self, clicked_id: str, buttons: dict, callback: callable):
        """Maneja click en botones de tipo (todo/imágenes/vídeos).
        
        Asegura que solo un botón esté seleccionado y llama al callback.
        """
        # Actualizar estado visual de todos los botones
        for btn_id, btn in buttons.items():
            btn.setChecked(btn_id == clicked_id)
        
        # Llamar al callback
        callback(clicked_id)
    
    def _get_unified_combo_style(self) -> str:
        """Retorna estilo CSS unificado para ComboBox en barras de filtros."""
        return f"""
            QComboBox {{
                background-color: {DesignSystem.COLOR_BG_1};
                border: 2px solid {DesignSystem.COLOR_BORDER};
                border-radius: {DesignSystem.RADIUS_BASE}px;
                padding: {DesignSystem.SPACE_8}px {DesignSystem.SPACE_12}px;
                font-size: {DesignSystem.FONT_SIZE_BASE}px;
                color: {DesignSystem.COLOR_TEXT};
            }}
            QComboBox:hover {{
                border-color: {DesignSystem.COLOR_PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: {DesignSystem.SPACE_8}px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {DesignSystem.COLOR_SURFACE};
                border: 1px solid {DesignSystem.COLOR_BORDER};
                selection-background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                selection-color: {DesignSystem.COLOR_TEXT};
                padding: {DesignSystem.SPACE_4}px;
            }}
        """
    
    def _update_filter_chip(
        self,
        status_chip: 'QLabel',
        filtered_count: int,
        total_count: int,
        loaded_count: Optional[int] = None,
        is_files_mode: bool = False
    ):
        """Actualiza el chip de estado de filtros con estilo unificado.
        
        Args:
            status_chip: QLabel del chip
            filtered_count: Elementos después de filtrar
            total_count: Total de elementos sin filtrar
            loaded_count: Elementos cargados en la vista (para tooltip)
            is_files_mode: Si True, el tooltip dice "archivos" en vez de "grupos"
        """
        entity = tr("common.files") if is_files_mode else tr("common.groups")
        status_chip.setObjectName("StatusChip")
        
        if filtered_count != total_count:
            # Hay filtros activos - color warning/accent
            status_chip.setText(f"{filtered_count}/{total_count}")
            status_chip.setStyleSheet(f"""
                QLabel#StatusChip {{
                    background-color: {DesignSystem.COLOR_WARNING};
                    color: {DesignSystem.COLOR_SURFACE};
                    border-radius: 18px;
                    padding: 0px 14px;
                    font-size: {DesignSystem.FONT_SIZE_SM}px;
                    font-weight: {DesignSystem.FONT_WEIGHT_BOLD};
                    min-width: 70px;
                }}
            """)
            tooltip = tr("dialogs.base.filter.filtered_tooltip", entity=entity, filtered=filtered_count, total=total_count)
            if loaded_count is not None:
                tooltip += "\n" + tr("dialogs.base.filter.loaded_in_list", loaded=loaded_count, total=filtered_count)
            status_chip.setToolTip(tooltip)
        else:
            # Sin filtros - color primario más sutil o neutro
            status_chip.setText(f"{total_count}/{total_count}")
            status_chip.setStyleSheet(f"""
                QLabel#StatusChip {{
                    background-color: {DesignSystem.COLOR_BG_1};
                    color: {DesignSystem.COLOR_PRIMARY};
                    border: 2px solid {DesignSystem.COLOR_PRIMARY};
                    border-radius: 18px;
                    padding: 0px 14px;
                    font-size: {DesignSystem.FONT_SIZE_SM}px;
                    font-weight: {DesignSystem.FONT_WEIGHT_BOLD};
                    min-width: 70px;
                }}
            """)
            status_chip.setToolTip(tr("dialogs.base.filter.showing_all", entity=entity, count=total_count))
    
    # Constantes para filtros de origen de fecha
    # Nombres reales usados por select_best_date_from_file() y select_best_date_from_common_date_to_2_files()
    DATE_SOURCE_FILTER_ALL = tr("dialogs.base.date_source.all")
    DATE_SOURCE_FILTER_OPTIONS = [
        tr("dialogs.base.date_source.all"),
        tr("dialogs.base.date_source.exif"),
        tr("dialogs.base.date_source.filename"),
        tr("dialogs.base.date_source.filesystem"),
    ]
    
    def _matches_source_filter(self, date_source: str, filter_value: str) -> bool:
        """Verifica si el origen de fecha coincide con el filtro seleccionado.
        
        Método centralizado para evitar duplicación entre diálogos.
        Soporta agrupación de fuentes relacionadas (EXIF, Filesystem).
        
        Args:
            date_source: Origen de la fecha del archivo. Valores posibles:
                - De select_best_date_from_file(): 'EXIF DateTimeOriginal', 'EXIF DateTimeOriginal (+02:00)',
                  'EXIF CreateDate', 'EXIF DateTimeDigitized', 'Filename', 'Video Metadata', 'mtime', 'ctime', 'birth'
                - De select_best_date_from_common_date_to_2_files(): 'exif_date_time_original', 'exif_create_date',
                  'exif_modify_date', 'fs_mtime', 'fs_ctime', 'fs_atime'
            filter_value: Valor seleccionado en el filtro
            
        Returns:
            True si coincide con el filtro
        """
        if not date_source or filter_value == self.DATE_SOURCE_FILTER_ALL:
            return True
        
        source_lower = date_source.lower()
        
        # Filtro EXIF: agrupa todos los tipos de EXIF
        if filter_value == tr("dialogs.base.date_source.exif"):
            return 'exif' in source_lower or 'video metadata' in source_lower
        
        # Filtro Filename
        if filter_value == tr("dialogs.base.date_source.filename"):
            return 'filename' in source_lower
        
        # Filtro Filesystem: agrupa mtime, ctime, atime, birth
        if filter_value == tr("dialogs.base.date_source.filesystem"):
            filesystem_keywords = ['mtime', 'ctime', 'atime', 'birth', 'fs_']
            return any(kw in source_lower for kw in filesystem_keywords)
        
        # Coincidencia exacta como fallback
        return date_source == filter_value