# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Base Worker class for all background tasks.
"""
from PyQt6.QtCore import QThread, pyqtSignal
from typing import Callable

class BaseWorker(QThread):
    """
    Base worker that provides common signals and helper for progress callbacks.
    
    Subclasses should override the 'finished' signal with a typed version
    matching their result dataclass type.
    
    Signals:
        progress_update(int, int, str): Emite (current, total, message) para actualizar progreso
        finished(object): Emite resultado de operación (subclases deben sobrescribir con tipo específico)
        error(str): Emite mensaje de error con traceback
    """
    progress_update = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)  # Genérico - subclases deben sobrescribir con tipo específico
    error = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_requested: bool = False

    def stop(self) -> None:
        """Request the worker to stop gracefully"""
        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        """Check if stop was requested"""
        return self._stop_requested

    def _create_progress_callback(
        self, 
        counts_in_message: bool = False, 
        emit_numbers: bool = False
    ) -> Callable[[int, int, str], bool]:
        """
        Return a progress callback(current, total, message) with consistent
        behavior across workers.

        - By default emits (0, 0, message) so the UI shows only the text.
        - If counts_in_message is True, appends " (current/total)" to the
          message and still emits numeric placeholders (0,0) for UI.
        - If emit_numbers is True, emits (current, total, message) so the
          UI can use real progress numbers.
        
        Returns:
            Callable that returns False when stop is requested, True otherwise
        """
        def callback(current: int, total: int, message: str) -> bool:
            # Single check for stop request (optimized)
            if self._stop_requested:
                return False
            
            try:
                if emit_numbers:
                    self.progress_update.emit(current, total, message)
                elif counts_in_message:
                    self.progress_update.emit(0, 0, f"{message} ({current}/{total})")
                else:
                    self.progress_update.emit(0, 0, message)
            except Exception:
                # La señal de progreso no debe bloquear el worker
                pass
            
            # Return stop status
            return not self._stop_requested

        return callback
