# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Configuración de pytest y fixtures compartidas para todos los tests.

Este archivo contiene fixtures reutilizables para crear archivos de prueba,
directorios temporales, y datos de muestra para los tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple
from PIL import Image


# ==================== PYQT6 / PYTEST-QT FIX (SEGFAULT PREVENTION) ====================
# PyQt6 segfaults when QApplication is destroyed during pytest-qt teardown.
# This happens because Qt C++ objects are freed in an unpredictable order
# when the Python process exits. The fix: create a single, session-scoped
# QApplication that is NEVER deleted during the test session.

@pytest.fixture(scope='session')
def qapp():
    """Session-scoped QApplication that prevents segfault on teardown.
    
    Overrides pytest-qt's default qapp fixture to avoid PyQt6 segfaults
    caused by QApplication destruction during process exit.
    """
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Intentionally do NOT delete or quit the QApplication.
    # Python's process exit will handle cleanup safely.


# ==================== FIXTURES DE DIRECTORIOS ====================

@pytest.fixture
def temp_dir():
    """
    Crea un directorio temporal que se limpia automáticamente después del test.
    """
    temp_path = Path(tempfile.mkdtemp()).resolve()
    yield temp_path
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def nested_temp_dir(temp_dir):
    subdirs = {
        'subdir1': temp_dir / 'subdir1',
        'subdir2': temp_dir / 'subdir2',
        'nested': temp_dir / 'subdir2' / 'nested',
        'subdir3': temp_dir / 'subdir3',
    }
    for subdir in subdirs.values():
        subdir.mkdir(parents=True, exist_ok=True)
    return temp_dir, subdirs


# ==================== FIXTURES DE ARCHIVOS ====================

@pytest.fixture
def create_test_image():
    created_files = []

    def _create_image(path: Path, size: Tuple[int, int] = (100, 100), color: str = 'blue', format: str = 'JPEG') -> Path:
        img = Image.new('RGB', size, color=color)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, format=format)
        created_files.append(path)
        return path

    yield _create_image

    for file_path in created_files:
        if file_path.exists():
            file_path.unlink()


@pytest.fixture
def create_test_video():
    created_files = []

    def _create_video(path: Path, size_bytes: int = 1024) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(b'\x00' * size_bytes)
        created_files.append(path)
        return path

    yield _create_video

    for file_path in created_files:
        if file_path.exists():
            file_path.unlink()


@pytest.fixture
def create_renamed_file():
    created_files = []

    def _create_renamed(directory: Path, date: datetime, file_type: str = 'IMG', extension: str = '.jpg', sequence: int = None, size: Tuple[int, int] = (100, 100)) -> Path:
        date_str = date.strftime('%Y%m%d_%H%M%S')
        if sequence:
            filename = f"{file_type}_{date_str}_{sequence:03d}{extension}"
        else:
            filename = f"{file_type}_{date_str}{extension}"
        file_path = directory / filename
        if extension.lower() in ['.jpg', '.jpeg', '.png', '.heic']:
            img = Image.new('RGB', size, color='blue')
            file_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(file_path, format='JPEG')
        else:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b'\x00' * 1024)
        created_files.append(file_path)
        return file_path

    yield _create_renamed

    for file_path in created_files:
        if file_path.exists():
            file_path.unlink()


@pytest.fixture
def create_live_photo_pair(create_test_image, create_test_video):
    def _create_pair(directory: Path, base_name: str, img_extension: str = '.HEIC', vid_extension: str = '.MOV', img_size: Tuple[int, int] = (100, 100), vid_size: int = 2048):
        img_path = create_test_image(path=directory / f"{base_name}{img_extension}", size=img_size)
        vid_path = create_test_video(path=directory / f"{base_name}{vid_extension}", size_bytes=vid_size)
        import os
        timestamp = datetime.now().timestamp()
        os.utime(img_path, (timestamp, timestamp))
        os.utime(vid_path, (timestamp, timestamp))
        return img_path, vid_path
    return _create_pair


@pytest.fixture
def sample_live_photos_directory(temp_dir, create_live_photo_pair):
    metadata = {'valid_pairs': [], 'orphan_images': [], 'orphan_videos': []}
    for i in range(1, 4):
        img, vid = create_live_photo_pair(directory=temp_dir, base_name=f'IMG_000{i}')
        metadata['valid_pairs'].append({'image': img, 'video': vid, 'base_name': f'IMG_000{i}'})
    orphan_img = temp_dir / 'IMG_ORPHAN.HEIC'
    img = Image.new('RGB', (100, 100), color='red')
    img.save(orphan_img, format='JPEG')
    metadata['orphan_images'].append(orphan_img)
    orphan_vid = temp_dir / 'VID_ORPHAN.MOV'
    orphan_vid.write_bytes(b'\x00' * 1024)
    metadata['orphan_videos'].append(orphan_vid)
    return temp_dir, metadata


@pytest.fixture
def sample_dates():
    now = datetime.now()
    return {
        'now': now,
        'yesterday': now - timedelta(days=1),
        'last_week': now - timedelta(weeks=1),
        'last_month': now - timedelta(days=30),
        'last_year': now - timedelta(days=365),
    }


@pytest.fixture
def mock_config(monkeypatch):
    config = {
        'MAX_WORKERS': 4,
        'SUPPORTED_IMAGE_EXTENSIONS': ['.jpg', '.jpeg', '.heic', '.png'],
        'SUPPORTED_VIDEO_EXTENSIONS': ['.mov', '.mp4'],
    }
    return config


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Tests unitarios de lógica de negocio (services, utils)")
    config.addinivalue_line("markers", "integration: Tests de integración entre componentes")
    config.addinivalue_line("markers", "ui: Tests de componentes UI (requiere PyQt6)")
    config.addinivalue_line("markers", "slow: Tests que tardan más de 1 segundo")
    config.addinivalue_line("markers", "live_photos: Tests específicos de funcionalidad Live Photos")
    config.addinivalue_line("markers", "duplicates: Tests de detección de duplicados")
    config.addinivalue_line("markers", "renaming: Tests de renombrado de archivos")
    config.addinivalue_line("markers", "organization: Tests de organización de archivos")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if 'services' in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        if 'ui' in str(item.fspath):
            item.add_marker(pytest.mark.ui)
        if 'slow' in item.nodeid:
            item.add_marker(pytest.mark.slow)


# ==================== FIXTURES DE REPOSITORIO ====================

@pytest.fixture(autouse=True)
def reset_file_info_repository():
    from services.file_metadata_repository_cache import FileInfoRepositoryCache
    FileInfoRepositoryCache.reset_instance()
    yield
    FileInfoRepositoryCache.reset_instance()


# ==================== COMPATIBILIDAD DE TESTS ====================
try:
    from services.file_metadata_repository_cache import FileInfoRepositoryCache
    from services.file_metadata import FileMetadata
    from services.result_types import LivePhotosAnalysisResult, HeicAnalysisResult, ExactDuplicateAnalysisResult

    class _MetadataCacheProxy:
        def __getattr__(self, item):
            inst = FileInfoRepositoryCache.get_instance()
            return getattr(inst, item)

    metadata_cache = _MetadataCacheProxy()

    if not hasattr(FileInfoRepositoryCache, 'add_file'):
        def _add_file(self, path, metadata: FileMetadata = None):
            from pathlib import Path
            p = Path(path).resolve()
            try:
                st = p.stat()
                fs_size = st.st_size
                fs_ctime = st.st_ctime
                fs_mtime = st.st_mtime
                fs_atime = st.st_atime
            except Exception:
                fs_size = fs_ctime = fs_mtime = fs_atime = 0

            if metadata is None:
                metadata = FileMetadata(
                    path=p,
                    fs_size=fs_size,
                    fs_ctime=fs_ctime,
                    fs_mtime=fs_mtime,
                    fs_atime=fs_atime
                )

            with self._lock:
                self._cache[p] = metadata

        FileInfoRepositoryCache.add_file = _add_file  # type: ignore

    if not hasattr(FileInfoRepositoryCache, 'get_selected_date'):
        def _get_selected_date(self, path):
            # For tests, return None to fall back to select_best_date_from_file with get_all_metadata_from_file
            return None, None
        FileInfoRepositoryCache.get_selected_date = _get_selected_date

    if not hasattr(FileInfoRepositoryCache, 'get_filesystem_modification_date'):
        def _get_filesystem_modification_date(self, path):
            meta = self.get_file_metadata(path)
            if meta:
                return datetime.fromtimestamp(meta.fs_mtime)
            return None
        FileInfoRepositoryCache.get_filesystem_modification_date = _get_filesystem_modification_date

    # Add backward compatibility properties to result classes
    if not hasattr(LivePhotosAnalysisResult, 'live_photos_found'):
        @property
        def _live_photos_found(self):
            return len(self.groups)
        LivePhotosAnalysisResult.live_photos_found = _live_photos_found

    if not hasattr(LivePhotosAnalysisResult, 'files_to_delete'):
        @property
        def _files_to_delete(self):
            return self.data.get('files_to_delete', [])
        LivePhotosAnalysisResult.files_to_delete = _files_to_delete

    if not hasattr(LivePhotosAnalysisResult, 'files_to_keep'):
        @property
        def _files_to_keep(self):
            return self.data.get('files_to_keep', [])
        LivePhotosAnalysisResult.files_to_keep = _files_to_keep

    if not hasattr(HeicAnalysisResult, 'total_pairs'):
        @property
        def _total_pairs(self):
            return len(self.duplicate_pairs)
        HeicAnalysisResult.total_pairs = _total_pairs

    if not hasattr(HeicAnalysisResult, 'total_files'):
        @property
        def _total_files(self):
            return self.heic_files + self.jpg_files
        HeicAnalysisResult.total_files = _total_files

    # Add properties for execution results
    if not hasattr(LivePhotosExecutionResult, 'files_deleted'):
        @property
        def _files_deleted(self):
            return self.files_affected
        LivePhotosExecutionResult.files_deleted = _files_deleted

    if not hasattr(LivePhotosExecutionResult, 'space_freed'):
        @property
        def _space_freed(self):
            return self.bytes_processed
        LivePhotosExecutionResult.space_freed = _space_freed

    if not hasattr(ExactDuplicateExecutionResult, 'files_deleted'):
        @property
        def _files_deleted_dup(self):
            return self.files_affected
        ExactDuplicateExecutionResult.files_deleted = _files_deleted_dup

    # Monkeypatch analyze methods to accept old signature (directory first)
    import services.live_photos_service
    import services.duplicates_exact_service
    import services.duplicates_similar_service
    import services.heic_service
    from services.file_metadata import FileMetadata
    from services.result_types import LivePhotosExecutionResult, ExactDuplicateExecutionResult
    from services.file_metadata_repository_cache import PopulationStrategy

    def _populate_cache_from_directory(directory: Path, repo):
        """Populate cache from directory for tests."""
        from pathlib import Path
        files = []
        for f in directory.rglob('*'):
            if f.is_file():
                files.append(f)
        if files:
            repo.populate_from_scan(files, PopulationStrategy.FILESYSTEM_METADATA)

    original_analyze_live = services.live_photos_service.LivePhotoService.analyze
    def _wrapped_analyze_live(self, directory_or_validate_dates, validate_dates=None, progress_callback=None, **kwargs):
        if isinstance(directory_or_validate_dates, str) or hasattr(directory_or_validate_dates, '__fspath__'):
            # Old signature: directory first - populate cache and call new API
            directory = Path(directory_or_validate_dates)
            repo = FileInfoRepositoryCache.get_instance()
            _populate_cache_from_directory(directory, repo)
            # Enable debug logging for this test
            import logging
            self.logger.setLevel(logging.DEBUG)
            return original_analyze_live(self, validate_dates=validate_dates if validate_dates is not None else True, progress_callback=progress_callback)
        else:
            # New signature: validate_dates first
            return original_analyze_live(self, validate_dates=directory_or_validate_dates, progress_callback=validate_dates, **kwargs)
    services.live_photos_service.LivePhotoService.analyze = _wrapped_analyze_live

    original_analyze_exact = services.duplicates_exact_service.DuplicatesExactService.analyze
    def _wrapped_analyze_exact(self, directory_or_progress, progress_callback=None, **kwargs):
        if isinstance(directory_or_progress, str) or hasattr(directory_or_progress, '__fspath__'):
            # Old signature: directory first
            directory = Path(directory_or_progress)
            repo = FileInfoRepositoryCache.get_instance()
            _populate_cache_from_directory(directory, repo)
            kwargs['directory'] = directory
            return original_analyze_exact(self, progress_callback=progress_callback, **kwargs)
        else:
            # New signature: progress_callback first
            return original_analyze_exact(self, progress_callback=directory_or_progress, **kwargs)
    services.duplicates_exact_service.DuplicatesExactService.analyze = _wrapped_analyze_exact

    original_analyze_similar = services.duplicates_similar_service.DuplicatesSimilarService.analyze
    def _wrapped_analyze_similar(self, directory_or_sensitivity, sensitivity=None, progress_callback=None, **kwargs):
        if isinstance(directory_or_sensitivity, str) or hasattr(directory_or_sensitivity, '__fspath__'):
            # Old signature: directory first
            directory = Path(directory_or_sensitivity)
            repo = FileInfoRepositoryCache.get_instance()
            _populate_cache_from_directory(directory, repo)
            kwargs['directory'] = directory
            return original_analyze_similar(self, sensitivity=sensitivity, progress_callback=progress_callback, **kwargs)
        else:
            # New signature: sensitivity first
            return original_analyze_similar(self, sensitivity=directory_or_sensitivity, progress_callback=sensitivity, **kwargs)
    services.duplicates_similar_service.DuplicatesSimilarService.analyze = _wrapped_analyze_similar

    original_analyze_heic = services.heic_service.HeicService.analyze
    def _wrapped_analyze_heic(self, directory_or_progress, progress_callback=None, **kwargs):
        if isinstance(directory_or_progress, str) or hasattr(directory_or_progress, '__fspath__'):
            # Old signature: directory first
            directory = Path(directory_or_progress)
            repo = FileInfoRepositoryCache.get_instance()
            _populate_cache_from_directory(directory, repo)
            kwargs['directory'] = directory
            return original_analyze_heic(self, progress_callback=progress_callback, **kwargs)
        else:
            # New signature: progress_callback first
            return original_analyze_heic(self, progress_callback=directory_or_progress, **kwargs)
    services.heic_service.HeicService.analyze = _wrapped_analyze_heic

except Exception:
    pass
