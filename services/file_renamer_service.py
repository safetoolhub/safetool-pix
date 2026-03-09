# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Renombrador de nombres de archivos multimedia - VERSIÓN FINAL
Refactorizado para usar MetadataCache.
"""
from pathlib import Path
from typing import List, Optional
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config
from utils.logger import get_logger, log_section_header_relevant, log_section_footer_relevant, log_section_header_discrete, log_section_footer_discrete
from services.result_types import RenameExecutionResult, RenameAnalysisResult, RenamePlanItem, RenamedFileItem
from services.base_service import BaseService, ProgressCallback
from utils.i18n import tr
from utils.date_utils import (
    select_best_date_from_file,
    format_renamed_name,
    is_renamed_filename    
)
from utils.file_utils import (
    launch_backup_creation,
    find_next_available_name,
    validate_file_exists,
    get_file_type,
    is_supported_file
)
from services.file_metadata_repository_cache import FileInfoRepositoryCache


class FileRenamerService(BaseService):
    """
    Renombrador de nombres de archivos multimedia
    """
    def __init__(self):
        super().__init__("FileRenamer")
    
    def analyze(
        self,
        directory: Path,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs
    ) -> RenameAnalysisResult:
        """
        Analiza un directorio para renombrado.
        """
        log_section_header_discrete(self.logger, f"ANALYZING DIRECTORY FOR RENAMING: {directory}")

        repo = FileInfoRepositoryCache.get_instance()
        all_files = []
        self.logger.info(f"Using FileInfoRepositoryCache ({repo.get_file_count()} files)")
        cached_files = repo.get_all_files()
        for meta in cached_files:
            try:
                if meta.path.is_relative_to(directory):
                    all_files.append(meta.path)
            except ValueError:
                continue

        total_files = len(all_files)
        self.logger.info(f"Found {total_files} files to analyze")
        renaming_map = {}
        already_renamed = 0
        conflicts = 0
        files_by_year = Counter()
        renaming_plan = []
        issues = []
        
        # Función para procesar un archivo
        def process_file(file_path):
            """Procesa un archivo y retorna su información de renombrado"""
            if is_renamed_filename(file_path.name):
                return ('already_renamed', file_path, None)
            
            # Obtener metadata del repositorio (debe estar precargada)
            file_metadata = repo.get_file_metadata(file_path)
            if not file_metadata:
                return ('no_metadata', file_path, f"Metadata not available: {file_path.name}")
            
            # Obtener fecha usando la mejor fecha calculada o calcularla
            file_date, date_source = repo.get_best_date(file_path)
            if not file_date:
                # Intentar calcular fecha ahora si no está en caché
                file_date, date_source = select_best_date_from_file(file_metadata)
                if not file_date:
                    return ('no_date', file_path, f"Could not obtain date: {file_path.name}")
            
            file_type = get_file_type(file_path.name)
            if file_type == 'OTHER':
                return ('unsupported', file_path, f"Unsupported file type: {file_path.name}")
            
            extension = file_path.suffix
            renamed_name = format_renamed_name(file_date, file_type, extension)
            
            return ('file_renamer', file_path, {
                'renamed_name': renamed_name,
                'original_path': file_path,
                'date': file_date,
                'date_source': date_source,
                'type': file_type,
                'extension': extension
            })

        processed = 0
        progress_interval = Config.UI_UPDATE_INTERVAL
        
        with self._parallel_processor(io_bound=True) as executor:
            futures = {executor.submit(process_file, f): f for f in all_files}
            
            for future in as_completed(futures):
                processed += 1
                
                if processed % progress_interval == 0:
                    if not self._report_progress(progress_callback, processed, total_files, tr("services.progress.analyzing_filenames")):
                         return self._create_empty_result(total_files) # Cancelled
                
                status, file_path, data = future.result()
                
                if status == 'already_renamed':
                    already_renamed += 1
                elif status == 'no_metadata':
                    issues.append(data)
                elif status == 'no_date':
                    issues.append(data)
                elif status == 'unsupported':
                    issues.append(data)
                elif status == 'file_renamer':
                    renamed_name = data['renamed_name']
                    if renamed_name not in renaming_map:
                        renaming_map[renamed_name] = []
                    renaming_map[renamed_name].append(data)
                    files_by_year[data['date'].year] += 1

        for renamed_name, file_list in renaming_map.items():
            if len(file_list) == 1:
                file_info = file_list[0]
                renaming_plan.append(RenamePlanItem(
                    original_path=file_info['original_path'],
                    new_name=renamed_name,
                    date=file_info['date'],
                    date_source=file_info['date_source'],
                    has_conflict=False,
                    sequence=None
                ))
            else:
                conflicts += len(file_list) - 1
                file_list.sort(key=lambda x: x['original_path'].stat().st_mtime)

                for i, file_info in enumerate(file_list, 1):
                    sequenced_name = format_renamed_name(
                        file_info['date'],
                        file_info['type'],
                        file_info['extension'],
                        sequence=i
                    )

                    renaming_plan.append(RenamePlanItem(
                        original_path=file_info['original_path'],
                        new_name=sequenced_name,
                        date=file_info['date'],
                        date_source=file_info['date_source'],
                        has_conflict=True,
                        sequence=i
                    ))

        log_section_footer_discrete(self.logger, f"Analysis completed: {len(renaming_plan)} files to rename")
        
        # Calcular totales del análisis
        total_analyzed = len(renaming_plan) + already_renamed + len(issues)
        
        return RenameAnalysisResult(
            renaming_plan=renaming_plan,
            already_renamed=already_renamed,
            conflicts=conflicts,
            files_by_year=dict(files_by_year),
            issues=issues,
            items_count=total_analyzed,
            bytes_total=0  # No necesitamos calcular tamaño para renombrado
        )
    
    def execute(
        self,
        analysis_result: RenameAnalysisResult,
        create_backup: bool = True,
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs
    ) -> RenameExecutionResult:
        """
        Ejecuta el renombrado según el plan.
        """
        renaming_plan = analysis_result.renaming_plan
        
        if not renaming_plan:
            return RenameExecutionResult(
                success=True,
                items_processed=0,
                message='No files to rename',
                dry_run=dry_run
            )

        return self._execute_operation(
            files=[item.original_path for item in renaming_plan],
            operation_name='renaming',
            execute_fn=lambda dry: self._do_renaming(
                renaming_plan,
                dry,
                progress_callback
            ),
            create_backup=create_backup,
            dry_run=dry_run,
            progress_callback=progress_callback
        )
    
    def _do_renaming(
        self,
        renaming_plan: List[RenamePlanItem],
        dry_run: bool,
        progress_callback: Optional[ProgressCallback]
    ) -> RenameExecutionResult:
        """
        Lógica real de renombrado de archivos.
        """
        mode_label = "SIMULATION" if dry_run else ""
        log_section_header_relevant(self.logger, "STARTING FILE RENAMING", mode=mode_label)
        self.logger.info(f"*** Files to rename: {len(renaming_plan)}")

        # Obtener instancia del repositorio para actualizar caché después de renombrar
        repo = FileInfoRepositoryCache.get_instance()
        
        result = RenameExecutionResult(success=True, dry_run=dry_run)
        total_files = len(renaming_plan)
        items_processed = 0
        files_affected = []
        
        for item in renaming_plan:
            original_path = item.original_path
            new_name = item.new_name
            new_path = original_path.parent / new_name

            try:
                try:
                    if not original_path.exists():
                        raise FileNotFoundError(f"File not found: {original_path.name}")
                except FileNotFoundError as e:
                    self.logger.warning(str(e))
                    continue

                had_conflict = False
                conflict_sequence = None
                
                # Chequeo dinámico de conflictos
                if new_path.exists():
                     # (Lógica original de preservación de sufijos, etc.)
                    original_stem = original_path.stem
                    original_parts = original_stem.split('_')
                    preserved_suffix = ""
                    if len(original_parts) > 0 and original_parts[-1].isdigit() and len(original_parts[-1]) != 3:
                        preserved_suffix = f"_{original_parts[-1]}"
                    
                    base_name = Path(new_name).stem
                    extension = Path(new_name).suffix
                    base_name_with_preserved = base_name + preserved_suffix
                    new_name, sequence = find_next_available_name(
                        original_path.parent, base_name_with_preserved, extension
                    )
                    new_path = original_path.parent / new_name
                    had_conflict = True
                    conflict_sequence = sequence
                    result.conflicts_resolved += 1

                if not dry_run:
                    original_path.rename(new_path)
                    
                    # Actualizar caché moviendo el archivo
                    repo.move_file(original_path, new_path)

                items_processed += 1
                files_affected.append(original_path)
                
                date_str = item.date.strftime('%Y-%m-%d %H:%M:%S') if item.date else ''
                
                result.renamed_files.append(RenamedFileItem(
                    original=original_path.name,
                    new_name=new_name,
                    date=date_str,
                    had_conflict=item.has_conflict
                ))

                if items_processed % Config.UI_UPDATE_INTERVAL == 0:
                    progress_key = "services.progress.simulating_n_of_total" if dry_run else "services.progress.renaming_n_of_total"
                    if not self._report_progress(progress_callback, items_processed, total_files, tr(progress_key, current=items_processed, total=total_files)):
                         break

                log_prefix = "FILE_RENAMED_SIMULATION" if dry_run else "FILE_RENAMED"
                date_source = item.date_source or 'unknown'
                conflict_info = f" | Conflict: {conflict_sequence}" if had_conflict else ""
                self.logger.info(f"{log_prefix}: {original_path} -> {new_name} | Date: {date_str} ({date_source}){conflict_info}")

            except Exception as e:
                error_msg = f"Error renaming {original_path.name}: {str(e)}"
                self.logger.error(error_msg)
                result.add_error(f"{original_path.name}: {str(e)}")

        result.items_processed = items_processed
        result.files_affected = files_affected

        if result.errors:
            result.success = len(result.errors) < len(renaming_plan)

        completion_label = "FILE RENAMING COMPLETED"
        result_verb = "would be renamed" if dry_run else "renamed"
        summary = f"{completion_label}\nResult: {items_processed} files {result_verb}"
        log_section_footer_relevant(self.logger, summary)
        
        result.message = summary if dry_run else f"Renamed {items_processed} files"
        if result.backup_path: result.message += f"\nBackup: {result.backup_path}"
        if result.errors: result.message += f"\nWarning: {len(result.errors)} errors found"

        return result
    
    def _create_empty_result(self, total):
        return RenameAnalysisResult(
            renaming_plan=[],
            already_renamed=0,
            conflicts=0,
            files_by_year={},
            issues=[]
        )
