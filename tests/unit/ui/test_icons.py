# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
import pytest
from PyQt6.QtWidgets import QApplication

from ui.styles.icons import icon_manager

# ensure a QApplication exists for qtawesome
_app = QApplication.instance() or QApplication([])


def test_settings_icon_exists_and_can_be_retrieved():
    # should not raise and return a QIcon
    icon = icon_manager.get_icon('settings')
    assert icon is not None
    # retrieving again with different size or color should still work
    icon2 = icon_manager.get_icon('settings', color="#ff0000", size=24)
    assert icon2 is not None


def test_invalid_icon_name_raises_value_error():
    with pytest.raises(ValueError):
        icon_manager.get_icon('nonexistent_icon')
