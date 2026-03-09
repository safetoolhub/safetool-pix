# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests específicos para el parámetro force_search en get_all_metadata_from_file()

El parámetro force_search=True permite forzar la extracción de todos los metadatos
(hash, EXIF) ignorando la configuración de la aplicación en settings_manager.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from utils.date_utils import get_all_metadata_from_file
from services.file_metadata import FileMetadata


@pytest.mark.unit
class TestGetAllMetadataFromFileForceSearch:
    """Tests para el parámetro force_search en get_all_metadata_from_file()"""
    
    def test_force_search_false_respects_settings_no_hash(self, tmp_path):
        """Con force_search=False, debe respetar configuración (no calcular hash si disabled)"""
        # Crear archivo de prueba
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake image data")
        
        # Mock settings para deshabilitar todo
        with patch('utils.settings_manager.settings_manager') as mock_settings:
            mock_settings.get_precalculate_hashes.return_value = False
            mock_settings.get_precalculate_image_exif.return_value = False
            mock_settings.get_precalculate_video_exif.return_value = False
            
            # Mock repository vacío
            with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_file_metadata.return_value = None
                mock_repo.get_filesystem_metadata.return_value = None
                mock_repo.get_hash.return_value = None
                mock_repo.get_exif.return_value = None
                mock_repo_class.get_instance.return_value = mock_repo
                
                # Ejecutar sin force_search
                result = get_all_metadata_from_file(test_file, force_search=False)
                
                # Verificar que NO tiene hash (respeta configuración)
                assert result.sha256 is None
                assert result.exif_DateTimeOriginal is None
                
                # Verificar que SÍ tiene metadatos del filesystem (siempre disponibles)
                assert result.fs_size > 0
                assert result.fs_mtime is not None
    
    def test_force_search_true_bypasses_settings_hash(self, tmp_path):
        """Con force_search=True, debe calcular hash aunque esté disabled en settings"""
        # Crear archivo de prueba
        test_file = tmp_path / "test.jpg"
        test_content = b"fake image data for hash test"
        test_file.write_bytes(test_content)
        
        # Mock settings para deshabilitar hash
        with patch('utils.settings_manager.settings_manager') as mock_settings:
            mock_settings.get_precalculate_hashes.return_value = False  # Deshabilitado
            mock_settings.get_precalculate_image_exif.return_value = False
            mock_settings.get_precalculate_video_exif.return_value = False
            
            # Mock repository vacío
            with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_file_metadata.return_value = None
                mock_repo.get_filesystem_metadata.return_value = None
                mock_repo.get_hash.return_value = None
                mock_repo.get_exif.return_value = None
                mock_repo_class.get_instance.return_value = mock_repo
                
                # Mock calculate_file_hash para devolver un hash conocido
                with patch('utils.file_utils.calculate_file_hash') as mock_hash:
                    mock_hash.return_value = "abc123def456"
                    
                    # Ejecutar CON force_search
                    result = get_all_metadata_from_file(test_file, force_search=True)
                    
                    # Verificar que SÍ calculó el hash (ignoró configuración)
                    assert result.sha256 == "abc123def456"
                    mock_hash.assert_called_once_with(test_file)
    
    def test_force_search_true_bypasses_settings_image_exif(self, tmp_path):
        """Con force_search=True, debe extraer EXIF de imágenes aunque esté disabled"""
        # Crear archivo de prueba
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake image data")
        
        # Mock settings para deshabilitar EXIF de imágenes
        with patch('utils.settings_manager.settings_manager') as mock_settings:
            mock_settings.get_precalculate_hashes.return_value = False
            mock_settings.get_precalculate_image_exif.return_value = False  # Deshabilitado
            mock_settings.get_precalculate_video_exif.return_value = False
            
            # Mock repository vacío
            with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_file_metadata.return_value = None
                mock_repo.get_filesystem_metadata.return_value = None
                mock_repo.get_hash.return_value = None
                mock_repo.get_exif.return_value = None
                mock_repo_class.get_instance.return_value = mock_repo
                
                # Mock is_image_file para simular que es imagen
                with patch('utils.file_utils.is_image_file') as mock_is_image:
                    mock_is_image.return_value = True
                    
                    # Mock get_exif_from_image para devolver EXIF
                    with patch('utils.file_utils.get_exif_from_image') as mock_exif:
                        mock_exif.return_value = {
                            'DateTimeOriginal': datetime(2023, 1, 15, 10, 30, 0),
                            'CreateDate': datetime(2023, 1, 15, 10, 30, 5)
                        }
                        
                        # Ejecutar CON force_search
                        result = get_all_metadata_from_file(test_file, force_search=True)
                        
                        # Verificar que SÍ extrajo EXIF (ignoró configuración)
                        assert result.exif_DateTimeOriginal is not None
                        assert '2023-01-15T10:30:00' in result.exif_DateTimeOriginal
                        mock_exif.assert_called_once_with(test_file)
    
    def test_force_search_true_bypasses_settings_video_exif(self, tmp_path):
        """Con force_search=True, debe extraer EXIF de videos aunque esté disabled"""
        # Crear archivo de prueba
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake video data")
        
        # Mock settings para deshabilitar EXIF de videos
        with patch('utils.settings_manager.settings_manager') as mock_settings:
            mock_settings.get_precalculate_hashes.return_value = False
            mock_settings.get_precalculate_image_exif.return_value = False
            mock_settings.get_precalculate_video_exif.return_value = False  # Deshabilitado
            
            # Mock repository vacío
            with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_file_metadata.return_value = None
                mock_repo.get_filesystem_metadata.return_value = None
                mock_repo.get_hash.return_value = None
                mock_repo.get_exif.return_value = None
                mock_repo_class.get_instance.return_value = mock_repo
                
                # Mock is_video_file para simular que es video
                with patch('utils.file_utils.is_video_file') as mock_is_video:
                    mock_is_video.return_value = True
                    
                    # Mock is_image_file debe retornar False
                    with patch('utils.file_utils.is_image_file') as mock_is_image:
                        mock_is_image.return_value = False
                        
                        # Mock get_exif_from_video para devolver fecha
                        with patch('utils.file_utils.get_exif_from_video') as mock_video_exif:
                            mock_video_exif.return_value = {'creation_time': datetime(2023, 1, 15, 10, 30, 0)}
                            
                            # Ejecutar CON force_search
                            result = get_all_metadata_from_file(test_file, force_search=True)
                            
                            # Verificar que SÍ extrajo metadata de video (ignoró configuración)
                            assert result.exif_DateTime is not None
                            # El formato puede ser '2023:01:15 10:30:00' o '2023-01-15T10:30:00'
                            assert '2023' in result.exif_DateTime and '01' in result.exif_DateTime and '15' in result.exif_DateTime
                            mock_video_exif.assert_called_once_with(test_file)
    
    def test_force_search_true_extracts_all_metadata_types(self, tmp_path):
        """Con force_search=True, debe extraer TODOS los tipos de metadata en una sola llamada"""
        # Crear archivo de prueba
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake comprehensive data")
        
        # Mock settings para deshabilitar TODO
        with patch('utils.settings_manager.settings_manager') as mock_settings:
            mock_settings.get_precalculate_hashes.return_value = False
            mock_settings.get_precalculate_image_exif.return_value = False
            mock_settings.get_precalculate_video_exif.return_value = False
            
            # Mock repository vacío
            with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_file_metadata.return_value = None
                mock_repo.get_filesystem_metadata.return_value = None
                mock_repo.get_hash.return_value = None
                mock_repo.get_exif.return_value = None
                mock_repo_class.get_instance.return_value = mock_repo
                
                with patch('utils.file_utils.is_image_file') as mock_is_image:
                    mock_is_image.return_value = True
                    
                    with patch('utils.file_utils.calculate_file_hash') as mock_hash:
                        mock_hash.return_value = "full_hash_123"
                        
                        with patch('utils.file_utils.get_exif_from_image') as mock_exif:
                            mock_exif.return_value = {
                                'DateTimeOriginal': datetime(2023, 1, 15, 10, 30, 0),
                                'CreateDate': datetime(2023, 1, 15, 10, 30, 5),
                                'GPSDateStamp': datetime(2023, 1, 15, 10, 0, 0)
                            }
                            
                            # Ejecutar CON force_search
                            result = get_all_metadata_from_file(test_file, force_search=True)
                            
                            # Verificar que tiene TODO (filesystem + hash + EXIF)
                            assert result.fs_size > 0  # Filesystem
                            assert result.fs_mtime is not None
                            assert result.sha256 == "full_hash_123"  # Hash
                            assert result.exif_DateTimeOriginal is not None  # EXIF
                            assert result.exif_DateTime is not None
                            assert result.exif_GPSDateStamp is not None
                            
                            # Verificar que se llamaron los métodos de extracción
                            mock_hash.assert_called_once()
                            mock_exif.assert_called_once()
    
    def test_force_search_false_uses_cache_when_available(self, tmp_path):
        """Con force_search=False, debe usar caché si está disponible"""
        # Crear archivo de prueba
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"cached data")
        
        # Crear metadata en caché
        cached_metadata = FileMetadata(
            path=test_file.resolve(),
            fs_size=100,
            fs_ctime=1609459200.0,
            fs_mtime=1609459200.0,
            fs_atime=1609459200.0,
            sha256="cached_hash_abc",
            exif_DateTimeOriginal="2023-01-15T10:30:00",
            exif_DateTime="2023-01-15T10:30:05"
        )
        
        # Mock repository con datos en caché
        with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_file_metadata.return_value = cached_metadata  # Caché hit
            mock_repo_class.get_instance.return_value = mock_repo
            
            # No debería llamar a ningún método de extracción
            with patch('utils.file_utils.calculate_file_hash') as mock_hash:
                with patch('utils.file_utils.get_exif_from_image') as mock_exif:
                    
                    # Ejecutar sin force_search
                    result = get_all_metadata_from_file(test_file, force_search=False)
                    
                    # Verificar que devolvió datos del caché
                    assert result.sha256 == "cached_hash_abc"
                    assert result.exif_DateTimeOriginal == "2023-01-15T10:30:00"
                    
                    # Verificar que NO llamó a métodos de extracción (usó caché)
                    mock_hash.assert_not_called()
                    mock_exif.assert_not_called()
    
    def test_force_search_parameter_default_value(self, tmp_path):
        """El parámetro force_search debe tener False como valor por defecto"""
        # Crear archivo de prueba
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"default test")
        
        # Mock settings para deshabilitar hash
        with patch('utils.settings_manager.settings_manager') as mock_settings:
            mock_settings.get_precalculate_hashes.return_value = False
            
            # Mock repository vacío
            with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_file_metadata.return_value = None
                mock_repo.get_filesystem_metadata.return_value = None
                mock_repo.get_hash.return_value = None
                mock_repo_class.get_instance.return_value = mock_repo
                
                with patch('utils.file_utils.calculate_file_hash') as mock_hash:
                    mock_hash.return_value = "should_not_be_called"
                    
                    # Llamar SIN especificar force_search (usar default)
                    result = get_all_metadata_from_file(test_file)
                    
                    # Por defecto (force_search=False), debe respetar settings
                    # Como hash está deshabilitado, NO debe calcular hash
                    assert result.sha256 is None
                    mock_hash.assert_not_called()


@pytest.mark.unit
class TestForceSearchUseCase:
    """Tests de casos de uso reales para force_search"""
    
    def test_dialog_file_details_use_case(self, tmp_path):
        """
        Caso de uso: Diálogo de detalles de archivo
        El usuario hace clic en "Ver detalles" en un archivo.
        El diálogo debe mostrar TODOS los metadatos disponibles,
        independientemente de la configuración global.
        """
        # Crear archivo de prueba
        test_file = tmp_path / "user_selected.jpg"
        test_file.write_bytes(b"user wants to see details")
        
        # Configuración global: TODO deshabilitado (usuario no quiere precálculo)
        with patch('utils.settings_manager.settings_manager') as mock_settings:
            mock_settings.get_precalculate_hashes.return_value = False
            mock_settings.get_precalculate_image_exif.return_value = False
            mock_settings.get_precalculate_video_exif.return_value = False
            
            # Caché vacío (archivo no ha sido escaneado)
            with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_file_metadata.return_value = None
                mock_repo.get_filesystem_metadata.return_value = None
                mock_repo.get_hash.return_value = None
                mock_repo.get_exif.return_value = None
                mock_repo_class.get_instance.return_value = mock_repo
                
                with patch('utils.file_utils.is_image_file', return_value=True):
                    with patch('utils.file_utils.calculate_file_hash', return_value="on_demand_hash"):
                        with patch('utils.file_utils.get_exif_from_image', return_value={
                            'DateTimeOriginal': datetime(2023, 1, 15, 10, 30, 0)
                        }):
                            # Diálogo llama con force_search=True para obtener TODO
                            result = get_all_metadata_from_file(test_file, force_search=True)
                            
                            # Verificar que obtuvo TODOS los metadatos para mostrar
                            assert result.sha256 == "on_demand_hash"
                            assert result.exif_DateTimeOriginal is not None
                            # El usuario ve la información completa en el diálogo


@pytest.mark.unit  
class TestForceSearchEdgeCases:
    """Tests de casos límite para force_search"""
    
    def test_force_search_with_error_in_hash_calculation(self, tmp_path):
        """force_search=True debe manejar errores en cálculo de hash gracefully"""
        test_file = tmp_path / "error_test.jpg"
        test_file.write_bytes(b"error prone")
        
        with patch('utils.settings_manager.settings_manager') as mock_settings:
            mock_settings.get_precalculate_hashes.return_value = False
            mock_settings.get_precalculate_image_exif.return_value = False
            
            with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_file_metadata.return_value = None
                mock_repo.get_filesystem_metadata.return_value = None
                mock_repo.get_hash.return_value = None
                mock_repo.get_exif.return_value = None
                mock_repo_class.get_instance.return_value = mock_repo
                
                # Mock hash que lanza error
                with patch('utils.file_utils.calculate_file_hash', side_effect=Exception("Hash error")):
                    
                    # No debe lanzar excepción, debe continuar
                    result = get_all_metadata_from_file(test_file, force_search=True)
                    
                    # Debe tener metadatos básicos aunque falló el hash
                    assert result.fs_size > 0
                    assert result.sha256 is None  # Hash falló, pero no rompe
    
    def test_force_search_with_error_in_exif_extraction(self, tmp_path):
        """force_search=True debe manejar errores en extracción de EXIF gracefully"""
        test_file = tmp_path / "corrupt_exif.jpg"
        test_file.write_bytes(b"corrupt exif data")
        
        with patch('utils.settings_manager.settings_manager') as mock_settings:
            mock_settings.get_precalculate_hashes.return_value = False
            mock_settings.get_precalculate_image_exif.return_value = False
            
            with patch('services.file_metadata_repository_cache.FileInfoRepositoryCache') as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_file_metadata.return_value = None
                mock_repo.get_filesystem_metadata.return_value = None
                mock_repo.get_hash.return_value = None
                mock_repo.get_exif.return_value = None
                mock_repo_class.get_instance.return_value = mock_repo
                
                with patch('utils.file_utils.is_image_file', return_value=True):
                    # Mock EXIF que lanza error
                    with patch('utils.file_utils.get_exif_from_image', side_effect=Exception("EXIF error")):
                        
                        # No debe lanzar excepción
                        result = get_all_metadata_from_file(test_file, force_search=True)
                        
                        # Debe tener metadatos básicos aunque falló EXIF
                        assert result.fs_size > 0
                        assert result.exif_DateTimeOriginal is None  # EXIF falló, pero no rompe
