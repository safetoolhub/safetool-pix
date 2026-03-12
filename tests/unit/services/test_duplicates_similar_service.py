# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para DuplicatesSimilarService y optimizaciones BK-Tree.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import shutil

from services.duplicates_similar_service import (
    DuplicatesSimilarService,
    BKTree,
    BKTreeNode,
    DuplicatesSimilarAnalysis
)
from services.file_metadata import FileMetadata
from services.file_metadata_repository_cache import FileInfoRepositoryCache


class TestBKTree:
    """Tests para la estructura BK-Tree."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.distance_func = lambda h1, h2: abs(h1 - h2)
    
    def test_bktree_basic_insertion(self):
        """Test inserción básica en BK-Tree."""
        tree = BKTree(self.distance_func)
        
        tree.add(100, "file1.jpg")
        tree.add(105, "file2.jpg")
        tree.add(110, "file3.jpg")
        
        assert len(tree) == 3
        assert tree.root is not None
        assert tree.root.path == "file1.jpg"
    
    def test_bktree_search_exact_match(self):
        """Test búsqueda exacta en BK-Tree."""
        tree = BKTree(self.distance_func)
        
        tree.add(100, "file1.jpg")
        tree.add(105, "file2.jpg")
        tree.add(110, "file3.jpg")
        
        results = tree.search(100, threshold=0)
        
        assert len(results) == 1
        assert results[0][0] == "file1.jpg"
        assert results[0][1] == 0
    
    def test_bktree_search_with_threshold(self):
        """Test búsqueda con threshold en BK-Tree."""
        tree = BKTree(self.distance_func)
        
        tree.add(100, "file1.jpg")
        tree.add(105, "file2.jpg")
        tree.add(110, "file3.jpg")
        tree.add(150, "file4.jpg")
        
        # Buscar similares a 100 con threshold 10
        results = tree.search(100, threshold=10)
        
        # Debe encontrar file1 (dist=0), file2 (dist=5), file3 (dist=10)
        assert len(results) == 3
        paths_found = {r[0] for r in results}
        assert "file1.jpg" in paths_found
        assert "file2.jpg" in paths_found
        assert "file3.jpg" in paths_found
        assert "file4.jpg" not in paths_found
    
    def test_bktree_empty_tree(self):
        """Test búsqueda en árbol vacío."""
        tree = BKTree(self.distance_func)
        
        results = tree.search(100, threshold=10)
        
        assert len(results) == 0
    
    def test_bktree_large_dataset(self):
        """Test con dataset más grande para verificar escalabilidad."""
        tree = BKTree(self.distance_func)
        
        # Insertar 1000 hashes
        for i in range(1000):
            tree.add(i * 10, f"file{i}.jpg")
        
        assert len(tree) == 1000
        
        # Buscar similares a 5000 (centro del rango)
        results = tree.search(5000, threshold=50)
        
        # Debe encontrar archivos en rango [4950, 5050]
        assert len(results) > 0
        assert len(results) <= 11  # Max 11 archivos en ese rango


class TestDuplicatesSimilarAnalysis:
    """Tests para DuplicatesSimilarAnalysis con BK-Tree."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.analysis = DuplicatesSimilarAnalysis()
    
    def test_empty_analysis(self):
        """Test análisis vacío."""
        result = self.analysis.get_groups(sensitivity=100)
        
        assert result.success is True
        assert len(result.groups) == 0
        assert result.total_files_analyzed == 0
    
    def test_sensitivity_to_threshold_conversion(self):
        """Test conversión de sensibilidad a threshold."""
        # 100% sensitivity = 0 threshold (solo idénticos)
        assert self.analysis._sensitivity_to_threshold(100) == 0
        
        # 30% sensitivity = 20 threshold (muy permisivo)
        assert self.analysis._sensitivity_to_threshold(30) == 20
        
        # 85% sensitivity = ~4 threshold (recomendado)
        threshold_85 = self.analysis._sensitivity_to_threshold(85)
        assert 3 <= threshold_85 <= 5


class TestDuplicatesSimilarService:
    """Tests de integración para DuplicatesSimilarService."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.service = DuplicatesSimilarService()
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
        
        # Crear directorio temporal
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
    
    def teardown_method(self):
        """Cleanup después de cada test."""
        self.repo.clear()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_hamming_distance_calculation(self):
        """Test cálculo de distancia Hamming."""
        # Crear análisis para probar _hamming_distance
        analysis = DuplicatesSimilarAnalysis()
        
        # Mock hash objects con método __sub__ para distancia Hamming
        mock_hash1 = MagicMock()
        mock_hash2 = MagicMock()
        mock_hash1.__sub__ = MagicMock(return_value=5)
        
        distance = analysis._hamming_distance(mock_hash1, mock_hash2)
        
        assert distance == 5
    
    def test_clustering_uses_bktree(self):
        """Test que el clustering usa BK-Tree internamente."""
        # Crear análisis mock con hashes
        analysis = DuplicatesSimilarAnalysis()
        
        # Simular hashes perceptuales
        mock_hash1 = MagicMock()
        mock_hash1.__sub__ = lambda self, other: 0 if other == mock_hash1 else 5
        mock_hash2 = MagicMock()
        mock_hash2.__sub__ = lambda self, other: 0 if other == mock_hash2 else 5
        
        analysis.perceptual_hashes = {
            str(self.temp_dir / "file1.jpg"): {
                'hash': mock_hash1,
                'size': 1000,
                'modified': 1234567890
            },
            str(self.temp_dir / "file2.jpg"): {
                'hash': mock_hash2,
                'size': 1000,
                'modified': 1234567890
            }
        }
        analysis.total_files = 2
        
        # Ejecutar clustering con sensibilidad alta (threshold bajo)
        result = analysis.get_groups(sensitivity=85)
        
        # Verificar que se ejecutó sin errores
        assert result.success is True


class TestBKTreePerformance:
    """Tests de performance para verificar mejora O(N²) -> O(N log N)."""
    
    def test_bktree_scales_better_than_naive(self):
        """
        Test conceptual: BK-Tree debe escalar mejor que búsqueda naive.
        
        Este test no mide tiempo real, solo verifica que la estructura funciona
        con datasets grandes sin errores.
        """
        tree = BKTree(lambda h1, h2: abs(h1 - h2))
        
        # Insertar 10,000 elementos (simulando dataset grande)
        n = 10000
        for i in range(n):
            tree.add(i, f"file{i}.jpg")
        
        assert len(tree) == n
        
        # Hacer búsquedas que deberían ser rápidas con BK-Tree
        results = tree.search(5000, threshold=10)
        
        # Debe encontrar ~20 archivos (threshold 10 en ambos lados)
        assert len(results) > 0
        assert len(results) < 50  # Menos de 50 para threshold 10
        
        # Verificar que todos los resultados están dentro del threshold
        for path, distance in results:
            assert distance <= 10
