# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Clase base para las stages de la interfaz de usuario.
Proporciona utilidades comunes como animaciones, persistencia y navegación.
"""

from typing import Optional, Callable
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QMainWindow, QGraphicsOpacityEffect, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QToolButton
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, QObject, QSize, Qt

from utils.settings_manager import settings_manager
from utils.logger import get_logger
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from config import Config
from utils.i18n import tr


class BaseStage(QObject):
    """
    Clase base abstracta para todas las stages de la UI.
    Define la interfaz común y proporciona utilidades compartidas.
    """

    def __init__(self, main_window: QMainWindow):
        """
        Inicializa la stage base.

        Args:
            main_window: Referencia a la ventana principal
        """
        super().__init__()
        self.main_window = main_window
        # Extraer el número del stage del nombre de la clase (Stage1Window -> 1)
        stage_num = ''.join(filter(str.isdigit, self.__class__.__name__))
        self.logger = get_logger(f'UI.Stage.{stage_num}')

        # Referencias a componentes compartidos
        self.main_layout = getattr(main_window, 'main_layout', None)

    def setup_ui(self) -> None:
        """
        Configura la interfaz de usuario para esta fase.
        Debe ser implementado por cada fase específica.
        """
        pass

    def cleanup(self) -> None:
        """
        Limpia los recursos y widgets de la fase actual.
        Debe ser implementado por cada fase específica.
        """
        pass

    def fade_out_widget(self, widget: QWidget, duration: int = 300,
                       on_finished: Optional[Callable] = None) -> None:
        """
        Aplica una animación de fade out a un widget.

        Args:
            widget: Widget a animar
            duration: Duración de la animación en ms
            on_finished: Callback opcional al terminar la animación
        """
        if not widget:
            return

        # Crear efecto de opacidad si no existe
        effect = widget.graphicsEffect()
        if not effect:
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        # Configurar animación
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Guardar referencia para evitar GC
        widget._fade_animation = animation

        # Conectar callback si se proporciona
        if on_finished:
            animation.finished.connect(on_finished)

        animation.start()

    def fade_in_widget(self, widget: QWidget, duration: int = 300) -> None:
        """
        Aplica una animación de fade in a un widget.

        Args:
            widget: Widget a animar
            duration: Duración de la animación en ms
        """
        if not widget:
            return

        # Crear efecto de opacidad si no existe
        effect = widget.graphicsEffect()
        if not effect:
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        # Configurar animación
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.InCubic)

        # Guardar referencia para evitar GC
        widget._fade_animation = animation

        animation.start()

    def load_last_folder(self) -> Optional[str]:
        """
        Carga la última carpeta analizada desde la configuración.

        Returns:
            Ruta de la última carpeta si existe y es válida, None en caso contrario
        """
        try:
            last_folder = settings_manager.get('last_analyzed_folder')
            if last_folder and Path(last_folder).exists():
                self.logger.debug(f"Last folder loaded: {last_folder}")
                return last_folder
            else:
                if last_folder:
                    self.logger.debug(f"Last folder invalid: {last_folder}")
                return None
        except Exception as e:
            self.logger.warning(f"Error loading last folder: {e}")
            return None

    def save_last_folder(self, folder_path: str) -> None:
        """
        Guarda la carpeta analizada en la configuración.

        Args:
            folder_path: Ruta de la carpeta a guardar
        """
        try:
            settings_manager.set('last_analyzed_folder', folder_path)
            self.logger.debug(f"Last folder saved: {folder_path}")
        except Exception as e:
            self.logger.warning(f"Error saving last folder: {e}")

    def save_analysis_results(self, results) -> None:
        """
        Guarda el resumen del análisis en la configuración.
        
        NOTA: La caché de metadatos NO se invalida aquí porque acabamos de
        crear una caché nueva y poblada que debe usarse en Stage 3.
        La invalidación solo debe hacerse después de operaciones destructivas
        (ver _invalidate_metadata_cache).

        Args:
            results: Resultados del análisis a guardar (objeto o dict)
        """
        try:
            # Si es un dataclass, convertir a dict para persistencia
            from dataclasses import is_dataclass, asdict
            if is_dataclass(results):
                # Antes de convertir a dict, remover metadata_cache del scan result
                # porque contiene un RLock que no se puede serializar
                if hasattr(results, 'scan') and hasattr(results.scan, 'metadata_cache'):
                    # Hacer una copia temporal sin la caché
                    import copy
                    results_copy = copy.copy(results)
                    results_copy.scan = copy.copy(results.scan)
                    results_copy.scan.metadata_cache = None
                    results_dict = asdict(results_copy)
                else:
                    results_dict = asdict(results)
            else:
                results_dict = results
                
            settings_manager.set('last_analysis_summary', results_dict)
            self.logger.debug("Analysis results saved")
        except Exception as e:
            self.logger.warning(f"Error saving analysis results: {e}")
    
    def _invalidate_metadata_cache(self) -> None:
        """
        Invalida completamente la caché de metadatos del singleton FileInfoRepositoryCache.
        
                CAUTION: This method should be used WITH GREAT CARE.
        
        Solo debe llamarse en situaciones excepcionales donde:
        - Ha ocurrido un error grave durante operaciones destructivas
        - La caché se ha corrompido o desincronizado
        - Se necesita forzar una recarga completa
        
        NO debe llamarse después de operaciones exitosas, ya que los servicios
        individuales actualizan la caché automáticamente (remove_file/move_file).
        
        Para operaciones normales, usar:
        - remove_file() para eliminaciones
        - move_file() para movimientos/renombrados
        """
        try:
            from services.file_metadata_repository_cache import FileInfoRepositoryCache
            
            # Obtener instancia singleton y limpiar completamente
            repo = FileInfoRepositoryCache.get_instance()
            entries_count = len(repo)
            
            if entries_count > 0:
                repo.clear()
                self.logger.warning(f"Metadata cache FULLY INVALIDATED ({entries_count} entries removed)")
            else:
                self.logger.debug("Metadata cache was already empty")
            
        except Exception as e:
            self.logger.error(f"Error invalidating metadata cache: {e}")

    def _invalidate_related_analysis_results(self, executed_tool_id: str) -> None:
        """
        Invalida los analysis_results de servicios relacionados después de una operación destructiva.
        
        Cuando una herramienta elimina archivos, los análisis de otras herramientas pueden
        quedar obsoletos porque contienen referencias a archivos que ya no existen.
        
        Este método limpia selectivamente los analysis_results que podrían verse afectados.
        
        Args:
            executed_tool_id: ID de la herramienta que acaba de ejecutarse
            
        Ejemplo:
            - Si se ejecuta 'live_photos' (elimina MOVs), los análisis de 'duplicates_exact',
              'duplicates_similar' y 'visual_identical' pueden tener grupos con esos MOVs.
        """
        if not hasattr(self, 'analysis_results') or self.analysis_results is None:
            return
        
        # Mapeo de qué análisis invalidar según la herramienta ejecutada
        # Las herramientas destructivas pueden afectar a cualquier otro análisis que trabaje con archivos
        destructive_tools = {
            'live_photos',      # Elimina MOV
            'heic',             # Elimina HEIC o JPG
            'duplicates_exact', # Elimina duplicados
            'duplicates_similar', # Elimina similares
            'visual_identical', # Elimina visualmente idénticos
            'zero_byte',        # Elimina archivos vacíos
        }
        
        # Si no es una herramienta destructiva, no hay nada que invalidar
        if executed_tool_id not in destructive_tools:
            return
        
        # Atributos de analysis_results que contienen datos de análisis de cada servicio
        analysis_attrs = {
            'live_photos': 'live_photos',
            'heic': 'heic',
            'duplicates_exact': 'duplicates',
            'duplicates_similar': 'duplicates_similar',
            'visual_identical': 'visual_identical',
            'zero_byte': 'zero_byte',
        }
        
        # Invalidar TODOS los análisis de herramientas destructivas excepto el que acaba de ejecutarse
        # (el que acaba de ejecutarse puede re-analizarse si el usuario lo desea)
        invalidated = []
        for tool_id, attr_name in analysis_attrs.items():
            if tool_id != executed_tool_id and hasattr(self.analysis_results, attr_name):
                current_value = getattr(self.analysis_results, attr_name, None)
                if current_value is not None:
                    setattr(self.analysis_results, attr_name, None)
                    invalidated.append(tool_id)
        
        if invalidated:
            self.logger.info(
                f"Analyses invalidated after {executed_tool_id}: {', '.join(invalidated)}. "
                f"They will be re-analyzed when clicking on each tool."
            )

    def get_analysis_summary(self) -> Optional[dict]:
        """
        Obtiene el resumen del último análisis desde la configuración.

        Returns:
            Diccionario con el resumen del análisis o None si no existe
        """
        try:
            return settings_manager.get('last_analysis_summary')
        except Exception as e:
            self.logger.warning(f"Error getting analysis summary: {e}")
            return None

    def transition_to_state(self, state_class: type, *args, **kwargs) -> None:
        """
        Transición genérica a otro estado.

        Args:
            state_class: Clase del estado al que transicionar
            *args, **kwargs: Argumentos para pasar al nuevo estado
        """
        # Limpiar estado actual
        self.cleanup()

        # Crear nuevo estado
        new_state = state_class(self.main_window, *args, **kwargs)

        # Configurar nuevo estado (protected against unhandled exceptions)
        try:
            new_state.setup_ui()
        except Exception as e:
            self.logger.critical(f"Fatal error during {state_class.__name__}.setup_ui(): {e}", exc_info=True)
            return

        # Actualizar referencia en main_window
        self.main_window.current_state = new_state

        self.logger.info(f"Transition completed to {state_class.__name__}")

    def create_header(self, 
                           title_text: Optional[str] = None,
                           subtitle_text: Optional[str] = None,
                           show_settings_button: bool = True,
                           show_about_button: bool = True,
                           on_settings_clicked: Optional[Callable] = None, 
                           on_about_clicked: Optional[Callable] = None) -> QFrame:
        """
        Crea la card de header profesional compartida entre stages.

        Args:
            title_text: Texto opcional para el título (por defecto usa "{APP_NAME}")
            subtitle_text: Texto opcional para el subtítulo (por defecto vacío)
            show_settings_button: Si mostrar el botón de configuración
            show_about_button: Si mostrar el botón "Acerca de"
            on_settings_clicked: Callback opcional para el botón de configuración
            on_about_clicked: Callback opcional para el botón "Acerca de"

        Returns:
            QFrame: La card de header
        """
        card = QFrame()
        card.setObjectName("headerCard")
        card.setStyleSheet(DesignSystem.get_header_style())

        # Layout horizontal con mejor organización
        layout = QHBoxLayout(card)
        layout.setSpacing(DesignSystem.SPACE_12)
        layout.setContentsMargins(0, 0, 0, 0)

        # Logo/Icono de la aplicación con fondo sutil
        icon_container = QFrame()
        icon_container.setFixedSize(56, 56)  # Tamaño fijo para que sea protagonista
        icon_container.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.COLOR_PRIMARY_LIGHT};
                border-radius: {DesignSystem.RADIUS_MD}px;
                padding: 0px;
                border: none;
            }}
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        app_icon = QLabel()
        ICON_SIZE_HEADER = 48  # Aumentado para llenar el contenedor de 56px
        if Config.APP_ICON_PATH.exists():
            pixmap = QPixmap(str(Config.APP_ICON_PATH))
            if not pixmap.isNull():
                # Escalar el icono para que ocupe casi todo el contenedor
                scaled_pixmap = pixmap.scaled(
                    ICON_SIZE_HEADER, 
                    ICON_SIZE_HEADER, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                app_icon.setPixmap(scaled_pixmap)
                app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                icon_manager.set_label_icon(app_icon, 'camera', color=DesignSystem.COLOR_PRIMARY, size=ICON_SIZE_HEADER)
        else:
            icon_manager.set_label_icon(app_icon, 'camera', color=DesignSystem.COLOR_PRIMARY, size=ICON_SIZE_HEADER)
        
        icon_layout.addWidget(app_icon)
        layout.addWidget(icon_container)

        # Contenedor de texto (título + subtítulo verticalmente)
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        # Título principal con versión pequeña a la derecha
        title = title_text if title_text is not None else Config.APP_NAME
        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(12)
        title_row_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        welcome_title = QLabel(title)
        welcome_title.setStyleSheet(DesignSystem.get_stage_title_style())
        title_row_layout.addWidget(welcome_title)

        by_label = QLabel("by safetoolhub.org")
        by_label.setStyleSheet(DesignSystem.get_header_brand_label_style())
        by_label.setAlignment(Qt.AlignmentFlag.AlignBottom)
        title_row_layout.addWidget(by_label)
        title_row_layout.addStretch()

        text_layout.addWidget(title_row)

        # Subtítulo (si se proporciona)
        if subtitle_text:
            welcome_subtitle = QLabel(subtitle_text)
            welcome_subtitle.setStyleSheet(DesignSystem.get_stage_subtitle_style())
            text_layout.addWidget(welcome_subtitle)

        layout.addWidget(text_container)

        # Espaciador para empujar botones a la derecha
        layout.addStretch()

        # Botones de acción (solo si se proporcionan callbacks y están habilitados)
        if show_settings_button and on_settings_clicked:
            btn_settings = QToolButton()
            btn_settings.setAutoRaise(True)
            btn_settings.setToolTip(tr("common.tooltip.settings"))
            icon_manager.set_button_icon(btn_settings, 'cog', color=DesignSystem.COLOR_TEXT_SECONDARY, size=20)
            btn_settings.setIconSize(QSize(20, 20))
            btn_settings.clicked.connect(on_settings_clicked)
            btn_settings.setStyleSheet(DesignSystem.get_icon_button_style())
            layout.addWidget(btn_settings)

        if show_about_button and on_about_clicked:
            btn_about = QToolButton()
            btn_about.setAutoRaise(True)
            btn_about.setToolTip(tr("common.tooltip.about"))
            icon_manager.set_button_icon(btn_about, 'information-outline', color=DesignSystem.COLOR_TEXT_SECONDARY, size=20)
            btn_about.setIconSize(QSize(20, 20))
            btn_about.clicked.connect(on_about_clicked)
            btn_about.setStyleSheet(DesignSystem.get_icon_button_style())
            layout.addWidget(btn_about)

        return card