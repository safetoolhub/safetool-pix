# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests unitarios para LivePhotoService.

Cubre la detección de Live Photos (imagen + video MOV), validación de fechas,
y la lógica de eliminación de videos.
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from config import Config
from services.live_photos_service import LivePhotoService
from services.result_types import (
    LivePhotosAnalysisResult, 
    LivePhotosExecutionResult,
    LivePhotoGroup,
    LivePhotoImageInfo
)
from services.file_metadata import FileMetadata


# ==================== FIXTURES ====================

@pytest.fixture
def live_photos_service():
    """Crea una instancia del servicio para tests."""
    return LivePhotoService()


@pytest.fixture
def mock_repo():
    """Mock del FileInfoRepositoryCache."""
    with patch('services.live_photos_service.FileInfoRepositoryCache.get_instance') as mock:
        yield mock.return_value


def create_mock_metadata(path: Path, size: int = 1024, mtime: float = None) -> MagicMock:
    """Crea un mock de FileMetadata con los campos necesarios."""
    meta = MagicMock(spec=FileMetadata)
    meta.path = Path(path)
    meta.fs_size = size
    meta.fs_mtime = mtime or datetime.now().timestamp()
    meta.fs_ctime = meta.fs_mtime
    meta.fs_atime = meta.fs_mtime
    meta.extension = meta.path.suffix.lower()
    meta.get_summary = MagicMock(return_value=f"Mock: {path}")
    return meta


# ==================== TESTS DE ANÁLISIS BÁSICO ====================

class TestLivePhotoServiceAnalysis:
    """Tests para el método analyze() del servicio."""
    
    def test_analyze_detects_valid_live_photo_group(self, live_photos_service, mock_repo):
        """Detecta un grupo válido de Live Photo (imagen + video con mismo nombre)."""
        dir_path = Path("/mock/photos")
        img_path = dir_path / "IMG_0001.heic"
        vid_path = dir_path / "IMG_0001.mov"
        
        img_meta = create_mock_metadata(img_path, size=5000)
        vid_meta = create_mock_metadata(vid_path, size=2000)
        
        mock_repo.get_all_files.return_value = [img_meta, vid_meta]
        mock_repo.get_file_count.return_value = 2
        
        # Fechas coinciden dentro de 5 segundos
        dt = datetime(2023, 6, 15, 14, 30, 0)
        with patch('services.live_photos_service.select_best_date_from_common_date_to_2_files', 
                   return_value=(dt, dt, 'exif_date_time_original')):
            result = live_photos_service.analyze(validate_dates=True)
        
        assert result.items_count == 1
        assert len(result.groups) == 1
        assert len(result.rejected_groups) == 0
        
        group = result.groups[0]
        assert group.video_path == vid_path
        assert len(group.images) == 1
        assert group.images[0].path == img_path
        assert group.date_difference == 0.0
    
    def test_analyze_rejects_group_with_time_difference_over_threshold(
        self, live_photos_service, mock_repo
    ):
        """Rechaza grupos donde la diferencia de tiempo excede el umbral."""
        dir_path = Path("/mock/photos")
        img_path = dir_path / "IMG_0001.jpg"
        vid_path = dir_path / "IMG_0001.mov"
        
        img_meta = create_mock_metadata(img_path, size=5000)
        vid_meta = create_mock_metadata(vid_path, size=2000)
        
        mock_repo.get_all_files.return_value = [img_meta, vid_meta]
        mock_repo.get_file_count.return_value = 2
        
        # Diferencia que excede el threshold configurado (Config.LIVE_PHOTO_MAX_TIME_DIFFERENCE_SECONDS + 10)
        threshold = Config.LIVE_PHOTO_MAX_TIME_DIFFERENCE_SECONDS
        time_diff = threshold + 10  # Supera el threshold
        dt_vid = datetime(2023, 6, 15, 14, 30, 0)
        dt_img = dt_vid + timedelta(seconds=time_diff)
        with patch('services.live_photos_service.select_best_date_from_common_date_to_2_files', 
                   return_value=(dt_vid, dt_img, 'fs_mtime')):
            result = live_photos_service.analyze(validate_dates=True)
        
        assert result.items_count == 0
        assert len(result.groups) == 0
        assert len(result.rejected_groups) == 1
        
        rejected = result.rejected_groups[0]
        assert rejected.date_difference == time_diff
    
    def test_analyze_accepts_group_without_date_validation(
        self, live_photos_service, mock_repo
    ):
        """Acepta grupos sin validar fechas cuando validate_dates=False."""
        dir_path = Path("/mock/photos")
        img_path = dir_path / "IMG_0001.jpeg"
        vid_path = dir_path / "IMG_0001.mov"
        
        img_meta = create_mock_metadata(img_path, size=5000)
        vid_meta = create_mock_metadata(vid_path, size=2000)
        
        mock_repo.get_all_files.return_value = [img_meta, vid_meta]
        mock_repo.get_file_count.return_value = 2
        
        result = live_photos_service.analyze(validate_dates=False)
        
        assert result.items_count == 1
        assert len(result.groups) == 1
        # Sin validación, date_difference debe ser 0
        assert result.groups[0].date_difference == 0.0
    
    def test_analyze_ignores_files_in_different_directories(
        self, live_photos_service, mock_repo
    ):
        """No empareja archivos con mismo nombre pero en directorios diferentes."""
        dir1 = Path("/mock/photos/2023")
        dir2 = Path("/mock/photos/2024")
        
        img_meta = create_mock_metadata(dir1 / "IMG_0001.heic", size=5000)
        vid_meta = create_mock_metadata(dir2 / "IMG_0001.mov", size=2000)
        
        mock_repo.get_all_files.return_value = [img_meta, vid_meta]
        mock_repo.get_file_count.return_value = 2
        
        result = live_photos_service.analyze(validate_dates=False)
        
        assert result.items_count == 0
        assert len(result.groups) == 0
    
    def test_analyze_handles_multiple_images_per_video(
        self, live_photos_service, mock_repo
    ):
        """Agrupa múltiples imágenes con el mismo video cuando comparten nombre base."""
        dir_path = Path("/mock/photos")
        
        # Dos imágenes con el mismo nombre base (diferentes extensiones)
        # En la realidad esto pasa cuando se renombra con sufijos como _photo
        img1_meta = create_mock_metadata(dir_path / "IMG_0001.heic", size=5000)
        img2_meta = create_mock_metadata(dir_path / "IMG_0001_photo.jpg", size=4000)
        vid_meta = create_mock_metadata(dir_path / "IMG_0001.mov", size=2000)
        
        mock_repo.get_all_files.return_value = [img1_meta, img2_meta, vid_meta]
        mock_repo.get_file_count.return_value = 3
        
        dt = datetime(2023, 6, 15, 14, 30, 0)
        with patch('services.live_photos_service.select_best_date_from_common_date_to_2_files', 
                   return_value=(dt, dt, 'exif_date_time_original')):
            result = live_photos_service.analyze(validate_dates=True)
        
        # Debe haber un grupo con el video + la imagen heic
        # El _photo se normaliza y coincide con img_0001
        assert result.items_count >= 1
    
    def test_analyze_returns_empty_when_no_videos(self, live_photos_service, mock_repo):
        """Retorna resultado vacío si no hay videos MOV."""
        dir_path = Path("/mock/photos")
        img_meta = create_mock_metadata(dir_path / "IMG_0001.heic", size=5000)
        
        mock_repo.get_all_files.return_value = [img_meta]
        mock_repo.get_file_count.return_value = 1
        
        result = live_photos_service.analyze(validate_dates=True)
        
        assert result.items_count == 0
        assert len(result.groups) == 0
    
    def test_analyze_returns_empty_when_no_photos(self, live_photos_service, mock_repo):
        """Retorna resultado vacío si no hay fotos."""
        dir_path = Path("/mock/photos")
        vid_meta = create_mock_metadata(dir_path / "IMG_0001.mov", size=2000)
        
        mock_repo.get_all_files.return_value = [vid_meta]
        mock_repo.get_file_count.return_value = 1
        
        result = live_photos_service.analyze(validate_dates=True)
        
        assert result.items_count == 0
        assert len(result.groups) == 0


# ==================== TESTS DE NORMALIZACIÓN DE NOMBRES ====================

class TestNameNormalization:
    """Tests para la función _normalize_name."""
    
    def test_normalize_removes_photo_suffix(self, live_photos_service):
        """Elimina sufijos _photo del nombre."""
        assert live_photos_service._normalize_name("IMG_0001_photo") == "img_0001"
        assert live_photos_service._normalize_name("IMG_0001_PHOTO") == "img_0001"
    
    def test_normalize_removes_video_suffix(self, live_photos_service):
        """Elimina sufijos _video del nombre."""
        assert live_photos_service._normalize_name("IMG_0001_video") == "img_0001"
        assert live_photos_service._normalize_name("IMG_0001-video") == "img_0001"
    
    def test_normalize_handles_space_suffixes(self, live_photos_service):
        """Elimina sufijos con espacios."""
        assert live_photos_service._normalize_name("IMG_0001 photo") == "img_0001"
        assert live_photos_service._normalize_name("IMG_0001 video") == "img_0001"
    
    def test_normalize_converts_to_lowercase(self, live_photos_service):
        """Convierte el nombre a minúsculas."""
        assert live_photos_service._normalize_name("IMG_0001") == "img_0001"
        assert live_photos_service._normalize_name("Photo_2023") == "photo_2023"
    
    def test_normalize_preserves_name_without_suffixes(self, live_photos_service):
        """Preserva nombres sin sufijos especiales."""
        assert live_photos_service._normalize_name("vacation_beach") == "vacation_beach"


# ==================== TESTS DE EJECUCIÓN ====================

class TestLivePhotoServiceExecution:
    """Tests para el método execute() del servicio."""
    
    def test_execute_returns_empty_result_for_empty_groups(self, live_photos_service):
        """Retorna resultado vacío si no hay grupos."""
        analysis = LivePhotosAnalysisResult(
            groups=[],
            rejected_groups=[],
            items_count=0,
            bytes_total=0,
            total_space=0
        )
        
        result = live_photos_service.execute(analysis, dry_run=True)
        
        assert result.success is True
        assert result.items_processed == 0
        assert result.videos_deleted == 0
    
    def test_execute_protects_video_with_long_duration(
        self, live_photos_service, mock_repo, temp_dir
    ):
        """Videos con duración > 3.2s no se eliminan (salvaguarda)."""
        from config import Config
        
        # Crear archivo de video real
        vid_path = temp_dir / "IMG_LONG.mov"
        vid_path.write_bytes(b'\x00' * 1024)
        
        # Mock del repositorio que devuelve duración > 3.2s
        long_video_meta = MagicMock(spec=FileMetadata)
        long_video_meta.path = vid_path
        long_video_meta.exif_VideoDurationSeconds = 5.0  # 5 segundos > 3.2s
        long_video_meta.extension = '.mov'
        
        mock_repo.get_file_metadata.return_value = long_video_meta
        mock_repo.get_all_files.return_value = []
        
        group = LivePhotoGroup(
            video_path=vid_path,
            video_size=1024,
            images=[LivePhotoImageInfo(
                path=temp_dir / "IMG_LONG.heic",
                size=5000,
                date=datetime.now(),
                date_source="test"
            )],
            base_name="IMG_LONG",
            directory=temp_dir,
            video_date=datetime.now(),
            video_date_source="test",
            date_source="test",
            date_difference=0.0
        )
        
        analysis = LivePhotosAnalysisResult(
            groups=[group],
            rejected_groups=[],
            items_count=1,
            bytes_total=6024,
            total_space=6024
        )
        
        result = live_photos_service.execute(analysis, dry_run=False, create_backup=False)
        
        assert result.success is True
        assert result.videos_deleted == 0  # No se eliminó
        assert vid_path.exists()  # El archivo sigue existiendo
        assert "protegidos" in result.message.lower() or "protected" in result.message.lower()
    
    def test_execute_deletes_video_with_short_duration(
        self, live_photos_service, mock_repo, temp_dir
    ):
        """Videos con duración <= 3.2s sí se eliminan."""
        # Crear archivo de video real
        vid_path = temp_dir / "IMG_SHORT.mov"
        vid_path.write_bytes(b'\x00' * 1024)
        
        # Mock del repositorio que devuelve duración corta
        short_video_meta = MagicMock(spec=FileMetadata)
        short_video_meta.path = vid_path
        short_video_meta.exif_VideoDurationSeconds = 2.5  # 2.5 segundos <= 3.2s
        short_video_meta.extension = '.mov'
        
        mock_repo.get_file_metadata.return_value = short_video_meta
        mock_repo.get_all_files.return_value = []
        
        group = LivePhotoGroup(
            video_path=vid_path,
            video_size=1024,
            images=[LivePhotoImageInfo(
                path=temp_dir / "IMG_SHORT.heic",
                size=5000,
                date=datetime.now(),
                date_source="test"
            )],
            base_name="IMG_SHORT",
            directory=temp_dir,
            video_date=datetime.now(),
            video_date_source="test",
            date_source="test",
            date_difference=0.0
        )
        
        analysis = LivePhotosAnalysisResult(
            groups=[group],
            rejected_groups=[],
            items_count=1,
            bytes_total=6024,
            total_space=6024
        )
        
        result = live_photos_service.execute(analysis, dry_run=False, create_backup=False)
        
        assert result.success is True
        assert result.videos_deleted == 1  # Sí se eliminó
        assert not vid_path.exists()  # El archivo fue eliminado
    
    def test_execute_dry_run_does_not_delete_files(
        self, live_photos_service, mock_repo, temp_dir
    ):
        """El modo dry_run no elimina archivos realmente."""
        # Crear archivos reales
        vid_path = temp_dir / "IMG_0001.mov"
        vid_path.write_bytes(b'\x00' * 1024)
        
        group = LivePhotoGroup(
            video_path=vid_path,
            video_size=1024,
            images=[LivePhotoImageInfo(
                path=temp_dir / "IMG_0001.heic",
                size=5000,
                date=datetime.now(),
                date_source="test"
            )],
            base_name="IMG_0001",
            directory=temp_dir,
            video_date=datetime.now(),
            video_date_source="test",
            date_source="test",
            date_difference=0.0
        )
        
        analysis = LivePhotosAnalysisResult(
            groups=[group],
            rejected_groups=[],
            items_count=1,
            bytes_total=6024,
            total_space=6024
        )
        
        result = live_photos_service.execute(analysis, dry_run=True, create_backup=False)
        
        assert result.success is True
        assert result.dry_run is True
        assert result.videos_deleted == 1
        assert vid_path.exists()  # El archivo sigue existiendo
    
    def test_execute_deletes_video_files(
        self, live_photos_service, mock_repo, temp_dir
    ):
        """El modo real elimina los videos."""
        # Crear archivos reales
        vid_path = temp_dir / "IMG_0001.mov"
        vid_path.write_bytes(b'\x00' * 1024)
        
        group = LivePhotoGroup(
            video_path=vid_path,
            video_size=1024,
            images=[LivePhotoImageInfo(
                path=temp_dir / "IMG_0001.heic",
                size=5000,
                date=datetime.now(),
                date_source="test"
            )],
            base_name="IMG_0001",
            directory=temp_dir,
            video_date=datetime.now(),
            video_date_source="test",
            date_source="test",
            date_difference=0.0
        )
        
        analysis = LivePhotosAnalysisResult(
            groups=[group],
            rejected_groups=[],
            items_count=1,
            bytes_total=6024,
            total_space=6024
        )
        
        result = live_photos_service.execute(analysis, dry_run=False, create_backup=False)
        
        assert result.success is True
        assert result.dry_run is False
        assert result.videos_deleted == 1
        assert not vid_path.exists()  # El archivo fue eliminado


# ==================== TESTS DE RESULT TYPES ====================

class TestLivePhotoGroupDataclass:
    """Tests para el dataclass LivePhotoGroup."""
    
    def test_total_size_includes_video_and_images(self):
        """total_size suma video + todas las imágenes."""
        group = LivePhotoGroup(
            video_path=Path("/mock/IMG.mov"),
            video_size=2000,
            images=[
                LivePhotoImageInfo(path=Path("/mock/IMG.heic"), size=5000, date=None, date_source=None),
                LivePhotoImageInfo(path=Path("/mock/IMG.jpg"), size=4000, date=None, date_source=None),
            ],
            base_name="IMG",
            directory=Path("/mock"),
            video_date=None,
            video_date_source=None,
            date_source=None,
            date_difference=0.0
        )
        
        assert group.total_size == 11000  # 2000 + 5000 + 4000
    
    def test_images_size_excludes_video(self):
        """images_size solo cuenta las imágenes."""
        group = LivePhotoGroup(
            video_path=Path("/mock/IMG.mov"),
            video_size=2000,
            images=[
                LivePhotoImageInfo(path=Path("/mock/IMG.heic"), size=5000, date=None, date_source=None),
            ],
            base_name="IMG",
            directory=Path("/mock"),
            video_date=None,
            video_date_source=None,
            date_source=None,
            date_difference=0.0
        )
        
        assert group.images_size == 5000
    
    def test_image_count_returns_number_of_images(self):
        """image_count retorna el número de imágenes."""
        group = LivePhotoGroup(
            video_path=Path("/mock/IMG.mov"),
            video_size=2000,
            images=[
                LivePhotoImageInfo(path=Path("/mock/IMG1.heic"), size=5000, date=None, date_source=None),
                LivePhotoImageInfo(path=Path("/mock/IMG2.jpg"), size=4000, date=None, date_source=None),
            ],
            base_name="IMG",
            directory=Path("/mock"),
            video_date=None,
            video_date_source=None,
            date_source=None,
            date_difference=0.0
        )
        
        assert group.image_count == 2
    
    def test_primary_image_returns_first_image(self):
        """primary_image retorna la primera imagen."""
        img1 = LivePhotoImageInfo(path=Path("/mock/IMG1.heic"), size=5000, date=None, date_source=None)
        img2 = LivePhotoImageInfo(path=Path("/mock/IMG2.jpg"), size=4000, date=None, date_source=None)
        
        group = LivePhotoGroup(
            video_path=Path("/mock/IMG.mov"),
            video_size=2000,
            images=[img1, img2],
            base_name="IMG",
            directory=Path("/mock"),
            video_date=None,
            video_date_source=None,
            date_source=None,
            date_difference=0.0
        )
        
        assert group.primary_image == img1
    
    def test_best_date_prefers_video_date(self):
        """best_date prefiere la fecha del video."""
        video_date = datetime(2023, 6, 15, 14, 30, 0)
        img_date = datetime(2023, 6, 15, 14, 30, 5)
        
        group = LivePhotoGroup(
            video_path=Path("/mock/IMG.mov"),
            video_size=2000,
            images=[
                LivePhotoImageInfo(path=Path("/mock/IMG.heic"), size=5000, date=img_date, date_source="exif"),
            ],
            base_name="IMG",
            directory=Path("/mock"),
            video_date=video_date,
            video_date_source="exif",
            date_source="exif",
            date_difference=5.0
        )
        
        assert group.best_date == video_date


class TestLivePhotosAnalysisResult:
    """Tests para el dataclass LivePhotosAnalysisResult."""
    
    def test_potential_savings_sums_video_sizes(self):
        """potential_savings suma los tamaños de todos los videos."""
        groups = [
            LivePhotoGroup(
                video_path=Path("/mock/IMG1.mov"), video_size=2000,
                images=[LivePhotoImageInfo(path=Path("/mock/IMG1.heic"), size=5000, date=None, date_source=None)],
                base_name="IMG1", directory=Path("/mock"),
                video_date=None, video_date_source=None, date_source=None, date_difference=0.0
            ),
            LivePhotoGroup(
                video_path=Path("/mock/IMG2.mov"), video_size=3000,
                images=[LivePhotoImageInfo(path=Path("/mock/IMG2.heic"), size=5000, date=None, date_source=None)],
                base_name="IMG2", directory=Path("/mock"),
                video_date=None, video_date_source=None, date_source=None, date_difference=0.0
            ),
        ]
        
        result = LivePhotosAnalysisResult(
            groups=groups,
            rejected_groups=[],
            items_count=2,
            bytes_total=15000,
            total_space=15000
        )
        
        assert result.potential_savings == 5000  # 2000 + 3000
    
    def test_total_images_counts_all_images(self):
        """total_images cuenta imágenes de todos los grupos."""
        groups = [
            LivePhotoGroup(
                video_path=Path("/mock/IMG1.mov"), video_size=2000,
                images=[
                    LivePhotoImageInfo(path=Path("/mock/IMG1.heic"), size=5000, date=None, date_source=None),
                    LivePhotoImageInfo(path=Path("/mock/IMG1.jpg"), size=4000, date=None, date_source=None),
                ],
                base_name="IMG1", directory=Path("/mock"),
                video_date=None, video_date_source=None, date_source=None, date_difference=0.0
            ),
            LivePhotoGroup(
                video_path=Path("/mock/IMG2.mov"), video_size=3000,
                images=[LivePhotoImageInfo(path=Path("/mock/IMG2.heic"), size=5000, date=None, date_source=None)],
                base_name="IMG2", directory=Path("/mock"),
                video_date=None, video_date_source=None, date_source=None, date_difference=0.0
            ),
        ]
        
        result = LivePhotosAnalysisResult(
            groups=groups,
            rejected_groups=[],
            items_count=2,
            bytes_total=19000,
            total_space=19000
        )
        
        assert result.total_images == 3  # 2 + 1
    
    def test_total_videos_equals_group_count(self):
        """total_videos es igual al número de grupos."""
        groups = [
            LivePhotoGroup(
                video_path=Path("/mock/IMG1.mov"), video_size=2000,
                images=[LivePhotoImageInfo(path=Path("/mock/IMG1.heic"), size=5000, date=None, date_source=None)],
                base_name="IMG1", directory=Path("/mock"),
                video_date=None, video_date_source=None, date_source=None, date_difference=0.0
            ),
        ]
        
        result = LivePhotosAnalysisResult(
            groups=groups,
            rejected_groups=[],
            items_count=1,
            bytes_total=7000,
            total_space=7000
        )
        
        assert result.total_videos == 1
