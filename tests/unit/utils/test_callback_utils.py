# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para utils/callback_utils.py
"""
import pytest
from utils.callback_utils import safe_progress_callback


@pytest.mark.unit
class TestSafeProgressCallback:
    """Tests para safe_progress_callback()"""
    
    def test_callback_executed(self):
        """Test que el callback se ejecuta correctamente"""
        results = []
        
        def callback(current, total, message):
            results.append((current, total, message))
        
        result = safe_progress_callback(callback, 50, 100, "Processing")
        
        assert result is True
        assert len(results) == 1
        assert results[0] == (50, 100, "Processing")
    
    def test_callback_returns_false(self):
        """Test que si callback retorna False, se propaga"""
        def callback(current, total, message):
            return False
        
        result = safe_progress_callback(callback, 50, 100, "Processing")
        
        assert result is False
    
    def test_callback_none(self):
        """Test que None callback no causa error"""
        result = safe_progress_callback(None, 50, 100, "Processing")
        
        assert result is True
    
    def test_callback_raises_exception(self):
        """Test que excepciones en callback no se propagan"""
        def callback(current, total, message):
            raise ValueError("Test error")
        
        # No debe lanzar excepción
        result = safe_progress_callback(callback, 50, 100, "Processing")
        
        assert result is True  # Continúa el proceso
