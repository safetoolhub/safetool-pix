# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Servicios de lógica de negocio para SafeTool Pix.

Este módulo expone los servicios y tipos de datos principales
utilizados por la capa UI de la aplicación.
"""

# Servicios principales
from .file_renamer_service import FileRenamerService
from .live_photos_service import LivePhotoService
from .file_organizer_service import FileOrganizerService, OrganizationType
from .heic_service import HeicService
from .duplicates_exact_service import DuplicatesExactService
from .duplicates_similar_service import DuplicatesSimilarService, DuplicatesSimilarAnalysis
from .visual_identical_service import VisualIdenticalService
from .zero_byte_service import ZeroByteService

# Tipos de resultado
from .result_types import (
    # Renaming
    RenameAnalysisResult,
    RenameExecutionResult,
    # Organization
    OrganizationAnalysisResult,
    OrganizationExecutionResult,
    # Exact Duplicates (SHA256)
    ExactDuplicateGroup,
    ExactDuplicateAnalysisResult,
    ExactDuplicateExecutionResult,
    # Similar Duplicates (Perceptual Hash)
    SimilarDuplicateGroup,
    SimilarDuplicateAnalysisResult,
    SimilarDuplicateExecutionResult,
    # HEIC
    HeicAnalysisResult,
    HeicExecutionResult,
    # Live Photos
    LivePhotoGroup,
    LivePhotosAnalysisResult,
    LivePhotosExecutionResult,
    # Visual Identical
    VisualIdenticalGroup,
    VisualIdenticalAnalysisResult,
    VisualIdenticalExecutionResult,
    # Zero Byte
    ZeroByteAnalysisResult,
    ZeroByteExecutionResult,
)

__all__ = [
    # Servicios
    'FileRenamerService',
    'LivePhotoService',
    'FileOrganizerService',
    'HeicService',
    'DuplicatesExactService',
    'DuplicatesSimilarService',
    'VisualIdenticalService',
    'ZeroByteService',
    # Enums
    'OrganizationType',
    # Dataclasses de servicios
    'LivePhotoGroup',
    'DuplicatesSimilarAnalysis',
    'VisualIdenticalGroup',
    # Exact Duplicates
    'ExactDuplicateGroup',
    'ExactDuplicateAnalysisResult',
    'ExactDuplicateExecutionResult',
    # Similar Duplicates
    'SimilarDuplicateGroup',
    'SimilarDuplicateAnalysisResult',
    'SimilarDuplicateExecutionResult',
    # Result types
    'RenameAnalysisResult',
    'RenameExecutionResult',
    'OrganizationAnalysisResult',
    'OrganizationExecutionResult',
    'HeicAnalysisResult',
    'HeicExecutionResult',
    'LivePhotosAnalysisResult',
    'LivePhotosExecutionResult',
    'VisualIdenticalAnalysisResult',
    'VisualIdenticalExecutionResult',
    'ZeroByteAnalysisResult',
    'ZeroByteExecutionResult',
]
