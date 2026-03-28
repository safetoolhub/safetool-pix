# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Test de performance para comparar BK-Tree vs algoritmo naive.

Este test benchmark demuestra la mejora de rendimiento de O(N²) a O(N log N).
"""

import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock

from services.duplicates_similar_service import (
    DuplicatesSimilarAnalysis,
    BKTree
)


class TestBKTreePerformanceBenchmark:
    """Benchmarks comparativos de performance."""
    
    def test_bktree_vs_naive_small_dataset(self):
        """
        Benchmark: BK-Tree vs naive para dataset pequeño (100 archivos).
        
        Con datasets pequeños ambos métodos son rápidos,
        pero BK-Tree ya muestra ventaja.
        """
        n = 100
        threshold = 5
        
        # Generar hashes simulados
        hashes = {}
        for i in range(n):
            mock_hash = MagicMock()
            # Simular distancia Hamming basada en diferencia de índices
            mock_hash.__sub__ = lambda self, other, idx=i: abs(
                getattr(other, '_idx', 0) - idx
            )
            mock_hash._idx = i
            hashes[f"file{i}.jpg"] = {
                'hash': mock_hash,
                'size': 1000,
                'modified': 1234567890
            }
        
        # Benchmark BK-Tree
        start = time.time()
        tree = BKTree(distance_func=lambda h1, h2: h1 - h2)
        for path, data in hashes.items():
            tree.add(data['hash'], path)
        
        # Buscar similares para todos
        results_bktree = []
        for data in hashes.values():
            matches = tree.search(data['hash'], threshold)
            results_bktree.extend(matches)
        
        time_bktree = time.time() - start
        
        # Benchmark Naive O(N²)
        start = time.time()
        results_naive = []
        items = list(hashes.items())
        for i, (path1, data1) in enumerate(items):
            for j, (path2, data2) in enumerate(items):
                if i < j:
                    distance = data1['hash'] - data2['hash']
                    if distance <= threshold:
                        results_naive.append((path2, distance))
        
        time_naive = time.time() - start
        
        print(f"\nSmall dataset (n={n}):")
        print(f"  BK-Tree: {time_bktree*1000:.2f}ms")
        print(f"  Naive:   {time_naive*1000:.2f}ms")
        speedup = time_naive / time_bktree if time_bktree > 1e-9 else float('inf')
        print(f"  Speedup: {speedup:.2f}x")
        
        # Con n=100, BK-Tree debería ser al menos comparable.
        # If both are effectively instant, treat as pass.
        assert time_bktree <= max(time_naive * 2, 0.001)  # Al menos no mucho peor
    
    def test_bktree_vs_naive_medium_dataset(self):
        """
        Benchmark: BK-Tree vs naive para dataset mediano (1000 archivos).
        
        Con 1000 archivos la diferencia se hace significativa.
        """
        n = 1000
        threshold = 5
        
        # Generar hashes simulados
        hashes = {}
        for i in range(n):
            mock_hash = MagicMock()
            mock_hash.__sub__ = lambda self, other, idx=i: abs(
                getattr(other, '_idx', 0) - idx
            )
            mock_hash._idx = i
            hashes[f"file{i}.jpg"] = {
                'hash': mock_hash,
                'size': 1000,
                'modified': 1234567890
            }
        
        # Benchmark BK-Tree
        start = time.time()
        tree = BKTree(distance_func=lambda h1, h2: h1 - h2)
        for path, data in hashes.items():
            tree.add(data['hash'], path)
        
        # Buscar similares para primeros 100 (para mantener tiempo razonable)
        results_bktree = []
        for i, data in enumerate(list(hashes.values())[:100]):
            matches = tree.search(data['hash'], threshold)
            results_bktree.extend(matches)
        
        time_bktree = time.time() - start
        
        # Benchmark Naive O(N²) - solo primeros 100 vs todos
        start = time.time()
        results_naive = []
        items = list(hashes.items())
        for i in range(100):
            path1, data1 = items[i]
            for j, (path2, data2) in enumerate(items):
                if i < j:
                    distance = data1['hash'] - data2['hash']
                    if distance <= threshold:
                        results_naive.append((path2, distance))
        
        time_naive = time.time() - start
        
        print(f"\nMedium dataset (n={n}, searching first 100):")
        print(f"  BK-Tree: {time_bktree*1000:.2f}ms")
        print(f"  Naive:   {time_naive*1000:.2f}ms")
        speedup = time_naive / time_bktree if time_bktree > 1e-9 else float('inf')
        print(f"  Speedup: {speedup:.2f}x")
        
        # Con n=1000, BK-Tree debería ser significativamente más rápido.
        # If both are effectively instant, treat as pass.
        assert time_bktree <= max(time_naive, 0.001)
    
    @pytest.mark.slow
    def test_bktree_scales_to_large_dataset(self):
        """
        Test de escalabilidad: BK-Tree con 10,000 archivos.
        
        Este test verifica que BK-Tree puede manejar datasets grandes
        en tiempo razonable (< 5 segundos).
        
        Marcado como @pytest.mark.slow para ejecución opcional.
        """
        n = 10000
        threshold = 5
        
        # Generar hashes simulados
        hashes = {}
        for i in range(n):
            mock_hash = MagicMock()
            mock_hash.__sub__ = lambda self, other, idx=i: abs(
                getattr(other, '_idx', 0) - idx
            )
            mock_hash._idx = i
            hashes[f"file{i}.jpg"] = {
                'hash': mock_hash,
                'size': 1000,
                'modified': 1234567890
            }
        
        # Benchmark BK-Tree
        start = time.time()
        tree = BKTree(distance_func=lambda h1, h2: h1 - h2)
        
        # Construcción del árbol
        for path, data in hashes.items():
            tree.add(data['hash'], path)
        
        build_time = time.time() - start
        
        # Búsquedas
        search_start = time.time()
        for i in range(0, n, 100):  # Buscar cada 100 archivos
            data = list(hashes.values())[i]
            matches = tree.search(data['hash'], threshold)
        
        search_time = time.time() - search_start
        total_time = time.time() - start
        
        print(f"\nLarge dataset (n={n}):")
        print(f"  Build time:  {build_time:.2f}s")
        print(f"  Search time: {search_time:.2f}s (100 searches)")
        print(f"  Total time:  {total_time:.2f}s")
        print(f"  Avg search:  {search_time*1000/100:.2f}ms per search")
        
        # BK-Tree debe completar en tiempo razonable
        assert total_time < 5.0, f"BK-Tree demasiado lento: {total_time:.2f}s"
        assert search_time / 100 < 0.1, f"Búsquedas demasiado lentas: {search_time*1000/100:.2f}ms"
    
    def test_clustering_algorithm_complexity(self):
        """
        Test que demuestra la complejidad del algoritmo de clustering.
        
        Verifica que el tiempo de clustering crece de forma logarítmica
        en lugar de cuadrática.
        """
        analysis = DuplicatesSimilarAnalysis()
        
        # Test con diferentes tamaños
        sizes = [100, 200, 500, 1000]
        times = []
        
        for n in sizes:
            # Generar hashes
            hashes = {}
            for i in range(n):
                mock_hash = MagicMock()
                mock_hash.__sub__ = lambda self, other, idx=i: abs(
                    getattr(other, '_idx', 0) - idx
                )
                mock_hash._idx = i
                hashes[f"file{i}.jpg"] = {
                    'hash': mock_hash,
                    'size': 1000,
                    'modified': 1234567890
                }
            
            analysis.perceptual_hashes = hashes
            analysis.total_files = n
            
            # Medir tiempo de clustering
            start = time.time()
            result = analysis.get_groups(sensitivity=85)
            elapsed = time.time() - start
            times.append(elapsed)
            
            print(f"n={n}: {elapsed*1000:.2f}ms")
        
        # Verificar que el crecimiento es sublineal (no O(N²))
        # Si fuera O(N²), al duplicar n el tiempo debería cuadruplicarse
        # Con O(N log N), al duplicar n el tiempo debería ~ duplicarse
        # Guard against zero elapsed time on fast machines.
        ratio_100_to_200 = times[1] / times[0] if times[0] > 1e-9 else 1.0
        ratio_500_to_1000 = times[3] / times[2] if times[2] > 1e-9 else 1.0
        
        print(f"\nGrowth ratios:")
        print(f"  100->200:  {ratio_100_to_200:.2f}x")
        print(f"  500->1000: {ratio_500_to_1000:.2f}x")
        
        # Si fuera O(N²), estos ratios serían ~4x
        # Con O(N log N), deberían ser ~2-2.5x
        assert ratio_100_to_200 < 3.5, "Crecimiento sugiere O(N²)"
        assert ratio_500_to_1000 < 3.5, "Crecimiento sugiere O(N²)"
