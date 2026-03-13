# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Eliminador de HEIC Duplicados
Refactorizado para usar MetadataCache.
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
from collections import defaultdict

from utils.i18n import tr
from services.result_types import HeicAnalysisResult, HeicExecutionResult, HEICDuplicatePair, AnalysisResult
from services.base_service import BaseService, ProgressCallback
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from services.file_metadata import FileMetadata
from config import Config
from utils.logger import (
    log_section_header_discrete,
    log_section_footer_discrete,
    log_section_header_relevant,
    log_section_footer_relevant
)
from utils.format_utils import format_size, format_duration


class HeicService(BaseService):
    """
    Servicio de HEIC - Compara archivos HEIC con sus equivalentes JPG
    
    Hereda de BaseService para logging estandarizado.
    """
    
    def __init__(self):
        super().__init__("HeicService")
        self.backup_dir = None
        
        # Configuración
        self.heic_extensions = {'.heic', '.heif'}
        self.jpg_extensions = {'.jpg', '.jpeg'}
        
        # Estadísticas
        self.stats = {
            'heic_files_found': 0,
            'jpg_files_found': 0,
            'duplicate_pairs_found': 0,
            'total_heic_size': 0,
            'total_jpg_size': 0,
            'potential_savings': 0,
            'rejected_by_time_diff': 0
        }
    
    def analyze(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        validate_dates: bool = True,
        **kwargs
    ) -> HeicAnalysisResult:
        """
        Analiza duplicados HEIC/JPG usando FileInfoRepository.
        
        Args:
            progress_callback: Callback
            validate_dates: Si validar fechas
            
        Returns:
            HeicAnalysisResult con análisis detallado
        """
        # Obtener FileInfoRepositoryCache
        repo = FileInfoRepositoryCache.get_instance()
        
        log_section_header_discrete(self.logger, "HEIC/JPG DUPLICATES ANALYSIS")
        self.logger.info(f"Using FileInfoRepositoryCache with {repo.get_file_count()} files")
        self.logger.info(f"Date validation: {'ENABLED' if validate_dates else 'DISABLED'}")
        
        if validate_dates:
            self.logger.info(f"Max tolerance: {Config.MAX_TIME_DIFFERENCE_SECONDS}s")
        
        self._reset_stats()
        
        results = {
            'duplicate_pairs': [],
            'orphan_heic': [],
            'orphan_jpg': [],
            'total_heic_files': 0,
            'total_jpg_files': 0,
            'total_duplicates': 0,
            'potential_savings_keep_jpg': 0,
            'potential_savings_keep_heic': 0,
            'by_directory': defaultdict(int),
            'rejected_pairs': []
        }
        
        # Obtener todos los archivos del repo
        try:
            all_files = repo.get_all_files()
        except Exception as e:
            self.logger.error(f"Error getting files from repository: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return self._create_empty_result()
        total_files = len(all_files)
        
        # Estructura optimizada: dict[Path, dict[str, FileMetadata]]
        heic_by_dir: Dict[Path, Dict[str, FileMetadata]] = defaultdict(dict)
        jpg_by_dir: Dict[Path, Dict[str, FileMetadata]] = defaultdict(dict)
        
        total_heic_count = 0
        total_jpg_count = 0
        
        # Clasificar archivos
        for i, meta in enumerate(all_files):
            try:
                if i % 1000 == 0 and not self._report_progress(progress_callback, i, total_files, tr("services.progress.classifying_heic_jpg")):
                    return self._create_empty_result()
                    
                extension = meta.extension
                base_name = meta.path.stem
                parent_dir = meta.path.parent
                
                if extension in self.heic_extensions:
                    heic_by_dir[parent_dir][base_name] = meta
                    self.stats['total_heic_size'] += meta.fs_size
                    total_heic_count += 1
                elif extension in self.jpg_extensions:
                    jpg_by_dir[parent_dir][base_name] = meta
                    self.stats['total_jpg_size'] += meta.fs_size
                    total_jpg_count += 1
            except Exception as e:
                self.logger.warning(f"Error classifying file {meta.path if hasattr(meta, 'path') else 'unknown'}: {e}")
                continue
        
        results['total_heic_files'] = total_heic_count
        results['total_jpg_files'] = total_jpg_count
        self.stats['heic_files_found'] = total_heic_count
        self.stats['jpg_files_found'] = total_jpg_count
        
        # Emparejar archivos
        duplicate_pairs = []
        matched_heic: Set[Path] = set()
        matched_jpg: Set[Path] = set()
        
        # Calcular total de pares a analizar para el log de progreso (INFO cada 10%)
        total_common_bases = 0
        for directory, h_dict in heic_by_dir.items():
            if directory in jpg_by_dir:
                total_common_bases += len(set(h_dict.keys()) & set(jpg_by_dir[directory].keys()))
        
        processed_pairs = 0
        progress_checkpoint = max(1, total_common_bases // 10)
        
        processed_dirs = 0
        total_dirs = len(heic_by_dir)
        
        for directory, heic_dict in heic_by_dir.items():
            processed_dirs += 1
            if processed_dirs % 10 == 0: # Report less frequently
                 self._report_progress(progress_callback, processed_dirs, total_dirs, tr("services.progress.pairing_files"))

            if directory not in jpg_by_dir:
                continue
            
            jpg_dict = jpg_by_dir[directory]
            
            # Bases comunes
            common_bases = sorted(list(set(heic_dict.keys()) & set(jpg_dict.keys())))
            
            for base_name in common_bases:
                processed_pairs += 1
                heic_meta = heic_dict[base_name]
                jpg_meta = jpg_dict[base_name]
                
                self.logger.debug(f"Analyzing pair: {base_name} in {directory}")
                
                
                try:
                    # Validación de fechas usando select_best_date_from_common_date_to_2_files
                    from utils.date_utils import select_best_date_from_common_date_to_2_files
                    
                    best_date_result = select_best_date_from_common_date_to_2_files(heic_meta, jpg_meta, verbose=True)
                    
                    if not best_date_result:
                        # No hay fecha común válida, rechazar
                        reject_reason = "No common date available for comparison"
                        self.logger.info(f"Pair rejected {base_name}: {reject_reason}")
                        # Details for diagnostics
                        self.logger.info(f"  HEIC metadata: {heic_meta.get_summary(verbose=True)}")
                        self.logger.info(f"  JPG metadata:  {jpg_meta.get_summary(verbose=True)}")
                        
                        rejected_pair = HEICDuplicatePair(
                            heic_path=heic_meta.path,
                            jpg_path=jpg_meta.path,
                            base_name=base_name,
                            heic_size=heic_meta.fs_size,
                            jpg_size=jpg_meta.fs_size,
                            directory=directory,
                            heic_date=None, 
                            jpg_date=None,
                            date_source=None,
                            date_difference=None
                        )
                        results['rejected_pairs'].append(rejected_pair)
                        continue
                        
                    heic_date, jpg_date, source_used = best_date_result
                    
                    # Calcular diferencia
                    time_diff = abs((heic_date - jpg_date).total_seconds())
                    
                    # Validar diferencia si corresponde (con pequeña tolerancia para evitar errores de precisión/drift del filesystem)
                    # Usamos 50ms (0.05s) como margen de seguridad razonable para operaciones en lote
                    if validate_dates and time_diff > (Config.MAX_TIME_DIFFERENCE_SECONDS + 0.05):
                        self.logger.info(f"** Pair rejected by time {heic_meta.path}: source={source_used}, diff={format_duration(time_diff)} (> {format_duration(Config.MAX_TIME_DIFFERENCE_SECONDS)})")
                        # Details for diagnostics
                        self.logger.info(f"  HEIC metadata: {heic_meta.get_summary(verbose=True)}")
                        self.logger.info(f"  JPG metadata:  {jpg_meta.get_summary(verbose=True)}")
                        self.stats['rejected_by_time_diff'] += 1
                        
                        rejected_pair = HEICDuplicatePair(
                            heic_path=heic_meta.path,
                            jpg_path=jpg_meta.path,
                            base_name=base_name,
                            heic_size=heic_meta.fs_size,
                            jpg_size=jpg_meta.fs_size,
                            directory=directory,
                            heic_date=heic_date,
                            jpg_date=jpg_date,
                            date_source=source_used,
                            date_difference=time_diff
                        )
                        results['rejected_pairs'].append(rejected_pair)
                        continue
                             
                    # Crear par válido
                    self.logger.debug(f"Pair accepted {base_name}: source={source_used}, diff={time_diff:.2f}s")
                    duplicate_pair = HEICDuplicatePair(
                        heic_path=heic_meta.path,
                        jpg_path=jpg_meta.path,
                        base_name=base_name,
                        heic_size=heic_meta.fs_size,
                        jpg_size=jpg_meta.fs_size,
                        directory=directory,
                        heic_date=heic_date,
                        jpg_date=jpg_date,
                        date_source=source_used,
                        date_difference=time_diff
                    )
                    
                    duplicate_pairs.append(duplicate_pair)
                    matched_heic.add(heic_meta.path)
                    matched_jpg.add(jpg_meta.path)
                    
                    results['potential_savings_keep_jpg'] += heic_meta.fs_size
                    results['potential_savings_keep_heic'] += jpg_meta.fs_size
                    results['by_directory'][str(directory)] += 1
                    
                except Exception as e:
                    self.logger.warning(f"Error processing pair {base_name}: {e}")
                    import traceback
                    self.logger.debug(traceback.format_exc())

                # Log INFO cada 10% de los pares totales
                if total_common_bases > 0 and processed_pairs % progress_checkpoint == 0:
                    percent = (processed_pairs / total_common_bases) * 100
                    self.logger.info(f"** HEIC analysis progress: {percent:.0f}% ({processed_pairs}/{total_common_bases} pairs)")

        results['duplicate_pairs'] = duplicate_pairs
        results['total_duplicates'] = len(duplicate_pairs)
        self.stats['duplicate_pairs_found'] = len(duplicate_pairs)
        self.stats['potential_savings'] = results['potential_savings_keep_jpg']
        
        # Encontrar huérfanos
        for directory, heic_dict in heic_by_dir.items():
            for base_name, meta in heic_dict.items():
                if meta.path not in matched_heic:
                    results['orphan_heic'].append(meta.path)
        
        for directory, jpg_dict in jpg_by_dir.items():
            for base_name, meta in jpg_dict.items():
                if meta.path not in matched_jpg:
                    results['orphan_jpg'].append(meta.path)
                    
        log_section_footer_discrete(self.logger, f"Analysis completed: {len(duplicate_pairs)} pairs")
        
        return HeicAnalysisResult(
            duplicate_pairs=duplicate_pairs,
            rejected_pairs=results.get('rejected_pairs', []),
            heic_files=results['total_heic_files'],
            jpg_files=results['total_jpg_files'],
            potential_savings_keep_jpg=results['potential_savings_keep_jpg'],
            potential_savings_keep_heic=results['potential_savings_keep_heic']
        )

    def execute(
        self,
        analysis_result: HeicAnalysisResult,
        dry_run: bool = False,
        create_backup: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs
    ) -> HeicExecutionResult:
        """
        Ejecuta eliminación HEIC/JPG.
        
        Args:
            analysis_result: Resultado del análisis
            dry_run: Simulación
            create_backup: Backup
            progress_callback: Progreso
            **kwargs: 'keep_format' ('jpg' o 'heic')
        """
        keep_format = kwargs.get('keep_format', 'jpg')
        duplicate_pairs = analysis_result.duplicate_pairs
        
        if not duplicate_pairs:
             return HeicExecutionResult(
                success=True,
                items_processed=0,
                bytes_processed=0,
                message='No duplicate files to delete',
                format_kept=keep_format,
                dry_run=dry_run
            )
            
        # Determinar archivos a eliminar
        if keep_format.lower() == 'jpg':
            files_to_delete = [pair.heic_path for pair in duplicate_pairs]
        else:
            files_to_delete = [pair.jpg_path for pair in duplicate_pairs]
            
        return self._execute_operation(
            files=files_to_delete,
            operation_name='heic_removal',
            execute_fn=lambda dry: self._do_heic_cleanup(
                duplicate_pairs,
                keep_format,
                dry,
                progress_callback
            ),
            create_backup=create_backup,
            dry_run=dry_run,
            progress_callback=progress_callback
        )

    def _do_heic_cleanup(
        self,
        duplicate_pairs: List[HEICDuplicatePair],
        keep_format: str,
        dry_run: bool,
        progress_callback: Optional[ProgressCallback]
    ) -> HeicExecutionResult:
        """Lógica real de eliminación (internal)"""
        
        mode = "SIMULATION" if dry_run else ""
        log_section_header_relevant(self.logger, "HEIC/JPG DUPLICATES REMOVAL", mode=mode)
        
        # Instanciar repo al principio para uso en todo el método
        repo = FileInfoRepositoryCache.get_instance()
        
        result = HeicExecutionResult(success=True, format_kept=keep_format, dry_run=dry_run)
        total_pairs = len(duplicate_pairs)
        
        files_affected = []
        items_processed = 0
        bytes_processed = 0
        
        for idx, pair in enumerate(duplicate_pairs):
             if not self._report_progress(progress_callback, idx+1, total_pairs, tr("services.progress.processing_pair_n_of_total", current=idx+1, total=total_pairs)):
                 break
                 
             file_to_delete = pair.heic_path if keep_format.lower() == 'jpg' else pair.jpg_path
             file_size = pair.heic_size if keep_format.lower() == 'jpg' else pair.jpg_size
             
             try:
                 if not file_to_delete.exists():
                     self.logger.warning(f"File not found: {file_to_delete}")
                     continue
                 
                 format_deleted = 'HEIC' if keep_format.lower() == 'jpg' else 'JPG'
                 
                 # Usar método centralizado de BaseService
                 if self._delete_file_with_logging(file_to_delete, file_size, format_deleted, dry_run):
                     items_processed += 1
                     bytes_processed += file_size
                     files_affected.append(file_to_delete)
                 else:
                     self.logger.warning(
                         f"FILE_DISCARDED: {file_to_delete} | "
                         f"Size: {format_size(file_size)} | "
                         f"Type: {format_deleted} | "
                         f"Reason: Could not delete file"
                     )
                     
             except Exception as e:
                 err = f"Error deleting {file_to_delete}: {e}"
                 result.add_error(err)
                 self.logger.error(err)

        # Poblar estadísticas en el objeto de resultado
        result.items_processed = items_processed
        result.bytes_processed = bytes_processed
        result.files_affected = files_affected

        # Resumen de archivos descartados
        total_descartados = total_pairs - items_processed
        if total_descartados > 0:
            self.logger.warning(
                f"DISCARDED_SUMMARY: {total_descartados}/{total_pairs} files could not be deleted"
            )

        # Resumen
        summary = self._format_operation_summary("HEIC/JPG Removal", items_processed, bytes_processed, dry_run)
        
        result.message = summary
        if result.backup_path:
            result.message += f"\n\nBackup: {result.backup_path}"
            
        log_section_footer_relevant(self.logger, summary)
        
        # Mostramos estadísticas de la caché al final
        repo.log_cache_statistics(level=logging.INFO)
        return result

    def _create_empty_result(self) -> HeicAnalysisResult:
        return HeicAnalysisResult(
            duplicate_pairs=[],
            heic_files=0,
            jpg_files=0,
            potential_savings_keep_jpg=0,
            potential_savings_keep_heic=0
        )

    def _reset_stats(self):
        for key in self.stats:
            self.stats[key] = 0
