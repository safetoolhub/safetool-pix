# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para la lógica de configuración de tamaño de ventana de SafeTool Pix
"""
import pytest
from unittest.mock import Mock, patch
from ui.styles.design_system import DesignSystem
from utils.screen_utils import (
    ScreenResolution,
    WindowSizeConfig,
    ScreenDetector,
    get_optimal_window_config
)


class TestWindowSizeLogic:
    """
    Tests para la lógica de determinación del tamaño de ventana
    basado en la resolución del monitor.
    """

    @pytest.mark.parametrize("screen_width,screen_height,expected_action,expected_size", [
        # Monitores FullHD o inferiores -> Maximizar
        (DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT, "maximize", None),
        (1366, 768, "maximize", None),
        (1280, 720, "maximize", None),
        (800, 600, "maximize", None),

        # Monitores 2K+ -> FullHD centrado
        (2560, 1440, "resize", (DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)),
        (2880, 1800, "resize", (DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)),
        (3840, 2160, "resize", (DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)),
        (3440, 1440, "resize", (DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)),

        # Casos borde
        (DesignSystem.FULLHD_WIDTH + 1, DesignSystem.FULLHD_HEIGHT, "resize", (DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)),  # Un pixel más -> FullHD
        (DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT + 1, "resize", (DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)),  # Un pixel más -> FullHD
        (DesignSystem.FULLHD_WIDTH + 1, DesignSystem.FULLHD_HEIGHT + 1, "resize", (DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)),  # Ambos -> FullHD
    ])
    def test_window_size_logic(self, screen_width, screen_height, expected_action, expected_size):
        """
        Test que verifica la lógica de determinación del tamaño de ventana
        basado en la resolución del monitor.

        Args:
            screen_width: Ancho del monitor en pixels
            screen_height: Alto del monitor en pixels
            expected_action: Acción esperada ('maximize' o 'resize')
            expected_size: Tamaño esperado si se hace resize (ancho, alto)
        """
        screen_res = ScreenResolution(screen_width, screen_height)
        action, size = WindowSizeConfig.get_optimal_window_size(screen_res)

        assert action == expected_action, f"Para {screen_res} se esperaba {expected_action}, pero se obtuvo {action}"
        if expected_size:
            assert size is not None and size.width == expected_size[0] and size.height == expected_size[1], f"Para {screen_res} se esperaba tamaño {expected_size}, pero se obtuvo {size}"
        else:
            assert size is None, f"Para {screen_res} se esperaba tamaño None, pero se obtuvo {size}"

    def test_window_centering_calculation(self):
        """
        Test que verifica el cálculo correcto del centrado de la ventana FullHD
        en monitores de diferentes tamaños.
        """
        test_cases = [
            # (screen_width, screen_height, expected_x, expected_y)
            (2560, 1440, (2560-DesignSystem.FULLHD_WIDTH)//2, (1440-DesignSystem.FULLHD_HEIGHT)//2),  # 2K
            (2880, 1800, (2880-DesignSystem.FULLHD_WIDTH)//2, (1800-DesignSystem.FULLHD_HEIGHT)//2),  # Retina
            (3840, 2160, (3840-DesignSystem.FULLHD_WIDTH)//2, (2160-DesignSystem.FULLHD_HEIGHT)//2),  # 4K
        ]

        for screen_width, screen_height, expected_x, expected_y in test_cases:
            screen_res = ScreenResolution(screen_width, screen_height)
            window_size = ScreenResolution(DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)
            center_x, center_y = WindowSizeConfig.calculate_center_position(screen_res, window_size)

            assert center_x == expected_x, f"Centro X incorrecto para {screen_res}"
            assert center_y == expected_y, f"Centro Y incorrecto para {screen_res}"

    def test_screen_resolution_class(self):
        """
        Test que verifica la funcionalidad de la clase ScreenResolution
        """
        res = ScreenResolution(1920, 1080)

        assert str(res) == "1920x1080"
        assert repr(res) == "ScreenResolution(1920, 1080)"
        assert res.is_fullhd_or_smaller is True
        assert res.is_larger_than_fullhd is False

        large_res = ScreenResolution(2560, 1440)
        assert large_res.is_fullhd_or_smaller is False
        assert large_res.is_larger_than_fullhd is True

    @patch('utils.screen_utils.ScreenDetector._detect_resolution')
    def test_screen_detector_fallback(self, mock_detect):
        """
        Test que verifica el fallback del detector de pantalla
        """
        mock_detect.return_value = ScreenResolution(1920, 1080)

        detector = ScreenDetector()
        resolution = detector.get_primary_screen_resolution()

        assert resolution.width == 1920
        assert resolution.height == 1080
        mock_detect.assert_called_once()

    def test_get_optimal_window_config_maximize(self):
        """
        Test de integración para configuración de ventana que resulta en maximizar
        """
        with patch('utils.screen_utils.screen_detector') as mock_detector:
            mock_detector.get_primary_screen_resolution.return_value = ScreenResolution(1920, 1080)

            action, window_size, center_pos = get_optimal_window_config()

            assert action == 'maximize'
            assert window_size is None
            assert center_pos is None

    def test_get_optimal_window_config_resize(self):
        """
        Test de integración para configuración de ventana que resulta en resize
        """
        with patch('utils.screen_utils.screen_detector') as mock_detector:
            mock_detector.get_primary_screen_resolution.return_value = ScreenResolution(2560, 1440)

            action, window_size, center_pos = get_optimal_window_config()

            assert action == 'resize'
            assert window_size is not None
            assert window_size.width == DesignSystem.FULLHD_WIDTH
            assert window_size.height == DesignSystem.FULLHD_HEIGHT
            assert center_pos is not None
            assert isinstance(center_pos, tuple)
            assert len(center_pos) == 2

    def test_resolution_categories(self):
        """
        Test que clasifica correctamente las resoluciones en categorías.
        """
        categories = {
            'HD': [(1366, 768), (1280, 720), (1024, 768)],
            'FullHD_standard': [(DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)],
            'FullHD_tall': [(DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT + 60)],  # Esta debería mostrar FullHD por height > 1080
            '2K': [(2560, 1440), (3440, 1440)],
            'Retina': [(2880, 1800), (3072, 1920)],
            '4K': [(3840, 2160), (4096, 2160)],
        }

        for category, resolutions in categories.items():
            for width, height in resolutions:
                screen_res = ScreenResolution(width, height)
                should_maximize = screen_res.is_fullhd_or_smaller

                if category in ['HD', 'FullHD_standard']:
                    # Deberían maximizarse
                    assert should_maximize, f"{category} {width}x{height} debería maximizarse"
                else:
                    # Deberían mostrar FullHD
                    assert not should_maximize, f"{category} {width}x{height} debería mostrar FullHD"


class TestWindowSizeIntegration:
    """
    Tests de integración para verificar que la configuración de ventana
    funciona correctamente en el contexto completo de la aplicación.
    """

    def test_main_window_initialization_with_different_resolutions(self):
        """
        Test de integración que verifica la inicialización de MainWindow
        con diferentes resoluciones simuladas.
        """
        # Este test requeriría mocking más complejo de QApplication y QScreen
        # Por ahora, solo documentamos la intención
        pytest.skip("Test de integración requiere mocking complejo de PyQt6 - implementar cuando sea necesario")

    def test_logging_output_for_window_configuration(self):
        """
        Test que verifica que se registra correctamente la configuración de ventana.
        """
        # Test que verifica los mensajes de log
        pytest.skip("Test de logging requiere setup de logging manager - implementar cuando sea necesario")