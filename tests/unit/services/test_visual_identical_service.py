# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para VisualIdenticalService - Detección de copias visuales idénticas.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.visual_identical_service import VisualIdenticalService
from services.result_types import VisualIdenticalAnalysisResult, VisualIdenticalGroup
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from services.file_metadata import FileMetadata


class TestVisualIdenticalServiceBasics:
    """Tests básicos del servicio."""
    
    def setup_method(self):
        """Setup para cada test."""
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
        self.service = VisualIdenticalService()
    
    def teardown_method(self):
        """Cleanup después de cada test."""
        self.repo.clear()
    
    def test_service_initialization(self):
        """Verifica que el servicio se inicializa correctamente."""
        assert self.service is not None
        assert self.service.logger is not None
    
    def test_analyze_empty_repository_returns_no_groups(self):
        """Con repositorio vacío, no debe encontrar grupos."""
        result = self.service.analyze()
        
        assert isinstance(result, VisualIdenticalAnalysisResult)
        assert result.success is True
        assert result.groups == []
        assert result.total_groups == 0


class TestVisualIdenticalServiceAnalyze:
    """Tests del método analyze()."""
    
    def setup_method(self):
        """Setup para cada test."""
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
        self.service = VisualIdenticalService()
    
    def teardown_method(self):
        """Cleanup después de cada test."""
        self.repo.clear()
    
    def test_analyze_returns_correct_result_type(self):
        """El método analyze() debe retornar VisualIdenticalAnalysisResult."""
        result = self.service.analyze()
        
        assert isinstance(result, VisualIdenticalAnalysisResult)
        assert hasattr(result, 'groups')
        assert hasattr(result, 'total_groups')
        assert hasattr(result, 'total_files')
        assert hasattr(result, 'space_recoverable')


class TestVisualIdenticalGroup:
    """Tests para la dataclass VisualIdenticalGroup."""
    
    def test_group_properties(self, tmp_path):
        """Verifica las propiedades calculadas del grupo."""
        # Crear archivos temporales de diferentes tamaños
        file1 = tmp_path / "image1.jpg"
        file2 = tmp_path / "image2.jpg"
        file3 = tmp_path / "image3.jpg"
        
        file1.write_bytes(b"x" * 1000)  # 1KB
        file2.write_bytes(b"y" * 2000)  # 2KB
        file3.write_bytes(b"z" * 500)   # 0.5KB
        
        # El grupo debe ser creado con file_sizes explícito
        group = VisualIdenticalGroup(
            hash_value="abc123",
            files=[file1, file2, file3],
            file_sizes=[1000, 2000, 500],
            total_size=3500,
            space_recoverable=1500,  # total - max (3500 - 2000)
            size_variation_percent=300.0  # (max - min) / min * 100
        )
        
        # Verificar propiedades
        assert group.file_count == 3
        assert group.largest_file == file2
        assert group.smallest_file == file3
    
    def test_group_largest_and_smallest_file(self, tmp_path):
        """Verifica las propiedades largest_file y smallest_file."""
        file1 = tmp_path / "small.jpg"
        file2 = tmp_path / "large.jpg"
        
        file1.write_bytes(b"x" * 100)
        file2.write_bytes(b"y" * 1000)
        
        group = VisualIdenticalGroup(
            hash_value="abc123",
            files=[file1, file2],
            file_sizes=[100, 1000]
        )
        
        assert group.largest_file == file2
        assert group.smallest_file == file1


class TestVisualIdenticalServiceExecute:
    """Tests del método execute()."""
    
    def setup_method(self):
        """Setup para cada test."""
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
        self.service = VisualIdenticalService()
    
    def teardown_method(self):
        """Cleanup después de cada test."""
        self.repo.clear()
    
    def test_execute_dry_run_does_not_delete(self, tmp_path):
        """En modo dry_run no debe eliminar archivos."""
        # Crear archivos
        file1 = tmp_path / "keep.jpg"
        file2 = tmp_path / "delete.jpg"
        
        file1.write_bytes(b"x" * 1000)
        file2.write_bytes(b"y" * 500)
        
        group = VisualIdenticalGroup(
            hash_value="abc123",
            files=[file1, file2]
        )
        
        result = self.service.execute(
            groups=[group],
            files_to_delete=[file2],
            create_backup=False,
            dry_run=True
        )
        
        assert result.success is True
        assert result.dry_run is True
        assert file2.exists()  # No debe haberse eliminado
    
    def test_execute_real_deletion(self, tmp_path):
        """Verifica que la eliminación real funciona."""
        # Crear archivos
        file1 = tmp_path / "keep.jpg"
        file2 = tmp_path / "delete.jpg"
        
        file1.write_bytes(b"x" * 1000)
        file2.write_bytes(b"y" * 500)
        
        group = VisualIdenticalGroup(
            hash_value="abc123",
            files=[file1, file2]
        )
        
        result = self.service.execute(
            groups=[group],
            files_to_delete=[file2],
            create_backup=False,
            dry_run=False
        )
        
        assert result.success is True
        assert result.dry_run is False
        assert file1.exists()  # El archivo a conservar sigue existiendo
        assert not file2.exists()  # El archivo a eliminar fue eliminado


class TestKeepStrategies:
    """Tests para las estrategias de conservación usando propiedades del grupo."""
    
    def test_largest_file_property(self, tmp_path):
        """Verifica que largest_file devuelve el archivo correcto."""
        small = tmp_path / "small.jpg"
        large = tmp_path / "large.jpg"
        
        small.write_bytes(b"x" * 100)
        large.write_bytes(b"y" * 1000)
        
        group = VisualIdenticalGroup(
            hash_value="abc123",
            files=[small, large],
            file_sizes=[100, 1000]
        )
        
        assert group.largest_file == large
    
    def test_smallest_file_property(self, tmp_path):
        """Verifica que smallest_file devuelve el archivo correcto."""
        small = tmp_path / "small.jpg"
        large = tmp_path / "large.jpg"
        
        small.write_bytes(b"x" * 100)
        large.write_bytes(b"y" * 1000)
        
        group = VisualIdenticalGroup(
            hash_value="abc123",
            files=[small, large],
            file_sizes=[100, 1000]
        )
        
        assert group.smallest_file == small
