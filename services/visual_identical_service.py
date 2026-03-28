# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Servicio de detección de copias visuales idénticas.

Detecta archivos que son visualmente IDÉNTICOS al 100% aunque tengan
diferente resolución, compresión o metadatos (fechas, EXIF, etc.).

Casos de uso típicos:
- Fotos enviadas por WhatsApp (comprimidas)
- Screenshots repetidos
- Copias redimensionadas
- Fotos con metadatos modificados

Usa perceptual hashing con sensibilidad 100% (threshold=0) para
detectar solo archivos visualmente idénticos, no similares.
"""

from pathlib import Path
from typing import List, Optional, Any, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from config import Config
from utils.logger import get_logger, log_section_header_discrete, log_section_footer_discrete
from utils.format_utils import format_size
from utils.i18n import tr
from services.result_types import VisualIdenticalAnalysisResult, VisualIdenticalGroup
from services.base_service import BaseService, ProgressCallback
from services.file_metadata_repository_cache import FileInfoRepositoryCache


class VisualIdenticalService(BaseService):
    """
    Servicio de detección de copias visuales idénticas.
    
    A diferencia de DuplicatesSimilarService que detecta archivos similares
    con diferentes grados de similitud, este servicio se enfoca exclusivamente
    en archivos visualmente IDÉNTICOS (100% similitud perceptual).
    
    Esto permite:
    - Detección más precisa (sin falsos positivos)
    - UI más simple (sin slider de sensibilidad)
    - Ejecución automática segura
    """

    def __init__(self):
        """Inicializa el detector de copias visuales idénticas."""
        super().__init__('VisualIdenticalService')

    def analyze(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs
    ) -> VisualIdenticalAnalysisResult:
        """
        Analiza buscando copias visualmente idénticas.
        
        Usa perceptual hash con threshold=0 (solo 100% idénticos).
        
        Args:
            progress_callback: Callback de progreso
            **kwargs: Args adicionales
            
        Returns:
            VisualIdenticalAnalysisResult con grupos de idénticos
        """
        log_section_header_discrete(self.logger, "VISUAL IDENTICAL COPIES ANALYSIS")
        
        repo = FileInfoRepositoryCache.get_instance()
        
        # Calcular hashes perceptuales
        perceptual_hashes = self._calculate_perceptual_hashes(
            repo,
            progress_callback
        )
        
        if not perceptual_hashes:
            self.logger.info("No valid perceptual hashes obtained")
            return VisualIdenticalAnalysisResult(
                success=True,
                groups=[],
                total_files=0,
                total_groups=0,
                total_duplicates=0,
                space_recoverable=0
            )
        
        # Agrupar por hash idéntico (threshold=0)
        groups = self._group_by_identical_hash(perceptual_hashes)
        
        # Calcular estadísticas
        total_groups = len(groups)
        total_duplicates = sum(len(g.files) - 1 for g in groups)
        space_recoverable = sum(g.space_recoverable for g in groups)
        
        self.logger.info(
            f"Groups found: {total_groups}, "
            f"Duplicates: {total_duplicates}, "
            f"Recoverable space: {space_recoverable / (1024*1024):.1f} MB"
        )
        
        log_section_footer_discrete(self.logger, "VISUAL IDENTICAL COPIES ANALYSIS COMPLETED")
        
        return VisualIdenticalAnalysisResult(
            success=True,
            groups=groups,
            total_files=len(perceptual_hashes),
            total_groups=total_groups,
            total_duplicates=total_duplicates,
            space_recoverable=space_recoverable
        )

    def _calculate_perceptual_hashes(
        self,
        repo: FileInfoRepositoryCache,
        progress_callback: Optional[ProgressCallback] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calcula hashes perceptuales de todos los archivos de imagen.
        
        Args:
            repo: Repositorio de metadatos de archivos
            progress_callback: Callback de progreso
        
        Returns:
            Dict con {file_path: {'hash': hash_value, 'size': size, 'modified': mtime}}
        """
        try:
            import imagehash
        except ImportError:
            self.logger.error("imagehash library not installed.")
            raise ImportError("imagehash library not installed. Run: pip install imagehash")
        
        import time
        
        hash_calc_start = time.time()
        self.logger.info("Calculating perceptual hashes...")
        
        # Obtener archivos desde FileInfoRepository
        all_metadata = repo.get_all_files()
        
        # Filtrar solo imágenes (videos son más costosos y menos comunes para este caso de uso)
        image_files = []
        supported_img = Config.SUPPORTED_IMAGE_EXTENSIONS
        
        for meta in all_metadata:
            if meta.extension in supported_img:
                image_files.append(meta.path)
        
        total_files = len(image_files)
        
        self.logger.info(f"Image files to process: {total_files}")
        
        if total_files == 0:
            return {}
        
        # Calcular hashes perceptuales en paralelo
        perceptual_hashes = {}
        processed = 0
        errors = 0
        
        # Usar phash por defecto (más robusto para este caso de uso)
        algorithm = Config.PERCEPTUAL_HASH_ALGORITHM
        hash_size = Config.PERCEPTUAL_HASH_SIZE
        
        with self._parallel_processor(io_bound=False) as executor:
            future_to_file = {}
            
            for file_path in image_files:
                future = executor.submit(
                    self._calculate_image_hash,
                    file_path,
                    algorithm,
                    hash_size
                )
                future_to_file[future] = file_path
            
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    phash = future.result(timeout=5.0)
                    if phash is not None:
                        # Obtener tamaño y fecha desde cache
                        meta = repo.get_file_metadata(file_path)
                        size = meta.fs_size if meta else file_path.stat().st_size
                        mtime = meta.fs_mtime if meta else file_path.stat().st_mtime
                        
                        # Obtener dimensiones si están disponibles
                        width = getattr(meta, 'image_width', None) if meta else None
                        height = getattr(meta, 'image_height', None) if meta else None
                        
                        perceptual_hashes[str(file_path)] = {
                            'hash': phash,
                            'size': size,
                            'modified': mtime,
                            'width': width,
                            'height': height
                        }
                    
                    processed += 1
                    if self._should_report_progress(processed, interval=50):
                        if not self._report_progress(
                            progress_callback,
                            processed,
                            total_files,
                            tr("services.progress.processing_file", name=file_path.name)
                        ):
                            break
                except TimeoutError:
                    processed += 1
                    self.logger.debug(f"Timeout processing {file_path.name}")
                except Exception as e:
                    errors += 1
                    processed += 1
                    self.logger.debug(f"Error processing {file_path.name}: {e}")
        
        # Log stats
        hash_calc_time = time.time() - hash_calc_start
        self.logger.info(
            f"Hashes calculated: {len(perceptual_hashes)} in {hash_calc_time:.1f}s "
            f"({len(perceptual_hashes)/max(hash_calc_time, 0.1):.1f} files/s)"
        )
        
        if errors > 0:
            self.logger.warning(f"Errors during calculation: {errors}")
        
        if len(perceptual_hashes) == 0 and total_files > 0:
            self.logger.error(
                f"All {total_files} hash calculations failed. "
                f"This usually indicates a missing dependency (scipy, pywt, numpy) "
                f"in the packaged binary. Check warnings above for details."
            )
        
        return perceptual_hashes

    def _calculate_image_hash(
        self,
        file_path: Path,
        algorithm: str = "phash",
        hash_size: int = 16
    ) -> Optional[Any]:
        """
        Calcula hash perceptual de una imagen.
        
        Args:
            file_path: Ruta al archivo de imagen
            algorithm: Algoritmo de hash ("dhash", "phash", "ahash")
            hash_size: Tamaño del hash
        
        Returns:
            Hash perceptual de la imagen o None si hay error
        """
        try:
            import imagehash
            from PIL import Image
            
            with Image.open(file_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Seleccionar algoritmo de hash
                if algorithm == "phash":
                    return imagehash.phash(img, hash_size=hash_size)
                elif algorithm == "ahash":
                    return imagehash.average_hash(img, hash_size=hash_size)
                else:  # dhash (default)
                    return imagehash.dhash(img, hash_size=hash_size)
                    
        except ImportError as e:
            self.logger.warning(f"Missing dependency for perceptual hash: {e}")
            return None
        except Exception as e:
            self.logger.debug(f"Error calculating hash for {file_path.name}: {e}")
            return None

    def _group_by_identical_hash(
        self,
        hashes: Dict[str, Dict[str, Any]]
    ) -> List[VisualIdenticalGroup]:
        """
        Agrupa archivos por hash perceptual idéntico.
        
        Solo agrupa archivos con EXACTAMENTE el mismo hash (distancia Hamming = 0).
        
        Args:
            hashes: Dict con {file_path: {'hash': hash_value, 'size': size, ...}}
        
        Returns:
            Lista de VisualIdenticalGroup con grupos de archivos idénticos
        """
        # Agrupar por hash string
        hash_groups: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
        
        for path, data in hashes.items():
            hash_str = str(data['hash'])
            if hash_str not in hash_groups:
                hash_groups[hash_str] = []
            hash_groups[hash_str].append((path, data))
        
        # Crear grupos solo donde hay más de 1 archivo
        groups = []
        
        for hash_str, files_data in hash_groups.items():
            if len(files_data) < 2:
                continue
            
            # Crear lista de archivos con metadata
            files = []
            sizes = []
            total_size = 0
            
            for path, data in files_data:
                files.append(Path(path))
                sizes.append(data['size'])
                total_size += data['size']
            
            # Calcular espacio recuperable (todo menos el archivo más grande)
            max_size = max(sizes)
            space_recoverable = total_size - max_size
            
            # Determinar si hay variación de tamaño significativa
            min_size = min(sizes)
            size_variation = ((max_size - min_size) / min_size * 100) if min_size > 0 else 0
            
            group = VisualIdenticalGroup(
                hash_value=hash_str,
                files=files,
                file_sizes=sizes,
                total_size=total_size,
                space_recoverable=space_recoverable,
                size_variation_percent=size_variation
            )
            groups.append(group)
        
        # Ordenar por espacio recuperable (mayor primero)
        groups.sort(key=lambda g: g.space_recoverable, reverse=True)
        
        self.logger.info(
            f"Identical groups found: {len(groups)} "
            f"(from {len(hash_groups)} unique hashes)"
        )
        
        return groups

    def execute(
        self,
        groups: List[VisualIdenticalGroup],
        files_to_delete: List[Path],
        create_backup: bool = True,
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None
    ):
        """
        Ejecuta la eliminación de archivos duplicados.
        
        Args:
            groups: Grupos de archivos idénticos
            files_to_delete: Lista de archivos a eliminar
            create_backup: Si crear backup antes de eliminar
            dry_run: Si es simulación
            progress_callback: Callback de progreso
            
        Returns:
            ExecutionResult con resultados
        """
        from services.result_types import VisualIdenticalExecutionResult
        from services.base_service import BackupCreationError
        
        log_section_header_discrete(self.logger, "EXECUTING IDENTICAL COPIES DELETION")
        
        if not files_to_delete:
            self.logger.info("No files to delete")
            return VisualIdenticalExecutionResult(
                success=True,
                dry_run=dry_run,
                items_processed=0,
                bytes_processed=0
            )
        
        # Crear backup usando método centralizado de BaseService
        backup_path = None
        if create_backup and not dry_run:
            self.logger.info("Creating backup of files...")
            try:
                backup_path = self._create_backup_for_operation(
                    files_to_delete,
                    'visual_identical',
                    progress_callback
                )
                if backup_path:
                    self.logger.info(f"Backup created at: {backup_path}")
            except BackupCreationError as e:
                self.logger.error(f"Error creating backup: {e}")
                return VisualIdenticalExecutionResult(
                    success=False,
                    dry_run=dry_run,
                    errors=[f"Error creating backup: {e}"]
                )
        
        # Eliminar archivos usando método centralizado
        deleted_count = 0
        deleted_bytes = 0
        errors = []
        files_affected = []
        
        total = len(files_to_delete)
        for i, file_path in enumerate(files_to_delete):
            try:
                file_size = file_path.stat().st_size if file_path.exists() else 0
                
                if self._delete_file_with_logging(file_path, file_size, 'visual_identical', dry_run):
                    deleted_count += 1
                    deleted_bytes += file_size
                    files_affected.append(file_path)
                else:
                    self.logger.warning(
                        f"FILE_SKIPPED: {file_path} | "
                        f"Size: {format_size(file_size)} | "
                        f"Type: visual_identical | "
                        f"Reason: Could not delete file"
                    )
                    errors.append(f"Could not delete: {file_path}")
                
                if self._should_report_progress(i, interval=10):
                    self._report_progress(
                        progress_callback,
                        i + 1,
                        total,
                        tr("services.progress.deleting_file", name=file_path.name)
                    )
                    
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")
                self.logger.error(f"Error deleting {file_path}: {e}")
        
        # Resumen de archivos descartados
        total_skipped = total - deleted_count
        if total_skipped > 0:
            self.logger.warning(
                f"SKIPPED_SUMMARY: {total_skipped}/{total} files could not be deleted"
            )
        
        log_section_footer_discrete(self.logger, "IDENTICAL COPIES DELETION COMPLETED")
        
        result = VisualIdenticalExecutionResult(
            success=len(errors) == 0,
            dry_run=dry_run,
            items_processed=deleted_count,
            bytes_processed=deleted_bytes,
            files_affected=files_affected,
            backup_path=backup_path,
            errors=errors
        )
        
        return result
