# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Organizador de Archivos
Refactorizado para usar MetadataCache.
"""

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config
from utils.logger import log_section_header_relevant, log_section_footer_relevant, log_section_header_discrete, log_section_footer_discrete
from utils.date_utils import select_best_date_from_file, get_all_metadata_from_file
from utils.file_utils import detect_file_source, cleanup_empty_directories, get_file_type, is_supported_file
from services.result_types import OrganizationExecutionResult, OrganizationAnalysisResult
from services.base_service import BaseService, ProgressCallback
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from utils.i18n import tr

class OrganizationType(Enum):
    """Tipos de organización disponibles"""
    BY_MONTH = "by_month"
    BY_YEAR = "by_year"
    BY_YEAR_MONTH = "by_year_month"
    BY_TYPE = "by_type"
    BY_SOURCE = "by_source"
    TO_ROOT = "to_root"

@dataclass
class FileMove:
    """Representa un movimiento de archivo"""
    source_path: Path
    target_path: Path
    original_name: str
    new_name: str
    subdirectory: str
    file_type: str
    size: int
    has_conflict: bool = False
    sequence: Optional[int] = None
    target_folder: Optional[str] = None
    source: str = "Unknown"
    best_date: Optional[datetime] = None
    best_date_source: Optional[str] = None

    def __post_init__(self):
        if not self.source_path.exists():
            # Permitimos que no exista si es simulacion o si se borró
            # pero en validación estricta deberíamos lanzar error.
            # BaseService original lanzaba ValueError.
            pass

class FileOrganizerService(BaseService):
    """Organizador de archivos - Mueve archivos multimedia de subdirectorios al directorio raíz"""

    def __init__(self):
        super().__init__("FileOrganizer")

    def analyze(self, 
                root_directory: Path, 
                organization_type: OrganizationType, 
                progress_callback: Optional[ProgressCallback] = None,
                group_by_source: bool = False,
                group_by_type: bool = False,
                date_grouping_type: Optional[str] = None,
                move_unsupported_to_other: bool = False,
                **kwargs) -> OrganizationAnalysisResult:
        """
        Analiza el directorio y genera un plan de organización usando metadatos.
        """
        log_section_header_discrete(self.logger, f"ANALYZING ORGANIZATION ({organization_type.value}): {root_directory}")

        repo = FileInfoRepositoryCache.get_instance()
        self.logger.info(f"Using FileInfoRepositoryCache with {repo.get_file_count()} files")
        
        subdirectories = {}
        root_files = []
        folder_names_in_root = set() # Nombres de carpetas/archivos en root para conflictos
        
        if not root_directory.exists():
             raise ValueError(f"Directory does not exist: {root_directory}")

        # Recopilar nombres existentes en root (para TO_ROOT y check de conflictos)
        try:
            folder_names_in_root = {item.name for item in root_directory.iterdir()}
        except Exception:
            pass

        # Usar caché de metadatos (repositorio pasivo)
        all_files = []
        self.logger.info(f"Using metadata cache ({repo.get_file_count()} files)")
        
        # Filtrar archivos que pertenecen a root_directory
        cache_files = repo.get_all_files()
        
        for meta in cache_files:
            # Comprobar si está dentro de root_directory
            try:
                if meta.path.is_relative_to(root_directory):
                    all_files.append(meta)
            except ValueError:
                continue

        total_files = len(all_files)
        total_scanned_size = sum(meta.fs_size for meta in all_files)
        files_by_type = Counter()
        processed_files = 0
        
        # Clasificar archivos en subdirectories y root_files
        for idx, meta in enumerate(all_files):
            if idx % 500 == 0:
                if idx % 5000 == 0 and idx > 0:
                    self.logger.info(f"Organizer: Classifying files {idx}/{total_files}")
                    
                if not self._report_progress(progress_callback, idx, total_files, tr("services.progress.classifying_files")):
                    return self._create_empty_result(root_directory, organization_type, group_by_source, group_by_type, date_grouping_type, move_unsupported_to_other)

            file_path = meta.path
            parent_dir = file_path.parent
            
            # Info dict para compatibilidad con lógica existente
            # Incluir best_date del cache (calculado en Phase 6 del scanner)
            # para evitar recalcularla en los generadores de plan
            info = {
                    'path': file_path,
                    'name': file_path.name,
                    'size': meta.fs_size,
                    'type': get_file_type(file_path.name),
                    '_best_date': meta.best_date,
                    '_best_date_source': meta.best_date_source,
            }
            files_by_type[info['type']] += 1

            if parent_dir == root_directory:
                root_files.append(info)
            else:
                # Es subdirectorio
                relative_path = file_path.relative_to(root_directory)
                subdir_name = str(relative_path.parent)
                
                if subdir_name not in subdirectories:
                    subdirectories[subdir_name] = {
                        'path': str(parent_dir),
                        'file_count': 0,
                        'total_size': 0,
                        'files': []
                    }
                subdirectories[subdir_name]['files'].append(info)
                subdirectories[subdir_name]['file_count'] += 1
                subdirectories[subdir_name]['total_size'] += meta.fs_size
        
        # Generar plan usando la lógica existente
        # existing_file_names es folder_names_in_root
        
        move_plan = []
        potential_conflicts = 0

        if subdirectories or root_files:
             move_plan = self._generate_move_plan(
                subdirectories,
                root_files,
                root_directory,
                folder_names_in_root,
                organization_type,
                progress_callback,
                group_by_source,
                group_by_type,
                date_grouping_type
            )
             potential_conflicts = sum(1 for move in move_plan if move.has_conflict)
        
        # Mover archivos no soportados a carpeta 'other/' si está activado
        if move_unsupported_to_other:
            other_moves = self._generate_other_files_moves(root_directory, all_files, progress_callback)
            move_plan.extend(other_moves)
            self.logger.info(f"Unsupported files to move to 'other/': {len(other_moves)}")

        log_section_footer_discrete(self.logger, f"Plan generado: {len(move_plan)} movimientos")

        # Recalcular dumps finales para result
        final_files_by_type = Counter()
        files_by_subdir = defaultdict(self._get_default_subdir_info)
        total_size = 0
        
        for move in move_plan:
             final_files_by_type[move.file_type] += 1
             total_size += move.size
             
             subdir_key = move.subdirectory if move.subdirectory != '<root>' else 'root_files'
             if subdir_key not in files_by_subdir:
                 if move.subdirectory == '<root>':
                     files_by_subdir[subdir_key]['path'] = str(root_directory)
                 else:
                     files_by_subdir[subdir_key]['path'] = str(root_directory / move.subdirectory)
             
             files_by_subdir[subdir_key]['file_count'] += 1
             files_by_subdir[subdir_key]['total_size'] += move.size
             files_by_subdir[subdir_key]['files'].append({
                 'path': move.source_path,
                 'name': move.original_name,
                 'size': move.size,
                 'type': move.file_type
             })

        return OrganizationAnalysisResult(
            move_plan=move_plan,
            root_directory=str(root_directory),
            organization_type=organization_type.value,
            subdirectories=subdirectories,
            items_count=total_files,
            bytes_total=total_scanned_size,
            group_by_source=group_by_source,
            group_by_type=group_by_type,
            date_grouping_type=date_grouping_type,
            move_unsupported_to_other=move_unsupported_to_other
        )
    
    def execute(self, 
                analysis_result: OrganizationAnalysisResult,
                create_backup: bool = True, 
                dry_run: bool = False, 
                progress_callback: Optional[ProgressCallback] = None, 
                **kwargs) -> OrganizationExecutionResult:
        """
        Ejecuta la organización (renombrado/movimiento).
        Adaptado para usar OrganizationAnalysisResult.
        """
        move_plan = analysis_result.move_plan
        cleanup_empty_dirs = kwargs.get('cleanup_empty_dirs', True)
        
        if not move_plan:
            return OrganizationExecutionResult(success=True, message='No files to move')

        root_directory = Path(analysis_result.root_directory)
        
        mode_label = "SIMULATION" if dry_run else ""
        log_section_header_relevant(self.logger, "STARTING FILE ORGANIZATION", mode=mode_label)
        self.logger.info(f"*** Files to move: {len(move_plan)}")
        
        result = OrganizationExecutionResult(success=True, dry_run=dry_run)
        
        try:
             # Crear carpetas
             folders = analysis_result.folders_to_create
             if not dry_run:
                 for f in folders:
                     (root_directory / f).mkdir(parents=True, exist_ok=True)
                     result.folders_created.append(str(root_directory / f))
             
             # Backup
             if create_backup and not dry_run:
                 self._report_progress(progress_callback, 0, len(move_plan), tr("services.progress.creating_backup"))
                 files = [m.source_path for m in move_plan]
                 bk_path = self._create_backup_for_operation(
                     files, 'organization', progress_callback
                 )
                 if bk_path:
                     result.backup_path = bk_path
             
             # Ejecución
             total = len(move_plan)
             items_processed = 0
             bytes_processed = 0
             files_affected = []
             
             self._report_progress(progress_callback, 0, total, tr("services.progress.organizing"))
             
             for move in move_plan:
                 items_processed += 1
                 if items_processed % Config.UI_UPDATE_INTERVAL == 0:
                      if not self._report_progress(progress_callback, items_processed, total, tr("services.progress.processing_n_of_total", current=items_processed, total=total)):
                          break
                 
                 target = move.target_path
                 
                 try:
                     # Defense in depth: skip no-op moves (source == target)
                     if move.source_path == target:
                         continue
                     
                     if not move.source_path.exists():
                         self.logger.warning(f"Source missing: {move.source_path}")
                         continue
                     
                     if dry_run:
                         bytes_processed += move.size
                         files_affected.append(target)
                         self.logger.info(f"FILE_MOVED_SIMULATION: {move.source_path} -> {target}")
                     else:
                         target.parent.mkdir(parents=True, exist_ok=True)
                         if target.exists():
                             # Fallback conflicto last second
                             stem = target.stem
                             suffix = target.suffix
                             counter = 1
                             while target.exists():
                                 target = target.parent / f"{stem}_{counter:03d}{suffix}"
                                 counter += 1
                         
                         move.source_path.rename(target)
                         bytes_processed += move.size
                         files_affected.append(target)
                         self.logger.info(f"FILE_MOVED: {move.source_path} -> {target}")
                         
                         # Actualizar caché moviendo el archivo (si está en caché)
                         repo = FileInfoRepositoryCache.get_instance()
                         repo.move_file(move.source_path, target)

                 except Exception as e:
                     result.add_error(f"Error {move.source_path.name}: {e}")
             
             result.items_processed = items_processed
             result.bytes_processed = bytes_processed
             result.files_affected = files_affected

             # Limpieza directorios vacíos (incluye preexistentes)
             if cleanup_empty_dirs and not dry_run:
                 removed = cleanup_empty_directories(root_directory)
                 result.empty_directories_removed = removed
                 if removed > 0:
                     self.logger.info(f"Empty folders removed: {removed}")
                 
             summary = self._format_operation_summary("Organization", items_processed, 0, dry_run)
             log_section_footer_relevant(self.logger, summary)
             result.message = summary
             if result.backup_path:
                  result.message += f"\nBackup: {result.backup_path}"
 
        except Exception as e:
            result.add_error(str(e))
            self.logger.error(f"Critical error: {e}")
            
        return result

    def _get_default_subdir_info(self):
        return {'path': '', 'file_count': 0, 'total_size': 0, 'files': []}
        
    def _create_empty_result(self, root, type_, group_by_source=False, group_by_type=False, date_grouping_type=None, move_unsupported_to_other=False):
        return OrganizationAnalysisResult(
            move_plan=[],
            root_directory=str(root),
            organization_type=type_.value,
            subdirectories={},
            group_by_source=group_by_source,
            group_by_type=group_by_type,
            date_grouping_type=date_grouping_type,
            move_unsupported_to_other=move_unsupported_to_other
        )

    # --- MÉTODOS DE GENERACIÓN DE PLAN (Idénticos a original, simplificados llamada) ---
    # Copiamos la lógica exacta de _generate_move_plan y sus submétodos
    
    def _generate_move_plan(self, subdirectories, root_files, root_directory, existing_file_names, organization_type, progress_callback, group_by_source, group_by_type, date_grouping_type):
        if organization_type == OrganizationType.TO_ROOT:
            return self._generate_move_plan_to_root(subdirectories, root_directory, existing_file_names, progress_callback)
        elif organization_type == OrganizationType.BY_MONTH:
            return self._generate_move_plan_by_month(subdirectories, root_files, root_directory, group_by_source, group_by_type, progress_callback)
        elif organization_type == OrganizationType.BY_YEAR:
            return self._generate_move_plan_by_year(subdirectories, root_files, root_directory, group_by_source, group_by_type, progress_callback)
        elif organization_type == OrganizationType.BY_YEAR_MONTH:
            return self._generate_move_plan_by_year_month(subdirectories, root_files, root_directory, group_by_source, group_by_type, progress_callback)
        elif organization_type == OrganizationType.BY_TYPE:
            return self._generate_move_plan_by_type(subdirectories, root_files, root_directory, group_by_source, date_grouping_type, progress_callback)
        elif organization_type == OrganizationType.BY_SOURCE:
            return self._generate_move_plan_by_source(subdirectories, root_files, root_directory, date_grouping_type, progress_callback)
        else:
            raise ValueError(f"Unsupported type: {organization_type}")

    # ... (Copiar todos los métodos _generate_move_plan_* y _resolve_conflicts_in_folder tal cual estaban, 
    # pero asegurando que select_best_date_from_file use FileInfoRepository)
    
    def _resolve_conflicts_in_folder(self, name_conflicts: Dict, target_folder: Path) -> List[FileMove]:
        move_plan = []
        
        # Pre-scan existing files ONCE for the entire folder (avoid repeated iterdir)
        existing_names = set()
        if target_folder.exists():
            try:
                existing_names = {item.name for item in target_folder.iterdir() if item.is_file()}
            except OSError:
                pass
        
        for file_name, moves in name_conflicts.items():
            if len(moves) == 1 and not moves[0].has_conflict:
                move_plan.append(moves[0])
            else:
                base_name = Path(file_name).stem
                extension = Path(file_name).suffix
                seq = 1
                
                for move in moves:
                    new_name = f"{base_name}_{seq:03d}{extension}"
                    # Check against pre-scanned names and dynamically added names
                    while new_name in existing_names:
                        seq += 1
                        new_name = f"{base_name}_{seq:03d}{extension}"
                    
                    existing_names.add(new_name)  # Track newly assigned names
                    move.new_name = new_name
                    move.target_path = target_folder / new_name
                    move.has_conflict = True
                    move.sequence = seq
                    seq += 1
                    move_plan.append(move)
        return move_plan

    def _generate_move_plan_to_root(self, subdirectories: Dict, root_directory: Path, existing_files: Set[str], progress_callback=None) -> List[FileMove]:
        move_plan = []
        name_conflicts = defaultdict(list)
        total_items = sum(len(d['files']) for d in subdirectories.values())
        processed = 0

        for subdir_name, subdir_data in subdirectories.items():
            for file_info in subdir_data['files']:
                processed += 1
                if processed % 1000 == 0:
                     self._report_progress(progress_callback, processed, total_items, tr("services.progress.analyzing"))
                
                fname = file_info['name']
                fpath = Path(file_info['path'])
                target_path = root_directory / fname
                
                # Skip no-op moves: file already in correct destination
                if fpath == target_path:
                    continue
                
                conflict = fname in existing_files
                # Usar best_date pre-calculada del cache (almacenada en info dict)
                file_date = file_info.get('_best_date')
                file_date_source = file_info.get('_best_date_source')
                if file_date is None:
                    # Fallback: calcular si no disponible en cache
                    file_metadata = get_all_metadata_from_file(fpath)
                    file_date, file_date_source = select_best_date_from_file(file_metadata)
                move = FileMove(fpath, target_path, fname, fname, subdir_name, file_info['type'], file_info['size'], conflict, source=detect_file_source(fname, fpath), best_date=file_date, best_date_source=file_date_source)
                name_conflicts[fname].append(move)
        return self._resolve_conflicts_in_folder(name_conflicts, root_directory)

    def _generate_other_files_moves(self, root_directory: Path, cached_files: list, progress_callback=None) -> List[FileMove]:
        """
        Genera plan de movimiento para archivos no soportados a carpeta 'other/'.
        Preserva la estructura de carpetas relativa dentro de 'other/'.
        
        Args:
            root_directory: Directorio raíz del proyecto
            cached_files: Lista de FileMetadata de archivos soportados (ya en caché)
            progress_callback: Callback de progreso opcional
            
        Returns:
            Lista de FileMove para archivos no soportados
        """
        move_plan = []
        cached_paths = {meta.path.resolve() for meta in cached_files}
        other_dir = root_directory / "other"
        
        # Escanear filesystem para encontrar archivos no soportados
        unsupported_files = []
        for f in root_directory.rglob('*'):
            if not f.is_file():
                continue
            # Saltar archivos que ya están en la caché (soportados)
            if f.resolve() in cached_paths:
                continue
            # Saltar archivos que ya están dentro de la carpeta 'other/'
            try:
                if f.is_relative_to(other_dir):
                    continue
            except (ValueError, TypeError):
                pass
            unsupported_files.append(f)
        
        if not unsupported_files:
            return move_plan
        
        self.logger.info(f"Unsupported files found: {len(unsupported_files)}")
        
        total = len(unsupported_files)
        for idx, f in enumerate(unsupported_files):
            if idx % 500 == 0 and progress_callback:
                self._report_progress(progress_callback, idx, total, tr("services.progress.classifying_unsupported"))
            
            relative = f.relative_to(root_directory)
            target_path = other_dir / relative
            
            # Skip no-op moves: file already in correct destination
            if f == target_path:
                continue
            
            target_folder_str = str(Path("other") / relative.parent) if str(relative.parent) != '.' else "other"
            
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            
            # Verificar conflicto (archivo ya existe en destino)
            has_conflict = target_path.exists()
            
            move = FileMove(
                source_path=f,
                target_path=target_path,
                original_name=f.name,
                new_name=f.name,
                subdirectory=str(relative.parent) if str(relative.parent) != '.' else '<root>',
                file_type='OTHER',
                size=size,
                has_conflict=has_conflict,
                target_folder=target_folder_str,
                source="Others"
            )
            move_plan.append(move)
        
        return move_plan

    def _generate_move_plan_by_month(self, subdirs, root_files, root_dir, group_src, group_type, progress_callback=None):
        return self._generic_date_plan(subdirs, root_files, root_dir, group_src, group_type, "%Y_%m", progress_callback)

    def _generate_move_plan_by_year(self, subdirs, root_files, root_dir, group_src, group_type, progress_callback=None):
         return self._generic_date_plan(subdirs, root_files, root_dir, group_src, group_type, "%Y", progress_callback)
         
    def _generate_move_plan_by_year_month(self, subdirs, root_files, root_dir, group_src, group_type, progress_callback=None):
         return self._generic_date_plan(subdirs, root_files, root_dir, group_src, group_type, "%Y/%m", progress_callback)

    def _generic_date_plan(self, subdirs, root_files, root_dir, group_src, group_type, date_fmt, progress_callback=None):
        move_plan = []
        files_map = defaultdict(list)
        
        # Calculate total files for global progress
        total_files = len(root_files) + sum(len(d['files']) for d in subdirs.values())
        processed_count = 0
        
        def process(files, subdir_name):
            nonlocal processed_count
            
            for info in files:
                processed_count += 1
                if processed_count % 500 == 0:
                   self._report_progress(progress_callback, processed_count, total_files, tr("services.progress.analyzing_dates"))
                
                path = Path(info['path'])
                
                # Usar best_date pre-calculada del cache (Phase 6 del scanner)
                # Solo recalcular si no está disponible (fallback)
                date = info.get('_best_date')
                date_source = info.get('_best_date_source')
                if not date:
                    file_metadata = get_all_metadata_from_file(path)
                    date, date_source = select_best_date_from_file(file_metadata)
                    if not date:
                        date = datetime.now()
                        date_source = None
                    info['_best_date'] = date
                    info['_best_date_source'] = date_source
                folder = date.strftime(date_fmt)
                if group_src: folder += f"/{detect_file_source(info['name'], path)}"
                if group_type:
                    t = 'Photos' if info['type'] == 'PHOTO' else 'Videos' if info['type'] == 'VIDEO' else 'Others'
                    folder += f"/{t}"
                files_map[folder].append({'info': info, 'subdir': subdir_name})

        # Iterate all files
        # Subdirectories
        for name, data in subdirs.items(): 
            process(data['files'], name)
        # Root files
        process(root_files, '<root>')
        
        for folder, items in files_map.items():
            target_folder = root_dir / folder
            conflicts = defaultdict(list)
            # Check existing
            exist = set()
            if target_folder.exists():
                exist = {i.name for i in target_folder.iterdir() if i.is_file()}
            
            for item in items:
                info = item['info']
                fname = info['name']
                source_path = Path(info['path'])
                target_path = target_folder / fname
                
                # Skip no-op moves: file already in correct destination
                if source_path == target_path:
                    continue
                
                move = FileMove(
                    source_path, target_path, fname, fname, item['subdir'],
                    info['type'], info['size'], fname in exist, target_folder=folder,
                    best_date=info.get('_best_date'),
                    best_date_source=info.get('_best_date_source')
                )
                conflicts[fname].append(move)
            move_plan.extend(self._resolve_conflicts_in_folder(conflicts, target_folder))
        return move_plan

    def _generate_move_plan_by_type(self, subdirectories: Dict, root_files: List[Dict], root_directory: Path, group_by_source: bool = False, date_grouping_type: Optional[str] = None, progress_callback=None) -> List[FileMove]:
        """Genera plan de movimiento separando por tipo de archivo (Fotos/Videos)"""
        move_plan = []
        files_by_type = defaultdict(list)
        type_folder_map = {'PHOTO': 'Photos', 'VIDEO': 'Videos'}

        # Calculate total files for global progress
        total_files = len(root_files) + sum(len(d['files']) for d in subdirectories.values())
        processed_count = 0

        def process_files(file_list, subdir_name):
            nonlocal processed_count
            
            for info in file_list:
                processed_count += 1
                if processed_count % 500 == 0:
                     self._report_progress(progress_callback, processed_count, total_files, tr("services.progress.analyzing_types"))
                
                path = Path(info['path'])
                info['path'] = str(path) # Ensure string for consistency if needed, though previously it was mixed usage
                
                file_path = Path(info['path'])
                file_type = info['type']
                folder_name = type_folder_map.get(file_type, 'Others')

                if group_by_source:
                    source = detect_file_source(info['name'], file_path)
                    folder_name = f"{folder_name}/{source}"
                
                if date_grouping_type:
                    # Usar best_date pre-calculada del cache
                    file_date = info.get('_best_date')
                    file_date_source = info.get('_best_date_source')
                    if not file_date:
                        file_metadata = get_all_metadata_from_file(file_path)
                        file_date, file_date_source = select_best_date_from_file(file_metadata)
                        if not file_date:
                            file_date = datetime.now()
                            file_date_source = None
                        info['_best_date'] = file_date
                        info['_best_date_source'] = file_date_source
                    date_folder = ""
                    if date_grouping_type == 'month': date_folder = file_date.strftime('%Y_%m')
                    elif date_grouping_type == 'year': date_folder = file_date.strftime('%Y')
                    elif date_grouping_type == 'year_month': date_folder = file_date.strftime('%Y/%m')
                    
                    if date_folder: folder_name = f"{folder_name}/{date_folder}"
                
                files_by_type[folder_name].append({'info': info, 'subdir': subdir_name})

        for name, data in subdirectories.items():
            process_files(data['files'], name)
        process_files(root_files, '<root>')

        for folder_name, items in files_by_type.items():
            target_folder = root_directory / folder_name
            name_conflicts = defaultdict(list)
            
            existing = set()
            if target_folder.exists():
                existing = {i.name for i in target_folder.iterdir() if i.is_file()}
            
            for item in items:
                info = item['info']
                fname = info['name']
                source_path = Path(info['path'])
                target_path = target_folder / fname
                
                # Skip no-op moves: file already in correct destination
                if source_path == target_path:
                    continue
                
                move = FileMove(
                    source_path, target_path, fname, fname,
                    item['subdir'], info['type'], info['size'], fname in existing,
                    target_folder=folder_name,
                    source=detect_file_source(fname, source_path),
                    best_date=info.get('_best_date'),
                    best_date_source=info.get('_best_date_source')
                )
                name_conflicts[fname].append(move)
            
            move_plan.extend(self._resolve_conflicts_in_folder(name_conflicts, target_folder))
            
        return move_plan

    def _generate_move_plan_by_source(self, subdirectories: Dict, root_files: List[Dict], root_directory: Path, date_grouping_type: Optional[str] = None, progress_callback=None) -> List[FileMove]:
        """Genera plan de movimiento separando por fuente detectada"""
        move_plan = []
        files_by_source = defaultdict(list)
        
        # Calculate total files for global progress
        total_files = len(root_files) + sum(len(d['files']) for d in subdirectories.values())
        processed_count = 0

        def process_files(file_list, subdir_name):
            nonlocal processed_count
            
            for info in file_list:
                processed_count += 1
                if processed_count % 500 == 0:
                     self._report_progress(progress_callback, processed_count, total_files, tr("services.progress.analyzing_sources"))
                
                file_path = Path(info['path'])
                source = detect_file_source(info['name'], file_path)

                if date_grouping_type:
                     # Usar best_date pre-calculada del cache
                     file_date = info.get('_best_date')
                     file_date_source = info.get('_best_date_source')
                     if not file_date:
                         file_metadata = get_all_metadata_from_file(file_path)
                         file_date, file_date_source = select_best_date_from_file(file_metadata)
                         if not file_date:
                             file_date = datetime.now()
                             file_date_source = None
                         info['_best_date'] = file_date
                         info['_best_date_source'] = file_date_source
                     date_folder = ""
                     if date_grouping_type == 'month': date_folder = file_date.strftime('%Y_%m')
                     elif date_grouping_type == 'year': date_folder = file_date.strftime('%Y')
                     elif date_grouping_type == 'year_month': date_folder = file_date.strftime('%Y/%m')
                     
                     if date_folder: source = f"{source}/{date_folder}"
                
                files_by_source[source].append({'info': info, 'subdir': subdir_name})

        for name, data in subdirectories.items(): process_files(data['files'], name)
        process_files(root_files, '<root>')

        for source_name, items in files_by_source.items():
            target_folder = root_directory / source_name
            name_conflicts = defaultdict(list)
            existing = set()
            if target_folder.exists():
                 existing = {i.name for i in target_folder.iterdir() if i.is_file()}
            
            for item in items:
                info = item['info']
                fname = info['name']
                source_path = Path(info['path'])
                target_path = target_folder / fname
                
                # Skip no-op moves: file already in correct destination
                if source_path == target_path:
                    continue
                
                move = FileMove(
                    source_path, target_path, fname, fname,
                    item['subdir'], info['type'], info['size'], fname in existing,
                    target_folder=source_name,
                    source=source_name,
                    best_date=info.get('_best_date'),
                    best_date_source=info.get('_best_date_source')
                )
                name_conflicts[fname].append(move)
            move_plan.extend(self._resolve_conflicts_in_folder(name_conflicts, target_folder))

        return move_plan
