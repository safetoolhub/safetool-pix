# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Servicio de detección de archivos similares mediante perceptual hashing.

Identifica fotos y vídeos visualmente similares: recortes, rotaciones,
ediciones o diferentes resoluciones.

Usa FileInfoRepositoryCache como única fuente de metadatos.
Optimizado con BK-Tree para clustering O(N log N).
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any, Dict, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import os

from config import Config
from utils.logger import get_logger, log_section_header_discrete, log_section_footer_discrete
from services.result_types import (
    SimilarDuplicateGroup,
    SimilarDuplicateAnalysisResult,
    SimilarDuplicateExecutionResult
)
from services.base_service import BaseService, BackupCreationError, ProgressCallback
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from utils.format_utils import format_size
from utils.i18n import tr


# Estrategias de selección soportadas
KEEP_STRATEGIES = ['oldest', 'newest', 'largest', 'smallest', 'manual']


class BKTreeNode:
    """
    Nodo de un BK-Tree (Burkhard-Keller Tree) para búsqueda métrica.
    Estructura de datos optimizada para búsquedas por distancia de Hamming.
    """
    def __init__(self, hash_value: Any, path: str):
        self.hash = hash_value
        self.path = path
        self.children: Dict[int, 'BKTreeNode'] = {}


class BKTree:
    """
    BK-Tree implementado para búsqueda eficiente de hashes perceptuales similares.
    
    Reduce complejidad de O(N²) a O(N log N) promedio para clustering.
    Basado en métrica de distancia de Hamming.
    """
    
    def __init__(self, distance_func):
        """
        Args:
            distance_func: Función para calcular distancia entre hashes (e.g., Hamming)
        """
        self.root: Optional[BKTreeNode] = None
        self.distance_func = distance_func
        self._size = 0
    
    def add(self, hash_value: Any, path: str) -> None:
        """Añade un hash al árbol."""
        if self.root is None:
            self.root = BKTreeNode(hash_value, path)
            self._size += 1
            return
        
        current = self.root
        while True:
            distance = self.distance_func(current.hash, hash_value)
            
            if distance in current.children:
                current = current.children[distance]
            else:
                current.children[distance] = BKTreeNode(hash_value, path)
                self._size += 1
                break
    
    def search(self, target_hash: Any, threshold: int) -> List[Tuple[str, int]]:
        """
        Busca todos los hashes dentro del threshold de distancia.
        
        Args:
            target_hash: Hash objetivo a buscar
            threshold: Distancia máxima permitida
            
        Returns:
            Lista de tuplas (path, distance) dentro del threshold
        """
        if self.root is None:
            return []
        
        results = []
        self._search_recursive(self.root, target_hash, threshold, results)
        return results
    
    def _search_recursive(
        self, 
        node: BKTreeNode, 
        target: Any, 
        threshold: int,
        results: List[Tuple[str, int]]
    ) -> None:
        """Búsqueda recursiva en el árbol."""
        distance = self.distance_func(node.hash, target)
        
        if distance <= threshold:
            results.append((node.path, distance))
        
        # Solo explorar ramas que puedan contener matches
        # Poda basada en desigualdad triangular
        min_dist = max(0, distance - threshold)
        max_dist = distance + threshold
        
        for child_dist, child_node in node.children.items():
            if min_dist <= child_dist <= max_dist:
                self._search_recursive(child_node, target, threshold, results)
    
    def __len__(self) -> int:
        return self._size


class DuplicatesSimilarAnalysis:
    """
    Contiene hashes perceptuales y permite generar grupos con
    cualquier sensibilidad en tiempo real.
    
    Esta clase separa el análisis costoso (cálculo de hashes) del
    clustering rápido, permitiendo ajustar la sensibilidad
    interactivamente sin reanalizar.
    
    Attributes:
        perceptual_hashes: Dict con {file_path: hash_data}
        workspace_path: Ruta del workspace analizado (o None)
        total_files: Número total de archivos analizados
        analysis_timestamp: Fecha/hora del análisis
    """
    
    def __init__(self):
        """Inicializa análisis vacío."""
        self.perceptual_hashes: Dict[str, Dict[str, Any]] = {}
        self.workspace_path: Optional[str] = None
        self.total_files: int = 0
        self.analysis_timestamp: Optional[datetime] = None
        self.hash_size: int = 8  # Tamaño del hash usado (bits = hash_size²)
        self._distance_cache: Dict[Tuple[int, int], int] = {}
        self._logger = get_logger('DuplicatesSimilarAnalysis')
        # Cache del último resultado de get_groups para evitar re-clustering costoso
        self._last_groups_result: Optional[SimilarDuplicateAnalysisResult] = None
        self._last_groups_sensitivity: Optional[int] = None
    
    def get_groups(
        self, 
        sensitivity: int,
        progress_callback: Optional[Any] = None
    ) -> SimilarDuplicateAnalysisResult:
        """
        Genera grupos con la sensibilidad especificada.
        
        MUY RÁPIDO (< 1 segundo) porque solo hace clustering
        usando los hashes ya calculados.
        
        Args:
            sensitivity: Sensibilidad de detección (30-100)
                - 100: Solo imágenes idénticas
                - 85: Muy similares (recomendado)
                - 50: Similares
                - 30: Algo similares
            progress_callback: Callable opcional (current, total, message) -> bool
                Permite reportar progreso y mantener UI responsiva.
                Si retorna False, el proceso debe detenerse.
        
        Returns:
            SimilarDuplicateAnalysisResult con grupos detectados
        """
        import time
        
        # Usar resultado cacheado si la sensibilidad no cambió
        if (self._last_groups_result is not None 
                and self._last_groups_sensitivity == sensitivity):
            self._logger.debug(
                f"Using cached clustering result (sensitivity {sensitivity}%)"
            )
            return self._last_groups_result
        
        start_time = time.time()
        
        self._logger.info(
            f"Starting clustering with sensitivity {sensitivity}% for {len(self.perceptual_hashes)} files..."
        )
        
        # Convertir sensibilidad a threshold de Hamming distance
        threshold = self._sensitivity_to_threshold(sensitivity)
        
        # Clustering rápido usando hashes pre-calculados
        groups = self._cluster_by_similarity(
            self.perceptual_hashes,
            threshold,
            self._distance_cache,
            progress_callback
        )
        
        elapsed = time.time() - start_time
        self._logger.info(
            f"Clustering completed in {elapsed:.3f}s ({len(groups)} groups found)"
        )
        
        # Calcular estadísticas
        total_groups = len(groups)
        total_similar = sum(len(g.files) - 1 for g in groups)
        space_recoverable = sum(g.space_recoverable for g in groups)
        
        min_similarity = min(g.similarity_score for g in groups) if groups else 0
        max_similarity = max(g.similarity_score for g in groups) if groups else 0
        
        self._logger.info(
            f"Groups generated: {total_groups}, "
            f"Similar: {total_similar}, "
            f"Similarity: {min_similarity:.0f}%-{max_similarity:.0f}%"
        )
        
        result = SimilarDuplicateAnalysisResult(
            success=True,
            groups=groups,
            total_files_analyzed=self.total_files,
            total_groups=total_groups,
            total_similar=total_similar,
            space_recoverable=space_recoverable,
            sensitivity=sensitivity
        )
        
        # Cachear resultado para evitar re-clustering costoso en la UI
        self._last_groups_result = result
        self._last_groups_sensitivity = sensitivity
        
        return result
    
    def get_last_groups_result(self) -> Optional[SimilarDuplicateAnalysisResult]:
        """
        Retorna el último resultado de get_groups() sin recalcular.
        
        Útil para mostrar estadísticas en la UI sin bloquear el hilo principal.
        Retorna None si get_groups() nunca ha sido llamado.
        """
        return self._last_groups_result
    
    def _sensitivity_to_threshold(self, sensitivity: int) -> int:
        """
        Convierte sensibilidad (30-100) a threshold de Hamming distance.
        """
        max_distance = Config.MAX_HAMMING_THRESHOLD
        # Mapeo inverso: 100% sens = 0 threshold, 30% sens = 20 threshold
        normalized = (100 - sensitivity) / 70  # 70 = 100 - 30
        return int(max_distance * normalized)
    
    def _cluster_by_similarity(
        self,
        hashes: Dict[str, Dict[str, Any]],
        threshold: int,
        distance_cache: Dict[Tuple[int, int], int],
        progress_callback: Optional[Any] = None
    ) -> List[SimilarDuplicateGroup]:
        """
        Agrupa archivos por similitud usando threshold de Hamming distance.
        
        Optimizado con BK-Tree: O(N log N) en promedio vs O(N²) anterior.
        
        Args:
            hashes: Dict con {path: {hash, size, ...}}
            threshold: Distancia Hamming máxima para considerar similares
            distance_cache: Cache de distancias (no usado actualmente con BK-Tree)
            progress_callback: Callable opcional (current, total, message) -> bool
        """
        import time
        
        if not hashes:
            return []
        
        total_files = len(hashes)
        
        # Fase 1: Construir BK-Tree para búsqueda eficiente
        tree_start = time.time()
        bk_tree = BKTree(distance_func=self._hamming_distance)
        
        paths = list(hashes.keys())
        
        # Reportar progreso durante construcción del árbol
        for i, path in enumerate(paths):
            bk_tree.add(hashes[path]['hash'], path)
            
            # Reportar cada 5% para no saturar la UI
            if progress_callback and i % max(1, total_files // 20) == 0:
                should_continue = progress_callback(
                    i, total_files, 
                    tr("services.progress.building_index", current=f"{i:,}", total=f"{total_files:,}")
                )
                if should_continue is False:
                    return []
        
        tree_time = time.time() - tree_start
        self._logger.info(f"  BK-Tree built: {len(bk_tree)} nodes in {tree_time:.3f}s")
        
        # Fase 2: Búsqueda y agrupación
        search_start = time.time()
        groups = []
        processed: Set[str] = set()
        total_searches = 0
        total_matches = 0
        files_searched = 0
        
        for path1 in paths:
            if path1 in processed:
                continue
            
            hash1 = hashes[path1]['hash']
            
            # Búsqueda eficiente de similares usando BK-Tree
            similar_matches = bk_tree.search(hash1, threshold)
            total_searches += 1
            total_matches += len(similar_matches)
            files_searched += 1
            
            # Reportar progreso cada 5% durante la búsqueda
            if progress_callback and files_searched % max(1, total_files // 20) == 0:
                should_continue = progress_callback(
                    files_searched, total_files,
                    tr("services.progress.grouping_similar", current=f"{files_searched:,}", total=f"{total_files:,}")
                )
                if should_continue is False:
                    return groups  # Retornar lo que tengamos hasta ahora
            
            if len(similar_matches) <= 1:  # Solo encontró a sí mismo
                continue
            
            # Construir grupo con archivos similares no procesados
            similar_files = []
            file_sizes = []
            hamming_distances = []
            
            for match_path, distance in similar_matches:
                if match_path not in processed:
                    similar_files.append(Path(match_path))
                    file_sizes.append(hashes[match_path]['size'])
                    if match_path != path1:  # No contar distancia a sí mismo
                        hamming_distances.append(distance)
                    processed.add(match_path)
            
            # Si el grupo tiene más de 1 archivo, guardarlo
            if len(similar_files) > 1:
                try:
                    # Calcular score de similitud basado en distancia Hamming
                    avg_hamming = (
                        sum(hamming_distances) / len(hamming_distances)
                        if hamming_distances else 0
                    )
                    
                    max_theoretical_dist = self.hash_size * self.hash_size
                    similarity_percentage = 100 - (avg_hamming / max_theoretical_dist * 100)
                    similarity_percentage = max(0, min(100, similarity_percentage))
                    
                    max_dist = Config.MAX_HAMMING_THRESHOLD
                    min_similarity_from_threshold = 100 - (threshold / max_dist * 100)
                    
                    if similarity_percentage < min_similarity_from_threshold:
                        continue
                    
                    group = SimilarDuplicateGroup(
                        hash_value=str(hash1),
                        files=similar_files,
                        file_sizes=file_sizes,
                        similarity_score=similarity_percentage
                    )
                    groups.append(group)
                except Exception as e:
                    self._logger.warning(f"Error processing group for {path1}: {e}")
                    continue
        
        search_time = time.time() - search_start
        self._logger.info(
            f"  Searches: {total_searches} files, {total_matches} total matches in {search_time:.3f}s"
        )
        
        # Ordenar grupos por variación de tamaño (más variación = más relevante)
        groups.sort(key=lambda g: g.size_variation_percent, reverse=True)
        
        # Log de estadísticas de variación
        if groups:
            variations = [g.size_variation_percent for g in groups]
            max_variation = max(variations) if variations else 0
            avg_variation = sum(variations) / len(variations) if variations else 0
            self._logger.info(
                f"  Size variation - Max: {max_variation:.1f}%, Average: {avg_variation:.1f}%"
            )
        
        return groups
    
    def _hamming_distance(self, hash1: Any, hash2: Any) -> int:
        return hash1 - hash2


class DuplicatesSimilarService(BaseService):
    """
    Servicio de detección y eliminación de archivos similares mediante perceptual hashing.
    
    Identifica fotos y vídeos visualmente similares, incluyendo recortes,
    rotaciones, ediciones o diferentes resoluciones.
    """

    def __init__(self):
        """Inicializa el detector de archivos similares."""
        super().__init__('DuplicatesSimilarService')
        self._cached_analysis: Optional[DuplicatesSimilarAnalysis] = None
    
    def analyze(
        self,
        sensitivity: int = 85,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs
    ) -> SimilarDuplicateAnalysisResult:
        """
        Analiza buscando duplicados similares (perceptual hash).
        
        Este es el método estándar compatible con el patrón de otros servicios.
        Calcula hashes perceptuales y genera grupos con la sensibilidad especificada.
        
        Args:
            sensitivity: Sensibilidad de detección (30-100, default 85)
                - 100: Solo imágenes idénticas
                - 85: Muy similares (recomendado)
                - 50: Similares
                - 30: Algo similares
            progress_callback: Callback de progreso
            **kwargs: Args adicionales
            
        Returns:
            SimilarDuplicateAnalysisResult con grupos detectados
        """
        log_section_header_discrete(self.logger, "SIMILAR DUPLICATES ANALYSIS")
        self.logger.info(f"Configured sensitivity: {sensitivity}%")
        
        repo = FileInfoRepositoryCache.get_instance()
        if self._cached_analysis is None:
            self._cached_analysis = self._calculate_perceptual_hashes(
                repo,
                progress_callback,
                algorithm=Config.PERCEPTUAL_HASH_ALGORITHM,
                hash_size=Config.PERCEPTUAL_HASH_SIZE,
                target=Config.PERCEPTUAL_HASH_TARGET,
                highfreq_factor=Config.PERCEPTUAL_HASH_HIGHFREQ_FACTOR
            )
        else:
            self.logger.info("Reusing previous perceptual hash analysis from memory")

        # Fase 2: Generar grupos con sensibilidad especificada
        result = self._cached_analysis.get_groups(sensitivity)
        
        log_section_footer_discrete(self.logger, "SIMILAR DUPLICATES ANALYSIS COMPLETED")
        return result
    
    def get_analysis_for_dialog(
        self,
        progress_callback: Optional[ProgressCallback] = None
    ) -> DuplicatesSimilarAnalysis:
        """
        Obtiene objeto DuplicatesSimilarAnalysis para uso interactivo en diálogos.
        
        Permite ajustar sensibilidad en tiempo real sin recalcular hashes.
        Este método es específico para el flujo de UI con ajuste dinámico.
        
        Args:
            progress_callback: Callback de progreso para cálculo de hashes
            
        Returns:
            DuplicatesSimilarAnalysis con hashes precalculados
        """
        repo = FileInfoRepositoryCache.get_instance()
        if self._cached_analysis is None:
            self._cached_analysis = self._calculate_perceptual_hashes(
                repo,
                progress_callback,
                algorithm=Config.PERCEPTUAL_HASH_ALGORITHM,
                hash_size=Config.PERCEPTUAL_HASH_SIZE,
                target=Config.PERCEPTUAL_HASH_TARGET,
                highfreq_factor=Config.PERCEPTUAL_HASH_HIGHFREQ_FACTOR
            )
        else:
            self.logger.info("Reusing previous perceptual hash analysis from memory")
        
        return self._cached_analysis

    def execute(
        self,
        analysis_result: SimilarDuplicateAnalysisResult,
        keep_strategy: str = 'largest',
        files_to_delete: Optional[List[Path]] = None,
        create_backup: bool = True,
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs
    ) -> SimilarDuplicateExecutionResult:
        """
        Ejecuta la eliminación de duplicados similares.
        
        Args:
            analysis_result: Resultado del análisis
            keep_strategy: Estrategia de conservación ('oldest', 'newest', 'largest', 'smallest', 'manual')
            files_to_delete: Lista específica de archivos a eliminar (para modo manual)
            create_backup: Si crear backup antes de eliminar
            dry_run: Si es simulación
            progress_callback: Callback de progreso
            
        Returns:
            SimilarDuplicateExecutionResult con resultados de la operación
        """
        from utils.logger import log_section_header_relevant, log_section_footer_relevant
        
        mode = "SIMULATION" if dry_run else ""
        log_section_header_relevant(
            self.logger,
            f"SIMILAR DUPLICATES DELETION - Strategy: {keep_strategy}",
            mode=mode
        )
        
        if keep_strategy not in KEEP_STRATEGIES:
            raise ValueError(f"Invalid strategy: {keep_strategy}. Options: {KEEP_STRATEGIES}")
        
        groups = analysis_result.groups
        files_to_delete_set = set(files_to_delete) if files_to_delete else None
        
        if not groups:
            self.logger.info("No groups to process")
            return SimilarDuplicateExecutionResult(
                success=True,
                items_processed=0,
                bytes_processed=0,
                keep_strategy=keep_strategy,
                dry_run=dry_run,
                message=tr("services.result.no_duplicates_to_delete")
            )
        
        # Filtrar grupos con archivos que aún existen
        filtered_groups = self._filter_existing_groups(groups)
        
        if not filtered_groups:
            self.logger.info("All groups were filtered out (files no longer exist)")
            return SimilarDuplicateExecutionResult(
                success=True,
                items_processed=0,
                bytes_processed=0,
                keep_strategy=keep_strategy,
                dry_run=dry_run,
                message=tr("services.result.no_duplicates_already_processed")
            )
        
        # Crear backup si es necesario
        backup_path = None
        if create_backup and not dry_run:
            all_files = [f for g in filtered_groups for f in g.files]
            try:
                backup_path = self._create_backup_for_operation(
                    all_files,
                    'similar_duplicates_deletion',
                    progress_callback
                )
                if not backup_path:
                    return SimilarDuplicateExecutionResult(
                        success=False,
                        errors=[tr("services.error.backup_creation_failed")],
                        keep_strategy=keep_strategy,
                        dry_run=dry_run
                    )
            except BackupCreationError as e:
                return SimilarDuplicateExecutionResult(
                    success=False,
                    errors=[f"Error creating backup: {e}"],
                    keep_strategy=keep_strategy,
                    dry_run=dry_run
                )
        
        # Procesar eliminaciones
        repo = FileInfoRepositoryCache.get_instance()
        files_affected = []
        files_kept = 0
        errors = []
        bytes_processed = 0
        
        # Calcular total de operaciones
        if keep_strategy == 'manual' and files_to_delete_set:
            total_operations = len(files_to_delete_set)
        elif keep_strategy == 'manual':
            # Modo manual sin archivos especificados: no borrar nada
            total_operations = 0
        else:
            total_operations = sum(len(g.files) - 1 for g in filtered_groups)
        
        processed = 0
        
        for group in filtered_groups:
            # Determinar qué archivo conservar y cuáles eliminar
            if keep_strategy == 'manual':
                if files_to_delete_set:
                    to_delete = [f for f in group.files if f in files_to_delete_set]
                    files_kept += len(group.files) - len(to_delete)
                else:
                    # Modo manual sin archivos especificados: no borrar nada de este grupo
                    to_delete = []
                    files_kept += len(group.files)
            else:
                keep_file = self._select_file_to_keep(group, keep_strategy, repo)
                to_delete = [f for f in group.files if f != keep_file]
                files_kept += 1
                
                # Log del archivo que se conserva
                self.logger.debug(
                    f"Keeping: {keep_file.name} | Similarity: {group.similarity_score:.0f}%"
                )
            
            # Eliminar archivos seleccionados
            for file_path in to_delete:
                try:
                    meta = repo.get_file_metadata(file_path)
                    file_size = meta.fs_size if meta else (file_path.stat().st_size if file_path.exists() else 0)
                    file_date = self._get_best_date_for_file(file_path, repo)
                    
                    if dry_run:
                        self.logger.info(
                            f"FILE_DELETED_SIMULATION: {file_path} | "
                            f"Size: {format_size(file_size)} | "
                            f"Date: {file_date} | "
                            f"Type: similar_duplicate | "
                            f"Similarity: {group.similarity_score:.0f}% | "
                            f"Strategy: {keep_strategy}"
                        )
                    else:
                        file_path.unlink()
                        repo.remove_file(file_path)
                        self.logger.info(
                            f"FILE_DELETED: {file_path} | "
                            f"Size: {format_size(file_size)} | "
                            f"Date: {file_date} | "
                            f"Type: similar_duplicate | "
                            f"Similarity: {group.similarity_score:.0f}% | "
                            f"Strategy: {keep_strategy}"
                        )
                    
                    files_affected.append(file_path)
                    bytes_processed += file_size
                    processed += 1
                    
                    if not self._report_progress(
                        progress_callback,
                        processed,
                        total_operations,
                        f"{tr('services.progress.simulation_prefix') if dry_run else ''}{tr('services.progress.deleting_file', name=file_path.name)}"
                    ):
                        break
                        
                except FileNotFoundError:
                    self.logger.warning(f"File not found: {file_path}")
                except Exception as e:
                    errors.append(f"{file_path}: {e}")
                    self.logger.error(f"Error deleting {file_path}: {e}")
        
        # Construir resultado
        result = SimilarDuplicateExecutionResult(
            success=len(errors) == 0,
            items_processed=processed,
            bytes_processed=bytes_processed,
            files_affected=files_affected,
            files_kept=files_kept,
            backup_path=backup_path,
            keep_strategy=keep_strategy,
            dry_run=dry_run,
            errors=errors
        )
        
        # Mensaje de resumen
        result.message = self._format_operation_summary(
            tr("services.operation.similar_duplicate_deletion"),
            processed,
            bytes_processed,
            dry_run
        )
        
        if backup_path:
            result.message += f"\n\nBackup created at:\n{backup_path}"
        
        log_section_footer_relevant(self.logger, result.message)
        
        return result

    def _filter_existing_groups(
        self,
        groups: List[SimilarDuplicateGroup]
    ) -> List[SimilarDuplicateGroup]:
        """
        Filtra grupos para incluir solo archivos que aún existen.
        
        Previene errores cuando otro servicio eliminó archivos entre
        el análisis y la ejecución.
        """
        filtered = []
        total_missing = 0
        
        for group in groups:
            existing_files = []
            existing_sizes = []
            
            for i, f in enumerate(group.files):
                if f.exists():
                    existing_files.append(f)
                    if group.file_sizes and i < len(group.file_sizes):
                        existing_sizes.append(group.file_sizes[i])
            
            missing = len(group.files) - len(existing_files)
            if missing > 0:
                total_missing += missing
                self.logger.debug(f"Group {group.hash_value[:8]}...: {missing} files no longer exist")
            
            if len(existing_files) >= 2:
                filtered.append(SimilarDuplicateGroup(
                    hash_value=group.hash_value,
                    files=existing_files,
                    file_sizes=existing_sizes,
                    similarity_score=group.similarity_score
                ))
        
        if total_missing > 0:
            self.logger.warning(
                f"{total_missing} files no longer exist. "
                f"Groups: {len(groups)} -> {len(filtered)}"
            )
        
        return filtered

    def _select_file_to_keep(
        self,
        group: SimilarDuplicateGroup,
        strategy: str,
        repo: FileInfoRepositoryCache
    ) -> Path:
        """
        Selecciona qué archivo conservar según la estrategia.
        
        IMPORTANTE: Usa FileInfoRepositoryCache para obtener fechas,
        NO accede directamente al disco con stat().
        """
        files = group.files
        
        if strategy == 'oldest':
            return min(files, key=lambda f: self._get_best_date_timestamp(f, repo))
        elif strategy == 'newest':
            return max(files, key=lambda f: self._get_best_date_timestamp(f, repo))
        elif strategy == 'largest':
            return max(files, key=lambda f: self._get_file_size(f, repo, group))
        elif strategy == 'smallest':
            return min(files, key=lambda f: self._get_file_size(f, repo, group))
        else:
            raise ValueError(f"Invalid strategy for selection: {strategy}")

    def _get_best_date_timestamp(self, file_path: Path, repo: FileInfoRepositoryCache) -> float:
        """Obtiene timestamp de la mejor fecha disponible desde el repositorio."""
        best_date, _ = repo.get_best_date(file_path)
        if best_date:
            return best_date.timestamp()
        
        # Fallback a fecha de modificación del filesystem
        meta = repo.get_file_metadata(file_path)
        if meta and meta.fs_mtime:
            return meta.fs_mtime
        
        return 0.0

    def _get_best_date_for_file(self, file_path: Path, repo: FileInfoRepositoryCache) -> str:
        """Obtiene string formateado de la mejor fecha disponible."""
        best_date, source = repo.get_best_date(file_path)
        if best_date:
            return f"{best_date.strftime('%Y-%m-%d %H:%M:%S')} ({source or 'unknown'})"
        
        meta = repo.get_file_metadata(file_path)
        if meta and meta.fs_mtime:
            dt = datetime.fromtimestamp(meta.fs_mtime)
            return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} (filesystem)"
        
        return "unknown date"

    def _get_file_size(
        self,
        file_path: Path,
        repo: FileInfoRepositoryCache,
        group: Optional[SimilarDuplicateGroup] = None
    ) -> int:
        """Obtiene tamaño del archivo, primero del grupo, luego del repositorio."""
        # Intentar desde el grupo (más eficiente)
        if group and group.file_sizes:
            try:
                idx = group.files.index(file_path)
                if idx < len(group.file_sizes):
                    return group.file_sizes[idx]
            except ValueError:
                pass
        
        # Fallback al repositorio
        meta = repo.get_file_metadata(file_path)
        return meta.fs_size if meta else 0

    def _calculate_perceptual_hashes(
        self,
        repo: FileInfoRepositoryCache,
        progress_callback: Optional[ProgressCallback] = None,
        algorithm: str = "dhash",
        hash_size: int = 8,
        target: str = "images",
        highfreq_factor: int = 4
    ) -> DuplicatesSimilarAnalysis:
        """
        Calcula hashes perceptuales de todos los archivos.
        
        Método interno usado por analyze() y get_analysis_for_dialog().
        
        Args:
            repo: Repositorio de metadatos de archivos
            progress_callback: Callback de progreso
            algorithm: Algoritmo de hash ("dhash", "phash", "ahash")
            hash_size: Tamaño del hash (8, 16, 32)
            target: Target de archivos ("images", "videos", "both")
            highfreq_factor: Factor de alta frecuencia para phash (4, 8)
        
        Returns:
            DuplicatesSimilarAnalysis con hashes calculados
        """
        try:
            import imagehash
        except ImportError:
            self.logger.error("imagehash library not installed.")
            raise ImportError("imagehash library not installed.")
        
        import time
        
        log_section_header_discrete(self.logger, "PERCEPTUAL HASH CALCULATION")
        hash_calc_start = time.time()
        self.logger.info(
            f"Calculating perceptual hashes (algorithm={algorithm}, "
            f"hash_size={hash_size}, target={target})..."
        )
        
        # 1. Obtener archivos desde FileInfoRepository
        all_metadata = repo.get_all_files()
        
        image_files = []
        video_files = []
        
        supported_img = Config.SUPPORTED_IMAGE_EXTENSIONS
        supported_vid = Config.SUPPORTED_VIDEO_EXTENSIONS
        
        for meta in all_metadata:
            if meta.extension in supported_img:
                image_files.append(meta.path)
            elif meta.extension in supported_vid:
                video_files.append(meta.path)
        
        # Filtrar según target configurado
        files_to_process_images = [] if target == "videos" else image_files
        files_to_process_videos = [] if target == "images" else video_files
        
        total_files = len(files_to_process_images) + len(files_to_process_videos)
        
        self.logger.info(
            f"Files to process: {total_files} "
            f"({len(files_to_process_images)} images, {len(files_to_process_videos)} videos) "
            f"[target={target}]"
        )
        
        analysis = DuplicatesSimilarAnalysis()
        
        if total_files == 0:
            self.logger.warning("No supported files found for processing")
            analysis.total_files = 0
            analysis.analysis_timestamp = datetime.now()
            return analysis
        
        # 2. Calcular hashes perceptuales en paralelo
        perceptual_hashes = {}
        processed = 0
        errors = 0
        timeouts = 0
        
        with self._parallel_processor(io_bound=False) as executor:
            future_to_file = {}
            
            # Procesar imágenes
            for file_path in files_to_process_images:
                future = executor.submit(
                    self._calculate_image_perceptual_hash,
                    file_path,
                    algorithm,
                    hash_size,
                    highfreq_factor
                )
                future_to_file[future] = file_path
            
            # Procesar videos
            for file_path in files_to_process_videos:
                future = executor.submit(
                    self._calculate_video_perceptual_hash,
                    file_path,
                    algorithm,
                    hash_size,
                    highfreq_factor
                )
                future_to_file[future] = file_path
            
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    phash = future.result(timeout=5.0)
                    if phash:
                        # Obtener tamaño desde cache si es posible para evitar stat
                        meta = repo.get_file_metadata(file_path)
                        size = meta.fs_size if meta else file_path.stat().st_size
                        mtime = meta.fs_mtime if meta else file_path.stat().st_mtime
                        
                        perceptual_hashes[str(file_path)] = {
                            'hash': phash,
                            'size': size,
                            'modified': mtime
                        }
                    
                    processed += 1
                    if self._should_report_progress(processed, interval=10):
                        if not self._report_progress(
                            progress_callback,
                            processed,
                            total_files,
                            tr("services.progress.processing_file", name=file_path.name)
                        ):
                            break
                except TimeoutError:
                    timeouts += 1
                    processed += 1
                    self.logger.warning(f"Timeout processing {file_path.name}")
                except Exception as e:
                    errors += 1
                    processed += 1
                    self.logger.debug(f"Error processing {file_path.name}: {e}")
        
        analysis.perceptual_hashes = perceptual_hashes
        analysis.total_files = len(perceptual_hashes)
        analysis.analysis_timestamp = datetime.now()
        analysis.hash_size = hash_size
        
        # Log stats
        hash_calc_time = time.time() - hash_calc_start
        self.logger.info(
            f"Hashes calculated: {analysis.total_files} in {hash_calc_time:.1f}s "
            f"({analysis.total_files/max(hash_calc_time, 0.1):.1f} files/s)"
        )
        
        if errors > 0:
            self.logger.warning(f"Errors: {errors}, Timeouts: {timeouts}")
        
        if analysis.total_files == 0 and total_files > 0:
            self.logger.error(
                f"All {total_files} hash calculations failed. "
                f"This usually indicates a missing dependency (scipy, pywt, numpy) "
                f"in the packaged binary. Check warnings above for details."
            )
        
        return analysis

    def _calculate_image_perceptual_hash(
        self,
        file_path: Path,
        algorithm: str = "dhash",
        hash_size: int = 8,
        highfreq_factor: int = 4
    ) -> Optional[Any]:
        """
        Calcula hash perceptual de una imagen.
        """
        try:
            import imagehash
            from PIL import Image
            
            with Image.open(file_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Seleccionar algoritmo de hash
                if algorithm == "phash":
                    return imagehash.phash(img, hash_size=hash_size, highfreq_factor=highfreq_factor)
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

    def _calculate_video_perceptual_hash(
        self,
        file_path: Path,
        algorithm: str = "dhash",
        hash_size: int = 8,
        highfreq_factor: int = 4
    ) -> Optional[Any]:
        """
        Calcula hash perceptual de un video extrayendo el frame central.
        """
        try:
            import cv2
            import imagehash
            from PIL import Image
            import os
            
            os.environ['OPENCV_FFMPEG_LOGLEVEL'] = '-8'
            cap = cv2.VideoCapture(str(file_path))
            if not cap.isOpened():
                return None
            
            # Property ID 7 = CAP_PROP_FRAME_COUNT
            total_frames = int(cap.get(7))
            if total_frames == 0:
                cap.release()
                return None
            
            # Property ID 1 = CAP_PROP_POS_FRAMES - buscar frame central
            cap.set(1, total_frames // 2)
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                return None
            
            # Convertir BGR a RGB para PIL
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            
            # Seleccionar algoritmo de hash
            if algorithm == "phash":
                return imagehash.phash(img, hash_size=hash_size, highfreq_factor=highfreq_factor)
            elif algorithm == "ahash":
                return imagehash.average_hash(img, hash_size=hash_size)
            else:  # dhash (default)
                return imagehash.dhash(img, hash_size=hash_size)
                
        except ImportError as e:
            self.logger.warning(f"Missing dependency for video perceptual hash: {e}")
            return None
        except Exception as e:
            self.logger.debug(f"Error calculating video hash for {file_path.name}: {e}")
            return None
