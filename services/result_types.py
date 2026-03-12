# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from pathlib import Path
from datetime import datetime
from services.file_metadata_repository_cache import FileInfoRepositoryCache

# ============================================================================
# GENERIC BASE CLASSES (The Core of the Refactor)
# ============================================================================

@dataclass
class BaseResult:
    """Base class for all results (Analysis and Execution)."""
    success: bool = True
    errors: List[str] = field(default_factory=list)
    message: Optional[str] = None
    
    def add_error(self, error: str):
        self.errors.append(error)
        self.success = False

@dataclass
class AnalysisResult(BaseResult):
    """
    Generic result for the Analysis phase.
    Services should populate `data` with specific findings if `items` is not enough.
    """
    items_count: int = 0          # Number of items found/analyzed
    bytes_total: int = 0          # Total size in bytes of relevance
    data: Any = None              # Payload specific to the service (e.g. list of duplicates)

@dataclass
class ExecutionResult(BaseResult):
    """
    Generic result for the Execution phase.
    All execution operations support dry_run mode and backup creation.
    """
    items_processed: int = 0
    bytes_processed: int = 0      # Bytes freed, moved, or renamed
    files_affected: List[Path] = field(default_factory=list) # List of files modified
    backup_path: Optional[Path] = None # If backup was created
    dry_run: bool = False         # Whether this was a dry-run (simulation)


# --- Zero Byte ---
@dataclass
class ZeroByteAnalysisResult(AnalysisResult):
    """Result for zero-byte files detection."""
    files: List[Path] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.items_count and self.files:
            self.items_count = len(self.files)

@dataclass
class ZeroByteExecutionResult(ExecutionResult):
    """Result for zero-byte files deletion."""
    pass

# --- HEIC Service ---
@dataclass
class HEICDuplicatePair:
    """Represents a pair of HEIC + JPG files."""
    heic_path: Path
    jpg_path: Path
    base_name: str
    heic_size: int
    jpg_size: int
    directory: Path
    heic_date: Optional[datetime] = None
    jpg_date: Optional[datetime] = None
    date_source: Optional[str] = None
    date_difference: Optional[float] = None
    
    @property
    def total_size(self) -> int:
        return self.heic_size + self.jpg_size

@dataclass
class HeicAnalysisResult(AnalysisResult):
    """Result for HEIC/JPG duplicate analysis."""
    duplicate_pairs: List[HEICDuplicatePair] = field(default_factory=list)
    rejected_pairs: List[HEICDuplicatePair] = field(default_factory=list)
    heic_files: int = 0
    jpg_files: int = 0
    potential_savings_keep_jpg: int = 0
    potential_savings_keep_heic: int = 0
    
    def __post_init__(self):
        if not self.items_count and self.duplicate_pairs:
            self.items_count = len(self.duplicate_pairs)
        if not self.bytes_total and self.duplicate_pairs:
            self.bytes_total = sum(p.total_size for p in self.duplicate_pairs)

@dataclass
class HeicExecutionResult(ExecutionResult):
    """Result for HEIC/JPG duplicate execution."""
    format_kept: Optional[str] = None  # 'heic' or 'jpg'


# --- Live Photos ---
@dataclass
class LivePhotoImageInfo:
    """Información de una imagen en un grupo Live Photo."""
    path: Path
    size: int
    date: Optional[datetime] = None
    date_source: Optional[str] = None


@dataclass
class LivePhotoGroup:
    """
    Representa un grupo de Live Photo: un video con una o más imágenes asociadas.
    
    Un Live Photo puede tener múltiples imágenes si el usuario ha editado/renombrado
    archivos manteniendo el mismo nombre base.
    """
    video_path: Path
    video_size: int
    images: List[LivePhotoImageInfo] = field(default_factory=list)
    base_name: str = ""
    directory: Path = field(default_factory=Path)
    video_date: Optional[datetime] = None
    video_date_source: Optional[str] = None
    date_source: Optional[str] = None  # Fuente usada para comparar fechas
    date_difference: Optional[float] = None  # Diferencia en segundos (max entre todas las imágenes)
    
    @property
    def total_size(self) -> int:
        """Tamaño total: video + todas las imágenes"""
        return self.video_size + sum(img.size for img in self.images)
    
    @property
    def images_size(self) -> int:
        """Tamaño total de todas las imágenes"""
        return sum(img.size for img in self.images)
    
    @property
    def image_count(self) -> int:
        """Número de imágenes en el grupo"""
        return len(self.images)
    
    @property
    def primary_image(self) -> Optional[LivePhotoImageInfo]:
        """Devuelve la primera imagen del grupo (la principal)"""
        return self.images[0] if self.images else None
    
    @property
    def best_date(self) -> Optional[datetime]:
        """Devuelve la mejor fecha disponible (video o primera imagen)"""
        if self.video_date:
            return self.video_date
        if self.images and self.images[0].date:
            return self.images[0].date
        return None


@dataclass
class LivePhotosAnalysisResult(AnalysisResult):
    """
    Result for Live Photos detection analysis.
    
    Attributes:
        groups: Lista de LivePhotoGroup validados (aceptados)
        rejected_groups: Lista de LivePhotoGroup rechazados por diferencia de fecha
        total_space: Espacio total usado por todos los Live Photos
    """
    groups: List[LivePhotoGroup] = field(default_factory=list)
    rejected_groups: List[LivePhotoGroup] = field(default_factory=list)
    total_space: int = 0  # Total space used by Live Photos (images + videos)
    
    def __post_init__(self):
        if not self.items_count and self.groups:
            self.items_count = len(self.groups)
        if not self.bytes_total and self.total_space:
            self.bytes_total = self.total_space
    
    @property
    def potential_savings(self) -> int:
        """Espacio que se liberaría eliminando todos los videos"""
        return sum(g.video_size for g in self.groups)
    
    @property
    def total_images(self) -> int:
        """Total de imágenes en todos los grupos"""
        return sum(g.image_count for g in self.groups)
    
    @property
    def total_videos(self) -> int:
        """Total de videos (igual a número de grupos)"""
        return len(self.groups)


@dataclass
class LivePhotosExecutionResult(ExecutionResult):
    """Result for Live Photos execution."""
    videos_deleted: int = 0


# --- Visual Identical (Perceptual 100%) ---
@dataclass
class VisualIdenticalGroup:
    """
    Grupo de archivos visualmente idénticos.
    
    Archivos con el mismo hash perceptual (distancia Hamming = 0),
    aunque pueden tener diferente tamaño, resolución o metadatos.
    """
    hash_value: str
    files: List[Path]
    file_sizes: List[int] = field(default_factory=list)
    total_size: int = 0
    space_recoverable: int = 0  # Espacio que se puede recuperar (total - archivo más grande)
    size_variation_percent: float = 0.0  # Variación de tamaño entre archivos
    
    @property
    def file_count(self) -> int:
        return len(self.files)
    
    @property
    def largest_file(self) -> Optional[Path]:
        """Devuelve el archivo más grande del grupo."""
        if not self.files or not self.file_sizes:
            return self.files[0] if self.files else None
        max_idx = self.file_sizes.index(max(self.file_sizes))
        return self.files[max_idx]
    
    @property
    def smallest_file(self) -> Optional[Path]:
        """Devuelve el archivo más pequeño del grupo."""
        if not self.files or not self.file_sizes:
            return self.files[0] if self.files else None
        min_idx = self.file_sizes.index(min(self.file_sizes))
        return self.files[min_idx]


@dataclass
class VisualIdenticalAnalysisResult(AnalysisResult):
    """Result for visual identical detection (100% perceptual match)."""
    groups: List[VisualIdenticalGroup] = field(default_factory=list)
    total_files: int = 0
    total_groups: int = 0
    total_duplicates: int = 0  # Archivos duplicados (total - 1 por grupo)
    space_recoverable: int = 0
    
    def __post_init__(self):
        if not self.items_count and self.groups:
            self.items_count = len(self.groups)
        if not self.total_groups and self.groups:
            self.total_groups = len(self.groups)
        if not self.bytes_total and self.space_recoverable:
            self.bytes_total = self.space_recoverable


@dataclass
class VisualIdenticalExecutionResult(ExecutionResult):
    """Result for visual identical deletion execution."""
    files_kept: int = 0
    keep_strategy: Optional[str] = None  # 'largest', 'smallest', 'oldest', 'newest'


# --- Exact Duplicates (SHA256) ---
@dataclass
class ExactDuplicateGroup:
    """
    Grupo de archivos exactamente idénticos (mismo SHA256).
    
    Estos archivos son copias bit a bit, incluso si tienen nombres diferentes.
    """
    hash_value: str  # SHA256 hash
    files: List[Path]
    file_size: int = 0  # Tamaño de cada archivo (todos iguales)
    
    @property
    def file_count(self) -> int:
        return len(self.files)
    
    @property
    def total_size(self) -> int:
        """Tamaño total del grupo (file_size * file_count)."""
        return self.file_size * len(self.files)
    
    @property
    def space_recoverable(self) -> int:
        """Espacio que se puede recuperar (total - 1 archivo)."""
        return self.file_size * max(0, len(self.files) - 1)


@dataclass
class ExactDuplicateAnalysisResult(AnalysisResult):
    """Result for exact duplicate detection analysis (SHA256)."""
    groups: List[ExactDuplicateGroup] = field(default_factory=list)
    total_files_scanned: int = 0
    total_groups: int = 0
    total_duplicates: int = 0  # Archivos duplicados (total files - 1 por grupo)
    space_recoverable: int = 0
    
    def __post_init__(self):
        if not self.items_count and self.groups:
            self.items_count = len(self.groups)
        if not self.total_groups and self.groups:
            self.total_groups = len(self.groups)
        if not self.bytes_total and self.space_recoverable:
            self.bytes_total = self.space_recoverable


@dataclass
class ExactDuplicateExecutionResult(ExecutionResult):
    """Result for exact duplicate deletion execution."""
    files_kept: int = 0
    keep_strategy: Optional[str] = None  # 'oldest', 'newest', 'largest', 'smallest', 'manual'


# --- Similar Duplicates (Perceptual Hash) ---
@dataclass
class SimilarDuplicateGroup:
    """
    Grupo de archivos visualmente similares (perceptual hash).
    
    Archivos que son similares visualmente pero pueden tener diferente
    tamaño, resolución, compresión o metadatos.
    """
    hash_value: str  # Perceptual hash representativo del grupo
    files: List[Path]
    file_sizes: List[int] = field(default_factory=list)
    similarity_score: float = 0.0  # Porcentaje de similitud (70-100%)
    
    @property
    def file_count(self) -> int:
        return len(self.files)
    
    @property
    def total_size(self) -> int:
        """Tamaño total de todos los archivos del grupo."""
        return sum(self.file_sizes) if self.file_sizes else 0
    
    @property
    def space_recoverable(self) -> int:
        """Espacio recuperable (todo menos el archivo más grande)."""
        if not self.file_sizes or len(self.file_sizes) < 2:
            return 0
        return self.total_size - max(self.file_sizes)
    
    @property
    def largest_file(self) -> Optional[Path]:
        """Devuelve el archivo más grande del grupo."""
        if not self.files or not self.file_sizes:
            return self.files[0] if self.files else None
        max_idx = self.file_sizes.index(max(self.file_sizes))
        return self.files[max_idx]
    
    @property
    def size_variation_percent(self) -> float:
        """Variación porcentual entre el archivo más grande y más pequeño."""
        if not self.file_sizes or len(self.file_sizes) < 2:
            return 0.0
        min_size = min(self.file_sizes)
        max_size = max(self.file_sizes)
        if min_size == 0:
            return 0.0
        return ((max_size - min_size) / min_size) * 100


@dataclass
class SimilarDuplicateAnalysisResult(AnalysisResult):
    """Result for similar duplicate detection analysis (perceptual hash)."""
    groups: List[SimilarDuplicateGroup] = field(default_factory=list)
    total_files_analyzed: int = 0
    total_groups: int = 0
    total_similar: int = 0  # Archivos similares (total files - 1 por grupo)
    space_recoverable: int = 0
    sensitivity: int = 85  # Sensibilidad usada para generar estos grupos
    
    def __post_init__(self):
        if not self.items_count and self.groups:
            self.items_count = len(self.groups)
        if not self.total_groups and self.groups:
            self.total_groups = len(self.groups)
        if not self.bytes_total and self.space_recoverable:
            self.bytes_total = self.space_recoverable


@dataclass
class SimilarDuplicateExecutionResult(ExecutionResult):
    """Result for similar duplicate deletion execution."""
    files_kept: int = 0
    keep_strategy: Optional[str] = None  # 'largest', 'smallest', 'oldest', 'newest', 'manual'


# --- Organization Service ---
@dataclass
class OrganizationAnalysisResult(AnalysisResult):
    """Result for file organization analysis."""
    move_plan: List[Any] = field(default_factory=list)  # List of FileMove objects
    root_directory: str = ''
    organization_type: str = 'to_root'  # Base organization type: 'to_root', 'by_month', 'by_year', 'by_year_month', 'by_type', 'by_source'
    subdirectories: Dict[str, Any] = field(default_factory=dict)  # Subdirectories found in root
    
    # Required for the UI to remember selection
    group_by_source: bool = False  # Whether to group by source (WhatsApp, Camera, etc.)
    group_by_type: bool = False    # Whether to group by type (Photos/Videos)
    date_grouping_type: Optional[str] = None  # Secondary date grouping: 'month', 'year', 'year_month'
    move_unsupported_to_other: bool = False  # Whether to move unsupported files to 'other/' folder
    
    @property
    def files_to_move(self) -> int:
        """Número de archivos que la estrategia actual moverá."""
        return len(self.move_plan)

    @property
    def bytes_to_move(self) -> int:
        """Tamaño total de los archivos que la estrategia actual moverá."""
        return sum(m.size for m in self.move_plan)

    @property
    def folders_to_create(self) -> List[str]:
        """Lista de carpetas únicas que se crearán."""
        return sorted(set(m.target_folder for m in self.move_plan if m.target_folder))

    def __post_init__(self):
        # We now keep __post_init__ empty to avoid automatic overrides
        pass

@dataclass
class OrganizationExecutionResult(ExecutionResult):
    """Result for file organization execution."""
    empty_directories_removed: int = 0
    moved_files: List[str] = field(default_factory=list)
    folders_created: List[str] = field(default_factory=list)


# --- Rename Service ---

@dataclass
class RenamePlanItem:
    """Item in a renaming plan - represents a file to be renamed."""
    original_path: Path
    new_name: str
    date: datetime
    date_source: str
    has_conflict: bool = False
    sequence: Optional[int] = None


@dataclass
class RenamedFileItem:
    """Item representing a file that was renamed during execution."""
    original: str
    new_name: str
    date: str
    had_conflict: bool = False


@dataclass
class RenameAnalysisResult(AnalysisResult):
    """Result for file renaming analysis."""
    renaming_plan: List[RenamePlanItem] = field(default_factory=list)
    already_renamed: int = 0
    conflicts: int = 0
    files_by_year: Dict[int, int] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    
    @property
    def need_renaming(self) -> int:
        """Número de archivos que realmente serán renombrados."""
        return len(self.renaming_plan)

    @property
    def cannot_process(self) -> int:
        """Número de archivos con problemas."""
        return len(self.issues)

@dataclass
class RenameExecutionResult(ExecutionResult):
    """Result for file renaming execution."""
    renamed_files: List[RenamedFileItem] = field(default_factory=list)
    conflicts_resolved: int = 0

    @property
    def files_renamed(self) -> int:
        """Alias para items_processed que usa la UI."""
        return self.items_processed

# ============================================================================
# DIRECTORY SCANNER RESULT TYPES
# ============================================================================

@dataclass
class DirectoryScanResult:
    """Resultado del escaneo inicial de directorio"""
    total_files: int
    images: List[Path] = field(default_factory=list)
    videos: List[Path] = field(default_factory=list)
    others: List[Path] = field(default_factory=list)
    
   
    # Tamaño total del directorio (calculado durante finalizacion)
    total_size: int = 0
    
    # Desglose por extensiones
    image_extensions: Dict[str, int] = field(default_factory=dict)
    video_extensions: Dict[str, int] = field(default_factory=dict)
    unsupported_extensions: Dict[str, int] = field(default_factory=dict)
    unsupported_files: List[Path] = field(default_factory=list)  # Rutas completas para DEBUG
    
    @property
    def image_count(self) -> int:
        return len(self.images)
    
    @property
    def video_count(self) -> int:
        return len(self.videos)
    
    @property
    def other_count(self) -> int:
        return len(self.others)


@dataclass
class ScanSnapshot:
    """Simple snapshot of scan results for Stage 2 -> Stage 3 transition."""
    directory: Path
    scan: DirectoryScanResult
    
    # Tool-specific analysis results (dynamically populated in Stage 3)
    live_photos: Optional[Any] = None
    heic: Optional[Any] = None
    duplicates: Optional[Any] = None  # Duplicados exactos
    duplicates_similar: Optional[Any] = None  # Archivos similares
    visual_identical: Optional[Any] = None  # Copias visuales idénticas
    zero_byte: Optional[Any] = None
    organization: Optional[Any] = None
    renaming: Optional[Any] = None