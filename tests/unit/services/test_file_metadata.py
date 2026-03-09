# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests exhaustivos para services/file_metadata.py

Cobertura completa del modelo FileMetadata: campos requeridos, opcionales,
propiedades calculadas, serialización/deserialización, y resumen para logging.
"""

import pytest
from pathlib import Path
from datetime import datetime

from services.file_metadata import FileMetadata


def _make_metadata(**kwargs):
    """Helper para crear FileMetadata con valores mínimos requeridos."""
    defaults = {
        'path': Path('/tmp/test.jpg'),
        'fs_size': 1024,
        'fs_ctime': 1700000000.0,
        'fs_mtime': 1700000000.0,
        'fs_atime': 1700000000.0,
    }
    defaults.update(kwargs)
    return FileMetadata(**defaults)


# =============================================================================
# CREATION & REQUIRED FIELDS
# =============================================================================

class TestFileMetadataCreation:
    """Tests de creación e inicialización de FileMetadata."""

    def test_create_with_required_fields(self):
        meta = _make_metadata()
        assert meta.path == Path('/tmp/test.jpg')
        assert meta.fs_size == 1024
        assert meta.fs_ctime == 1700000000.0
        assert meta.fs_mtime == 1700000000.0
        assert meta.fs_atime == 1700000000.0

    def test_optional_fields_default_to_none(self):
        meta = _make_metadata()
        assert meta.sha256 is None
        assert meta.best_date is None
        assert meta.best_date_source is None
        assert meta.exif_ImageWidth is None
        assert meta.exif_ImageLength is None
        assert meta.exif_DateTime is None
        assert meta.exif_DateTimeOriginal is None
        assert meta.exif_DateTimeDigitized is None
        assert meta.exif_ExifVersion is None
        assert meta.exif_SubSecTimeOriginal is None
        assert meta.exif_OffsetTimeOriginal is None
        assert meta.exif_Software is None
        assert meta.exif_VideoDurationSeconds is None
        assert meta.exif_GPSDateStamp is None
        assert meta.exif_GPSTimeStamp is None

    def test_create_with_hash(self):
        meta = _make_metadata(sha256='abc123')
        assert meta.sha256 == 'abc123'

    def test_create_with_best_date(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        meta = _make_metadata(best_date=dt, best_date_source='EXIF DateTimeOriginal')
        assert meta.best_date == dt
        assert meta.best_date_source == 'EXIF DateTimeOriginal'

    def test_create_with_exif_fields(self):
        meta = _make_metadata(
            exif_ImageWidth=4000,
            exif_ImageLength=3000,
            exif_DateTime='2024:01:15 10:30:00',
            exif_Software='GIMP 2.10',
        )
        assert meta.exif_ImageWidth == 4000
        assert meta.exif_ImageLength == 3000
        assert meta.exif_DateTime == '2024:01:15 10:30:00'
        assert meta.exif_Software == 'GIMP 2.10'


# =============================================================================
# PROPERTIES
# =============================================================================

class TestFileMetadataProperties:
    """Tests de propiedades calculadas de FileMetadata."""

    def test_extension_jpg(self):
        meta = _make_metadata(path=Path('/tmp/photo.JPG'))
        assert meta.extension == '.jpg'

    def test_extension_png(self):
        meta = _make_metadata(path=Path('/tmp/image.png'))
        assert meta.extension == '.png'

    def test_extension_heic(self):
        meta = _make_metadata(path=Path('/tmp/photo.HEIC'))
        assert meta.extension == '.heic'

    def test_extension_mp4(self):
        meta = _make_metadata(path=Path('/tmp/video.MP4'))
        assert meta.extension == '.mp4'

    def test_has_exif_false_when_no_exif(self):
        meta = _make_metadata()
        assert meta.has_exif is False

    def test_has_exif_true_with_datetime(self):
        meta = _make_metadata(exif_DateTime='2024:01:15 10:30:00')
        assert meta.has_exif is True

    def test_has_exif_true_with_image_width(self):
        meta = _make_metadata(exif_ImageWidth=4000)
        assert meta.has_exif is True

    def test_has_exif_true_with_video_duration(self):
        meta = _make_metadata(exif_VideoDurationSeconds=3.5)
        assert meta.has_exif is True

    def test_has_exif_true_with_software(self):
        meta = _make_metadata(exif_Software='Photoshop')
        assert meta.has_exif is True

    def test_has_exif_true_with_gps(self):
        meta = _make_metadata(exif_GPSDateStamp='2024:01:15')
        assert meta.has_exif is True

    def test_has_hash_false(self):
        meta = _make_metadata()
        assert meta.has_hash is False

    def test_has_hash_true(self):
        meta = _make_metadata(sha256='abc')
        assert meta.has_hash is True

    def test_has_best_date_false(self):
        meta = _make_metadata()
        assert meta.has_best_date is False

    def test_has_best_date_true(self):
        meta = _make_metadata(best_date=datetime.now())
        assert meta.has_best_date is True

    def test_is_image_jpg(self):
        meta = _make_metadata(path=Path('/tmp/photo.jpg'))
        assert meta.is_image is True

    def test_is_image_png(self):
        meta = _make_metadata(path=Path('/tmp/photo.png'))
        assert meta.is_image is True

    def test_is_image_heic(self):
        meta = _make_metadata(path=Path('/tmp/photo.heic'))
        assert meta.is_image is True

    def test_is_video_mp4(self):
        meta = _make_metadata(path=Path('/tmp/video.mp4'))
        assert meta.is_video is True

    def test_is_video_mov(self):
        meta = _make_metadata(path=Path('/tmp/video.mov'))
        assert meta.is_video is True

    def test_not_image_for_video(self):
        meta = _make_metadata(path=Path('/tmp/video.mp4'))
        assert meta.is_image is False

    def test_not_video_for_image(self):
        meta = _make_metadata(path=Path('/tmp/photo.jpg'))
        assert meta.is_video is False

    def test_file_type_photo(self):
        meta = _make_metadata(path=Path('/tmp/photo.jpg'))
        assert meta.file_type == 'PHOTO'

    def test_file_type_video(self):
        meta = _make_metadata(path=Path('/tmp/video.mp4'))
        assert meta.file_type == 'VIDEO'

    def test_file_type_other(self):
        meta = _make_metadata(path=Path('/tmp/document.txt'))
        assert meta.file_type == 'OTHER'


# =============================================================================
# VIDEO DURATION FORMATTED
# =============================================================================

class TestVideoDurationFormatted:
    """Tests de la propiedad video_duration_formatted."""

    def test_none_when_no_duration(self):
        meta = _make_metadata()
        assert meta.video_duration_formatted is None

    def test_short_duration_with_decimal(self):
        meta = _make_metadata(exif_VideoDurationSeconds=1.5)
        assert meta.video_duration_formatted == "1.5 seg"

    def test_very_short_duration(self):
        meta = _make_metadata(exif_VideoDurationSeconds=0.3)
        assert meta.video_duration_formatted == "0.3 seg"

    def test_medium_duration_no_decimal(self):
        meta = _make_metadata(exif_VideoDurationSeconds=45.0)
        assert meta.video_duration_formatted == "45 seg"

    def test_duration_exactly_10(self):
        meta = _make_metadata(exif_VideoDurationSeconds=10.0)
        assert meta.video_duration_formatted == "10 seg"

    def test_long_duration_minutes(self):
        meta = _make_metadata(exif_VideoDurationSeconds=90.0)
        assert meta.video_duration_formatted == "1:30 min"

    def test_duration_exactly_60(self):
        meta = _make_metadata(exif_VideoDurationSeconds=60.0)
        assert meta.video_duration_formatted == "1:00 min"

    def test_duration_boundary_9_9(self):
        meta = _make_metadata(exif_VideoDurationSeconds=9.9)
        assert "seg" in meta.video_duration_formatted


# =============================================================================
# EXIF DATES
# =============================================================================

class TestGetExifDates:
    """Tests de get_exif_dates()."""

    def test_empty_when_no_exif(self):
        meta = _make_metadata()
        assert meta.get_exif_dates() == {}

    def test_returns_datetime(self):
        meta = _make_metadata(exif_DateTime='2024:01:15 10:30:00')
        dates = meta.get_exif_dates()
        assert 'DateTime' in dates
        assert dates['DateTime'] == '2024:01:15 10:30:00'

    def test_returns_datetime_original(self):
        meta = _make_metadata(exif_DateTimeOriginal='2024:01:15 10:30:00')
        dates = meta.get_exif_dates()
        assert 'DateTimeOriginal' in dates

    def test_returns_datetime_digitized(self):
        meta = _make_metadata(exif_DateTimeDigitized='2024:01:15 10:30:00')
        dates = meta.get_exif_dates()
        assert 'DateTimeDigitized' in dates

    def test_returns_gps_datestamp(self):
        meta = _make_metadata(exif_GPSDateStamp='2024:01:15')
        dates = meta.get_exif_dates()
        assert 'GPSDateStamp' in dates

    def test_returns_gps_timestamp(self):
        meta = _make_metadata(exif_GPSTimeStamp='10:30:00')
        dates = meta.get_exif_dates()
        assert 'GPSTimeStamp' in dates

    def test_returns_multiple_dates(self):
        meta = _make_metadata(
            exif_DateTime='2024:01:15 10:30:00',
            exif_DateTimeOriginal='2024:01:15 10:30:01',
        )
        dates = meta.get_exif_dates()
        assert len(dates) == 2


# =============================================================================
# SERIALIZATION (to_dict / from_dict)
# =============================================================================

class TestSerialization:
    """Tests de serialización y deserialización."""

    def test_to_dict_returns_dict(self):
        meta = _make_metadata()
        result = meta.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_has_required_keys(self):
        meta = _make_metadata()
        d = meta.to_dict()
        assert 'path' in d
        assert 'fs_size' in d
        assert 'fs_ctime' in d
        assert 'fs_mtime' in d
        assert 'fs_atime' in d

    def test_to_dict_path_is_string(self):
        meta = _make_metadata()
        d = meta.to_dict()
        assert isinstance(d['path'], str)

    def test_to_dict_best_date_iso_format(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        meta = _make_metadata(best_date=dt)
        d = meta.to_dict()
        assert d['best_date'] == '2024-01-15T10:30:00'

    def test_to_dict_best_date_none(self):
        meta = _make_metadata()
        d = meta.to_dict()
        assert d['best_date'] is None

    def test_from_dict_basic(self):
        data = {
            'path': '/tmp/test.jpg',
            'fs_size': 1024,
            'fs_ctime': 1700000000.0,
            'fs_mtime': 1700000000.0,
            'fs_atime': 1700000000.0,
        }
        meta = FileMetadata.from_dict(data)
        assert meta.path == Path('/tmp/test.jpg')
        assert meta.fs_size == 1024

    def test_from_dict_with_hash(self):
        data = {
            'path': '/tmp/test.jpg',
            'fs_size': 1024,
            'fs_ctime': 1700000000.0,
            'fs_mtime': 1700000000.0,
            'fs_atime': 1700000000.0,
            'sha256': 'abc123',
        }
        meta = FileMetadata.from_dict(data)
        assert meta.sha256 == 'abc123'

    def test_from_dict_with_best_date(self):
        data = {
            'path': '/tmp/test.jpg',
            'fs_size': 1024,
            'fs_ctime': 1700000000.0,
            'fs_mtime': 1700000000.0,
            'fs_atime': 1700000000.0,
            'best_date': '2024-01-15T10:30:00',
            'best_date_source': 'EXIF DateTimeOriginal',
        }
        meta = FileMetadata.from_dict(data)
        assert meta.best_date == datetime(2024, 1, 15, 10, 30, 0)
        assert meta.best_date_source == 'EXIF DateTimeOriginal'

    def test_from_dict_with_invalid_date(self):
        data = {
            'path': '/tmp/test.jpg',
            'fs_size': 1024,
            'fs_ctime': 1700000000.0,
            'fs_mtime': 1700000000.0,
            'fs_atime': 1700000000.0,
            'best_date': 'not-a-date',
        }
        meta = FileMetadata.from_dict(data)
        assert meta.best_date is None

    def test_roundtrip_serialization(self):
        """to_dict() -> from_dict() preserva los datos."""
        original = _make_metadata(
            sha256='deadbeef',
            best_date=datetime(2024, 6, 15, 12, 0, 0),
            best_date_source='mtime',
            exif_ImageWidth=4000,
            exif_Software='GIMP',
        )
        d = original.to_dict()
        restored = FileMetadata.from_dict(d)
        assert restored.path == original.path
        assert restored.fs_size == original.fs_size
        assert restored.sha256 == original.sha256
        assert restored.best_date == original.best_date
        assert restored.best_date_source == original.best_date_source
        assert restored.exif_ImageWidth == original.exif_ImageWidth
        assert restored.exif_Software == original.exif_Software


# =============================================================================
# GET SUMMARY
# =============================================================================

class TestGetSummary:
    """Tests de get_summary()."""

    def test_summary_returns_string(self):
        meta = _make_metadata()
        assert isinstance(meta.get_summary(), str)

    def test_summary_contains_filename(self):
        meta = _make_metadata(path=Path('/tmp/photo.jpg'))
        assert 'photo.jpg' in meta.get_summary()

    def test_summary_contains_size(self):
        meta = _make_metadata(fs_size=2048)
        assert '2048' in meta.get_summary()

    def test_summary_verbose_mode(self):
        meta = _make_metadata(exif_ImageWidth=4000)
        verbose = meta.get_summary(verbose=True)
        assert 'ImageWidth=4000' in verbose

    def test_summary_non_verbose_mode(self):
        meta = _make_metadata(exif_DateTime='2024:01:15')
        normal = meta.get_summary(verbose=False)
        assert 'exif_dates=' in normal

    def test_summary_with_hash(self):
        meta = _make_metadata(sha256='abcdef1234567890')
        summary = meta.get_summary()
        assert 'abcdef12' in summary  # First 8 chars

    def test_summary_without_hash(self):
        meta = _make_metadata()
        summary = meta.get_summary()
        assert 'pending' in summary

    def test_summary_with_best_date(self):
        meta = _make_metadata(best_date=datetime(2024, 1, 15), best_date_source='EXIF')
        summary = meta.get_summary()
        assert '2024-01-15' in summary
        assert 'EXIF' in summary

    def test_summary_without_best_date(self):
        meta = _make_metadata()
        summary = meta.get_summary()
        assert 'best_date=pending' in summary

    def test_summary_with_no_exif(self):
        meta = _make_metadata()
        summary = meta.get_summary()
        assert 'exif=none' in summary
