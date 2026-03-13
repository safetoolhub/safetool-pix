# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Utilidades para detección y configuración de resolución de pantalla
Desacoplado de PyQt6 para facilitar migración a otras plataformas
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ScreenResolution:
    """Clase para representar una resolución de pantalla"""
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

    def __str__(self) -> str:
        return f"{self.width}x{self.height}"

    def __repr__(self) -> str:
        return f"ScreenResolution({self.width}, {self.height})"

    @property
    def is_fullhd_or_smaller(self) -> bool:
        """Verifica si la resolución es FullHD o menor"""
        from ui.styles.design_system import DesignSystem
        return self.width <= DesignSystem.FULLHD_WIDTH and self.height <= DesignSystem.FULLHD_HEIGHT

    @property
    def is_larger_than_fullhd(self) -> bool:
        """Verifica si la resolución es mayor que FullHD"""
        from ui.styles.design_system import DesignSystem
        return self.width > DesignSystem.FULLHD_WIDTH or self.height > DesignSystem.FULLHD_HEIGHT


class WindowSizeConfig:
    """Configuración de tamaño de ventana basada en resolución de pantalla"""

    @staticmethod
    def get_optimal_window_size(screen_resolution: ScreenResolution) -> Tuple[str, Optional[ScreenResolution]]:
        """
        Determina el tamaño óptimo de ventana basado en la resolución del monitor

        Args:
            screen_resolution: Resolución del monitor principal

        Returns:
            Tupla con (acción, tamaño)
            - acción: 'maximize' o 'resize'
            - tamaño: ScreenResolution si resize, None si maximize
        """
        if screen_resolution.is_larger_than_fullhd:
            # Monitor 2K+ o superior: mostrar en FullHD
            from ui.styles.design_system import DesignSystem
            optimal_size = ScreenResolution(DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)
            return 'resize', optimal_size
        else:
            # Monitor FullHD o inferior: maximizar
            return 'maximize', None

    @staticmethod
    def calculate_center_position(screen_resolution: ScreenResolution,
                                window_size: ScreenResolution) -> Tuple[int, int]:
        """
        Calcula la posición para centrar una ventana en la pantalla

        Args:
            screen_resolution: Resolución del monitor
            window_size: Tamaño de la ventana a centrar

        Returns:
            Tupla (x, y) con la posición superior izquierda
        """
        x = (screen_resolution.width - window_size.width) // 2
        y = (screen_resolution.height - window_size.height) // 2
        return x, y


class ScreenDetector:
    """
    Detector de resolución de pantalla multiplataforma
    Abstrae la detección para facilitar migración a otras plataformas
    """

    def __init__(self, platform_adapter=None):
        """
        Args:
            platform_adapter: Adaptador específico de plataforma (PyQt6, Tkinter, etc.)
                             Si None, intenta detectar automáticamente
        """
        self.platform_adapter = platform_adapter
        self._cached_resolution = None

    def get_primary_screen_resolution(self) -> ScreenResolution:
        """
        Obtiene la resolución del monitor principal

        Returns:
            ScreenResolution con las dimensiones del monitor
        """
        if self._cached_resolution:
            return self._cached_resolution

        try:
            resolution = self._detect_resolution()
            self._cached_resolution = resolution
            logger.info(f"Screen resolution detected: {resolution}")
            return resolution
        except Exception as e:
            logger.warning(f"Error detecting screen resolution: {e}")
            # Fallback a FullHD
            from ui.styles.design_system import DesignSystem
            fallback = ScreenResolution(DesignSystem.FULLHD_WIDTH, DesignSystem.FULLHD_HEIGHT)
            logger.info(f"Using fallback resolution: {fallback}")
            return fallback

    def _detect_resolution(self) -> ScreenResolution:
        """
        Detecta la resolución usando el adaptador de plataforma
        """
        if self.platform_adapter:
            return self.platform_adapter.get_screen_resolution()

        # Auto-detección basada en plataforma
        import platform
        system = platform.system().lower()

        if system == "linux":
            return self._detect_linux_resolution()
        elif system == "windows":
            return self._detect_windows_resolution()
        elif system == "darwin":  # macOS
            return self._detect_macos_resolution()
        else:
            raise NotImplementedError(f"Unsupported platform: {system}")

    def _detect_linux_resolution(self) -> ScreenResolution:
        """Detección específica para Linux"""
        try:
            # Usar xrandr si está disponible
            import subprocess
            result = subprocess.run(['xrandr'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parsear salida de xrandr para encontrar resolución actual
                lines = result.stdout.split('\n')
                for line in lines:
                    if '*' in line:  # Línea con resolución actual
                        parts = line.strip().split()
                        if len(parts) >= 1:
                            res_part = parts[0]
                            if 'x' in res_part:
                                width, height = map(int, res_part.split('x'))
                                return ScreenResolution(width, height)
        except (subprocess.SubprocessError, ValueError, FileNotFoundError):
            pass

        # Fallback: usar PyQt6 si está disponible
        return self._detect_qt_resolution()

    def _detect_windows_resolution(self) -> ScreenResolution:
        """Detección específica para Windows"""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            return ScreenResolution(width, height)
        except (ImportError, AttributeError):
            # Fallback: usar PyQt6 si está disponible
            return self._detect_qt_resolution()

    def _detect_macos_resolution(self) -> ScreenResolution:
        """Detección específica para macOS"""
        try:
            import subprocess
            # Usar system_profiler para obtener información de pantalla
            result = subprocess.run(
                ['system_profiler', 'SPDisplaysDataType'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Resolution:' in line:
                        # Parsear línea como "Resolution: 2880 x 1800"
                        parts = line.split('x')
                        if len(parts) >= 2:
                            width = int(parts[0].split()[-1])
                            height = int(parts[1].strip())
                            return ScreenResolution(width, height)
        except (subprocess.SubprocessError, ValueError):
            pass

        # Fallback: usar PyQt6 si está disponible
        return self._detect_qt_resolution()

    def _detect_qt_resolution(self) -> ScreenResolution:
        """Fallback usando PyQt6"""
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QScreen

            # Crear aplicación temporal si no existe
            app = QApplication.instance()
            if app is None:
                app = QApplication([])

            screen = app.primaryScreen()
            size = screen.size()
            return ScreenResolution(size.width(), size.height())
        except ImportError:
            raise RuntimeError("Could not detect screen resolution. PyQt6 not available.")


# Instancia global para uso en la aplicación
screen_detector = ScreenDetector()


def get_optimal_window_config() -> Tuple[str, Optional[ScreenResolution], Optional[Tuple[int, int]]]:
    """
    Función principal para obtener la configuración óptima de ventana

    Returns:
        Tupla con (acción, tamaño_ventana, posicion_centro)
        - acción: 'maximize' o 'resize'
        - tamaño_ventana: ScreenResolution si resize, None si maximize
        - posicion_centro: (x, y) si resize, None si maximize
    """
    screen_res = screen_detector.get_primary_screen_resolution()
    action, window_size = WindowSizeConfig.get_optimal_window_size(screen_res)

    if action == 'resize' and window_size:
        center_pos = WindowSizeConfig.calculate_center_position(screen_res, window_size)
        return action, window_size, center_pos
    else:
        return action, None, None