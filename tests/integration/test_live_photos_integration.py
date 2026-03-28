# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests de integración para LivePhotoService.

Estos tests usan archivos reales en un directorio temporal para validar
el flujo completo de análisis y ejecución.
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from services.live_photos_service import LivePhotoService
from services.file_metadata_repository_cache import FileInfoRepositoryCache, PopulationStrategy
from utils.file_utils import get_exif_from_image


# ==================== FIXTURES ====================

@pytest.fixture
def reset_repository():
    """Limpia el repositorio antes y después de cada test."""
    repo = FileInfoRepositoryCache.get_instance()
    repo.clear()
    yield repo
    repo.clear()


@pytest.fixture
def live_photos_service():
    """Crea una instancia del servicio."""
    return LivePhotoService()


@pytest.fixture
def live_photo_pair(temp_dir, create_test_image):
    """Crea un par imagen + video MOV en el directorio temporal."""
    img_path = temp_dir / "IMG_0001.heic"
    vid_path = temp_dir / "IMG_0001.mov"
    
    # Crear imagen real
    create_test_image(img_path, size=(100, 100), format='JPEG')
    # Renombrar a .heic (es solo para test, el contenido no importa)
    
    # Crear video falso
    vid_path.write_bytes(b'\x00' * 2048)
    
    return img_path, vid_path


@pytest.fixture
def multiple_live_photos(temp_dir, create_test_image):
    """Crea múltiples pares de Live Photos en el directorio temporal."""
    pairs = []
    for i in range(3):
        img_path = temp_dir / f"IMG_{i:04d}.jpg"
        vid_path = temp_dir / f"IMG_{i:04d}.mov"
        
        create_test_image(img_path, size=(100, 100), format='JPEG')
        vid_path.write_bytes(b'\x00' * (1024 * (i + 1)))
        
        pairs.append((img_path, vid_path))
    
    return pairs


# ==================== TESTS DE INTEGRACIÓN ====================

class TestLivePhotoServiceIntegration:
    """Tests de integración con archivos reales."""
    
    def test_analyze_detects_real_live_photo_pair(
        self, live_photos_service, reset_repository, live_photo_pair
    ):
        """Detecta un par real de Live Photo con archivos en disco."""
        img_path, vid_path = live_photo_pair
        repo = reset_repository
        
        # Poblar el repositorio con los archivos
        repo.populate_from_scan(
            [img_path, vid_path],
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            stop_check_callback=lambda: False
        )
        
        result = live_photos_service.analyze(validate_dates=False)
        
        assert result.success is True
        assert result.items_count == 1
        assert len(result.groups) == 1
        
        group = result.groups[0]
        # Use resolve() on both sides to normalize Windows 8.3 short-name
        # aliases (e.g. RUNNER~1 vs runneradmin) that appear on CI runners.
        assert group.video_path.resolve() == vid_path.resolve()
        assert group.base_name == "img_0001"  # normalizado a minúsculas
    
    def test_analyze_detects_multiple_live_photo_pairs(
        self, live_photos_service, reset_repository, multiple_live_photos
    ):
        """Detecta múltiples pares de Live Photos."""
        repo = reset_repository
        
        all_files = [f for pair in multiple_live_photos for f in pair]
        repo.populate_from_scan(
            all_files,
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            stop_check_callback=lambda: False
        )
        
        result = live_photos_service.analyze(validate_dates=False)
        
        assert result.success is True
        assert result.items_count == 3
        assert len(result.groups) == 3
    
    def test_execute_dry_run_preserves_all_files(
        self, live_photos_service, reset_repository, live_photo_pair
    ):
        """El modo dry_run no elimina ningún archivo."""
        img_path, vid_path = live_photo_pair
        repo = reset_repository
        
        repo.populate_from_scan(
            [img_path, vid_path],
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            stop_check_callback=lambda: False
        )
        
        analysis = live_photos_service.analyze(validate_dates=False)
        result = live_photos_service.execute(analysis, dry_run=True, create_backup=False)
        
        assert result.success is True
        assert result.dry_run is True
        assert result.videos_deleted == 1
        
        # Ambos archivos deben existir
        assert img_path.exists()
        assert vid_path.exists()
    
    def test_execute_real_deletion_removes_only_videos(
        self, live_photos_service, reset_repository, live_photo_pair
    ):
        """La ejecución real elimina solo los videos, preservando imágenes."""
        img_path, vid_path = live_photo_pair
        repo = reset_repository
        
        repo.populate_from_scan(
            [img_path, vid_path],
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            stop_check_callback=lambda: False
        )
        
        analysis = live_photos_service.analyze(validate_dates=False)
        result = live_photos_service.execute(analysis, dry_run=False, create_backup=False)
        
        assert result.success is True
        assert result.dry_run is False
        assert result.videos_deleted == 1
        
        # Solo el video debe ser eliminado
        assert img_path.exists()
        assert not vid_path.exists()
    
    def test_execute_multiple_pairs_removes_all_videos(
        self, live_photos_service, reset_repository, multiple_live_photos
    ):
        """La ejecución real elimina todos los videos de múltiples pares."""
        repo = reset_repository
        
        all_files = [f for pair in multiple_live_photos for f in pair]
        repo.populate_from_scan(
            all_files,
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            stop_check_callback=lambda: False
        )
        
        analysis = live_photos_service.analyze(validate_dates=False)
        result = live_photos_service.execute(analysis, dry_run=False, create_backup=False)
        
        assert result.success is True
        assert result.videos_deleted == 3
        
        # Todas las imágenes deben existir, todos los videos eliminados
        for img_path, vid_path in multiple_live_photos:
            assert img_path.exists()
            assert not vid_path.exists()
    
    def test_analysis_respects_directory_boundaries(
        self, live_photos_service, reset_repository, temp_dir, create_test_image
    ):
        """No empareja archivos con mismo nombre pero en directorios diferentes."""
        # Crear subdirectorios
        dir1 = temp_dir / "2023"
        dir2 = temp_dir / "2024"
        dir1.mkdir()
        dir2.mkdir()
        
        # Crear imagen en dir1, video en dir2
        img_path = dir1 / "IMG_0001.jpg"
        vid_path = dir2 / "IMG_0001.mov"
        
        create_test_image(img_path, size=(100, 100), format='JPEG')
        vid_path.write_bytes(b'\x00' * 1024)
        
        repo = reset_repository
        repo.populate_from_scan(
            [img_path, vid_path],
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            stop_check_callback=lambda: False
        )
        
        result = live_photos_service.analyze(validate_dates=False)
        
        assert result.items_count == 0
        assert len(result.groups) == 0
    
    def test_analysis_handles_empty_repository(self, live_photos_service, reset_repository):
        """Maneja graciosamente un repositorio vacío."""
        result = live_photos_service.analyze(validate_dates=False)
        
        assert result.success is True
        assert result.items_count == 0
        assert len(result.groups) == 0
        assert len(result.rejected_groups) == 0
    
    def test_analysis_ignores_orphan_videos(
        self, live_photos_service, reset_repository, temp_dir
    ):
        """Ignora videos sin imagen correspondiente."""
        vid_path = temp_dir / "IMG_0001.mov"
        vid_path.write_bytes(b'\x00' * 1024)
        
        repo = reset_repository
        repo.populate_from_scan(
            [vid_path],
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            stop_check_callback=lambda: False
        )
        
        result = live_photos_service.analyze(validate_dates=False)
        
        assert result.items_count == 0
        assert len(result.groups) == 0
    
    def test_analysis_ignores_orphan_images(
        self, live_photos_service, reset_repository, temp_dir, create_test_image
    ):
        """Ignora imágenes sin video correspondiente."""
        img_path = temp_dir / "IMG_0001.heic"
        create_test_image(img_path, size=(100, 100), format='JPEG')
        
        repo = reset_repository
        repo.populate_from_scan(
            [img_path],
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            stop_check_callback=lambda: False
        )
        
        result = live_photos_service.analyze(validate_dates=False)
        
        assert result.items_count == 0
        assert len(result.groups) == 0


class TestLivePhotoServicePotentialSavings:
    """Tests para calcular correctamente el espacio a liberar."""
    
    def test_potential_savings_equals_video_sizes(
        self, live_photos_service, reset_repository, temp_dir, create_test_image
    ):
        """El ahorro potencial es la suma de tamaños de videos."""
        # Crear pares con videos de diferentes tamaños
        for i, size in enumerate([1024, 2048, 4096]):
            img_path = temp_dir / f"IMG_{i:04d}.jpg"
            vid_path = temp_dir / f"IMG_{i:04d}.mov"
            
            create_test_image(img_path, size=(100, 100), format='JPEG')
            vid_path.write_bytes(b'\x00' * size)
        
        repo = reset_repository
        all_files = list(temp_dir.glob("*"))
        repo.populate_from_scan(
            all_files,
            strategy=PopulationStrategy.FILESYSTEM_METADATA,
            stop_check_callback=lambda: False
        )
        
        result = live_photos_service.analyze(validate_dates=False)
        
        expected_savings = 1024 + 2048 + 4096
        assert result.potential_savings == expected_savings
