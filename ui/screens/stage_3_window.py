# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Stage 3: Grid de herramientas.
Muestra el resumen del análisis y el grid de herramientas disponibles.
"""

from pathlib import Path
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QGridLayout, QMessageBox,
    QDialog, QPushButton
)
from PyQt6.QtCore import QTimer, Qt
import qtawesome as qta

from config import Config
from utils.settings_manager import settings_manager, SettingsManager
from .base_stage import BaseStage
from ui.styles.design_system import DesignSystem
from ui.styles.icons import icon_manager
from ui.tools_definitions import get_tool_title, CATEGORY_CLEANUP, CATEGORY_VISUAL, CATEGORY_ORGANIZATION
from ui.screens.summary_card import SummaryCard
from ui.screens.tool_card import ToolCard
from ui.dialogs.live_photos_dialog import LivePhotosDialog
from ui.dialogs.heic_dialog import HeicDialog
from ui.dialogs.duplicates_exact_dialog import DuplicatesExactDialog
from ui.dialogs.file_organizer_dialog import FileOrganizerDialog
from ui.dialogs.file_renamer_dialog import FileRenamerDialog
from ui.dialogs.zero_byte_dialog import ZeroByteDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.about_dialog import AboutDialog
from ui.dialogs.visual_identical_dialog import VisualIdenticalDialog
from ui.dialogs.duplicates_similar_dialog import DuplicatesSimilarDialog
from utils.format_utils import format_size, format_file_count
from utils.logger import log_section_header_discrete
from utils.i18n import tr
from services.file_metadata_repository_cache import FileInfoRepositoryCache

# Importar tool cards
from ui.screens.tool_cards import (
    create_live_photos_card,
    create_heic_card,
    create_duplicates_exact_card,
    create_duplicates_similar_card,
    create_visual_identical_card,
    create_file_organizer_card,
    create_file_renamer_card,
    create_zero_byte_card,
)


class Stage3Window(BaseStage):
    """
    Stage 3: Grid de herramientas.
    Muestra resumen del análisis y herramientas disponibles para ejecutar.
    """

    def __init__(self, main_window, selected_folder: str, analysis_results: Dict[str, Any]):
        super().__init__(main_window)

        # Parámetros del estado
        self.selected_folder = selected_folder
        self.analysis_results = analysis_results
        
        # Extraer metadata_cache del análisis para reutilizarla
        self.metadata_cache = None
        if analysis_results and analysis_results.scan:
            scan_data = analysis_results.scan
            if hasattr(scan_data, 'metadata_cache') and scan_data.metadata_cache:
                self.metadata_cache = scan_data.metadata_cache
                self.logger.debug("Metadata cache available from initial analysis")

        # Referencias a widgets del estado
        self.header = None
        self.stale_banner = None
        self.summary_card = None
        self.tools_grid = None
        self.tool_cards = {}  # Dict de tool_id -> ToolCard


    def setup_ui(self) -> None:
        """Configura la interfaz de usuario del Stage 3."""
        self.logger.debug("Setting up Stage 3 UI")

        # Limpiar el layout principal antes de agregar nuevos widgets
        while self.main_layout.count():
            child = self.main_layout.takeAt(0)
            if child.widget():
                child.widget().hide()
                child.widget().setParent(None)

        # Añadir espaciado encima del header
        self.main_layout.addSpacing(2)

        # Crear y mostrar header
        self.header = self.create_header(
            on_settings_clicked=self._on_settings_clicked,
            on_about_clicked=self._on_about_clicked
        )
        self.main_layout.addWidget(self.header)
        self.main_layout.addSpacing(DesignSystem.SPACE_4)  # Reducido de SPACE_6 para optimizar espacio vertical

        # Crear banner de advertencia (oculto por defecto)
        self.stale_banner = self._create_stale_banner()
        self.main_layout.addWidget(self.stale_banner)
        
        # Iniciar creación de UI
        self._show_summary_card()
        self._create_tools_grid()

        self.logger.debug("Stage 3 UI configured")

    def cleanup(self) -> None:
        """Limpia los recursos del Stage 3."""
        self.logger.debug("Cleaning up Stage 3")

        # Limpiar referencias
        if self.header:
            self.header.hide()
            self.header.setParent(None)
            self.header = None

        if self.stale_banner:
            self.stale_banner.hide()
            self.stale_banner.setParent(None)
            self.stale_banner = None

        if self.summary_card:
            self.summary_card.hide()
            self.summary_card.setParent(None)
            self.summary_card = None

        if self.tools_grid:
            self.tools_grid.hide()
            self.tools_grid.setParent(None)
            self.tools_grid = None

        self.tool_cards.clear()

    def _cleanup_grid_section(self) -> None:
        """
        Elimina todos los items del layout principal que están después del summary_card.
        Esto incluye: spacings, tools_grid, y stretches añadidos en _create_tools_grid.
        Necesario para evitar acumulación de gaps al recrear el grid.
        """
        if not self.summary_card:
            return
        
        # Encontrar el índice del summary_card en el layout
        summary_index = -1
        for i in range(self.main_layout.count()):
            item = self.main_layout.itemAt(i)
            if item and item.widget() == self.summary_card:
                summary_index = i
                break
        
        if summary_index == -1:
            return
        
        # Eliminar todos los items después del summary_card (en orden inverso)
        while self.main_layout.count() > summary_index + 1:
            item = self.main_layout.takeAt(summary_index + 1)
            if item:
                widget = item.widget()
                if widget:
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()
                # Los spacers y stretches no tienen widget, se eliminan automáticamente con takeAt
        
        self.tools_grid = None

    def _create_stale_banner(self) -> QWidget:
        """Crea el banner de advertencia de estadísticas desactualizadas"""
        parent_widget = self.main_window.centralWidget() if self.main_window.centralWidget() else self.main_window
        banner = QFrame(parent_widget)
        banner.setObjectName("staleBanner")
        
        # Estilo del banner
        banner.setStyleSheet(DesignSystem.get_stale_banner_style())
        
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(DesignSystem.SPACE_16, DesignSystem.SPACE_12, 
                                 DesignSystem.SPACE_16, DesignSystem.SPACE_12)
        layout.setSpacing(DesignSystem.SPACE_16)
        
        # Icono
        icon_label = QLabel()
        icon = qta.icon('fa5s.exclamation-triangle', color=DesignSystem.COLOR_WARNING)
        icon_label.setPixmap(icon.pixmap(24, 24))
        layout.addWidget(icon_label)
        
        # Mensaje
        msg_label = QLabel(tr("stage3.banner.stale_stats"))
        msg_label.setStyleSheet(f"color: {DesignSystem.COLOR_TEXT}; font-size: {DesignSystem.FONT_SIZE_BASE}px;")
        layout.addWidget(msg_label)
        
        layout.addStretch()
        
        # Botón de re-análisis
        btn = QPushButton(tr("stage3.button.reanalyze_now"))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIcon(qta.icon('fa5s.sync-alt', color=DesignSystem.COLOR_TEXT))
        btn.setStyleSheet(DesignSystem.get_warning_button_style())
        btn.clicked.connect(self._on_reanalyze)
        layout.addWidget(btn)
        
        banner.hide()
        return banner

    def _show_summary_card(self):
        """Muestra la summary card"""
        # Crear y mostrar summary card
        self.summary_card = SummaryCard(self.selected_folder)
        self.summary_card.change_folder_requested.connect(self._on_change_folder)
        self.summary_card.reanalyze_requested.connect(self._on_reanalyze)
        
        # Añadir al layout principal
        self.main_layout.addWidget(self.summary_card)

        # Actualizar estadísticas de la summary card
        total_files = 0
        total_size = 0
        num_images = 0
        num_videos = 0
        num_others = 0
        
        if self.analysis_results and hasattr(self.analysis_results, 'scan'):
            scan = self.analysis_results.scan
            total_files = scan.total_files
            total_size = scan.total_size
            num_images = len(scan.images) if hasattr(scan, 'images') else 0
            num_videos = len(scan.videos) if hasattr(scan, 'videos') else 0
            num_others = len(scan.others) if hasattr(scan, 'others') else 0

        # Mostrar estadísticas
        self.summary_card.update_stats(total_files, total_size, num_images, num_videos, num_others)

    def _create_tools_grid(self):
        """Crea el grid categorizado de herramientas"""
        # Limpiar todos los items del layout después del summary_card
        # Esto incluye: spacing, tools_grid previo, y stretch
        self._cleanup_grid_section()
        
        self.tool_cards.clear()
        
        # Container principal para el grid
        grid_container = QWidget()
        main_grid_layout = QVBoxLayout(grid_container)
        main_grid_layout.setSpacing(DesignSystem.SPACE_12) # Aún más reducido
        main_grid_layout.setContentsMargins(0, 0, 0, 0)

        # Helper para crear secciones
        def create_section(title, icon_name):
            section_widget = QWidget()
            section_layout = QVBoxLayout(section_widget)
            section_layout.setSpacing(DesignSystem.SPACE_4) # Mínimo
            section_layout.setContentsMargins(0, 0, 0, 0)
            
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(0, 0, 0, 0)
            icon_label = QLabel()
            icon_manager.set_label_icon(icon_label, icon_name, color=DesignSystem.COLOR_TEXT_SECONDARY, size=12)
            header_layout.addWidget(icon_label)
            
            title_label = QLabel(title.upper())
            title_label.setStyleSheet(DesignSystem.get_section_title_style())
            header_layout.addWidget(title_label)
            header_layout.addStretch()
            section_layout.addLayout(header_layout)
            
            grid = QGridLayout()
            grid.setSpacing(DesignSystem.SPACE_8) # Más compacto
            # Asegurar que las columnas tengan el mismo ancho
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            section_layout.addLayout(grid)
            return section_widget, grid

        # 1. SECCIÓN: LIMPIEZA Y ESPACIO
        cleanup_section, cleanup_grid = create_section(CATEGORY_CLEANUP.title, "delete-sweep")
        
        # Cards de limpieza
        zero_byte_card = create_zero_byte_card(self.analysis_results, self._on_tool_clicked)
        heic_card = create_heic_card(self.analysis_results, self._on_tool_clicked)
        live_photos_card = create_live_photos_card(self.analysis_results, self._on_tool_clicked)
        exact_dup_card = create_duplicates_exact_card(self.analysis_results, self._on_tool_clicked)
        
        cleanup_grid.addWidget(zero_byte_card, 0, 0)
        cleanup_grid.addWidget(heic_card, 0, 1)
        cleanup_grid.addWidget(live_photos_card, 1, 0)
        cleanup_grid.addWidget(exact_dup_card, 1, 1)
        
        self.tool_cards['zero_byte'] = zero_byte_card
        self.tool_cards['heic'] = heic_card
        self.tool_cards['live_photos'] = live_photos_card
        self.tool_cards['duplicates_exact'] = exact_dup_card
        
        main_grid_layout.addWidget(cleanup_section)

        # 2. SECCIÓN: DETECCIÓN VISUAL
        similar_section, similar_grid = create_section(CATEGORY_VISUAL.title, "image-search")
        
        # Card de copias visuales idénticas (100% similitud)
        visual_identical_card = create_visual_identical_card(self.analysis_results, self._on_tool_clicked)
        similar_grid.addWidget(visual_identical_card, 0, 0)
        self.tool_cards['visual_identical'] = visual_identical_card
        
        # Card de archivos similares (sensibilidad ajustable)
        similar_dup_card = create_duplicates_similar_card(self.analysis_results, self._on_tool_clicked)
        similar_grid.addWidget(similar_dup_card, 0, 1)
        self.tool_cards['duplicates_similar'] = similar_dup_card
        
        main_grid_layout.addWidget(similar_section)

        # 3. SECCIÓN: ORGANIZACIÓN
        org_section, org_grid = create_section(CATEGORY_ORGANIZATION.title, "folder-move")
        organize_card = create_file_organizer_card(self._on_tool_clicked)
        rename_card = create_file_renamer_card(self._on_tool_clicked)
        org_grid.addWidget(organize_card, 0, 0)
        org_grid.addWidget(rename_card, 0, 1)
        self.tool_cards['file_organizer'] = organize_card
        self.tool_cards['file_renamer'] = rename_card
        main_grid_layout.addWidget(org_section)

        # Añadir al layout principal
        self.main_layout.addSpacing(DesignSystem.SPACE_16)
        self.main_layout.addWidget(grid_container)
        
        self.tools_grid = grid_container
        
        # Añadir stretch al final del layout principal para empujar todo hacia arriba
        self.main_layout.addStretch()

        # Update scroll
        if hasattr(self.main_window, 'scroll_area'):
            self.main_window.scroll_area.update()



    # Card creation methods moved to ui/screens/tool_cards/
    # They are now imported as functions

    def _on_tool_clicked(self, tool_id: str):
        """
        Maneja el clic en una tool card y abre el diálogo correspondiente
        """
        self.logger.info(f"Tool clicked: {tool_id}")

        if not self.analysis_results:
            QMessageBox.warning(self.main_window, tr("common.error"), tr("stage3.error.no_analysis_data"))
            return

        # Verificar si necesitamos ejecutar análisis primero (usando hasattr)
        # NOTA: file_renamer y file_organizer SIEMPRE requieren análisis fresco porque
        # modifican los archivos (nombres/ubicaciones) y el análisis previo queda obsoleto
        should_analyze = False
        
        if tool_id == 'live_photos' and not (hasattr(self.analysis_results, 'live_photos') and self.analysis_results.live_photos):
            should_analyze = True
        elif tool_id == 'heic' and not (hasattr(self.analysis_results, 'heic') and self.analysis_results.heic):
            should_analyze = True
        elif tool_id == 'duplicates_exact' and not (hasattr(self.analysis_results, 'duplicates') and self.analysis_results.duplicates):
            should_analyze = True
        elif tool_id == 'zero_byte' and not (hasattr(self.analysis_results, 'zero_byte') and self.analysis_results.zero_byte):
            should_analyze = True
        elif tool_id == 'visual_identical' and not (hasattr(self.analysis_results, 'visual_identical') and self.analysis_results.visual_identical):
            should_analyze = True
        elif tool_id == 'duplicates_similar' and not (hasattr(self.analysis_results, 'duplicates_similar') and self.analysis_results.duplicates_similar):
            should_analyze = True
        elif tool_id == 'file_organizer':
            # SIEMPRE analizar file_organizer (modifica ubicaciones de archivos)
            should_analyze = True
        elif tool_id == 'file_renamer':
            # SIEMPRE analizar file_renamer (modifica nombres de archivos)
            should_analyze = True
            
        if should_analyze:
            # Ejecutar análisis bajo demanda
            self._run_analysis_and_open_dialog(tool_id)
            return
        
        # Si ya tenemos datos, abrir el diálogo
        self._open_tool_dialog(tool_id)
    
    def _open_tool_dialog(self, tool_id: str):
        """
        Abre el diálogo correspondiente a una herramienta sin hacer análisis.
        Asume que el análisis ya está disponible en self.analysis_results.
        """
        # Abrir diálogo correspondiente si ya tenemos datos
        dialog = None
        
        if tool_id == 'live_photos':
            if hasattr(self.analysis_results, 'live_photos') and self.analysis_results.live_photos:
                live_photo_data = self.analysis_results.live_photos
                if live_photo_data.items_count > 0:
                    dialog = LivePhotosDialog(live_photo_data, self.main_window)
                else:
                    QMessageBox.information(self.main_window, tr("common.info"), tr("stage3.info.no_live_photos"))

        elif tool_id == 'heic':
            if hasattr(self.analysis_results, 'heic') and self.analysis_results.heic:
                heic_data = self.analysis_results.heic
                if heic_data.items_count > 0:
                    dialog = HeicDialog(heic_data, self.main_window)
                else:
                     QMessageBox.information(self.main_window, tr("common.info"), tr("stage3.info.no_heic_pairs"))

        elif tool_id == 'duplicates_exact':
            if hasattr(self.analysis_results, 'duplicates') and self.analysis_results.duplicates:
                dup_data = self.analysis_results.duplicates
                if dup_data.total_groups > 0:
                    dialog = DuplicatesExactDialog(dup_data, self.main_window)
                else:
                     QMessageBox.information(self.main_window, tr("common.info"), tr("stage3.info.no_exact_copies"))

        elif tool_id == 'visual_identical':
            if hasattr(self.analysis_results, 'visual_identical') and self.analysis_results.visual_identical:
                vi_data = self.analysis_results.visual_identical
                if vi_data.total_groups > 0:
                    dialog = VisualIdenticalDialog(vi_data, self.main_window)
                else:
                    QMessageBox.information(
                        self.main_window, 
                        tr("stage3.info.no_visual_identical_title"), 
                        tr("stage3.info.no_visual_identical_msg")
                    )

        elif tool_id == 'duplicates_similar':
            if hasattr(self.analysis_results, 'duplicates_similar') and self.analysis_results.duplicates_similar:
                sim_data = self.analysis_results.duplicates_similar
                # DuplicatesSimilarAnalysis contiene perceptual_hashes, no total_groups
                # El diálogo genera los grupos dinámicamente con get_groups()
                if len(sim_data.perceptual_hashes) > 0:
                    dialog = DuplicatesSimilarDialog(sim_data, self.main_window)
                else:
                    QMessageBox.information(
                        self.main_window, 
                        tr("stage3.info.no_files_to_analyze_title"), 
                        tr("stage3.info.no_files_to_analyze_msg")
                    )

        elif tool_id == 'file_organizer':
            # Organizing puede funcionar sin análisis previo (usa defaults o analiza on-fly)
            org_data = getattr(self.analysis_results, 'organization', None) if hasattr(self.analysis_results, 'organization') else None
            dialog = FileOrganizerDialog(org_data, self.main_window)

        elif tool_id == 'file_renamer':
            # Renaming igual
            rename_data = getattr(self.analysis_results, 'renaming', None) if hasattr(self.analysis_results, 'renaming') else None
            dialog = FileRenamerDialog(rename_data, self.main_window)
            
        elif tool_id == 'zero_byte':
            if hasattr(self.analysis_results, 'zero_byte') and self.analysis_results.zero_byte:
                zero_byte_data = self.analysis_results.zero_byte
                if zero_byte_data.items_count > 0:
                    dialog = ZeroByteDialog(zero_byte_data, self.main_window)
                else:
                     QMessageBox.information(self.main_window, tr("common.info"), tr("stage3.info.no_empty_files"))

        if dialog:
            result = dialog.exec()
            # Si el usuario aceptó el diálogo, ejecutar las acciones
            if result == QDialog.DialogCode.Accepted:
                self._execute_tool_action(tool_id, dialog)
            else:
                # Diálogo cancelado: refrescar el grid para actualizar estados de las cards.
                # Necesario porque algunos diálogos modifican el estado interno del análisis
                # durante su ejecución (ej: duplicates_similar caching de clustering).
                self._create_tools_grid()
            
    def _run_analysis_and_open_dialog(self, tool_id: str):
        """
        Ejecuta el análisis específico para una herramienta y luego abre su diálogo.
        """
        from ui.workers import (
            LivePhotosAnalysisWorker,
            HeicAnalysisWorker,
            DuplicatesExactAnalysisWorker,
            DuplicatesSimilarAnalysisWorker,
            VisualIdenticalAnalysisWorker,
            ZeroByteAnalysisWorker,
            FileOrganizerAnalysisWorker,
            FileRenamerAnalysisWorker
        )
        from PyQt6.QtWidgets import QProgressDialog
        
        # Mapeo de tool_id a Worker Class
        worker_map = {
            'live_photos': (LivePhotosAnalysisWorker, tr("stage3.progress.analyzing_live_photos")),
            'heic': (HeicAnalysisWorker, tr("stage3.progress.searching_heic")),
            'duplicates_exact': (DuplicatesExactAnalysisWorker, tr("stage3.progress.searching_exact_copies")),
            'visual_identical': (VisualIdenticalAnalysisWorker, tr("stage3.progress.searching_visual_identical")),
            'duplicates_similar': (DuplicatesSimilarAnalysisWorker, tr("stage3.progress.analyzing_similar")),
            'zero_byte': (ZeroByteAnalysisWorker, tr("stage3.progress.searching_empty_files")),
            'file_organizer': (FileOrganizerAnalysisWorker, tr("stage3.progress.analyzing_structure")),
            'file_renamer': (FileRenamerAnalysisWorker, tr("stage3.progress.analyzing_names"))
        }
        
        if tool_id not in worker_map:
            return

        WorkerClass, message = worker_map[tool_id]
        
        # Crear diálogo de progreso
        progress = QProgressDialog(message, "Cancelar", 0, 0, self.main_window)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.resize(450, 120)  # Ancho aumentado para que el texto no se corte
        
        # Crear worker - algunos servicios ya no necesitan metadata_cache
        refactorized_tools = {'live_photos', 'heic', 'duplicates_exact', 'visual_identical', 'zero_byte', 'file_renamer', 'file_organizer'}
        if tool_id in refactorized_tools:
            worker = WorkerClass(Path(self.selected_folder))
        elif tool_id == 'duplicates_similar':
            # DuplicatesSimilarAnalysisWorker necesita directory y opcionalmente sensibilidad
            worker = WorkerClass(Path(self.selected_folder), sensitivity=85)
        else:
            worker = WorkerClass(Path(self.selected_folder), self.metadata_cache)
        
        def on_finished(result):
            progress.close()
            if result:
                # Guardar resultado en analysis_results
                if tool_id == 'live_photos':
                    self.analysis_results.live_photos = result
                    # Refrescar el grid completo para actualizar la card
                    self._create_tools_grid()
                    
                elif tool_id == 'heic':
                    self.analysis_results.heic = result
                    self._create_tools_grid()
                    
                elif tool_id == 'duplicates_exact':
                    self.analysis_results.duplicates = result
                    self._create_tools_grid()
                    
                elif tool_id == 'visual_identical':
                    self.analysis_results.visual_identical = result
                    self._create_tools_grid()
                    
                elif tool_id == 'duplicates_similar':
                    self.analysis_results.duplicates_similar = result
                    self._create_tools_grid()
                    
                elif tool_id == 'zero_byte':
                    self.analysis_results.zero_byte = result
                    self._create_tools_grid()
                
                elif tool_id == 'file_organizer':
                    self.analysis_results.organization = result
                    self._create_tools_grid()
                
                elif tool_id == 'file_renamer':
                    self.analysis_results.renaming = result
                    self._create_tools_grid()
                
                # Abrir el diálogo automáticamente, pero sin volver a analizar
                self._open_tool_dialog(tool_id)
                
            worker.deleteLater()
            
        def on_error(msg):
            progress.close()
            QMessageBox.critical(self.main_window, tr("common.error"), tr("stage3.error.analysis_failed", msg=msg))
            worker.deleteLater()
            
        def on_progress_update(current, total, msg):
            # Si total > 0, usar barra determinada. Si no, indeterminada.
            if total > 0:
                if progress.maximum() != total:
                    progress.setMaximum(total)
                progress.setValue(current)
            else:
                if progress.maximum() != 0:
                    progress.setMaximum(0)
                    progress.setValue(0)
            
            progress.setLabelText(f"{message}\n{msg}")

        worker.progress_update.connect(on_progress_update)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        
        progress.canceled.connect(worker.stop)
        worker.start()
        progress.exec()
    
    def _execute_tool_action(self, tool_id: str, dialog):
        """
        Ejecuta las acciones de una herramienta usando el worker correspondiente.
        
        Args:
            tool_id: ID de la herramienta ('live_photos', 'heic', etc)
            dialog: Diálogo que contiene el accepted_plan
        """
        from ui.workers import (
            LivePhotosExecutionWorker,
            HeicExecutionWorker,
            DuplicatesExecutionWorker,
            VisualIdenticalExecutionWorker,
            FileOrganizerExecutionWorker,
            FileRenamerExecutionWorker,
            ZeroByteExecutionWorker,
        )
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        
        if not hasattr(dialog, 'accepted_plan'):
            self.logger.warning(f"Dialog for {tool_id} has no accepted_plan")
            return
        
        plan = dialog.accepted_plan
        self.logger.info(f"Executing actions for {tool_id} with plan: {list(plan.keys()) if isinstance(plan, dict) else type(plan)}")
        
        # === VERIFICAR CONFIRMACIÓN ADICIONAL PARA ELIMINACIÓN ===
        # Lista de herramientas destructivas (que eliminan archivos)
        destructive_tools = ['live_photos', 'heic', 'duplicates_exact', 'duplicates_similar', 'visual_identical', 'zero_byte']
        
        # Solo pedir confirmación si es una operación real (no simulada)
        is_dry_run = plan.get('dry_run', False)
        
        if tool_id in destructive_tools and not is_dry_run and settings_manager.get_confirm_delete():
            reply = QMessageBox.question(
                self.main_window,
                tr("stage3.confirm.delete_title"),
                tr("stage3.confirm.delete_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.logger.info(f"Operation {tool_id} cancelled by user at additional confirmation")
                return

        # Crear diálogo de progreso
        progress_dialog = QProgressDialog(
            tr("stage3.progress.executing_operation"),
            tr("common.cancel"),
            0, 100,
            self.main_window
        )
        progress_dialog.setWindowTitle(tr("stage3.progress.processing_title"))
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setValue(0)
        progress_dialog.resize(450, 120)  # Ancho aumentado para que el texto no se corte
        
        # Crear worker según la herramienta
        worker = None
        
        if tool_id == 'live_photos':
            from services.live_photos_service import LivePhotoService
            service = LivePhotoService()
            # LivePhotosExecutionWorker espera (service, analysis: dataclass, create_backup, dry_run)
            worker = LivePhotosExecutionWorker(
                service,
                analysis=plan.get('analysis'),
                create_backup=plan.get('create_backup', True),
                dry_run=plan.get('dry_run', False)
            )
        
        elif tool_id == 'heic':
            from services.heic_service import HeicService
            service = HeicService()
            # HeicExecutionWorker espera (service, analysis: dataclass, keep_format, create_backup, dry_run)
            worker = HeicExecutionWorker(
                service=service,
                analysis=plan.get('analysis'),
                keep_format=plan.get('keep_format', 'jpg'),
                create_backup=plan.get('create_backup', True),
                dry_run=plan.get('dry_run', False)
            )
        
        elif tool_id == 'duplicates_exact':
            from services.duplicates_exact_service import DuplicatesExactService
            detector = DuplicatesExactService()
            # DuplicatesExecutionWorker espera (detector, analysis: dataclass, keep_strategy, create_backup, dry_run, metadata_cache)
            worker = DuplicatesExecutionWorker(
                detector=detector,
                analysis=plan.get('analysis'),
                keep_strategy=plan.get('keep_strategy', 'first'),
                create_backup=plan.get('create_backup', True),
                dry_run=plan.get('dry_run', False),
                metadata_cache=self.metadata_cache,
                files_to_delete=plan.get('files_to_delete')
            )
        
        elif tool_id == 'duplicates_similar':
            from services.duplicates_similar_service import DuplicatesSimilarService
            detector = DuplicatesSimilarService()
            # DuplicatesExecutionWorker espera (detector, analysis: dataclass, keep_strategy, create_backup, dry_run, metadata_cache)
            worker = DuplicatesExecutionWorker(
                detector=detector,
                analysis=plan.get('analysis'),
                keep_strategy=plan.get('keep_strategy', 'manual'),
                create_backup=plan.get('create_backup', True),
                dry_run=plan.get('dry_run', False),
                metadata_cache=self.metadata_cache,
                files_to_delete=plan.get('files_to_delete')
            )
        
        elif tool_id == 'file_organizer':
            from services.file_organizer_service import FileOrganizerService
            organizer = FileOrganizerService()
            # FileOrganizerExecutionWorker espera (organizer, analysis: dataclass, cleanup_empty_dirs, create_backup, dry_run)
            worker = FileOrganizerExecutionWorker(
                organizer=organizer,
                analysis=plan.get('analysis'),
                cleanup_empty_dirs=plan.get('cleanup_empty_dirs', True),
                create_backup=plan.get('create_backup', True),
                dry_run=plan.get('dry_run', False)
            )
        
        elif tool_id == 'file_renamer':
            from services.file_renamer_service import FileRenamerService
            renamer = FileRenamerService()
            # FileRenamerExecutionWorker espera (renamer, analysis: dataclass, create_backup, dry_run)
            worker = FileRenamerExecutionWorker(
                renamer=renamer,
                analysis=plan.get('analysis'),
                create_backup=plan.get('create_backup', True),
                dry_run=plan.get('dry_run', False)
            )

        elif tool_id == 'zero_byte':
            from services.zero_byte_service import ZeroByteService
            service = ZeroByteService()
            # ZeroByteExecutionWorker espera (service, analysis: dataclass, create_backup, dry_run)
            worker = ZeroByteExecutionWorker(
                service=service,
                analysis=plan.get('analysis'),
                create_backup=plan.get('create_backup', True),
                dry_run=plan.get('dry_run', False)
            )
        
        elif tool_id == 'visual_identical':
            from services.visual_identical_service import VisualIdenticalService
            service = VisualIdenticalService()
            # VisualIdenticalExecutionWorker espera (service, groups, files_to_delete, create_backup, dry_run)
            worker = VisualIdenticalExecutionWorker(
                service=service,
                groups=plan.get('groups', []),
                files_to_delete=plan.get('files_to_delete', []),
                create_backup=plan.get('create_backup', True),
                dry_run=plan.get('dry_run', False)
            )
        
        if not worker:
            self.logger.error(f"Could not create worker for {tool_id}")
            return
        
        # Variable para controlar si ya se canceló
        is_cancelled = False
        
        # Conectar señales del worker
        def on_progress(current, total, message):
            # Ignorar actualizaciones si ya se canceló
            if is_cancelled:
                return
            if total > 0:
                progress_dialog.setValue(int((current / total) * 100))
            progress_dialog.setLabelText(message)
        
        def on_finished(result):
            # Ignorar si ya se canceló
            if is_cancelled:
                return
            
            # Desconectar señal de cancelación antes de cerrar
            try:
                progress_dialog.canceled.disconnect(on_cancel)
            except (RuntimeError, TypeError):
                pass
            
            progress_dialog.close()
            
            # Registrar resultado
            log_msg = f"Operation {tool_id} completed"
            if hasattr(result, 'success'):
                log_msg += f" (Success={result.success})"
            self.logger.info(log_msg)
            
            # Log detallado en debug para no inundar el info con listas enormes de archivos
            self.logger.debug(f"Detailed result for {tool_id}: {result}")
            
            # Mostrar resultado
            if result and hasattr(result, 'success') and result.success:
                # Build standardized success message
                was_simulation = plan.get('dry_run', False)
                has_backup = plan.get('create_backup', False)
                message, title = self._build_success_message(result, was_simulation, has_backup, tool_id)
                
                # Show success message using standard QMessageBox
                QMessageBox.information(
                    self.main_window,
                    title,
                    message
                )
                
                # Only ask for re-analysis if operation was NOT simulated
                # Simulated operations (dry_run=True) don't modify files, so re-analysis is unnecessary
                was_simulation = plan.get('dry_run', False)
                
                # ================================================================
                # INVALIDAR ANÁLISIS RELACIONADOS DESPUÉS DE OPERACIÓN DESTRUCTIVA
                # Esto previene que otras herramientas usen datos obsoletos que
                # contienen referencias a archivos que ya fueron eliminados.
                # ================================================================
                if not was_simulation:
                    self._invalidate_related_analysis_results(tool_id)
                
                # file_organizer y file_renamer no borran archivos, solo mueven/renombran
                # No tiene sentido pedir re-análisis para ellos
                skip_reanalysis_tools = {'file_organizer', 'file_renamer'}
                
                if not was_simulation and tool_id not in skip_reanalysis_tools:
                    # Verificar si se debe pedir confirmación antes de reanalizar
                    should_confirm = settings_manager.get_confirm_reanalyze()
                    
                    if should_confirm:
                        # Pedir confirmación al usuario
                        service_message = self._get_service_update_message(tool_id)
                        
                        reply = QMessageBox.question(
                            self.main_window,
                            "Actualizar estadísticas",
                            service_message,
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.Yes  # Default to Yes
                        )
                        
                        if reply == QMessageBox.StandardButton.Yes:
                            # Re-analyze specific service
                            log_section_header_discrete(self.logger, f"Statistics update requested for {tool_id}")
                            # NOTA: No invalidamos la caché aquí porque el usuario quiere actualizar estadísticas
                            # La caché ya está actualizada, solo necesitamos recalcular el análisis del servicio
                            QTimer.singleShot(500, lambda: self._update_service_stats(tool_id))
                        else:
                            # User chose to skip re-analysis
                            self.logger.info("User skipped re-analysis, statistics may be outdated")
                            
                            # NOTA: La caché ya se actualizó automáticamente durante la operación.
                            # Esta invalidación completa es opcional y conservadora por si hubo
                            # algún error en las actualizaciones individuales.
                            self._invalidate_metadata_cache()
                            
                            # Mostrar banner de advertencia
                            if self.stale_banner:
                                self.stale_banner.show()
                                # Asegurar que el banner sea visible (scroll to top if needed)
                                if hasattr(self.main_window, 'scroll_area'):
                                    self.main_window.scroll_area.ensureWidgetVisible(self.stale_banner)
                    else:
                        # Actualizar automáticamente sin confirmación
                        self.logger.info(f"Automatically updating statistics for {tool_id} (no confirmation)")
                        log_section_header_discrete(self.logger, f"Automatic statistics update for {tool_id}")
                        # Usar QTimer con lambda que capture excepciones
                        def safe_update():
                            try:
                                self._update_service_stats(tool_id, auto_update=True)
                            except Exception as e:
                                self.logger.error(f"Critical error in automatic update of {tool_id}: {e}")
                                import traceback
                                self.logger.error(traceback.format_exc())
                                QMessageBox.critical(
                                    self.main_window,
                                    tr("stage3.error.update_failed_title"),
                                    tr("stage3.error.update_failed_msg", tool_id=tool_id, error=str(e)[:300])
                                )
                        QTimer.singleShot(500, safe_update)
        
        def on_error(error_message):
            # Ignorar si ya se canceló
            if is_cancelled:
                return
            
            # Desconectar señal de cancelación antes de cerrar
            try:
                progress_dialog.canceled.disconnect(on_cancel)
            except (RuntimeError, TypeError):
                pass
                
            progress_dialog.close()
            self.logger.error(f"Error in operation {tool_id}: {error_message}")
            QMessageBox.critical(
                self.main_window,
                tr("common.error"),
                tr("stage3.error.operation_failed_msg", error=error_message[:500])
            )
            worker.deleteLater()
        
        def on_cancel():
            """Maneja la cancelación del diálogo de progreso"""
            nonlocal is_cancelled
            is_cancelled = True
            
            # Solicitar al worker que se detenga
            try:
                worker.stop()
            except RuntimeError:
                # Worker ya fue eliminado, cerrar el diálogo directamente
                progress_dialog.close()
                self.logger.info(f"Operation {tool_id} already finished at cancellation time")
                return
            
            # Actualizar el mensaje del diálogo mientras esperamos
            progress_dialog.setLabelText(tr("stage3.progress.cancelling"))
            progress_dialog.setCancelButton(None)  # Deshabilitar el botón de cancelar
            
            # Desconectar señales de procesamiento pero mantener finished para limpieza
            try:
                worker.progress_update.disconnect(on_progress)
            except (RuntimeError, TypeError):
                # Worker eliminado o señal ya desconectada
                pass
            
            # Conectar un handler simplificado para finished que solo limpia
            def on_cancelled_cleanup():
                progress_dialog.close()
                try:
                    worker.deleteLater()
                except RuntimeError:
                    pass  # Ya fue eliminado
                self.logger.info(f"Operation {tool_id} cancelled and cleaned up correctly")
            
            # Desconectar handlers anteriores y conectar el de limpieza
            try:
                worker.finished.disconnect(on_finished)
                worker.error.disconnect(on_error)
            except (RuntimeError, TypeError):
                # Worker eliminado o señales ya desconectadas
                pass
            
            # Intentar reconectar solo si el worker todavía existe
            try:
                worker.finished.connect(on_cancelled_cleanup)
                worker.error.connect(on_cancelled_cleanup)
            except RuntimeError:
                # Worker ya fue eliminado, limpiar directamente
                on_cancelled_cleanup()
                return
            
            self.logger.info(f"Operation {tool_id} - Cancellation requested by user")
        
        worker.progress_update.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        
        # Conectar cancelación con handler explícito
        progress_dialog.canceled.connect(on_cancel)
        
        # Iniciar worker
        worker.start()
        self.logger.debug(f"Worker for {tool_id} started")
    
    def _get_service_update_message(self, tool_id: str) -> str:
        """
        Genera el mensaje específico para actualizar estadísticas de un servicio.
        
        Args:
            tool_id: ID del servicio (live_photos, heic, duplicates_exact, etc.)
            
        Returns:
            Mensaje personalizado para el diálogo
        """
        service_name = get_tool_title(tool_id)
        
        return (
            tr("stage3.confirm.update_stats_msg", name=service_name)
        )
    
    # Herramientas que NO liberan espacio (solo mueven/renombran archivos)
    _NON_SPACE_FREEING_TOOLS = {'file_organizer', 'file_renamer'}

    def _build_success_message(self, result, was_simulation: bool, has_backup: bool, tool_id: str = '') -> tuple:
        """
        Construye mensaje de éxito estandarizado para todas las herramientas.
        
        Args:
            result: ExecutionResult del servicio
            was_simulation: Si la operación fue en modo simulación (dry_run)
            has_backup: Si el usuario solicitó crear backup
            tool_id: Identificador de la herramienta (para personalizar el mensaje)
            
        Returns:
            Tuple (message, title) con el mensaje y título formateados
        """
        from utils.format_utils import format_size
        
        # Title based on mode
        if was_simulation:
            title = tr("stage3.result.simulation_title")
        else:
            title = tr("stage3.result.operation_title")
        
        # Build detailed summary
        summary_lines = []
        
        # File processing statistics
        if hasattr(result, 'items_processed') and result.items_processed > 0:
            if was_simulation:
                summary_lines.append(tr("stage3.result.files_would_process", count=result.items_processed))
            else:
                summary_lines.append(tr("stage3.result.files_processed", count=result.items_processed))
        
        # Space freed/would be freed (only for tools that actually delete files)
        if tool_id not in self._NON_SPACE_FREEING_TOOLS:
            if hasattr(result, 'bytes_processed') and result.bytes_processed > 0:
                if was_simulation:
                    summary_lines.append(tr("stage3.result.space_would_free", size=format_size(result.bytes_processed)))
                else:
                    summary_lines.append(tr("stage3.result.space_freed", size=format_size(result.bytes_processed)))
        
        # Additional service message content
        service_message = ""
        if hasattr(result, 'message') and result.message:
            service_message = result.message.strip()
        
        # Backup info
        backup_info = ""
        if has_backup:
            if was_simulation:
                backup_info = "\n" + tr("stage3.result.backup_simulation")
            elif hasattr(result, 'backup_path') and result.backup_path:
                backup_info = "\n\n" + tr("stage3.result.backup_created", path=result.backup_path)
            else:
                backup_info = "\n\n" + tr("stage3.result.backup_no_files")
        
        # Error warnings
        errors_info = ""
        if hasattr(result, 'errors') and result.errors:
            errors_info = "\n\n" + tr("stage3.result.errors_warning", count=len(result.errors))
        
        # Simulation note
        simulation_note = ""
        if was_simulation:
            simulation_note = "\n\n" + tr("stage3.result.simulation_note")
        
        # Build final message
        if summary_lines:
            summary = "\n".join(summary_lines)
            message = f"{summary}{backup_info}{errors_info}{simulation_note}"
        elif service_message:
            message = f"{service_message}{backup_info}{errors_info}{simulation_note}"
        else:
            base = tr("stage3.result.simulation_completed") if was_simulation else tr("stage3.result.operation_completed")
            message = f"{base}{backup_info}{errors_info}{simulation_note}"
        
        return message, title
    
    def _update_service_stats(self, tool_id: str, auto_update: bool = False) -> None:
        """
        Actualiza las estadísticas de un servicio específico y refresca la UI.
        
        Usa workers en segundo plano con diálogo de progreso para no congelar la UI,
        especialmente importante para análisis costosos como duplicates_similar.
        
        Args:
            tool_id: ID del servicio a actualizar
            auto_update: Si es True, no muestra mensaje de confirmación al finalizar
        """
        self.logger.info(f"Updating statistics for service: {tool_id} (auto_update={auto_update})")
        
        # Reutilizar el sistema de workers existente con diálogo de progreso
        self._run_analysis_for_stats_update(tool_id, auto_update)
    
    def _run_analysis_for_stats_update(self, tool_id: str, auto_update: bool = False) -> None:
        """
        Ejecuta el análisis de una herramienta en segundo plano con diálogo de progreso.
        
        Similar a _run_analysis_and_open_dialog pero:
        - NO abre el diálogo de la herramienta al finalizar
        - Muestra mensaje de éxito según auto_update
        - Refresca la UI de Stage 3
        
        Args:
            tool_id: ID de la herramienta
            auto_update: Si True, no muestra mensaje de confirmación
        """
        from ui.workers import (
            LivePhotosAnalysisWorker,
            HeicAnalysisWorker,
            DuplicatesExactAnalysisWorker,
            DuplicatesSimilarAnalysisWorker,
            VisualIdenticalAnalysisWorker,
            ZeroByteAnalysisWorker,
            FileOrganizerAnalysisWorker,
            FileRenamerAnalysisWorker
        )
        from PyQt6.QtWidgets import QProgressDialog
        
        # Mapeo de tool_id a Worker Class y mensaje
        worker_map = {
            'live_photos': (LivePhotosAnalysisWorker, tr("stage3.progress.updating_live_photos")),
            'heic': (HeicAnalysisWorker, tr("stage3.progress.updating_heic")),
            'duplicates_exact': (DuplicatesExactAnalysisWorker, tr("stage3.progress.updating_exact_copies")),
            'visual_identical': (VisualIdenticalAnalysisWorker, tr("stage3.progress.updating_visual")),
            'duplicates_similar': (DuplicatesSimilarAnalysisWorker, tr("stage3.progress.updating_similar")),
            'zero_byte': (ZeroByteAnalysisWorker, tr("stage3.progress.updating_empty")),
            'file_organizer': (FileOrganizerAnalysisWorker, tr("stage3.progress.updating_structure")),
            'file_renamer': (FileRenamerAnalysisWorker, tr("stage3.progress.updating_names"))
        }
        
        if tool_id not in worker_map:
            self.logger.warning(f"Unknown service for update: {tool_id}")
            return

        WorkerClass, message = worker_map[tool_id]
        
        # Crear diálogo de progreso
        progress = QProgressDialog(message, "Cancelar", 0, 0, self.main_window)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.resize(450, 120)
        
        # Crear worker
        refactorized_tools = {'live_photos', 'heic', 'duplicates_exact', 'visual_identical', 'zero_byte', 'file_renamer', 'file_organizer'}
        if tool_id in refactorized_tools:
            worker = WorkerClass(Path(self.selected_folder))
        elif tool_id == 'duplicates_similar':
            worker = WorkerClass(Path(self.selected_folder), sensitivity=85)
        else:
            worker = WorkerClass(Path(self.selected_folder), self.metadata_cache)
        
        def on_finished(result):
            progress.close()
            if result:
                # Actualizar el análisis en analysis_results
                if tool_id == 'live_photos':
                    self.analysis_results.live_photos = result
                elif tool_id == 'heic':
                    self.analysis_results.heic = result
                elif tool_id == 'duplicates_exact':
                    self.analysis_results.duplicates = result
                elif tool_id == 'duplicates_similar':
                    self.analysis_results.duplicates_similar = result
                elif tool_id == 'visual_identical':
                    self.analysis_results.visual_identical = result
                elif tool_id == 'file_organizer':
                    self.analysis_results.organization = result
                elif tool_id == 'file_renamer':
                    self.analysis_results.renaming = result
                elif tool_id == 'zero_byte':
                    self.analysis_results.zero_byte = result
                
                # Guardar resultados y refrescar UI
                self.save_analysis_results(self.analysis_results)
                self._refresh_stage_3_ui()
                
                self.logger.info(f"Statistics updated successfully for {tool_id}")
                
                # Mostrar mensaje solo si NO es auto_update
                if not auto_update:
                    service_name = get_tool_title(tool_id)
                    QMessageBox.information(
                        self.main_window,
                        tr("stage3.info.stats_updated_title"),
                        tr("stage3.info.stats_updated_msg", name=service_name)
                    )
            else:
                self.logger.warning(f"Could not get updated analysis for {tool_id}")
            
            worker.deleteLater()
            
        def on_error(msg):
            progress.close()
            self.logger.error(f"Error updating statistics for {tool_id}: {msg}")
            QMessageBox.warning(
                self.main_window,
                tr("common.error"),
                tr("stage3.error.stats_update_failed_msg", name=get_tool_title(tool_id), msg=msg)
            )
            worker.deleteLater()
            
        def on_progress_update(current, total, msg):
            if total > 0:
                if progress.maximum() != total:
                    progress.setMaximum(total)
                progress.setValue(current)
            else:
                if progress.maximum() != 0:
                    progress.setMaximum(0)
                    progress.setValue(0)
            
            progress.setLabelText(f"{message}\n{msg}")

        worker.progress_update.connect(on_progress_update)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        
        progress.canceled.connect(worker.stop)
        worker.start()
        progress.exec()

    def _sync_scan_results_with_cache(self) -> None:
        """
        Sincroniza los resultados del escaneo inicial con el estado actual de la caché.
        Útil después de operaciones que eliminan o mueven archivos.
        """
        if not self.analysis_results or not hasattr(self.analysis_results, 'scan') or not self.analysis_results.scan:
            return

        repo = FileInfoRepositoryCache.get_instance()
        all_metadata = repo.get_all_files()
        
        # Reiniciar contadores y listas en el objeto scan existente
        scan = self.analysis_results.scan
        scan.total_files = len(all_metadata)
        scan.total_size = sum(m.fs_size for m in all_metadata)
        scan.images = [m.path for m in all_metadata if m.is_image]
        scan.videos = [m.path for m in all_metadata if m.is_video]
        scan.others = [m.path for m in all_metadata if not m.is_image and not m.is_video]
        
        self.logger.debug(
            f"Scan synchronized with cache: {scan.total_files} files, "
            f"{format_size(scan.total_size)}"
        )
    
    def _refresh_stage_3_ui(self) -> None:
        """
        Refresca la UI completa de Stage 3 con los analysis_results actualizados.
        """
        try:
            self.logger.debug("Refreshing Stage 3 UI with updated data")

            # Sincronizar estadísticas globales con la caché
            self._sync_scan_results_with_cache()

            # Paso 1: Identificar índice del banner para limpiar SOLO lo que hay debajo
            banner_index = -1
            for i in range(self.main_layout.count()):
                item = self.main_layout.itemAt(i)
                if item.widget() and item.widget().objectName() == "staleBanner":
                    banner_index = i
                    break
            
            # Si no encontramos banner (raro), asumimos después del header (index 1 aprox)
            # Pero mejor buscar header si falla banner
            if banner_index == -1:
                # Fallback seguro: limpiar todo menos los primeros 2 elementos (Header + Spacing)
                banner_index = 2 

            # Paso 2: Limpiar todo lo que esté DESPUÉS del banner
            # Iteramos hacia atrás hasta llegar al banner_index
            while self.main_layout.count() > banner_index + 1:
                item = self.main_layout.takeAt(self.main_layout.count() - 1)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
                elif item.spacerItem():
                    # Eliminar spacers también
                    pass
            
            self.summary_card = None
            self.tools_grid = None
            self.tool_cards.clear()
            
            # Recrear la UI de forma atómica dentro del results_container
            self.logger.debug("Recreating Stage 3 UI...")
            
            # Recrear sin animaciones
            self._show_summary_card()
            self._create_tools_grid()
            
            self.logger.debug("Stage 3 UI refreshed successfully")
            
        except Exception as e:
            self.logger.error(f"Error refreshing Stage 3 UI: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise  # Re-lanzar para que se capture en el nivel superior
    
    def _on_reanalyze(self):
        """Maneja el clic en "Reanalizar" (legacy - ahora debería ser raro usarlo)"""
        self.logger.info("Re-analyzing full folder (legacy mode)")

        # Limpiar widgets del ESTADO 3
        if self.stale_banner:
            self.stale_banner.hide()
            self.stale_banner.setParent(None)
            self.stale_banner = None

        if self.summary_card:
            self.summary_card.hide()
            self.summary_card.setParent(None)
            self.summary_card = None

        if self.tools_grid:
            self.tools_grid.hide()
            self.tools_grid.setParent(None)
            self.tools_grid = None

        self.tool_cards.clear()

        # Volver a ESTADO 2 y reanalizar a través de MainWindow
        self.main_window._transition_to_state_2(self.selected_folder)

    def _on_change_folder(self):
        """Maneja el clic en "Cambiar carpeta" """
        reply = QMessageBox.question(
            self.main_window,
            tr("stage3.confirm.change_folder_title"),
            tr("stage3.confirm.change_folder_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Limpiar estado y volver a ESTADO 1
            self._reset_to_state_1()


    def _reset_to_state_1(self):
        """Reinicia la ventana al ESTADO 1"""
        self.logger.info("Resetting to STAGE 1")

        # Limpiar todos los widgets
        if self.summary_card:
            self.summary_card.setParent(None)
            self.summary_card = None

        if self.tools_grid:
            self.tools_grid.setParent(None)
            self.tools_grid = None

        self.tool_cards.clear()

        # Transición al Estado 1 a través de MainWindow
        self.main_window._transition_to_state_1()

    def _on_settings_clicked(self):
        """Maneja el clic en el botón de configuración"""
        self.logger.debug("Opening settings dialog")
        dialog = SettingsDialog(self.main_window)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()
        
    def _on_settings_saved(self):
        """Maneja cambios en la configuración"""
        if self.summary_card:
            self.summary_card.update_path_display()

    def _on_about_clicked(self):
        """Maneja el clic en el botón 'Acerca de'"""
        self.logger.debug("Opening 'About' dialog")
        dialog = AboutDialog(self.main_window)
        dialog.exec()   

    

