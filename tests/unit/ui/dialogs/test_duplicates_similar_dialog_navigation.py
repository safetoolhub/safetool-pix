# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.

import pytest
from unittest.mock import MagicMock
from pathlib import Path
from ui.dialogs.duplicates_similar_dialog import DuplicatesSimilarDialog
from services.duplicates_similar_service import DuplicatesSimilarAnalysis
from services.result_types import SimilarDuplicateGroup

@pytest.fixture
def dialog(qtbot):
    """Fixture to create the dialog with mocked analysis."""
    analysis = MagicMock(spec=DuplicatesSimilarAnalysis)
    analysis.total_files = 0
    analysis.perceptual_hashes = {}  # Mock empty dict
    # Create dialog
    # We mock _initial_load to avoid auto-triggering things we don't want in unit tests
    # But checking source code, _initial_load is called via QTimer.singleShot(100)
    # qtbot can handle this or we can just ignore it if we set up state manually.
    
    dlg = DuplicatesSimilarDialog(analysis)
    return dlg

def create_mock_group(score=90):
    return SimilarDuplicateGroup(
        hash_value="hash",
        files=[Path("/a"), Path("/b")],
        file_sizes=[100, 100],
        similarity_score=score
    )

@pytest.mark.ui
def test_group_navigation_next_wrap_around(qtbot, dialog):
    """Test that clicking Next on the last group wraps around to the first group."""
    # Setup state manually
    groups = [create_mock_group() for _ in range(3)] # 3 groups
    dialog.all_groups = groups
    dialog.filtered_groups = groups # Assume no filters active
    dialog.current_group_index = 2 # Last group (index 0, 1, 2)
    
    # Mock _load_group to verify it gets called with correct index
    # We perform the real logic inside _next_group, which calls _load_group
    # But _load_group does UI work we might want to avoid or mock. 
    # Actually, let's let _load_group behave normally if possible, or mock it if complex.
    # _load_group updates UI. Let's mock it to isolate navigation logic.
    dialog._load_group = MagicMock()
    
    # Act
    dialog._next_group()
    
    # Assert
    dialog._load_group.assert_called_once_with(0)

@pytest.mark.ui
def test_group_navigation_prev_wrap_around(qtbot, dialog):
    """Test that clicking Previous on the first group wraps around to the last group."""
    # Setup state
    groups = [create_mock_group() for _ in range(3)] # 3 groups
    dialog.all_groups = groups
    dialog.filtered_groups = groups
    dialog.current_group_index = 0 # First group
    
    dialog._load_group = MagicMock()
    
    # Act
    dialog._previous_group()
    
    # Assert
    dialog._load_group.assert_called_once_with(2) # Last index

@pytest.mark.ui
def test_navigation_buttons_enabled_state_multiple_groups(qtbot, dialog):
    """Test that buttons are enabled when there are multiple groups."""
    groups = [create_mock_group() for _ in range(3)]
    dialog.all_groups = groups
    dialog.filtered_groups = groups
    
    # We need to run _load_group's logic part that updates buttons
    # Since we mocked _load_group in other tests, here we want to test the Side Effects of it
    # But _load_group does a lot. Let's trust the logic inspection or run the real method?
    # Running real method requires UI setup. 
    # Let's mock _create_file_card and other UI heavy lifters to make _load_group safe(r).
    
    from PyQt6.QtWidgets import QFrame
    dialog._create_file_card = MagicMock(return_value=QFrame())
    dialog._update_group_similarity_display = MagicMock()
    
    # Call real _load_group
    dialog._load_group(0)
    
    assert dialog.prev_btn.isEnabled() is True
    assert dialog.next_btn.isEnabled() is True

@pytest.mark.ui
def test_navigation_buttons_disabled_single_group(qtbot, dialog):
    """Test that buttons are disabled when there is only one group."""
    groups = [create_mock_group()]
    dialog.all_groups = groups
    dialog.filtered_groups = groups
    
    from PyQt6.QtWidgets import QFrame
    dialog._create_file_card = MagicMock(return_value=QFrame())
    dialog._update_group_similarity_display = MagicMock()
    
    # Call real _load_group
    dialog._load_group(0)
    
    assert dialog.prev_btn.isEnabled() is False
    assert dialog.next_btn.isEnabled() is False
