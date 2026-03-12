# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Worker threads para análisis bajo demanda (Stage 3).
Permite ejecutar tareas de análisis de herramientas específicas en background.

Note: InitialAnalysisWorker (Stage 2) está en initial_analysis_worker.py
"""

from PyQt6.QtCore import pyqtSignal
from pathlib import Path
from typing import Optional

from .base_worker import BaseWorker


# ============================================================================
# ON-DEMAND ANALYSIS WORKERS (STAGE 3)
# ============================================================================

class LivePhotosAnalysisWorker(BaseWorker):
    finished = pyqtSignal(object)
    
    def __init__(self, directory: Path, metadata_cache=None):
        super().__init__()
        self.directory = directory
        self.metadata_cache = metadata_cache
        
    def run(self):
        try:
            if self._stop_requested: return
            from services.live_photos_service import LivePhotoService
            
            service = LivePhotoService()
            result = service.analyze(
                validate_dates=True,  # Validar fechas por defecto
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            
            if not self._stop_requested:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class HeicAnalysisWorker(BaseWorker):
    finished = pyqtSignal(object)
    
    def __init__(self, directory: Path, metadata_cache=None):
        super().__init__()
        self.directory = directory
        self.metadata_cache = metadata_cache
        
    def run(self):
        try:
            if self._stop_requested: return
            from services.heic_service import HeicService
            service = HeicService()
            result = service.analyze(
                progress_callback=self._create_progress_callback(emit_numbers=True),
                directory=self.directory
            )
            if not self._stop_requested:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DuplicatesExactAnalysisWorker(BaseWorker):
    finished = pyqtSignal(object)
    
    def __init__(self, directory: Path, metadata_cache=None):
        super().__init__()
        self.directory = directory
        self.metadata_cache = metadata_cache
        
    def run(self):
        try:
            if self._stop_requested: return
            from services.duplicates_exact_service import DuplicatesExactService
            service = DuplicatesExactService()
            result = service.analyze(
                progress_callback=self._create_progress_callback(emit_numbers=True),
                directory=self.directory
            )
            if not self._stop_requested:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ZeroByteAnalysisWorker(BaseWorker):
    finished = pyqtSignal(object)
    
    def __init__(self, directory: Path, metadata_cache=None):
        super().__init__()
        self.directory = directory
        self.metadata_cache = metadata_cache
        
    def run(self):
        try:
            if self._stop_requested: return
            from services.zero_byte_service import ZeroByteService
            service = ZeroByteService()
            result = service.analyze(
                directory=self.directory,
                progress_callback=self._create_progress_callback(emit_numbers=True),
                metadata_cache=self.metadata_cache
            )
            if not self._stop_requested:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class FileRenamerAnalysisWorker(BaseWorker):
    finished = pyqtSignal(object)
    
    def __init__(self, directory: Path):
        super().__init__()
        self.directory = directory
        
    def run(self):
        try:
            if self._stop_requested: return
            from services.file_renamer_service import FileRenamerService
            service = FileRenamerService()
            result = service.analyze(
                directory=self.directory,
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            if not self._stop_requested:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class FileOrganizerAnalysisWorker(BaseWorker):
    """Worker para análisis de organización de archivos con opciones de agrupación"""
    finished = pyqtSignal(object)
    
    def __init__(
        self,
        directory: Path,
        organization_type=None,
        group_by_source: bool = False,
        group_by_type: bool = False,
        date_grouping_type: Optional[str] = None,
        move_unsupported_to_other: bool = False
    ):
        super().__init__()
        self.directory = directory
        self.organization_type = organization_type
        self.group_by_source = group_by_source
        self.group_by_type = group_by_type
        self.date_grouping_type = date_grouping_type
        self.move_unsupported_to_other = move_unsupported_to_other
        
    def run(self):
        try:
            if self._stop_requested: return
            from services.file_organizer_service import FileOrganizerService
            from services.file_organizer_service import OrganizationType
            
            service = FileOrganizerService()
            
            org_type = self.organization_type
            if org_type is None:
                org_type = OrganizationType.TO_ROOT
            elif isinstance(org_type, str):
                org_type = OrganizationType(org_type)
                
            result = service.analyze(
                root_directory=self.directory,
                organization_type=org_type,
                progress_callback=self._create_progress_callback(emit_numbers=True),
                group_by_source=self.group_by_source,
                group_by_type=self.group_by_type,
                date_grouping_type=self.date_grouping_type,
                move_unsupported_to_other=self.move_unsupported_to_other
            )
            if not self._stop_requested:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class DuplicatesSimilarAnalysisWorker(BaseWorker):
    """
    Worker para análisis de archivos similares (perceptual hash).
    
    Calcula hashes perceptuales y retorna DuplicatesSimilarAnalysis
    para uso interactivo en el diálogo con ajuste de sensibilidad en tiempo real.
    """
    finished = pyqtSignal(object)  # DuplicatesSimilarAnalysis
    
    def __init__(
        self,
        directory: Path,
        sensitivity: int = 85
    ):
        super().__init__()
        self.directory = directory
        self.sensitivity = sensitivity
    
    def run(self) -> None:
        try:
            if self._stop_requested:
                return
            
            from services.duplicates_similar_service import DuplicatesSimilarService
            
            service = DuplicatesSimilarService()
            # Usar get_analysis_for_dialog() para obtener DuplicatesSimilarAnalysis
            # que permite ajuste de sensibilidad en tiempo real en el diálogo
            result = service.get_analysis_for_dialog(
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            
            if not self._stop_requested:
                self.finished.emit(result)
        
        except Exception as e:
            if not self._stop_requested:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.error.emit(error_msg)


class VisualIdenticalAnalysisWorker(BaseWorker):
    """
    Worker para análisis de copias visuales idénticas.
    
    Detecta archivos visualmente IDÉNTICOS al 100% aunque tengan
    diferente resolución, compresión o metadatos.
    """
    finished = pyqtSignal(object)  # VisualIdenticalAnalysisResult
    
    def __init__(self, directory: Path, metadata_cache=None):
        super().__init__()
        self.directory = directory
        self.metadata_cache = metadata_cache
    
    def run(self) -> None:
        try:
            if self._stop_requested:
                return
            
            from services.visual_identical_service import VisualIdenticalService
            
            service = VisualIdenticalService()
            result = service.analyze(
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            
            if not self._stop_requested:
                self.finished.emit(result)
        
        except Exception as e:
            if not self._stop_requested:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.error.emit(error_msg)

