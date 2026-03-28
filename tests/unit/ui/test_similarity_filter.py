# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.

import pytest
from PyQt6.QtCore import Qt
from ui.dialogs.duplicates_similar_dialog import DualRangeSlider, DuplicatesSimilarDialog
from services.duplicates_similar_service import DuplicatesSimilarAnalysis

@pytest.mark.ui
class TestDualRangeSlider:
    def test_initial_state(self, qtbot):
        slider = DualRangeSlider(parent=None)
        assert slider.minimum == 0
        assert slider.maximum == 100
        assert slider.lower_value == 0
        assert slider.upper_value == 100
        assert slider.minimumHeight() >= 40

    def test_set_range_allow_overlap(self, qtbot):
        slider = DualRangeSlider(parent=None)
        
        # Test distinct values
        slider.set_range(20, 80)
        assert slider.lower_value == 20
        assert slider.upper_value == 80
        
        # Test equal values (overlap) - now allowed
        slider.set_range(50, 50)
        assert slider.lower_value == 50
        assert slider.upper_value == 50
        
        # Test crossing values (should be sanitized)
        slider.set_range(80, 20)
        # Depending on implementation, it might swap or clamp. 
        # My implementation: if lower > upper, upper = lower.
        # So set_range(80, 20) -> lower=80, upper=20 -> check -> upper=80
        assert slider.lower_value == 80
        assert slider.upper_value == 80

@pytest.mark.ui
class TestSimilarityFilterWidget:
    def test_spinbox_sync(self, qtbot):
        analysis = DuplicatesSimilarAnalysis()
        analysis.total_files = 0
        dialog = DuplicatesSimilarDialog(analysis)
        
        # Access the private/internal widgets for testing
        # They are created in _create_similarity_range_widget called by _setup_ui
        
        assert hasattr(dialog, 'min_spin')
        assert hasattr(dialog, 'max_spin')
        assert hasattr(dialog, 'range_slider')
        
        min_spin = dialog.min_spin
        max_spin = dialog.max_spin
        slider = dialog.range_slider
        
        # Initial state
        assert min_spin.value() == 70
        assert max_spin.value() == 100
        assert slider.lower_value == 70
        assert slider.upper_value == 100
        
        # Change SpinBox -> Update Slider
        min_spin.setValue(80)
        assert slider.lower_value == 80
        
        max_spin.setValue(90)
        assert slider.upper_value == 90
        
        # Change Slider -> Update SpinBox
        # We need to emit the signal because programmatic changes to python variables 
        # in DualRangeSlider don't emit valueChanged automatically unless we call set_range or interact
        
        slider.set_range(75, 95) 
        # set_range emits valueChanged in my implementation
        
        assert min_spin.value() == 75
        assert max_spin.value() == 95
        
    def test_spinbox_cross_protection(self, qtbot):
        analysis = DuplicatesSimilarAnalysis()
        analysis.total_files = 0
        dialog = DuplicatesSimilarDialog(analysis)
        
        min_spin = dialog.min_spin
        max_spin = dialog.max_spin
        
        min_spin.setValue(80)
        max_spin.setValue(90)
        
        # Try to set min > max
        min_spin.setValue(95)
        # Should push max to 95
        assert max_spin.value() == 95
        assert min_spin.value() == 95
        
        # Try to set max < min
        min_spin.setValue(80)
        max_spin.setValue(95)
        
        max_spin.setValue(70)
        # Should push min to 70
        assert min_spin.value() == 70
        assert max_spin.value() == 70

@pytest.mark.ui
class TestSimilarityFiltering:
    """Tests para verificar la lógica de filtrado de grupos."""
    
    def test_group_matches_filter_logic(self, qtbot):
        analysis = DuplicatesSimilarAnalysis()
        analysis.total_files = 0
        dialog = DuplicatesSimilarDialog(analysis)
        
        # Simular grupo con 85% similitud
        from services.result_types import SimilarDuplicateGroup
        from pathlib import Path
        group = SimilarDuplicateGroup(
            hash_value="test",
            files=[Path("/a"), Path("/b")],
            file_sizes=[100, 100],
            similarity_score=85
        )
        
        # 1. Rango amplio (70-100) -> Debe pasar
        dialog.range_slider.set_range(70, 100)
        assert dialog._group_matches_similarity_filter(group) is True
        
        # 2. Rango ajustado que incluye 85 (80-90) -> Debe pasar
        dialog.range_slider.set_range(80, 90)
        assert dialog._group_matches_similarity_filter(group) is True
        
        # 3. Rango superior excluyente (90-100) -> No debe pasar
        dialog.range_slider.set_range(90, 100)
        assert dialog._group_matches_similarity_filter(group) is False
        
        # 4. Rango inferior excluyente (70-80) -> No debe pasar
        dialog.range_slider.set_range(70, 80)
        assert dialog._group_matches_similarity_filter(group) is False
        
        # 5. Rango exacto (85-85) -> Debe pasar
        dialog.range_slider.set_range(85, 85)
        assert dialog._group_matches_similarity_filter(group) is True

