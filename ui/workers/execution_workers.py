# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Execution Workers for performing destructive/modification actions.
"""
from typing import TYPE_CHECKING, List, Optional, Union
from pathlib import Path
from PyQt6.QtCore import pyqtSignal

from .base_worker import BaseWorker

if TYPE_CHECKING:
    from services.result_types import (
        RenameAnalysisResult,
        OrganizationExecutionResult,
        OrganizationAnalysisResult,
        LivePhotosExecutionResult,
        LivePhotosAnalysisResult,
        HeicExecutionResult,
        HeicAnalysisResult,
        ExactDuplicateAnalysisResult,
        ExactDuplicateExecutionResult,
        SimilarDuplicateAnalysisResult,
        SimilarDuplicateExecutionResult,
        ZeroByteExecutionResult
    )
    from services.file_renamer_service import FileRenamerService
    from services.live_photos_service import LivePhotoService
    from services.file_organizer_service import FileOrganizerService
    from services.heic_service import HeicService
    from services.duplicates_exact_service import DuplicatesExactService
    from services.duplicates_similar_service import DuplicatesSimilarService
    from services.zero_byte_service import ZeroByteService


class FileRenamerExecutionWorker(BaseWorker):
    """
    Worker para ejecutar renombrado de nombres de archivos
    """
    finished = pyqtSignal(object)  # RenameExecutionResult

    def __init__(
        self, 
        renamer: 'FileRenamerService',
        analysis: 'RenameAnalysisResult',
        create_backup: bool = True,
        dry_run: bool = False
    ):
        super().__init__()
        self.renamer = renamer
        self.analysis = analysis
        self.create_backup = create_backup
        self.dry_run = dry_run

    def run(self) -> None:
        try:
            if self._stop_requested:
                return
            
            # Importar aquí para evitar circularidad real
            from services.result_types import RenameExecutionResult
            
            results = self.renamer.execute(
                self.analysis,
                create_backup=self.create_backup,
                dry_run=self.dry_run,
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            
            if not self._stop_requested:
                self.finished.emit(results)
        except Exception as e:
            if not self._stop_requested:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.error.emit(error_msg)


class LivePhotosExecutionWorker(BaseWorker):
    """
    Worker para ejecutar limpieza de Live Photos
    """
    finished = pyqtSignal(object)  # LivePhotosExecutionResult

    def __init__(self, service: 'LivePhotoService', analysis: 'LivePhotosAnalysisResult', 
                 create_backup: bool = True, dry_run: bool = False):
        super().__init__()
        self.service = service
        self.analysis = analysis
        self.create_backup = create_backup
        self.dry_run = dry_run

    def run(self) -> None:
        try:
            if self._stop_requested:
                return
            
            results = self.service.execute(
                self.analysis,
                create_backup=self.create_backup,
                dry_run=self.dry_run,
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            
            if not self._stop_requested:
                self.finished.emit(results)
        except Exception as e:
            if not self._stop_requested:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.error.emit(error_msg)


class FileOrganizerExecutionWorker(BaseWorker):
    """
    Worker para ejecutar organización de archivos
    """
    finished = pyqtSignal(object)  # OrganizationExecutionResult

    def __init__(
        self,
        organizer: 'FileOrganizerService',
        analysis: 'OrganizationAnalysisResult',
        cleanup_empty_dirs: bool = True,
        create_backup: bool = True,
        dry_run: bool = False
    ):
        super().__init__()
        self.organizer = organizer
        self.analysis = analysis
        self.cleanup_empty_dirs = cleanup_empty_dirs
        self.create_backup = create_backup
        self.dry_run = dry_run

    def run(self) -> None:
        try:
            if self._stop_requested:
                return
            
            results = self.organizer.execute(
                self.analysis,
                create_backup=self.create_backup,
                cleanup_empty_dirs=self.cleanup_empty_dirs,
                dry_run=self.dry_run,
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            
            if not self._stop_requested:
                self.finished.emit(results)
        except Exception as e:
            if not self._stop_requested:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.error.emit(error_msg)


class HeicExecutionWorker(BaseWorker):
    """
    Worker para ejecutar eliminación de duplicados HEIC
    """
    finished = pyqtSignal(object)  # HeicExecutionResult

    def __init__(
        self,
        service: 'HeicService',
        analysis: 'HeicAnalysisResult',
        keep_format: str,
        create_backup: bool = True,
        dry_run: bool = False
    ):
        super().__init__()
        self.service = service  # Fixed assignment (was self.remover = remover)
        self.analysis = analysis
        self.keep_format = keep_format
        self.create_backup = create_backup
        self.dry_run = dry_run

    def run(self) -> None:
        try:
            if self._stop_requested:
                return
            
            results = self.service.execute(
                self.analysis,
                keep_format=self.keep_format,
                create_backup=self.create_backup,
                dry_run=self.dry_run,
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            
            if not self._stop_requested:
                self.finished.emit(results)
        except Exception as e:
            if not self._stop_requested:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.error.emit(error_msg)


class DuplicatesExecutionWorker(BaseWorker):
    """
    Worker para eliminación de duplicados (exactos o similares)
    """
    finished = pyqtSignal(object)  # ExactDuplicateExecutionResult | SimilarDuplicateExecutionResult
    
    def __init__(
        self,
        detector: 'DuplicatesExactService | DuplicatesSimilarService',
        analysis: 'ExactDuplicateAnalysisResult | SimilarDuplicateAnalysisResult',
        keep_strategy: str,
        create_backup: bool = True,
        dry_run: bool = False,
        metadata_cache = None,
        files_to_delete: Optional[List[Path]] = None
    ):
        super().__init__()
        self.detector = detector
        self.analysis = analysis
        self.keep_strategy = keep_strategy
        self.create_backup = create_backup
        self.dry_run = dry_run
        self.metadata_cache = metadata_cache
        self.files_to_delete = files_to_delete
    
    def run(self) -> None:
        try:
            if self._stop_requested:
                return
            
            results = self.detector.execute(
                self.analysis,
                keep_strategy=self.keep_strategy,
                create_backup=self.create_backup,
                dry_run=self.dry_run,
                progress_callback=self._create_progress_callback(emit_numbers=True),
                metadata_cache=self.metadata_cache,
                files_to_delete=self.files_to_delete
            )
            
            if not self._stop_requested:
                self.finished.emit(results)
        
        except Exception as e:
            if not self._stop_requested:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.error.emit(error_msg)


class ZeroByteExecutionWorker(BaseWorker):
    """
    Worker para eliminación de archivos de 0 bytes
    """
    finished = pyqtSignal(object)  # ZeroByteExecutionResult

    def __init__(
        self,
        service: 'ZeroByteService',
        analysis: 'ZeroByteAnalysisResult',
        create_backup: bool = True,
        dry_run: bool = False
    ):
        super().__init__()
        self.service = service
        self.analysis = analysis
        self.create_backup = create_backup
        self.dry_run = dry_run

    def run(self) -> None:
        try:
            if self._stop_requested:
                return
            
            results = self.service.execute(
                self.analysis,
                create_backup=self.create_backup,
                dry_run=self.dry_run,
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            
            if not self._stop_requested:
                self.finished.emit(results)
        except Exception as e:
            if not self._stop_requested:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.error.emit(error_msg)


class VisualIdenticalExecutionWorker(BaseWorker):
    """
    Worker para eliminación de copias visuales idénticas.
    """
    finished = pyqtSignal(object)  # VisualIdenticalExecutionResult

    def __init__(
        self,
        service,  # VisualIdenticalService
        groups: List,  # List[VisualIdenticalGroup]
        files_to_delete: List[Path],
        create_backup: bool = True,
        dry_run: bool = False
    ):
        super().__init__()
        self.service = service
        self.groups = groups
        self.files_to_delete = files_to_delete
        self.create_backup = create_backup
        self.dry_run = dry_run

    def run(self) -> None:
        try:
            if self._stop_requested:
                return
            
            results = self.service.execute(
                groups=self.groups,
                files_to_delete=self.files_to_delete,
                create_backup=self.create_backup,
                dry_run=self.dry_run,
                progress_callback=self._create_progress_callback(emit_numbers=True)
            )
            
            if not self._stop_requested:
                self.finished.emit(results)
        except Exception as e:
            if not self._stop_requested:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self.error.emit(error_msg)
