# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para utils/screen_utils.py
"""
import pytest
from utils.screen_utils import (
    ScreenResolution,
    WindowSizeConfig,
    ScreenDetector,
    get_optimal_window_config
)


@pytest.mark.unit
class TestScreenResolution:
    """Tests para ScreenResolution"""
    
    def test_init(self):
        """Test inicialización"""
        res = ScreenResolution(1920, 1080)
        assert res.width == 1920
        assert res.height == 1080
    
    def test_str_representation(self):
        """Test representación string"""
        res = ScreenResolution(1920, 1080)
        assert str(res) == "1920x1080"
    
    def test_repr(self):
        """Test repr"""
        res = ScreenResolution(1920, 1080)
        repr_str = repr(res)
        assert "1920" in repr_str
        assert "1080" in repr_str
    
    def test_is_fullhd_or_smaller_true(self):
        """Test detección de FullHD o menor"""
        res = ScreenResolution(1920, 1080)
        assert res.is_fullhd_or_smaller is True
        
        res_smaller = ScreenResolution(1366, 768)
        assert res_smaller.is_fullhd_or_smaller is True
    
    def test_is_fullhd_or_smaller_false(self):
        """Test detección de mayor que FullHD"""
        res = ScreenResolution(2560, 1440)
        assert res.is_fullhd_or_smaller is False
    
    def test_is_larger_than_fullhd_true(self):
        """Test detección de mayor que FullHD"""
        res = ScreenResolution(2560, 1440)
        assert res.is_larger_than_fullhd is True
        
        res_4k = ScreenResolution(3840, 2160)
        assert res_4k.is_larger_than_fullhd is True
    
    def test_is_larger_than_fullhd_false(self):
        """Test detección de FullHD o menor"""
        res = ScreenResolution(1920, 1080)
        assert res.is_larger_than_fullhd is False
        
        res_smaller = ScreenResolution(1366, 768)
        assert res_smaller.is_larger_than_fullhd is False


@pytest.mark.unit
class TestWindowSizeConfig:
    """Tests para WindowSizeConfig"""
    
    def test_get_optimal_window_size_fullhd(self):
        """Test tamaño óptimo para FullHD"""
        screen = ScreenResolution(1920, 1080)
        action, size = WindowSizeConfig.get_optimal_window_size(screen)
        
        assert action in ['maximize', 'resize']
        if action == 'resize':
            assert size is not None
            assert isinstance(size, ScreenResolution)
    
    def test_get_optimal_window_size_large_screen(self):
        """Test tamaño óptimo para pantalla grande"""
        screen = ScreenResolution(2560, 1440)
        action, size = WindowSizeConfig.get_optimal_window_size(screen)
        
        assert action in ['maximize', 'resize']
        if action == 'resize':
            assert size is not None
    
    def test_calculate_center_position(self):
        """Test cálculo de posición centrada"""
        screen = ScreenResolution(1920, 1080)
        window = ScreenResolution(800, 600)
        
        x, y = WindowSizeConfig.calculate_center_position(screen, window)
        
        assert x == (1920 - 800) // 2
        assert y == (1080 - 600) // 2
        assert x >= 0
        assert y >= 0


@pytest.mark.unit
class TestScreenDetector:
    """Tests para ScreenDetector"""
    
    def test_init_default(self):
        """Test inicialización por defecto"""
        detector = ScreenDetector()
        assert detector is not None
    
    def test_get_primary_screen_resolution(self):
        """Test obtención de resolución de pantalla"""
        detector = ScreenDetector()
        resolution = detector.get_primary_screen_resolution()
        
        assert isinstance(resolution, ScreenResolution)
        assert resolution.width > 0
        assert resolution.height > 0


@pytest.mark.unit
class TestGetOptimalWindowConfig:
    """Tests para get_optimal_window_config"""
    
    def test_returns_tuple(self):
        """Test que retorna tupla con configuración"""
        result = get_optimal_window_config()
        
        assert isinstance(result, tuple)
        assert len(result) == 3
        
        action, size, position = result
        assert action in ['maximize', 'resize']
        
        if action == 'resize':
            assert size is not None
            assert position is not None
