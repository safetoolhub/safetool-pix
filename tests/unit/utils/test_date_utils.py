# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests unitarios para utils/date_utils.py

Tests exhaustivos de las funciones de extracción y selección de fechas,
con especial atención a casos edge, fechas None y datos corruptos.
"""
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from utils.date_utils import (
    select_best_date_from_common_date_to_2_files,
    select_best_date_from_file,
    format_renamed_name,
    is_renamed_filename,
    get_all_metadata_from_file,
    _validate_date_coherence,
    DateCoherenceResult,
)
from services.file_metadata import FileMetadata
from utils.file_utils import (
    get_exif_from_image,
    get_exif_from_video
)
from config import Config


def _create_test_metadata(
    path: Path = None,
    fs_size: int = 1000,
    fs_ctime: float = 0.0,
    fs_mtime: float = 0.0,
    fs_atime: float = 0.0,
    exif_date_time_original: str = None,
    exif_date_time: str = None,
    exif_date_time_digitized: str = None,
    exif_offset_time_original: str = None,
    exif_gps_date_stamp: str = None,
    exif_software: str = None,
) -> FileMetadata:
    """Helper para crear FileMetadata para tests.
    
    Por defecto todos los timestamps son 0.0 (sin fecha).
    Para tests que necesitan fechas filesystem, pasar explícitamente:
        fs_ctime=datetime(...).timestamp()
    
    Nota: Los parámetros usan snake_case por conveniencia, pero se mapean
    a los nombres camelCase reales de FileMetadata.
    """
    return FileMetadata(
        path=path or Path('/test/file.jpg'),
        fs_size=fs_size,
        fs_ctime=fs_ctime,
        fs_mtime=fs_mtime,
        fs_atime=fs_atime,
        exif_DateTimeOriginal=exif_date_time_original,
        exif_DateTime=exif_date_time,
        exif_DateTimeDigitized=exif_date_time_digitized,
        exif_OffsetTimeOriginal=exif_offset_time_original,
        exif_GPSDateStamp=exif_gps_date_stamp,
        exif_Software=exif_software,
    )



@pytest.mark.unit
class TestSelectEarliestDate:
    """Tests para la lógica de priorización de fechas con FileMetadata"""
    
    def test_all_exif_dates_available_returns_earliest(self):
        """Debe devolver la fecha EXIF más antigua cuando todas están disponibles"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:01:15 10:30:00',  # Más antigua
            exif_date_time='2023:01:15 10:31:00',
            exif_date_time_digitized='2023:01:15 10:32:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 1, 15, 10, 30)
        assert result_source == 'EXIF DateTimeOriginal'
    
    def test_only_exif_create_date_available(self):
        """Debe devolver CreateDate cuando es la única fecha EXIF"""
        metadata = _create_test_metadata(
            exif_date_time='2023:03:20 14:45:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 3, 20, 14, 45)
        assert result_source == 'EXIF CreateDate'

    def test_gps_date_has_highest_priority(self):
        """EXIF DateTimeOriginal tiene prioridad sobre GPS DateStamp"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:01:15 10:31:00',
            exif_date_time='2023:01:15 10:32:00',
            exif_gps_date_stamp='2023:01:15 10:30:00',
        )

        result_date, result_source = select_best_date_from_file(metadata)

        # GPS ya no tiene prioridad máxima, se selecciona DateTimeOriginal
        assert result_date == datetime(2023, 1, 15, 10, 31)
        assert result_source == 'EXIF DateTimeOriginal'

    def test_datetimeoriginal_with_offset_has_higher_priority(self):
        """DateTimeOriginal con OffsetTimeOriginal debe preferirse y mostrar tz en la fuente"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:06:01 09:00:00',
            exif_offset_time_original='+02:00',
        )

        result_date, result_source = select_best_date_from_file(metadata)

        assert result_date == datetime(2023, 6, 1, 9, 0)
        assert 'OffsetTime' in result_source or '+02:00' in result_source

    def test_filename_used_when_no_exif(self):
        """Si no hay EXIF, usar fecha del nombre de archivo"""
        # Archivo tipo WhatsApp con fecha en nombre
        metadata = _create_test_metadata(
            path=Path('/test/IMG-20241113-WA0001.jpg'),
        )

        result_date, result_source = select_best_date_from_file(metadata)

        # Debe usar la fecha del nombre de archivo
        assert result_date == datetime(2024, 11, 13, 0, 0)
        assert result_source == 'Filename'

    def test_video_metadata_used_when_is_video(self):
        """Si es video, usar exif_date_time como Video Metadata"""
        # Para videos, exif_date_time contiene la fecha del video
        metadata = _create_test_metadata(
            path=Path('/test/video.mp4'),  # Extensión de video
            exif_date_time='2024:01:15 14:30:00',
        )

        result_date, result_source = select_best_date_from_file(metadata)

        # Para videos, exif_date_time se usa como EXIF CreateDate o Video Metadata
        assert result_date == datetime(2024, 1, 15, 14, 30)
    
    def test_only_exif_date_digitized_available(self):
        """Debe devolver DateTimeDigitized cuando es la única fecha EXIF"""
        metadata = _create_test_metadata(
            exif_date_time_digitized='2023:05:10 09:00:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 5, 10, 9, 0)
        assert result_source == 'EXIF DateTimeDigitized'
    
    def test_exif_date_original_has_priority_over_digitized(self):
        """DateTimeOriginal tiene prioridad estricta sobre DateTimeDigitized"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:05:20 10:30:00',  # Primera prioridad
            exif_date_time='2023:05:20 10:35:00',
            exif_date_time_digitized='2023:05:15 08:00:00',  # Más antigua, pero menor prioridad
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Se selecciona DateTimeOriginal por prioridad estricta, no la más antigua
        assert result_date == datetime(2023, 5, 20, 10, 30)
        assert result_source == 'EXIF DateTimeOriginal'
    
    def test_epoch_zero_exif_dates_are_ignored(self):
        """Fechas EXIF de epoch 0 (1970-01-01 00:00:00) deben ignorarse y usar siguiente prioridad"""
        metadata = _create_test_metadata(
            exif_date_time_original='1970:01:01 00:00:00',  # Epoch zero - debe ignorarse
            exif_date_time='1970:01:01 00:00:00',  # Epoch zero - debe ignorarse
            exif_date_time_digitized='1970:01:01 00:00:00',  # Epoch zero - debe ignorarse
            path=Path('/test/20230115_103045_VIDEO.mp4'),  # Fecha en nombre de archivo
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe usar la fecha del nombre de archivo ya que todas las EXIF son epoch zero
        assert result_date == datetime(2023, 1, 15, 10, 30, 45)
        assert result_source == 'Filename'
    
    def test_no_exif_uses_filesystem_dates(self):
        """Sin EXIF debe usar fechas del sistema de archivos"""
        metadata = _create_test_metadata(
            fs_ctime=datetime(2024, 1, 1, 12, 0).timestamp(),
            fs_mtime=datetime(2024, 1, 2, 14, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2024, 1, 1, 12, 0)
        # Source puede ser 'ctime' o 'birth' dependiendo de la plataforma
        assert result_source in ('ctime', 'birth')
    
    def test_no_exif_mtime_is_earliest(self):
        """Sin EXIF y mtime más antiguo debe devolver mtime"""
        metadata = _create_test_metadata(
            fs_ctime=datetime(2024, 1, 2, 14, 0).timestamp(),
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),  # Más antigua
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2024, 1, 1, 12, 0)
        assert result_source == 'mtime'
    
    def test_exif_priority_over_older_filesystem_dates(self):
        """EXIF debe tener prioridad incluso si fechas del sistema son más antiguas"""
        metadata = _create_test_metadata(
            exif_date_time='2023:06:15 10:00:00',  # EXIF más reciente
            fs_ctime=datetime(2020, 1, 1, 12, 0).timestamp(),  # Más antigua pero ignorada
            fs_mtime=datetime(2019, 6, 15, 8, 0).timestamp(),  # Más antigua pero ignorada
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe devolver EXIF CreateDate, no las fechas más antiguas del sistema
        assert result_date == datetime(2023, 6, 15, 10, 0)
        assert result_source == 'EXIF CreateDate'
    
    def test_no_dates_available(self):
        """Sin fechas disponibles debe devolver None, None"""
        metadata = _create_test_metadata()  # Sin fechas
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date is None
        assert result_source is None
    
    def test_only_modification_date_available(self):
        """Solo mtime disponible debe devolverlo"""
        metadata = _create_test_metadata(
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2024, 1, 1, 12, 0)
        assert result_source == 'mtime'
    
    def test_only_creation_date_available(self):
        """Solo creation_date disponible debe devolverlo"""
        metadata = _create_test_metadata(
            fs_ctime=datetime(2024, 1, 1, 12, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2024, 1, 1, 12, 0)
        # Source depende de la plataforma
        assert result_source in ('ctime', 'birth')


@pytest.mark.unit
class TestGetExifDates:
    """Tests para extracción de fechas EXIF"""
    
    def test_image_with_all_exif_dates(self):
        """Imagen con todas las fechas EXIF debe extraerlas correctamente"""
        mock_exif = {
            36867: '2023:01:15 10:30:00',  # DateTimeOriginal
            306: '2023:01:15 10:31:00',     # DateTime (CreateDate)
            36868: '2023:01:15 10:32:00'    # DateTimeDigitized
        }
        mock_image = MagicMock()
        mock_image.__enter__ = Mock(return_value=mock_image)
        mock_image.__exit__ = Mock(return_value=False)
        mock_image.getexif.return_value = mock_exif
        
        with patch('PIL.Image.open', return_value=mock_image), \
             patch('PIL.ExifTags.TAGS', {
                 36867: 'DateTimeOriginal',
                 306: 'DateTime',
                 36868: 'DateTimeDigitized'
             }):
            result = get_exif_from_image(Path('/fake/image.jpg'))
            
            assert result['DateTimeOriginal'] == datetime(2023, 1, 15, 10, 30, 0)
            assert result['CreateDate'] == datetime(2023, 1, 15, 10, 31, 0)
            assert result['DateTimeDigitized'] == datetime(2023, 1, 15, 10, 32, 0)
    
    def test_image_with_partial_exif_dates(self):
        """Imagen con algunas fechas EXIF debe extraer solo las disponibles"""
        mock_exif = {
            36867: '2023:01:15 10:30:00',  # Solo DateTimeOriginal
        }
        mock_image = MagicMock()
        mock_image.__enter__ = Mock(return_value=mock_image)
        mock_image.__exit__ = Mock(return_value=False)
        mock_image.getexif.return_value = mock_exif
        
        with patch('PIL.Image.open', return_value=mock_image), \
             patch('PIL.ExifTags.TAGS', {36867: 'DateTimeOriginal'}):
            result = get_exif_from_image(Path('/fake/image.jpg'))
            
            assert result['DateTimeOriginal'] == datetime(2023, 1, 15, 10, 30, 0)
            assert result['CreateDate'] is None
            assert result['DateTimeDigitized'] is None
    
    def test_image_with_corrupted_exif_date(self):
        """Fecha EXIF corrupta debe ser ignorada y devolver None"""
        mock_image = MagicMock()
        mock_image.__enter__ = Mock(return_value=mock_image)
        mock_image.__exit__ = Mock(return_value=False)
        mock_image._getexif.return_value = {
            36867: 'invalid-date-format',  # Formato inválido
        }
        
        with patch('PIL.Image.open', return_value=mock_image), \
             patch('PIL.ExifTags.TAGS', {36867: 'DateTimeOriginal'}):
            result = get_exif_from_image(Path('/fake/image.jpg'))
            
            assert result['DateTimeOriginal'] is None
            assert result['CreateDate'] is None
            assert result['DateTimeDigitized'] is None
    
    def test_image_with_mixed_valid_and_corrupted_dates(self):
        """Mezcla de fechas válidas y corruptas debe extraer solo las válidas"""
        mock_exif = {
            36867: '2023:01:15 10:30:00',  # Válida
            306: 'corrupted-date',          # Corrupta
            36868: '2023:01:15 10:32:00'   # Válida
        }
        mock_image = MagicMock()
        mock_image.__enter__ = Mock(return_value=mock_image)
        mock_image.__exit__ = Mock(return_value=False)
        mock_image.getexif.return_value = mock_exif
        
        with patch('PIL.Image.open', return_value=mock_image), \
             patch('PIL.ExifTags.TAGS', {
                 36867: 'DateTimeOriginal',
                 306: 'DateTime',
                 36868: 'DateTimeDigitized'
             }):
            result = get_exif_from_image(Path('/fake/image.jpg'))
            
            assert result['DateTimeOriginal'] == datetime(2023, 1, 15, 10, 30, 0)
            assert result['CreateDate'] is None  # Corrupta
            assert result['DateTimeDigitized'] == datetime(2023, 1, 15, 10, 32, 0)
    
    def test_image_with_gps_and_offset(self):
        """Extrae GPSDateStamp y OffsetTimeOriginal correctamente"""
        # Crear estructura EXIF con GPSInfo
        gps_info = {
            1: '2023:01:15',        # GPSDateStamp
            2: (10, 30, 0)          # GPSTimeStamp as ints
        }

        # Tag id 999 representa GPSInfo en este mock
        mock_exif = {
            36867: '2023:01:15 10:30:00',  # DateTimeOriginal
            32867: '+02:00',               # OffsetTimeOriginal (made-up tag id)
            999: gps_info
        }
        mock_image = MagicMock()
        mock_image.__enter__ = Mock(return_value=mock_image)
        mock_image.__exit__ = Mock(return_value=False)
        mock_image.getexif.return_value = mock_exif

        with patch('PIL.Image.open', return_value=mock_image), \
             patch('PIL.ExifTags.TAGS', {36867: 'DateTimeOriginal', 32867: 'OffsetTimeOriginal', 999: 'GPSInfo'}), \
             patch('PIL.ExifTags.GPSTAGS', {1: 'GPSDateStamp', 2: 'GPSTimeStamp'}):
            result = get_exif_from_image(Path('/fake/image.jpg'))

            assert result['DateTimeOriginal'] == datetime(2023, 1, 15, 10, 30, 0)
            assert result['OffsetTimeOriginal'] == '+02:00'
            # GPS Date y Time ahora son strings separados
            assert result['GPSDateStamp'] == '2023:01:15'
            assert result['GPSTimeStamp'] == '10:30:00'


@pytest.mark.unit
class TestGetAllFileDates:
    """Tests para extracción completa de fechas de archivos"""
    
    def test_file_with_all_dates_available(self, temp_dir, create_test_image):
        """Archivo con todas las fechas debe extraerlas correctamente"""
        image_path = create_test_image(temp_dir / 'test.jpg', size=(100, 100))
        
        # Mock EXIF dates
        with patch('utils.file_utils.get_exif_from_image', return_value={
            'DateTimeOriginal': datetime(2023, 1, 15, 10, 30, 0),
            'CreateDate': datetime(2023, 1, 15, 10, 31, 0),
            'DateTimeDigitized': datetime(2023, 1, 15, 10, 32, 0),
            'SubSecTimeOriginal': None,
            'OffsetTimeOriginal': None,
            'GPSDateStamp': None,
            'Software': None
        }), \
        patch('utils.settings_manager.settings_manager.get_precalculate_image_exif', return_value=True), \
        patch('utils.settings_manager.settings_manager.get_precalculate_hashes', return_value=False), \
        patch('utils.settings_manager.settings_manager.get_precalculate_video_exif', return_value=False):
            file_metadata = get_all_metadata_from_file(image_path)
            
            # Verificar atributos directamente en FileMetadata
            assert file_metadata.exif_DateTimeOriginal is not None
            assert file_metadata.exif_DateTime is not None  # CreateDate se mapea a DateTime
            assert file_metadata.exif_DateTimeDigitized is not None
            assert file_metadata.fs_mtime > 0
            assert file_metadata.fs_ctime > 0
    
    def test_file_without_exif(self, temp_dir, create_test_image):
        """Archivo sin EXIF debe tener solo fechas del sistema"""
        image_path = create_test_image(temp_dir / 'test.jpg', size=(100, 100))
        
        with patch('utils.file_utils.get_exif_from_image', return_value={
            'DateTimeOriginal': None,
            'CreateDate': None,
            'DateTimeDigitized': None,
            'SubSecTimeOriginal': None,
            'OffsetTimeOriginal': None,
            'GPSDateStamp': None,
            'Software': None
        }), \
        patch('utils.settings_manager.settings_manager.get_precalculate_image_exif', return_value=True), \
        patch('utils.settings_manager.settings_manager.get_precalculate_hashes', return_value=False), \
        patch('utils.settings_manager.settings_manager.get_precalculate_video_exif', return_value=False):
            file_metadata = get_all_metadata_from_file(image_path)
            
            assert file_metadata.exif_DateTimeOriginal is None
            assert file_metadata.exif_DateTime is None
            assert file_metadata.exif_DateTimeDigitized is None
            assert file_metadata.fs_mtime > 0
    
    def test_nonexistent_file_returns_empty_dates(self):
        """Archivo inexistente debe devolver metadatos mínimos"""
        file_metadata = get_all_metadata_from_file(Path('/nonexistent/file.jpg'))
        
        # Como el archivo no existe, debe tener valores por defecto (0.0 o None)
        assert file_metadata.exif_DateTimeOriginal is None
        assert file_metadata.exif_DateTime is None
        assert file_metadata.exif_DateTimeDigitized is None

    def test_video_metadata_disabled_by_config(self, temp_dir, create_test_video):
        """Cuando get_precalculate_video_exif es False, no debe llamar a get_exif_from_video"""
        video_path = create_test_video(temp_dir / 'test.mp4')

        with patch('utils.settings_manager.settings_manager.get_precalculate_video_exif', return_value=False), \
             patch('utils.settings_manager.settings_manager.get_precalculate_image_exif', return_value=False), \
             patch('utils.settings_manager.settings_manager.get_precalculate_hashes', return_value=False), \
             patch('utils.file_utils.get_exif_from_video') as mock_get_video_metadata:
            file_metadata = get_all_metadata_from_file(video_path)

            # No debe llamar a get_exif_from_video
            mock_get_video_metadata.assert_not_called()

            # exif_DateTime (que almacena video metadata) debe ser None
            assert file_metadata.exif_DateTime is None

    def test_video_metadata_enabled_by_config(self, temp_dir, create_test_video):
        """Cuando get_precalculate_video_exif es True, debe llamar a get_exif_from_video"""
        video_path = create_test_video(temp_dir / 'test.mp4')
        expected_video_date = datetime(2023, 6, 15, 14, 30, 0)

        with patch('utils.settings_manager.settings_manager.get_precalculate_video_exif', return_value=True), \
             patch('utils.settings_manager.settings_manager.get_precalculate_image_exif', return_value=False), \
             patch('utils.settings_manager.settings_manager.get_precalculate_hashes', return_value=False), \
             patch('utils.file_utils.get_exif_from_video', return_value={'creation_time': expected_video_date}) as mock_get_video_metadata:
            file_metadata = get_all_metadata_from_file(video_path)

            # Debe llamar a get_exif_from_video
            mock_get_video_metadata.assert_called_once_with(video_path)

            # Para videos, la fecha se guarda en exif_DateTime como string ISO
            assert file_metadata.exif_DateTime is not None

    def test_video_metadata_enabled_but_no_metadata_available(self, temp_dir, create_test_video):
        """Cuando get_precalculate_video_exif es True pero no hay metadatos, debe devolver None"""
        video_path = create_test_video(temp_dir / 'test.mp4')

        with patch('utils.settings_manager.settings_manager.get_precalculate_video_exif', return_value=True), \
             patch('utils.settings_manager.settings_manager.get_precalculate_image_exif', return_value=False), \
             patch('utils.settings_manager.settings_manager.get_precalculate_hashes', return_value=False), \
             patch('utils.file_utils.get_exif_from_video', return_value={}) as mock_get_video_metadata:
            file_metadata = get_all_metadata_from_file(video_path)

            # Debe llamar a get_exif_from_video
            mock_get_video_metadata.assert_called_once_with(video_path)

            # exif_DateTime debe ser None
            assert file_metadata.exif_DateTime is None


@pytest.mark.unit
class TestGetDateFromFile:
    """Tests para la función principal de extracción de fecha"""
    
    def test_file_with_exif_returns_exif_date(self, temp_dir, create_test_image):
        """Archivo con EXIF debe devolver fecha EXIF"""
        from services.file_metadata import FileMetadata
        
        image_path = create_test_image(temp_dir / 'test.jpg', size=(100, 100))
        
        # Crear un FileMetadata mock con fechas EXIF
        mock_metadata = FileMetadata(
            path=image_path,
            fs_size=1000,
            fs_ctime=datetime(2024, 1, 1, 12, 0).timestamp(),
            fs_mtime=datetime(2024, 1, 2, 14, 0).timestamp(),
            fs_atime=datetime(2024, 1, 3, 16, 0).timestamp(),
            exif_DateTimeOriginal='2023-01-15T10:30:00',
            exif_DateTime='2023-01-15T10:31:00'
        )
        
        result_date, result_source = select_best_date_from_file(mock_metadata)
        assert result_date == datetime(2023, 1, 15, 10, 30, 0)
        assert 'EXIF' in result_source
    
    def test_file_without_exif_returns_filesystem_date(self, temp_dir, create_test_image):
        """Archivo sin EXIF debe devolver fecha del sistema"""
        from services.file_metadata import FileMetadata
        
        image_path = create_test_image(temp_dir / 'test.jpg', size=(100, 100))
        
        # Crear un FileMetadata mock sin EXIF
        mock_metadata = FileMetadata(
            path=image_path,
            fs_size=1000,
            fs_ctime=datetime(2024, 1, 1, 12, 0).timestamp(),
            fs_mtime=datetime(2024, 1, 2, 14, 0).timestamp(),
            fs_atime=datetime(2024, 1, 3, 16, 0).timestamp()
        )
        
        result_date, result_source = select_best_date_from_file(mock_metadata)
        assert result_date == datetime(2024, 1, 1, 12, 0)
    
    def test_file_with_no_dates_returns_none(self, temp_dir, create_test_image):
        """Archivo sin fechas debe devolver None"""
        from services.file_metadata import FileMetadata
        
        image_path = create_test_image(temp_dir / 'test.jpg', size=(100, 100))
        
        mock_metadata = FileMetadata(
            path=image_path,
            fs_size=1000,
            fs_ctime=0.0,
            fs_mtime=0.0,
            fs_atime=0.0
        )
        
        result_date, result_source = select_best_date_from_file(mock_metadata)
        assert result_date is None
        assert result_source is None


@pytest.mark.unit
class TestFormatRenamedName:
    """Tests para generación de nombres en formato renombrado"""
    
    def test_basic_photo_name(self):
        """Debe generar nombre básico para foto sin secuencia"""
        date = datetime(2023, 1, 15, 10, 30, 45)
        result = format_renamed_name(date, 'PHOTO', '.jpg')
        
        assert result == '20230115_103045_PHOTO.JPG'
    
    def test_basic_video_name(self):
        """Debe generar nombre básico para video sin secuencia"""
        date = datetime(2023, 1, 15, 10, 30, 45)
        result = format_renamed_name(date, 'VIDEO', '.mov')
        
        assert result == '20230115_103045_VIDEO.MOV'
    
    def test_photo_with_sequence(self):
        """Debe generar nombre con secuencia para foto"""
        date = datetime(2023, 1, 15, 10, 30, 45)
        result = format_renamed_name(date, 'PHOTO', '.jpg', sequence=5)
        
        assert result == '20230115_103045_PHOTO_005.JPG'
    
    def test_sequence_padding(self):
        """Debe rellenar secuencia con ceros a la izquierda"""
        date = datetime(2023, 1, 15, 10, 30, 45)
        result = format_renamed_name(date, 'VIDEO', '.mp4', sequence=42)
        
        assert result == '20230115_103045_VIDEO_042.MP4'
    
    def test_extension_uppercase(self):
        """Debe convertir extensión a mayúsculas"""
        date = datetime(2023, 1, 15, 10, 30, 45)
        result = format_renamed_name(date, 'PHOTO', '.jpeg')
        
        assert result == '20230115_103045_PHOTO.JPEG'


@pytest.mark.unit
class TestIsRenamedFilename:
    """Tests para verificación rápida de nombres renombrados"""
    
    def test_valid_renamed_name_returns_true(self):
        """Debe reconocer nombre válido renombrado"""
        assert is_renamed_filename('20230115_103045_PHOTO.JPG') is True
    
    def test_valid_renamed_name_with_sequence_returns_true(self):
        """Debe reconocer nombre válido con secuencia"""
        assert is_renamed_filename('20230115_103045_VIDEO_042.MOV') is True
    
    def test_invalid_name_returns_false(self):
        """Debe rechazar nombre no renombrado"""
        assert is_renamed_filename('IMG_1234.JPG') is False
    
    def test_empty_name_returns_false(self):
        """Debe rechazar nombre vacío"""
        assert is_renamed_filename('') is False
    
    def test_partial_match_returns_false(self):
        """Debe rechazar coincidencia parcial"""
        assert is_renamed_filename('20230115_PHOTO.JPG') is False
    
    def test_extension_with_digits_mp4(self):
        """Debe reconocer nombres con extensión MP4 (contiene dígito)"""
        assert is_renamed_filename('20230115_103045_VIDEO.MP4') is True
    
    def test_extension_with_digits_m4v(self):
        """Debe reconocer nombres con extensión M4V (contiene dígito)"""
        assert is_renamed_filename('20230115_103045_VIDEO.M4V') is True
    
    def test_extension_with_sequence_and_digits(self):
        """Debe reconocer nombres con secuencia y extensión con dígitos"""
        assert is_renamed_filename('20230115_103045_VIDEO_001.MP4') is True


@pytest.mark.unit
class TestFilenameDateVsMtimePrecision:
    """Tests para validar que mtime tiene prioridad sobre filename cuando es más precisa"""
    
    def test_filename_date_with_zeros_and_matching_mtime_day_prefers_mtime(self):
        """Cuando filename tiene fecha sin hora (00:00:00) y mtime coincide en día, preferir mtime"""
        # Caso: IMG_20230515.jpg (sin hora) -> 2023-05-15 00:00:00
        # mtime: 2023-05-15 14:30:45 (más precisa)
        metadata = _create_test_metadata(
            path=Path('/test/IMG-20230515-WA0001.jpg'),  # Patrón WhatsApp sin hora
            fs_mtime=datetime(2023, 5, 15, 14, 30, 45).timestamp(),
            fs_ctime=datetime(2023, 5, 15, 14, 30, 45).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe preferir mtime porque tiene hora precisa
        assert result_date == datetime(2023, 5, 15, 14, 30, 45)
        assert result_source == 'mtime (more precise than filename)'
    
    def test_filename_date_with_time_keeps_filename(self):
        """Cuando filename tiene hora completa, mantener filename aunque mtime coincida"""
        # Caso: IMG_20230515_143045.jpg (con hora) -> 2023-05-15 14:30:45
        # mtime: 2023-05-15 14:30:47 (diferencia menor)
        metadata = _create_test_metadata(
            path=Path('/test/IMG_20230515_143045.jpg'),  # Patrón con hora completa
            fs_mtime=datetime(2023, 5, 15, 14, 30, 47).timestamp(),
            fs_ctime=datetime(2023, 5, 15, 14, 30, 47).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe mantener filename porque ya tiene hora precisa
        assert result_date == datetime(2023, 5, 15, 14, 30, 45)
        assert result_source == 'Filename'
    
    def test_filename_date_zeros_different_day_than_mtime_keeps_filename(self):
        """Si filename y mtime tienen diferente día, usar filename aunque tenga 00:00:00"""
        # Caso: IMG_20230515.jpg -> 2023-05-15 00:00:00
        # mtime: 2023-05-20 10:00:00 (día diferente)
        metadata = _create_test_metadata(
            path=Path('/test/IMG-20230515-WA0001.jpg'),
            fs_mtime=datetime(2023, 5, 20, 10, 0, 0).timestamp(),
            fs_ctime=datetime(2023, 5, 20, 10, 0, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe mantener filename aunque tenga 00:00:00 porque el día no coincide
        assert result_date == datetime(2023, 5, 15, 0, 0, 0)
        assert result_source == 'Filename'
    
    def test_filename_date_zeros_no_mtime_keeps_filename(self):
        """Si no hay mtime disponible, usar filename aunque tenga 00:00:00"""
        metadata = _create_test_metadata(
            path=Path('/test/IMG-20230515-WA0001.jpg'),
            fs_ctime=datetime(2023, 5, 15, 10, 0, 0).timestamp(),
            # Sin mtime
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe usar filename porque no hay mtime
        assert result_date == datetime(2023, 5, 15, 0, 0, 0)
        assert result_source == 'Filename'
    
    def test_filename_with_partial_time_keeps_filename(self):
        """Filename con hora parcial (ej: solo hora, minutos=00) debe mantenerse"""
        # Caso hipotético: nombre personalizado con solo hora
        # Creamos metadata manualmente sin path para simular
        from services.file_metadata import FileMetadata
        
        metadata = FileMetadata(
            path=Path('/test/custom_file.jpg'),
            fs_size=1000,
            fs_ctime=datetime(2023, 5, 15, 14, 0, 0).timestamp(),
            fs_mtime=datetime(2023, 5, 15, 14, 30, 45).timestamp(),
            fs_atime=datetime(2023, 5, 15, 14, 30, 45).timestamp(),
        )
        
        # Simular fecha extraída con hora no-cero (ej: 14:00:00)
        # Para esto necesitamos mockear extract_date_from_filename
        from unittest.mock import patch
        with patch('utils.date_utils.extract_date_from_filename') as mock_extract:
            mock_extract.return_value = datetime(2023, 5, 15, 14, 0, 0)  # Hora 14:00:00
            
            result_date, result_source = select_best_date_from_file(metadata)
            
            # Como la hora NO es 00:00:00, debe mantener filename
            assert result_date == datetime(2023, 5, 15, 14, 0, 0)
            assert result_source == 'Filename'


@pytest.mark.unit
class TestEdgeCasesAndCorruptedData:
    """Tests para casos edge y datos corruptos"""
    
    def test_select_earliest_with_all_none_except_one_exif(self):
        """Una sola fecha EXIF disponible debe ser seleccionada"""
        metadata = _create_test_metadata(
            exif_date_time_digitized='2023:01:15 10:30:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 1, 15, 10, 30)
        assert result_source == 'EXIF DateTimeDigitized'
    
    def test_select_earliest_with_same_timestamps(self):
        """Todas las fechas iguales debe devolver la primera en prioridad"""
        same_date_str = '2023:01:15 10:30:00'
        same_ts = datetime(2023, 1, 15, 10, 30).timestamp()
        metadata = _create_test_metadata(
            exif_date_time_original=same_date_str,
            exif_date_time=same_date_str,
            exif_date_time_digitized=same_date_str,
            fs_ctime=same_ts,
            fs_mtime=same_ts,
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe devolver una fecha EXIF (prioridad)
        assert result_date == datetime(2023, 1, 15, 10, 30)
        assert 'EXIF' in result_source
    
    def test_format_renamed_name_with_zero_sequence(self):
        """Secuencia 0 debe generar nombre con _000"""
        date = datetime(2023, 1, 15, 10, 30, 45)
        result = format_renamed_name(date, 'PHOTO', '.jpg', sequence=0)
        
        # sequence=0 es falsy, no debe incluirse
        assert result == '20230115_103045_PHOTO.JPG'


@pytest.mark.unit
class TestSelectChosenDateCombinatorial:
    """Tests exhaustivos con combinatoria de todas las fuentes de fechas usando FileMetadata"""
    
    # === TESTS DE FECHAS EXIF (Prioridad Máxima) ===
    
    def test_datetime_original_only(self):
        """Solo DateTimeOriginal disponible"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:05:10 14:30:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 5, 10, 14, 30)
        assert result_source == 'EXIF DateTimeOriginal'
    
    def test_datetime_original_with_offset(self):
        """DateTimeOriginal con OffsetTimeOriginal tiene nombre descriptivo"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:05:10 14:30:00',
            exif_offset_time_original='+02:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 5, 10, 14, 30)
        assert '+02:00' in result_source
        assert 'DateTimeOriginal' in result_source
    
    def test_create_date_only(self):
        """Solo CreateDate disponible (mapeado a exif_date_time)"""
        metadata = _create_test_metadata(
            exif_date_time='2023:06:15 09:00:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 6, 15, 9, 0)
        assert result_source == 'EXIF CreateDate'
    
    def test_date_digitized_only(self):
        """Solo DateTimeDigitized disponible"""
        metadata = _create_test_metadata(
            exif_date_time_digitized='2023:07:20 11:45:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 7, 20, 11, 45)
        assert result_source == 'EXIF DateTimeDigitized'
    
    def test_all_three_exif_dates_returns_earliest(self):
        """Con las 3 fechas EXIF, debe devolver DateTimeOriginal (prioridad estricta)"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:05:10 14:00:00',  # Primera prioridad
            exif_date_time='2023:05:10 12:00:00',  # Más antigua, pero menor prioridad
            exif_date_time_digitized='2023:05:10 16:00:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 5, 10, 14, 0)
        assert result_source == 'EXIF DateTimeOriginal'
    
    # === TESTS DE GPS DATESTAMP (Solo validación) ===
    
    def test_gps_with_exif_original_gps_ignored(self):
        """GPS DateStamp es ignorado cuando hay EXIF DateTimeOriginal"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:08:04 18:49:23',
            exif_gps_date_stamp='2023:08:04 20:00:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # GPS no debe ser seleccionado
        assert result_date == datetime(2023, 8, 4, 18, 49, 23)
        assert result_source == 'EXIF DateTimeOriginal'
    
    def test_gps_only_not_selected(self):
        """GPS DateStamp solo (sin EXIF) no se selecciona, cae a filesystem"""
        metadata = _create_test_metadata(
            exif_gps_date_stamp='2023:08:04 20:00:00',
            fs_ctime=datetime(2024, 1, 1, 12, 0).timestamp(),
            fs_mtime=datetime(2024, 1, 2, 14, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe caer a fechas filesystem (GPS no se usa como principal)
        assert result_date == datetime(2024, 1, 1, 12, 0)
        assert 'EXIF' not in result_source
    
    # === TESTS DE FILENAME DATE (Prioridad Secundaria) ===
    
    def test_filename_date_when_no_exif(self):
        """Filename date es seleccionado cuando no hay EXIF"""
        metadata = _create_test_metadata(
            path=Path('/test/IMG-20241113-WA0001.jpg'),
            fs_ctime=datetime(2024, 11, 15, 12, 0).timestamp(),
            fs_mtime=datetime(2024, 11, 16, 14, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2024, 11, 13, 0, 0)
        assert result_source == 'Filename'
    
    def test_filename_date_ignored_when_exif_exists(self):
        """Filename date es ignorado cuando hay EXIF"""
        metadata = _create_test_metadata(
            path=Path('/test/IMG-20241113-WA0001.jpg'),
            exif_date_time_original='2023:05:10 14:30:00',
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # EXIF tiene prioridad sobre filename
        assert result_date == datetime(2023, 5, 10, 14, 30)
        assert result_source == 'EXIF DateTimeOriginal'
    
    # === TESTS DE VIDEO METADATA ===
    
    def test_video_metadata_when_no_exif_no_filename(self):
        """Video metadata (exif_date_time para videos) es seleccionado cuando no hay EXIF fecha original"""
        metadata = _create_test_metadata(
            path=Path('/test/video.mp4'),
            exif_date_time='2024:01:15 14:30:00',
            fs_ctime=datetime(2024, 1, 15, 12, 0).timestamp(),
            fs_mtime=datetime(2024, 1, 15, 16, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Para videos sin DateTimeOriginal, usa exif_date_time
        assert result_date == datetime(2024, 1, 15, 14, 30)
    
    # === TESTS DE FILESYSTEM DATES (Último recurso) ===
    
    def test_creation_date_only_filesystem(self):
        """Solo creation_date disponible (último recurso)"""
        metadata = _create_test_metadata(
            fs_ctime=datetime(2024, 1, 1, 12, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2024, 1, 1, 12, 0)
        assert result_source in ('ctime', 'birth')
    
    def test_modification_date_only_filesystem(self):
        """Solo modification_date disponible"""
        metadata = _create_test_metadata(
            fs_mtime=datetime(2024, 1, 2, 14, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2024, 1, 2, 14, 0)
        assert result_source == 'mtime'
    
    def test_filesystem_dates_returns_earliest(self):
        """Con ambas fechas filesystem, devuelve la más antigua"""
        metadata = _create_test_metadata(
            fs_ctime=datetime(2024, 1, 1, 12, 0).timestamp(),  # Más antigua
            fs_mtime=datetime(2024, 1, 2, 14, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2024, 1, 1, 12, 0)
        assert result_source in ('ctime', 'birth')
    
    def test_filesystem_ignored_when_exif_exists(self):
        """Fechas filesystem son ignoradas cuando hay EXIF"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:05:10 14:30:00',
            fs_ctime=datetime(2022, 1, 1, 12, 0).timestamp(),  # Más antigua pero ignorada
            fs_mtime=datetime(2021, 6, 15, 8, 0).timestamp(),  # Mucho más antigua
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # EXIF tiene prioridad absoluta sobre filesystem
        assert result_date == datetime(2023, 5, 10, 14, 30)
        assert result_source == 'EXIF DateTimeOriginal'
    
    # === TESTS DE CASOS COMPLEJOS (Combinatoria completa) ===
    
    def test_all_sources_available_exif_wins(self):
        """Con todas las fuentes, DateTimeOriginal tiene prioridad absoluta"""
        metadata = _create_test_metadata(
            path=Path('/test/IMG-20241113-WA0001.jpg'),  # Tiene fecha en filename
            exif_date_time_original='2023:05:10 14:30:00',  # Primera prioridad
            exif_date_time='2023:05:10 12:00:00',  # Más antigua EXIF, pero menor prioridad
            exif_date_time_digitized='2023:05:10 16:00:00',
            exif_gps_date_stamp='2023:05:10 10:00:00',  # Más antigua global pero GPS ignorado
            fs_ctime=datetime(2022, 1, 1, 12, 0).timestamp(),  # Más antigua filesystem
            fs_mtime=datetime(2021, 6, 15, 8, 0).timestamp(),
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe seleccionar DateTimeOriginal por prioridad estricta
        assert result_date == datetime(2023, 5, 10, 14, 30)
        assert result_source == 'EXIF DateTimeOriginal'
    
    def test_completely_empty_returns_none(self):
        """Sin ninguna fecha disponible debe devolver None"""
        metadata = _create_test_metadata()
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date is None
        assert result_source is None
    
    def test_dates_with_same_timestamp_exif_preferred(self):
        """Con timestamps idénticos, EXIF tiene prioridad en el source"""
        same_date_str = '2023:05:10 12:00:00'
        same_ts = datetime(2023, 5, 10, 12, 0).timestamp()
        metadata = _create_test_metadata(
            path=Path('/test/IMG-20230510-WA0001.jpg'),  # Misma fecha en filename
            exif_date_time_original=same_date_str,
            fs_ctime=same_ts,
            fs_mtime=same_ts,
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        assert result_date == datetime(2023, 5, 10, 12, 0)
        assert 'EXIF' in result_source
    
    def test_extreme_date_differences_handled_correctly(self):
        """Diferencias extremas de fechas: prioridad estricta evita fechas corruptas"""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:05:10 14:30:00',  # Primera prioridad
            exif_date_time='1990:01:01 00:00:00',  # 33 años antes (posible corrupción)
            fs_ctime=datetime(2024, 12, 31, 23, 59).timestamp(),  # En el futuro
        )
        
        result_date, result_source = select_best_date_from_file(metadata)
        
        # Debe devolver DateTimeOriginal, no la fecha corrupta de 1990
        assert result_date == datetime(2023, 5, 10, 14, 30)
        assert result_source == 'EXIF DateTimeOriginal'


@pytest.mark.unit
class TestVideoMetadataConfiguration:
    """Tests para la configuración de extracción de metadatos de video"""

    def setup_method(self):
        """Guarda el estado de configuración antes de cada test"""
        from utils.settings_manager import settings_manager
        self.settings_manager = settings_manager
        
        # Guardar configuraciones originales
        self.original_video_exif = self.settings_manager.get_precalculate_video_exif()
        self.original_hashes = self.settings_manager.get_precalculate_hashes()
        self.original_image_exif = self.settings_manager.get_precalculate_image_exif()
    
    def teardown_method(self):
        """Restaura el estado de configuración después de cada test"""
        # Restaurar configuraciones originales
        self.settings_manager.set_precalculate_video_exif(self.original_video_exif)
        self.settings_manager.set_precalculate_hashes(self.original_hashes)
        self.settings_manager.set_precalculate_image_exif(self.original_image_exif)

    def test_settings_manager_defaults_to_false(self):
        """get_precalculate_video_exif debe devolver False por defecto"""
        # Remover la clave para obtener el valor por defecto
        self.settings_manager.remove(self.settings_manager.KEY_PRECALCULATE_VIDEO_EXIF)
        
        # Verificar que el valor por defecto es False
        assert self.settings_manager.get_precalculate_video_exif() is False

    def test_settings_manager_can_be_configured(self):
        """get_precalculate_video_exif debe poder configurarse"""
        # Establecer a True
        self.settings_manager.set_precalculate_video_exif(True)
        assert self.settings_manager.get_precalculate_video_exif() is True
        
        # Establecer a False
        self.settings_manager.set_precalculate_video_exif(False)
        assert self.settings_manager.get_precalculate_video_exif() is False

@pytest.mark.unit
class TestGetBestCommonCreationDate2FilesComprehensive:
    """Tests exhaustivos para select_best_date_from_common_date_to_2_files con la nueva lógica profesional"""

    @pytest.fixture
    def file1_exif(self):
        from types import SimpleNamespace
        return SimpleNamespace(
            path="file1.jpg",
            exif_date_time_original=datetime(2023, 1, 1, 12, 0, 0),
            exif_create_date=datetime(2023, 1, 1, 12, 30, 0),
            mtime=datetime(2023, 1, 1, 15, 0, 0).timestamp(),
            ctime=datetime(2023, 1, 1, 16, 0, 0).timestamp(),
            atime=datetime(2023, 1, 1, 17, 0, 0).timestamp()
        )

    @pytest.fixture
    def file2_exif(self):
        from types import SimpleNamespace
        return SimpleNamespace(
            path="file2.heic",
            exif_date_time_original=datetime(2023, 1, 1, 12, 0, 5),
            exif_create_date=datetime(2023, 1, 1, 12, 31, 0),
            mtime=datetime(2023, 1, 1, 15, 1, 0).timestamp(),
            ctime=datetime(2023, 1, 1, 16, 1, 0).timestamp(),
            atime=datetime(2023, 1, 1, 17, 1, 0).timestamp()
        )

    def test_priority_1_exif_original(self, file1_exif, file2_exif):
        """Debe priorizar EXIF DateTimeOriginal sobre todo lo demás"""
        # Cambiamos mtime para que sea "más viejo" pero EXIF debe mandar
        file1_exif.mtime = datetime(2020, 1, 1).timestamp()
        file2_exif.mtime = datetime(2020, 1, 1).timestamp()
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1_exif, file2_exif)
        
        assert d1 == datetime(2023, 1, 1, 12, 0, 0)
        assert d2 == datetime(2023, 1, 1, 12, 0, 5)
        assert source == 'exif_date_time_original'

    def test_fallback_to_exif_create_date(self, file1_exif, file2_exif):
        """Debe caer a EXIF CreateDate si no hay Original"""
        file1_exif.exif_date_time_original = None
        file2_exif.exif_date_time_original = None
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1_exif, file2_exif)
        
        assert d1 == datetime(2023, 1, 1, 12, 30, 0)
        assert d2 == datetime(2023, 1, 1, 12, 31, 0)
        assert source == 'exif_create_date'

    def test_filesystem_fallback_mtime_is_oldest(self, file1_exif, file2_exif):
        """Sin EXIF, debe elegir mtime si es la fuente común más antigua (caso normal)"""
        file1_exif.exif_date_time_original = None
        file1_exif.exif_create_date = None
        file2_exif.exif_date_time_original = None
        file2_exif.exif_create_date = None
        
        # mtime < ctime < atime
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1_exif, file2_exif)
        
        assert d1 == datetime(2023, 1, 1, 15, 0, 0)
        assert d2 == datetime(2023, 1, 1, 15, 1, 0)
        assert source == 'fs_mtime'

    def test_filesystem_fallback_ctime_is_oldest(self, file1_exif, file2_exif, caplog):
        """Sin EXIF, debe elegir ctime si es más antigua que mtime (anomalía detectada)"""
        import logging
        file1_exif.exif_date_time_original = None
        file1_exif.exif_create_date = None
        file1_exif.exif_modify_date = None
        file2_exif.exif_date_time_original = None
        file2_exif.exif_create_date = None
        file2_exif.exif_modify_date = None
        
        # ctime (14:00) < mtime (15:00)
        file1_exif.ctime = datetime(2023, 1, 1, 14, 0, 0).timestamp()
        file2_exif.ctime = datetime(2023, 1, 1, 14, 1, 0).timestamp()
        
        with caplog.at_level(logging.WARNING):
            d1, d2, source = select_best_date_from_common_date_to_2_files(file1_exif, file2_exif)
            
            assert d1 == datetime(2023, 1, 1, 14, 0, 0)
            assert d2 == datetime(2023, 1, 1, 14, 1, 0)
            assert source == 'fs_ctime'
            assert "ANOMALÍA DE FECHAS" in caplog.text
            assert "fs_ctime" in caplog.text

    def test_only_returns_if_source_present_in_both(self, file1_exif, file2_exif):
        """Solo debe devolver una fuente si ambos archivos disponen de ella"""
        from types import SimpleNamespace
        file1_exif.exif_date_time_original = None
        file1_exif.exif_create_date = None
        file1_exif.exif_modify_date = None
        file2_exif.exif_date_time_original = None
        file2_exif.exif_create_date = None
        file2_exif.exif_modify_date = None

        # f1 solo tiene mtime, f2 solo tiene ctime
        # No hay fuente COMÚN
        f1_solo_m = SimpleNamespace(path="f1", mtime=datetime(2020,1,1).timestamp())
        f2_solo_c = SimpleNamespace(path="f2", ctime=datetime(2020,1,1).timestamp())
        
        result = select_best_date_from_common_date_to_2_files(f1_solo_m, f2_solo_c)
        assert result is None

    def test_mixed_exif_one_file_only(self, file1_exif, file2_exif):
        """Si solo un archivo tiene EXIF, debe caer a filesystem (fuente común)"""
        # file1 tiene EXIF, file2 no
        file2_exif.exif_date_time_original = None
        file2_exif.exif_create_date = None
        file2_exif.exif_modify_date = None
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1_exif, file2_exif)
        
        # Cae a mtime porque es la fuente común (pese a que f1 tenía EXIF)
        assert source == 'fs_mtime'
        assert d1 == datetime(2023, 1, 1, 15, 0, 0)
        assert d2 == datetime(2023, 1, 1, 15, 1, 0)

    def test_absolute_oldest_among_commons(self, file1_exif, file2_exif):
        """Debe elegir la fuente común que contenga la fecha absoluta más antigua"""
        file1_exif.exif_date_time_original = None
        file1_exif.exif_create_date = None
        file2_exif.exif_date_time_original = None
        file2_exif.exif_create_date = None

        # mtime: 2023
        # ctime: 2022 (La más antigua común)
        # atime: 2024
        file1_exif.mtime = datetime(2023, 1, 1).timestamp()
        file1_exif.ctime = datetime(2022, 1, 1).timestamp()
        file1_exif.atime = datetime(2024, 1, 1).timestamp()
        
        file2_exif.mtime = datetime(2023, 1, 1, 1).timestamp()
        file2_exif.ctime = datetime(2022, 1, 1, 1).timestamp()
        file2_exif.atime = datetime(2024, 1, 1, 1).timestamp()
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1_exif, file2_exif)
        
        assert source == 'fs_ctime'
        assert d1 == datetime(2022, 1, 1)

    def test_handles_missing_attributes_gracefully(self):
        """Debe manejar objetos que no tienen todos los campos del protocolo"""
        from types import SimpleNamespace
        f1 = SimpleNamespace(path="f1") # Sin mtime/ctime/atime/exif
        f2 = SimpleNamespace(path="f2")
        
        result = select_best_date_from_common_date_to_2_files(f1, f2)
        assert result is None
    def test_exif_dates_as_strings_are_parsed_correctly(self):
        """
        BUG FIX: EXIF dates como strings deben ser parseados correctamente.
        
        Antes del fix, cuando FileMetadata tenía exif_date_time_original como string
        "2023:08:10 15:41:34", la función _to_dt() no podía convertirlo y caía
        a filesystem timestamps (mtime/ctime).
        
        Este test verifica que strings EXIF se parsean correctamente y tienen
        prioridad sobre filesystem dates.
        """
        from types import SimpleNamespace
        
        # Simular FileMetadata con EXIF como strings (formato real del caché)
        file1 = SimpleNamespace(
            path="/tmp/test/images/IMG_0022.HEIC",
            exif_date_time_original="2023:08:10 15:41:34",  # String EXIF, NO datetime
            exif_date_time="2023:08:10 15:41:34",
            fs_mtime=1691703949.0,  # 2023-08-10 pero hora diferente
            fs_ctime=1766818401.512191,
            fs_atime=1766832805.0878773
        )
        
        file2 = SimpleNamespace(
            path="/tmp/test/images/IMG_0022.jpg",
            exif_date_time_original="2023:08:10 15:41:34",  # String EXIF, NO datetime
            exif_date_time="2023:08:10 15:41:34",
            fs_mtime=1691703949.0,
            fs_ctime=1766818401.5821912,
            fs_atime=1766832805.0838773
        )
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1, file2)
        
        # DEBE usar EXIF, NO filesystem timestamps
        assert source == 'exif_date_time_original', f"Expected EXIF source but got {source}"
        assert d1 == datetime(2023, 8, 10, 15, 41, 34)
        assert d2 == datetime(2023, 8, 10, 15, 41, 34)

    def test_exif_strings_mixed_with_filesystem_timestamps(self):
        """
        Verifica que strings EXIF tienen prioridad incluso cuando filesystem
        timestamps están disponibles y son más antiguos.
        """
        from types import SimpleNamespace
        
        file1 = SimpleNamespace(
            path="/test/file1.jpg",
            exif_date_time_original="2023:08:10 15:41:34",  # String EXIF
            fs_mtime=datetime(2020, 1, 1).timestamp(),  # Mucho más antiguo
            fs_ctime=datetime(2020, 1, 1).timestamp()
        )
        
        file2 = SimpleNamespace(
            path="/test/file2.jpg",
            exif_date_time_original="2023:08:10 15:41:35",  # String EXIF
            fs_mtime=datetime(2020, 1, 1).timestamp(),
            fs_ctime=datetime(2020, 1, 1).timestamp()
        )
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1, file2)
        
        # DEBE priorizar EXIF sobre filesystem
        assert source == 'exif_date_time_original'
        assert d1.year == 2023  # NO 2020
        assert d2.year == 2023
    
    def test_epoch_zero_exif_dates_are_ignored_in_common_date_selection(self):
        """Fechas EXIF de epoch 0 deben ignorarse en la selección común entre dos archivos"""
        from types import SimpleNamespace
        
        # Archivo 1 con fecha EXIF epoch zero
        file1 = SimpleNamespace(
            path="/test/file1.mp4",
            exif_date_time_original=datetime(1970, 1, 1, 0, 0, 0),  # Epoch zero - debe ignorarse
            exif_date_time=datetime(1970, 1, 1, 0, 0, 0),  # Epoch zero - debe ignorarse
            fs_mtime=datetime(2021, 9, 4, 11, 56, 41).timestamp(),  # Fecha real del filesystem
            fs_ctime=datetime(2021, 9, 4, 11, 56, 41).timestamp()
        )
        
        # Archivo 2 con fecha EXIF epoch zero
        file2 = SimpleNamespace(
            path="/test/file2.jpg",
            exif_date_time_original=datetime(1970, 1, 1, 0, 0, 0),  # Epoch zero - debe ignorarse
            exif_date_time=datetime(1970, 1, 1, 0, 0, 0),  # Epoch zero - debe ignorarse
            fs_mtime=datetime(2021, 9, 4, 11, 56, 42).timestamp(),  # Fecha real del filesystem
            fs_ctime=datetime(2021, 9, 4, 11, 56, 42).timestamp()
        )
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1, file2)
        
        # Debe usar filesystem dates ya que EXIF epoch zero se ignora
        assert source == 'fs_mtime'
        assert d1 == datetime(2021, 9, 4, 11, 56, 41)
        assert d2 == datetime(2021, 9, 4, 11, 56, 42)


@pytest.mark.unit
class TestTimezoneNormalization:
    """Tests para normalización de timezone en comparación de fechas EXIF.
    
    COMPORTAMIENTO:
    - Si AMBOS archivos tienen offset de timezone: normalizar a UTC para comparación justa
    - Si alguno NO tiene offset: usar hora local sin normalizar (no asumir UTC)
    - Caso iPhone Live Photo: com.apple.quicktime.creationdate provee offset al video,
      así que ambos tendrán offset y se normalizarán correctamente
    """
    
    def test_timezone_normalization_image_with_offset_vs_video_utc(self):
        """
        Imagen con offset y video SIN offset: NO normalizar, usar hora local.
        
        Cuando solo un archivo tiene offset de timezone, no podemos asumir que
        el otro está en UTC. Se comparan las horas tal cual (hora local).
        
        En el caso real de iPhone Live Photos, get_exif_from_video() ahora
        extrae el offset de com.apple.quicktime.creationdate y lo propaga,
        así que ambos tendrán offset y se normalizarán correctamente.
        """
        from types import SimpleNamespace
        
        # Imagen iPhone con hora local y offset
        image = SimpleNamespace(
            path="/test/IMG_3831.JPG",
            exif_date_time_original="2021:07:06 15:37:26",  # Hora local
            exif_offset_time_original="+02:00"  # UTC+2
        )
        
        # Video sin offset (caso genérico sin Apple metadata)
        video = SimpleNamespace(
            path="/test/IMG_3831.MOV",
            exif_date_time_original="2021:07:06 13:37:26"  # Sin offset
        )
        
        vid_date, img_date, source = select_best_date_from_common_date_to_2_files(video, image)
        
        # Sin normalización: se usan las horas tal cual
        assert source == 'exif_date_time_original'
        assert vid_date == datetime(2021, 7, 6, 13, 37, 26)
        assert img_date == datetime(2021, 7, 6, 15, 37, 26)
        # Diferencia es 2 horas (sin normalización)
        assert abs((vid_date - img_date).total_seconds()) == 7200
    
    def test_timezone_normalization_iphone_live_photo_both_offsets(self):
        """
        iPhone Live Photo con com.apple.quicktime.creationdate: ambos tienen offset.
        
        Caso real corregido: get_exif_from_video() ahora extrae la fecha
        precisa de com.apple.quicktime.creationdate y la propaga con offset.
        Ambos archivos tienen offset -> se normalizan a UTC -> diferencia ~0.
        """
        from types import SimpleNamespace
        
        # Imagen iPhone: 2021-07-06 15:37:26 hora local (UTC+2)
        image = SimpleNamespace(
            path="/test/IMG_3831.JPG",
            exif_date_time_original="2021:07:06 15:37:26",
            exif_offset_time_original="+02:00"
        )
        
        # Video iPhone con offset propagado desde com.apple.quicktime.creationdate
        video = SimpleNamespace(
            path="/test/IMG_3831.MOV",
            exif_date_time_original="2021:07:06 15:37:26",  # Misma hora local
            exif_OffsetTimeOriginal="+02:00"  # Offset desde apple.creationdate
        )
        
        vid_date, img_date, source = select_best_date_from_common_date_to_2_files(video, image)
        
        # Ambos con offset -> normalizados a UTC
        assert source == 'exif_date_time_original'
        assert vid_date == datetime(2021, 7, 6, 13, 37, 26)  # 15:37:26 - 2h
        assert img_date == datetime(2021, 7, 6, 13, 37, 26)
        assert abs((vid_date - img_date).total_seconds()) == 0
    
    def test_timezone_normalization_negative_offset(self):
        """Offset negativo (ej: -05:00 América) + archivo sin offset: no normalizar"""
        from types import SimpleNamespace
        
        # Archivo 1 con offset negativo (ej: Nueva York en verano)
        file1 = SimpleNamespace(
            path="/test/file1.jpg",
            exif_date_time_original="2023:08:10 10:00:00",  # Hora local NYC
            exif_offset_time_original="-04:00"  # EDT
        )
        
        # Archivo 2 sin offset
        file2 = SimpleNamespace(
            path="/test/file2.mov",
            exif_date_time_original="2023:08:10 14:00:00"  # Sin offset
        )
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1, file2)
        
        assert source == 'exif_date_time_original'
        # Sin normalización: se usan horas tal cual
        assert d1 == datetime(2023, 8, 10, 10, 0, 0)
        assert d2 == datetime(2023, 8, 10, 14, 0, 0)
        assert abs((d1 - d2).total_seconds()) == 14400  # 4h en segundos
    
    def test_timezone_normalization_both_with_negative_offset(self):
        """Ambos con offsets negativos diferentes: normalizar a UTC"""
        from types import SimpleNamespace
        
        # Archivo 1 en EDT (-04:00)
        file1 = SimpleNamespace(
            path="/test/file1.jpg",
            exif_date_time_original="2023:08:10 10:00:00",
            exif_offset_time_original="-04:00"
        )
        
        # Archivo 2 en UTC (+00:00)
        file2 = SimpleNamespace(
            path="/test/file2.mov",
            exif_date_time_original="2023:08:10 14:00:00",
            exif_offset_time_original="+00:00"  # Explícitamente UTC
        )
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1, file2)
        
        assert source == 'exif_date_time_original'
        # Ambos normalizados a UTC: 10:00 - (-4h) = 14:00 UTC
        assert d1 == datetime(2023, 8, 10, 14, 0, 0)
        assert d2 == datetime(2023, 8, 10, 14, 0, 0)
        assert abs((d1 - d2).total_seconds()) == 0
    
    def test_timezone_both_files_with_offset(self):
        """Ambos archivos con offset deben normalizarse a UTC"""
        from types import SimpleNamespace
        
        # Archivo 1 en UTC+2
        file1 = SimpleNamespace(
            path="/test/file1.jpg",
            exif_date_time_original="2023:08:10 16:00:00",
            exif_offset_time_original="+02:00"
        )
        
        # Archivo 2 en UTC+9 (Japón)
        file2 = SimpleNamespace(
            path="/test/file2.jpg",
            exif_date_time_original="2023:08:10 23:00:00",
            exif_offset_time_original="+09:00"
        )
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1, file2)
        
        # Ambos representan las 14:00 UTC
        assert d1 == datetime(2023, 8, 10, 14, 0, 0)  # 16:00 - 2h
        assert d2 == datetime(2023, 8, 10, 14, 0, 0)  # 23:00 - 9h
        assert abs((d1 - d2).total_seconds()) == 0
    
    def test_timezone_no_offset_treated_as_utc(self):
        """Sin offset explícito, se asume UTC (sin conversión)"""
        from types import SimpleNamespace
        
        file1 = SimpleNamespace(
            path="/test/file1.jpg",
            exif_date_time_original="2023:08:10 15:00:00"
            # Sin exif_offset_time_original
        )
        
        file2 = SimpleNamespace(
            path="/test/file2.jpg",
            exif_date_time_original="2023:08:10 15:00:05"
        )
        
        d1, d2, source = select_best_date_from_common_date_to_2_files(file1, file2)
        
        # Sin offset, las fechas se mantienen tal cual
        assert d1 == datetime(2023, 8, 10, 15, 0, 0)
        assert d2 == datetime(2023, 8, 10, 15, 0, 5)
        assert abs((d1 - d2).total_seconds()) == 5
    
    def test_timezone_offset_formats(self):
        """Soporta varios formatos de offset: +02:00, +0200, Z"""
        from utils.date_utils import _parse_timezone_offset
        
        # Formato estándar con :
        assert _parse_timezone_offset("+02:00") == 7200
        assert _parse_timezone_offset("-05:00") == -18000
        
        # Formato sin :
        assert _parse_timezone_offset("+0200") == 7200
        assert _parse_timezone_offset("-0500") == -18000
        
        # UTC
        assert _parse_timezone_offset("Z") == 0
        assert _parse_timezone_offset("+00:00") == 0
        assert _parse_timezone_offset("-00:00") == 0
        
        # None o inválido
        assert _parse_timezone_offset(None) is None
        assert _parse_timezone_offset("") is None
        assert _parse_timezone_offset("invalid") is None


@pytest.mark.unit
class TestValidateDateCoherence:
    """Tests para _validate_date_coherence — debe devolver DateCoherenceResult (frozen dataclass)."""

    def test_returns_dataclass_not_dict(self):
        """El resultado debe ser DateCoherenceResult, no un dict."""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:01:15 10:30:00',
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),
        )
        result = _validate_date_coherence(metadata)

        assert isinstance(result, DateCoherenceResult)
        assert not isinstance(result, dict)

    def test_warnings_is_tuple(self):
        """warnings debe ser una tupla (inmutable) para frozen dataclass."""
        metadata = _create_test_metadata()
        result = _validate_date_coherence(metadata)

        assert isinstance(result.warnings, tuple)

    def test_clean_file_high_confidence(self):
        """Archivo sin anomalías debe tener is_valid=True y confidence='high'."""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:01:15 10:30:00',
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),
            fs_ctime=datetime(2023, 1, 15, 10, 30, 0).timestamp(),
        )
        result = _validate_date_coherence(metadata)

        assert result.is_valid is True
        assert result.warnings == ()
        assert result.confidence == 'high'

    def test_exif_after_mtime_warning(self):
        """EXIF posterior a mtime debe generar EXIF_AFTER_MTIME y is_valid=False."""
        metadata = _create_test_metadata(
            exif_date_time_original='2025:06:01 10:00:00',
            fs_mtime=datetime(2023, 1, 1, 12, 0).timestamp(),
        )
        result = _validate_date_coherence(metadata)

        assert 'EXIF_AFTER_MTIME' in result.warnings
        assert result.is_valid is False

    def test_exif_divergence_warning(self):
        """Divergencia mayor a 1 año entre campos EXIF genera EXIF_DIVERGENCE."""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:01:15 10:30:00',
            exif_date_time='2021:01:15 10:30:00',  # >1 año de diferencia
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),
        )
        result = _validate_date_coherence(metadata)

        assert 'EXIF_DIVERGENCE' in result.warnings
        assert result.is_valid is False

    def test_digitized_before_original_warning(self):
        """DateTimeDigitized anterior a DateTimeOriginal genera DIGITIZED_BEFORE_ORIGINAL."""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:06:01 10:00:00',
            exif_date_time_digitized='2023:01:01 10:00:00',  # 5 meses antes
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),
        )
        result = _validate_date_coherence(metadata)

        assert 'DIGITIZED_BEFORE_ORIGINAL' in result.warnings
        assert result.is_valid is False

    def test_software_detected_warning(self):
        """Campo Software presente genera SOFTWARE_DETECTED (solo informativo)."""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:01:15 10:30:00',
            exif_software='Adobe Photoshop',
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),
            fs_ctime=datetime(2023, 1, 15, 10, 30, 0).timestamp(),
        )
        result = _validate_date_coherence(metadata)

        assert 'SOFTWARE_DETECTED' in result.warnings
        assert result.confidence == 'medium'  # 1 warning -> medium

    def test_recent_transfer_warning(self):
        """ctime muy diferente de EXIF genera RECENT_TRANSFER."""
        metadata = _create_test_metadata(
            exif_date_time_original='2020:01:15 10:30:00',
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),
            fs_ctime=datetime(2024, 1, 1, 12, 0).timestamp(),  # 4 años después
        )
        result = _validate_date_coherence(metadata)

        assert 'RECENT_TRANSFER' in result.warnings

    def test_gps_divergence_warning(self):
        """GPS date >1 día diferente de EXIF genera GPS_DIVERGENCE."""
        metadata = _create_test_metadata(
            exif_date_time_original='2023:01:15 10:30:00',
            exif_gps_date_stamp='2023:02:20 10:30:00',  # >1 mes
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),
            fs_ctime=datetime(2023, 1, 15, 10, 30, 0).timestamp(),
        )
        result = _validate_date_coherence(metadata)

        assert 'GPS_DIVERGENCE' in result.warnings

    def test_multiple_warnings_low_confidence(self):
        """Múltiples warnings con is_valid=False dan confidence='low'."""
        metadata = _create_test_metadata(
            exif_date_time_original='2025:06:01 10:00:00',  # Futuro (EXIF_AFTER_MTIME)
            exif_date_time='2021:01:01 10:00:00',          # >1 año (EXIF_DIVERGENCE)
            fs_mtime=datetime(2023, 1, 1, 12, 0).timestamp(),
        )
        result = _validate_date_coherence(metadata)

        assert result.is_valid is False
        assert result.confidence == 'low'
        assert len(result.warnings) >= 2

    def test_no_exif_dates_returns_valid(self):
        """Sin fechas EXIF debe devolver is_valid=True (nada que validar)."""
        metadata = _create_test_metadata(
            fs_mtime=datetime(2024, 1, 1, 12, 0).timestamp(),
        )
        result = _validate_date_coherence(metadata)

        assert result.is_valid is True
        assert result.confidence == 'high'

    def test_frozen_dataclass_is_immutable(self):
        """DateCoherenceResult debe ser inmutable (frozen)."""
        metadata = _create_test_metadata()
        result = _validate_date_coherence(metadata)

        with pytest.raises(AttributeError):
            result.is_valid = False  # type: ignore