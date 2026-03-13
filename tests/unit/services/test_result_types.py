# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests exhaustivos para services/result_types.py

Cobertura de todos los dataclasses de resultado: BaseResult, AnalysisResult,
ExecutionResult, y todos los tipos específicos de cada servicio.
"""

import pytest
from pathlib import Path
from datetime import datetime
from dataclasses import fields

from services.result_types import (
    BaseResult,
    AnalysisResult,
    ExecutionResult,
    ZeroByteAnalysisResult,
    ZeroByteExecutionResult,
    HEICDuplicatePair,
    HeicAnalysisResult,
    HeicExecutionResult,
    LivePhotoImageInfo,
    LivePhotoGroup,
    LivePhotosAnalysisResult,
    LivePhotosExecutionResult,
    VisualIdenticalGroup,
    VisualIdenticalAnalysisResult,
    VisualIdenticalExecutionResult,
    ExactDuplicateGroup,
    ExactDuplicateAnalysisResult,
    ExactDuplicateExecutionResult,
    SimilarDuplicateGroup,
    SimilarDuplicateAnalysisResult,
    SimilarDuplicateExecutionResult,
    OrganizationAnalysisResult,
    OrganizationExecutionResult,
    RenamePlanItem,
    RenamedFileItem,
    RenameAnalysisResult,
    RenameExecutionResult,
    DirectoryScanResult,
    ScanSnapshot,
)


# =============================================================================
# BASE RESULT
# =============================================================================

class TestBaseResult:
    """Tests de BaseResult."""

    def test_default_success(self):
        result = BaseResult()
        assert result.success is True

    def test_default_errors_empty(self):
        result = BaseResult()
        assert result.errors == []

    def test_default_message_none(self):
        result = BaseResult()
        assert result.message is None

    def test_add_error(self):
        result = BaseResult()
        result.add_error("test error")
        assert len(result.errors) == 1
        assert "test error" in result.errors

    def test_add_error_sets_success_false(self):
        result = BaseResult()
        result.add_error("failure")
        assert result.success is False

    def test_multiple_errors(self):
        result = BaseResult()
        result.add_error("error1")
        result.add_error("error2")
        assert len(result.errors) == 2

    def test_custom_message(self):
        result = BaseResult(message="done")
        assert result.message == "done"


# =============================================================================
# ANALYSIS RESULT
# =============================================================================

class TestAnalysisResult:
    """Tests de AnalysisResult."""

    def test_inherits_base_result(self):
        result = AnalysisResult()
        assert isinstance(result, BaseResult)

    def test_default_items_count(self):
        assert AnalysisResult().items_count == 0

    def test_default_bytes_total(self):
        assert AnalysisResult().bytes_total == 0

    def test_default_data_none(self):
        assert AnalysisResult().data is None

    def test_custom_values(self):
        result = AnalysisResult(items_count=10, bytes_total=4096, data="payload")
        assert result.items_count == 10
        assert result.bytes_total == 4096
        assert result.data == "payload"


# =============================================================================
# EXECUTION RESULT
# =============================================================================

class TestExecutionResult:
    """Tests de ExecutionResult."""

    def test_inherits_base_result(self):
        result = ExecutionResult()
        assert isinstance(result, BaseResult)

    def test_default_items_processed(self):
        assert ExecutionResult().items_processed == 0

    def test_default_bytes_processed(self):
        assert ExecutionResult().bytes_processed == 0

    def test_default_files_affected_empty(self):
        assert ExecutionResult().files_affected == []

    def test_default_backup_path_none(self):
        assert ExecutionResult().backup_path is None

    def test_default_dry_run_false(self):
        assert ExecutionResult().dry_run is False

    def test_dry_run_true(self):
        result = ExecutionResult(dry_run=True)
        assert result.dry_run is True


# =============================================================================
# ZERO BYTE
# =============================================================================

class TestZeroByteResults:
    """Tests de resultados Zero Byte."""

    def test_analysis_default_files_empty(self):
        result = ZeroByteAnalysisResult()
        assert result.files == []

    def test_analysis_inherits_analysis_result(self):
        assert isinstance(ZeroByteAnalysisResult(), AnalysisResult)

    def test_analysis_post_init_counts_files(self):
        files = [Path('/tmp/a'), Path('/tmp/b')]
        result = ZeroByteAnalysisResult(files=files)
        assert result.items_count == 2

    def test_analysis_post_init_skips_if_items_count_set(self):
        files = [Path('/tmp/a')]
        result = ZeroByteAnalysisResult(files=files, items_count=5)
        assert result.items_count == 5

    def test_execution_inherits_execution_result(self):
        assert isinstance(ZeroByteExecutionResult(), ExecutionResult)


# =============================================================================
# HEIC
# =============================================================================

class TestHEICResults:
    """Tests de resultados HEIC."""

    def test_heic_pair_total_size(self):
        pair = HEICDuplicatePair(
            heic_path=Path('/tmp/a.heic'),
            jpg_path=Path('/tmp/a.jpg'),
            base_name='a',
            heic_size=5000,
            jpg_size=3000,
            directory=Path('/tmp'),
        )
        assert pair.total_size == 8000

    def test_heic_pair_optional_dates(self):
        pair = HEICDuplicatePair(
            heic_path=Path('/tmp/a.heic'),
            jpg_path=Path('/tmp/a.jpg'),
            base_name='a',
            heic_size=100,
            jpg_size=100,
            directory=Path('/tmp'),
        )
        assert pair.heic_date is None
        assert pair.jpg_date is None

    def test_heic_analysis_post_init(self):
        pair = HEICDuplicatePair(
            heic_path=Path('/tmp/a.heic'),
            jpg_path=Path('/tmp/a.jpg'),
            base_name='a',
            heic_size=5000,
            jpg_size=3000,
            directory=Path('/tmp'),
        )
        result = HeicAnalysisResult(duplicate_pairs=[pair])
        assert result.items_count == 1
        assert result.bytes_total == 8000

    def test_heic_execution_format_kept(self):
        result = HeicExecutionResult(format_kept='jpg')
        assert result.format_kept == 'jpg'


# =============================================================================
# LIVE PHOTOS
# =============================================================================

class TestLivePhotoResults:
    """Tests de resultados Live Photos."""

    def test_live_photo_image_info(self):
        info = LivePhotoImageInfo(path=Path('/tmp/img.heic'), size=4096)
        assert info.path == Path('/tmp/img.heic')
        assert info.size == 4096
        assert info.date is None

    def test_live_photo_group_total_size(self):
        images = [
            LivePhotoImageInfo(path=Path('/tmp/a.heic'), size=4000),
            LivePhotoImageInfo(path=Path('/tmp/b.heic'), size=3000),
        ]
        group = LivePhotoGroup(
            video_path=Path('/tmp/a.mov'),
            video_size=2000,
            images=images,
        )
        assert group.total_size == 9000

    def test_live_photo_group_images_size(self):
        images = [LivePhotoImageInfo(path=Path('/tmp/a.heic'), size=4000)]
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=2000, images=images)
        assert group.images_size == 4000

    def test_live_photo_group_image_count(self):
        images = [
            LivePhotoImageInfo(path=Path('/tmp/a.heic'), size=100),
            LivePhotoImageInfo(path=Path('/tmp/b.heic'), size=100),
        ]
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=100, images=images)
        assert group.image_count == 2

    def test_live_photo_group_primary_image(self):
        img = LivePhotoImageInfo(path=Path('/tmp/first.heic'), size=100)
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=100, images=[img])
        assert group.primary_image == img

    def test_live_photo_group_primary_image_none(self):
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=100)
        assert group.primary_image is None

    def test_live_photo_group_best_date_from_video(self):
        dt = datetime(2024, 1, 15)
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=100, video_date=dt)
        assert group.best_date == dt

    def test_live_photo_group_best_date_from_image(self):
        dt = datetime(2024, 1, 15)
        img = LivePhotoImageInfo(path=Path('/tmp/a.heic'), size=100, date=dt)
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=100, images=[img])
        assert group.best_date == dt

    def test_live_photo_group_best_date_none(self):
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=100)
        assert group.best_date is None

    def test_live_photos_analysis_potential_savings(self):
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=5000)
        result = LivePhotosAnalysisResult(groups=[group])
        assert result.potential_savings == 5000

    def test_live_photos_analysis_total_images(self):
        img = LivePhotoImageInfo(path=Path('/tmp/a.heic'), size=100)
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=100, images=[img])
        result = LivePhotosAnalysisResult(groups=[group])
        assert result.total_images == 1

    def test_live_photos_analysis_total_videos(self):
        group = LivePhotoGroup(video_path=Path('/tmp/a.mov'), video_size=100)
        result = LivePhotosAnalysisResult(groups=[group, group])
        assert result.total_videos == 2

    def test_live_photos_execution_videos_deleted(self):
        result = LivePhotosExecutionResult(videos_deleted=3)
        assert result.videos_deleted == 3


# =============================================================================
# VISUAL IDENTICAL
# =============================================================================

class TestVisualIdenticalResults:
    """Tests de resultados Visual Identical."""

    def test_group_file_count(self):
        group = VisualIdenticalGroup(
            hash_value='abc',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
        )
        assert group.file_count == 2

    def test_group_largest_file(self):
        group = VisualIdenticalGroup(
            hash_value='abc',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_sizes=[1000, 2000],
        )
        assert group.largest_file == Path('/tmp/b.jpg')

    def test_group_smallest_file(self):
        group = VisualIdenticalGroup(
            hash_value='abc',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_sizes=[1000, 2000],
        )
        assert group.smallest_file == Path('/tmp/a.jpg')

    def test_group_largest_file_no_sizes(self):
        group = VisualIdenticalGroup(
            hash_value='abc',
            files=[Path('/tmp/a.jpg')],
        )
        assert group.largest_file == Path('/tmp/a.jpg')

    def test_analysis_post_init(self):
        group = VisualIdenticalGroup(hash_value='abc', files=[Path('/tmp/a.jpg')])
        result = VisualIdenticalAnalysisResult(groups=[group])
        assert result.items_count == 1
        assert result.total_groups == 1


# =============================================================================
# EXACT DUPLICATES
# =============================================================================

class TestExactDuplicateResults:
    """Tests de resultados Exact Duplicates."""

    def test_group_file_count(self):
        group = ExactDuplicateGroup(
            hash_value='sha256',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_size=1000,
        )
        assert group.file_count == 2

    def test_group_total_size(self):
        group = ExactDuplicateGroup(
            hash_value='sha256',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_size=1000,
        )
        assert group.total_size == 2000

    def test_group_space_recoverable(self):
        group = ExactDuplicateGroup(
            hash_value='sha256',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg'), Path('/tmp/c.jpg')],
            file_size=1000,
        )
        assert group.space_recoverable == 2000  # 3 files - 1 keep = 2 * 1000

    def test_group_space_recoverable_single_file(self):
        group = ExactDuplicateGroup(
            hash_value='sha256',
            files=[Path('/tmp/a.jpg')],
            file_size=1000,
        )
        assert group.space_recoverable == 0

    def test_analysis_post_init(self):
        group = ExactDuplicateGroup(hash_value='s', files=[Path('/tmp/a.jpg')])
        result = ExactDuplicateAnalysisResult(groups=[group])
        assert result.items_count == 1
        assert result.total_groups == 1

    def test_execution_keep_strategy(self):
        result = ExactDuplicateExecutionResult(keep_strategy='oldest')
        assert result.keep_strategy == 'oldest'


# =============================================================================
# SIMILAR DUPLICATES
# =============================================================================

class TestSimilarDuplicateResults:
    """Tests de resultados Similar Duplicates."""

    def test_group_file_count(self):
        group = SimilarDuplicateGroup(
            hash_value='phash',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_sizes=[1000, 2000],
        )
        assert group.file_count == 2

    def test_group_total_size(self):
        group = SimilarDuplicateGroup(
            hash_value='phash',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_sizes=[1000, 2000],
        )
        assert group.total_size == 3000

    def test_group_space_recoverable(self):
        group = SimilarDuplicateGroup(
            hash_value='phash',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_sizes=[1000, 2000],
        )
        assert group.space_recoverable == 1000  # 3000 - 2000

    def test_group_space_recoverable_single_file(self):
        group = SimilarDuplicateGroup(
            hash_value='phash',
            files=[Path('/tmp/a.jpg')],
            file_sizes=[1000],
        )
        assert group.space_recoverable == 0

    def test_group_largest_file(self):
        group = SimilarDuplicateGroup(
            hash_value='phash',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_sizes=[1000, 3000],
        )
        assert group.largest_file == Path('/tmp/b.jpg')

    def test_group_size_variation_percent(self):
        group = SimilarDuplicateGroup(
            hash_value='phash',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_sizes=[1000, 2000],
        )
        assert group.size_variation_percent == 100.0  # (2000-1000)/1000 * 100

    def test_group_size_variation_zero_size(self):
        group = SimilarDuplicateGroup(
            hash_value='phash',
            files=[Path('/tmp/a.jpg'), Path('/tmp/b.jpg')],
            file_sizes=[0, 1000],
        )
        assert group.size_variation_percent == 0.0

    def test_analysis_sensitivity(self):
        result = SimilarDuplicateAnalysisResult(sensitivity=90)
        assert result.sensitivity == 90


# =============================================================================
# ORGANIZATION
# =============================================================================

class TestOrganizationResults:
    """Tests de resultados Organization."""

    def test_analysis_defaults(self):
        result = OrganizationAnalysisResult()
        assert result.move_plan == []
        assert result.root_directory == ''
        assert result.organization_type == 'to_root'
        assert result.group_by_source is False
        assert result.group_by_type is False

    def test_analysis_files_to_move(self):
        result = OrganizationAnalysisResult()
        assert result.files_to_move == 0

    def test_execution_defaults(self):
        result = OrganizationExecutionResult()
        assert result.empty_directories_removed == 0
        assert result.moved_files == []
        assert result.folders_created == []


# =============================================================================
# RENAME
# =============================================================================

class TestRenameResults:
    """Tests de resultados Rename."""

    def test_plan_item(self):
        item = RenamePlanItem(
            original_path=Path('/tmp/photo.jpg'),
            new_name='20240115_103000_IMG.jpg',
            date=datetime(2024, 1, 15, 10, 30),
            date_source='EXIF',
        )
        assert item.has_conflict is False
        assert item.sequence is None

    def test_plan_item_with_conflict(self):
        item = RenamePlanItem(
            original_path=Path('/tmp/photo.jpg'),
            new_name='20240115_103000_IMG.jpg',
            date=datetime(2024, 1, 15, 10, 30),
            date_source='EXIF',
            has_conflict=True,
            sequence=2,
        )
        assert item.has_conflict is True
        assert item.sequence == 2

    def test_renamed_file_item(self):
        item = RenamedFileItem(
            original='photo.jpg',
            new_name='20240115_103000_IMG.jpg',
            date='2024-01-15',
        )
        assert item.had_conflict is False

    def test_analysis_need_renaming(self):
        items = [
            RenamePlanItem(
                original_path=Path('/tmp/a.jpg'),
                new_name='new.jpg',
                date=datetime.now(),
                date_source='EXIF',
            )
        ]
        result = RenameAnalysisResult(renaming_plan=items)
        assert result.need_renaming == 1

    def test_analysis_cannot_process(self):
        result = RenameAnalysisResult(issues=['bad file 1', 'bad file 2'])
        assert result.cannot_process == 2

    def test_execution_files_renamed_alias(self):
        result = RenameExecutionResult(items_processed=5)
        assert result.files_renamed == 5


# =============================================================================
# DIRECTORY SCAN
# =============================================================================

class TestDirectoryScanResult:
    """Tests de DirectoryScanResult."""

    def test_creation(self):
        result = DirectoryScanResult(total_files=10)
        assert result.total_files == 10
        assert result.images == []
        assert result.videos == []
        assert result.others == []

    def test_image_count(self):
        result = DirectoryScanResult(
            total_files=3,
            images=[Path('/tmp/a.jpg'), Path('/tmp/b.png')],
        )
        assert result.image_count == 2

    def test_video_count(self):
        result = DirectoryScanResult(
            total_files=2,
            videos=[Path('/tmp/a.mp4')],
        )
        assert result.video_count == 1

    def test_other_count(self):
        result = DirectoryScanResult(
            total_files=1,
            others=[Path('/tmp/a.txt')],
        )
        assert result.other_count == 1


# =============================================================================
# SCAN SNAPSHOT
# =============================================================================

class TestScanSnapshot:
    """Tests de ScanSnapshot."""

    def test_creation(self):
        scan = DirectoryScanResult(total_files=5)
        snapshot = ScanSnapshot(directory=Path('/tmp/test'), scan=scan)
        assert snapshot.directory == Path('/tmp/test')
        assert snapshot.scan.total_files == 5

    def test_optional_results_default_none(self):
        scan = DirectoryScanResult(total_files=0)
        snapshot = ScanSnapshot(directory=Path('/tmp'), scan=scan)
        assert snapshot.live_photos is None
        assert snapshot.heic is None
        assert snapshot.duplicates is None
        assert snapshot.duplicates_similar is None
        assert snapshot.visual_identical is None
        assert snapshot.zero_byte is None
        assert snapshot.organization is None
        assert snapshot.renaming is None
