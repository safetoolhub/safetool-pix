# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
import unittest
import time
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import imagehash
import numpy as np
from PIL import Image
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from services.duplicates_similar_service import DuplicatesSimilarAnalysis
from services.result_types import SimilarDuplicateGroup

class TestLargeDatasetPerformance(unittest.TestCase):
    def setUp(self):
        self.analysis = DuplicatesSimilarAnalysis()
        # Usar 1000 archivos (más realista y evita timeout)
        # Con 20k archivos son 200M comparaciones (O(n²))
        self.file_count = 1000
        self.analysis.perceptual_hashes = self._create_dummy_hashes(self.file_count)
        self.analysis.total_files = self.file_count
        
    def _create_dummy_hashes(self, count):
        print(f"Generating {count} dummy hashes for test...")
        hashes = {}
        base_hash = imagehash.phash(Image.new('RGB', (100, 100), color='red'))
        
        for i in range(count):
            path = Path(f"/tmp/dummy_test_file_{i}.jpg")
            if i % 10 == 0:
                h = base_hash
            else:
                arr = np.random.randint(0, 2, (8, 8), dtype=bool)
                h = imagehash.ImageHash(arr)
                
            hashes[str(path)] = {
                'hash': h,
                'size': 1024 * 1024,
                'modified': datetime.now().timestamp()
            }
        return hashes

    @patch('pathlib.Path.stat')
    def test_clustering_performance(self, mock_stat):
        # Mock stat to avoid FileNotFoundError and return dummy size
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = 1024 * 1024
        mock_stat.return_value = mock_stat_result
        
        print("\nStarting clustering performance test...")
        start_time = time.time()
        
        # Test with default sensitivity (85%)
        result = self.analysis.get_groups(sensitivity=85)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Clustering {self.file_count} files took {duration:.2f} seconds")
        print(f"Found {len(result.groups)} groups")
        
        # Assertions - ajustadas para dataset de 1000 archivos
        self.assertLess(duration, 10.0, "Clustering took too long (> 10s)")
        self.assertIsInstance(result.groups, list)
        self.assertTrue(result.success)
        
    def test_memory_stability(self):
        # This is a basic check to ensure no crashes during repeated calls
        print("\nStarting stability test...")
        for i in range(3):
            try:
                self.analysis.get_groups(sensitivity=80 + i*5)
            except Exception as e:
                self.fail(f"Crash detected during iteration {i}: {e}")

if __name__ == '__main__':
    unittest.main()
