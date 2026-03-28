# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Fixtures compartidas para tests de UI.

Soluciona la condición de carrera en DuplicatesSimilarDialog:
QTimer.singleShot(100, self._initial_load) dispara _initial_load 100ms después
de crear el diálogo. Si el test finaliza antes, _initial_load se ejecuta durante
el teardown de pytest-qt causando segfaults (processEvents en _regenerate_groups).

La solución: parchear QTimer.singleShot automáticamente en todos los tests UI
para que las llamadas diferidas no se ejecuten durante los tests.
"""

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def _patch_qtimer_singleshot():
    """Impide que QTimer.singleShot dispare callbacks diferidos durante tests.

    DuplicatesSimilarDialog.__init__ programa _initial_load con
    QTimer.singleShot(100, callback). Ese callback puede ejecutarse durante
    el teardown del test causando segfaults. Este fixture reemplaza
    singleShot con un no-op para todos los tests UI.
    """
    with patch('ui.dialogs.duplicates_similar_dialog.QTimer') as mock_timer:
        mock_timer.singleShot = lambda *args, **kwargs: None
        yield
