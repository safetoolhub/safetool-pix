# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch
from services.heic_service import HeicService
from services.result_types import HEICDuplicatePair, HeicAnalysisResult
from services.file_metadata import FileMetadata

@pytest.fixture
def heic_service():
    return HeicService()

@pytest.fixture
def mock_repo():
    with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache.get_instance') as mock:
        yield mock.return_value

def create_mock_metadata(path, size=1024, mtime=None):
    meta = MagicMock(spec=FileMetadata)
    meta.path = Path(path)
    meta.fs_size = size
    meta.fs_mtime = mtime or datetime.now().timestamp()
    meta.extension = meta.path.suffix.lower()
    return meta

def test_heic_analysis_logic(heic_service, mock_repo):
    # Setup files in same directory with same base name
    dir_path = Path("/mock/dir")
    heic_path = dir_path / "photo.heic"
    jpg_path = dir_path / "photo.jpg"
    
    heic_meta = create_mock_metadata(heic_path, size=5000)
    jpg_meta = create_mock_metadata(jpg_path, size=8000)
    
    mock_repo.get_all_files.return_value = [heic_meta, jpg_meta]
    
    # Test case 1: Dates match within 5s
    dt = datetime(2023, 1, 1, 12, 0, 0)
    with patch('utils.date_utils.select_best_date_from_common_date_to_2_files', return_value=(dt, dt, 'EXIF')):
        result = heic_service.analyze(validate_dates=True)
        
        assert len(result.duplicate_pairs) == 1
        assert len(result.rejected_pairs) == 0
        assert result.duplicate_pairs[0].date_source == 'EXIF'
        assert result.duplicate_pairs[0].date_difference == 0.0

    # Test case 2: Dates differ by > 5s
    dt_heic = datetime(2023, 1, 1, 12, 0, 0)
    dt_jpg = datetime(2023, 1, 1, 12, 0, 10)
    with patch('utils.date_utils.select_best_date_from_common_date_to_2_files', return_value=(dt_heic, dt_jpg, 'EXIF')):
        result = heic_service.analyze(validate_dates=True)
        
        assert len(result.duplicate_pairs) == 0
        assert len(result.rejected_pairs) == 1
        assert result.rejected_pairs[0].date_difference == 10.0
        assert result.rejected_pairs[0].date_source == 'EXIF'

    # Test case 3: No common date
    with patch('utils.date_utils.select_best_date_from_common_date_to_2_files', return_value=None):
        result = heic_service.analyze(validate_dates=True)
        
        assert len(result.duplicate_pairs) == 0
        assert len(result.rejected_pairs) == 1
        assert result.rejected_pairs[0].date_source is None
