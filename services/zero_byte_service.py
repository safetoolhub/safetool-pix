# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Servicio para detectar y eliminar archivos de 0 bytes.
Refactorizado para usar FileInfoRepository como fuente única de verdad.
"""
import logging
from pathlib import Path
from typing import List, Optional

from services.base_service import BaseService, ProgressCallback
from services.result_types import ZeroByteAnalysisResult, ZeroByteExecutionResult
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from utils.logger import log_section_header_relevant, log_section_footer_relevant
from utils.i18n import tr


class ZeroByteService(BaseService):
    """
    Servicio para gestionar archivos de 0 bytes.
    
    Patrón:
    - Análisis: Filtra archivos de 0 bytes del FileInfoRepository
    - Ejecución: Elimina archivos con backup y logging estandarizado
    - Usa FileInfoRepository.get_instance()
    """
    
    def __init__(self):
        super().__init__('ZeroByteService')

    def analyze(self, 
                progress_callback: Optional[ProgressCallback] = None,
                **kwargs) -> ZeroByteAnalysisResult:
        """
        Busca archivos de 0 bytes usando FileInfoRepository como fuente de verdad.
        
        Args:
            progress_callback: Callback opcional para reportar progreso
            
        Returns:
            ZeroByteAnalysisResult con lista de archivos de 0 bytes encontrados
        """
        repo = FileInfoRepositoryCache.get_instance()
        total = repo.get_file_count()  # O(1) optimizado
        
        self.logger.info(f"Searching for 0-byte files in repository ({total} files)")
        
        zero_byte_files = []
        all_files = repo.get_all_files()
        
        for i, meta in enumerate(all_files):
            if meta.fs_size == 0:
                zero_byte_files.append(meta.path)
            
            # Reportar progreso periódicamente (intervalo alto, operación en memoria rápida)
            if self._should_report_progress(i, interval=5000):
                if not self._report_progress(progress_callback, i, total, tr("services.progress.filtering_empty_files")):
                    break
                     
        self.logger.info(f"Found {len(zero_byte_files)} 0-byte files")
        
        return ZeroByteAnalysisResult(
            files=zero_byte_files,
            items_count=len(zero_byte_files)
        )

    def execute(self, 
                analysis_result: ZeroByteAnalysisResult,
                dry_run: bool = False,
                create_backup: bool = True,
                progress_callback: Optional[ProgressCallback] = None,
                **kwargs) -> ZeroByteExecutionResult:
        """
        Elimina los archivos de 0 bytes identificados en el análisis.
        
        Args:
            analysis_result: Resultado del análisis con archivos a eliminar
            dry_run: Si True, simula la operación sin eliminar archivos
            create_backup: Si True, crea backup antes de eliminar
            progress_callback: Callback opcional para reportar progreso
            
        Returns:
            ZeroByteExecutionResult con estadísticas de la operación
        """
        files_to_delete = analysis_result.files
        
        # Usar template method _execute_operation de BaseService
        return self._execute_operation(
            files=files_to_delete,
            operation_name='zero_byte_deletion',
            execute_fn=lambda dr: self._do_zero_byte_deletion(
                files_to_delete, 
                dr, 
                progress_callback
            ),
            create_backup=create_backup,
            dry_run=dry_run,
            progress_callback=progress_callback
        )
    
    def _do_zero_byte_deletion(
        self,
        files_to_delete: List[Path],
        dry_run: bool,
        progress_callback: Optional[ProgressCallback]
    ) -> ZeroByteExecutionResult:
        """
        Lógica real de eliminación de archivos de 0 bytes.
        
        Args:
            files_to_delete: Lista de paths de archivos a eliminar
            dry_run: Si True, solo simula la eliminación
            progress_callback: Callback opcional para reportar progreso
            
        Returns:
            ZeroByteExecutionResult con estadísticas de archivos procesados
        """
        result = ZeroByteExecutionResult(dry_run=dry_run)
        total = len(files_to_delete)
        
        mode = "SIMULATION" if dry_run else ""
        log_section_header_relevant(self.logger, "EMPTY FILE DELETION", mode=mode)
        self.logger.info(f"*** Files to process: {total}")
        
        files_affected = []
        items_processed = 0
        
        for i, file_path in enumerate(files_to_delete):
            if not self._report_progress(
                progress_callback,
                i,
                total,
                f"{tr('services.progress.would_delete') if dry_run else tr('services.progress.deleting')}\n{file_path.name}"
            ):
                break
            
            try:
                # Obtener extensión para log
                file_extension = file_path.suffix.upper().lstrip('.')
                file_type = file_extension if file_extension else 'UNKNOWN'
                
                # Usar método centralizado de BaseService
                if self._delete_file_with_logging(file_path, 0, file_type, dry_run):
                    items_processed += 1
                    files_affected.append(file_path)
                else:
                    self.logger.warning(
                        f"FILE_SKIPPED: {file_path} | "
                        f"Size: 0 B | Type: {file_type} | "
                        f"Reason: Could not delete file"
                    )
                    result.add_error(f"Could not delete: {file_path}")
                        
            except Exception as e:
                result.add_error(f"Error processing {file_path}: {e}")
        
        result.items_processed = items_processed
        result.files_affected = files_affected
        
        # Resumen de archivos descartados
        total_skipped = total - items_processed
        if total_skipped > 0:
            self.logger.warning(
                f"SKIPPED_SUMMARY: {total_skipped}/{total} files could not be deleted"
            )
        
        # Usar _format_operation_summary de BaseService
        summary = self._format_operation_summary(
            tr("services.operation.empty_file_deletion"),
            items_processed,
            space_amount=0,  # Son archivos de 0 bytes
            dry_run=dry_run
        )
        
        result.message = summary
        log_section_footer_relevant(self.logger, summary)

        # Mostramos estadísticas de la caché al final
        repo = FileInfoRepositoryCache.get_instance()
        repo.log_cache_statistics(level=logging.INFO)
        
        self._report_progress(progress_callback, total, total, tr("services.progress.operation_completed"))
            
        return result

