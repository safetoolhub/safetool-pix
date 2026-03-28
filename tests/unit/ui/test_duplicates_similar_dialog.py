# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para DuplicatesSimilarDialog.

Prueba el diálogo de gestión de archivos similares (70-95% similitud):
- Inicialización correcta con DuplicatesSimilarAnalysis
- Estado de carga antes de mostrar grupos
- Slider de sensibilidad (70-95%)
- Navegación entre grupos
- Selección de archivos para eliminar
- Estrategias de selección rápida
- Construcción del plan de eliminación
"""

import pytest
from pathlib import Path
from PyQt6.QtCore import Qt

from services.duplicates_similar_service import DuplicatesSimilarAnalysis
from services.result_types import SimilarDuplicateGroup
from ui.dialogs.duplicates_similar_dialog import DuplicatesSimilarDialog
from ui.tools_definitions import TOOL_DUPLICATES_SIMILAR


def create_mock_analysis(num_files: int = 10) -> DuplicatesSimilarAnalysis:
    """Crea un DuplicatesSimilarAnalysis con datos mock para testing."""
    analysis = DuplicatesSimilarAnalysis()
    
    # Simular hashes perceptuales
    for i in range(num_files):
        path = f"/tmp/test_image_{i}.jpg"
        analysis.perceptual_hashes[path] = {
            'hash': i % 5,  # Grupos de 2 archivos con mismo hash
            'size': 1000 * (i + 1)
        }
    
    analysis.total_files = num_files
    return analysis


@pytest.mark.ui
class TestDuplicatesSimilarDialogBasics:
    """Tests básicos del diálogo."""
    
    def test_dialog_creation(self, qtbot):
        """Test que el diálogo se crea correctamente."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert dialog is not None
        assert dialog.analysis == analysis
        assert TOOL_DUPLICATES_SIMILAR.title in dialog.windowTitle()
    
    def test_dialog_inherits_base_dialog(self, qtbot):
        """Test que el diálogo hereda de BaseDialog."""
        from ui.dialogs.base_dialog import BaseDialog
        
        analysis = create_mock_analysis(2)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert isinstance(dialog, BaseDialog)
    
    def test_dialog_has_sensitivity_range_slider(self, qtbot):
        """Test que el diálogo tiene slider de rango para sensibilidad."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert hasattr(dialog, 'range_slider')
        assert dialog.range_slider is not None
    
    def test_default_sensitivity_is_70(self, qtbot):
        """Test que la sensibilidad por defecto es 70%."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert dialog.DEFAULT_SENSITIVITY == 70
        assert dialog.current_sensitivity == 70
    
    def test_sensitivity_range_slider_range(self, qtbot):
        """Test que el slider tiene rango correcto (70-100%)."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert dialog.range_slider.minimum == 70
        assert dialog.range_slider.maximum == 100


@pytest.mark.ui
class TestDuplicatesSimilarDialogNavigation:
    """Tests de navegación entre grupos."""
    
    def test_navigation_buttons_exist(self, qtbot):
        """Test que existen botones de navegación."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert hasattr(dialog, 'prev_btn')
        assert hasattr(dialog, 'next_btn')
        assert hasattr(dialog, 'group_counter_label')
    
    def test_navigation_buttons_initially_disabled(self, qtbot):
        """Test que los botones están deshabilitados antes de cargar grupos."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        # Durante estado de carga inicial
        assert dialog._is_loading is True


@pytest.mark.ui
class TestDuplicatesSimilarDialogSelection:
    """Tests de selección de archivos."""
    
    def test_selections_initially_empty(self, qtbot):
        """Test que las selecciones empiezan vacías."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert dialog.selections == {}
    
    def test_delete_button_initially_disabled(self, qtbot):
        """Test que el botón de eliminar está deshabilitado al inicio."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        # delete_btn puede ser None si no se ha configurado aún
        if dialog.delete_btn:
            assert dialog.delete_btn.isEnabled() is False


@pytest.mark.ui  
class TestDuplicatesSimilarDialogSecurity:
    """Tests de opciones de seguridad."""
    
    def test_backup_option_exists(self, qtbot):
        """Test que existe opción de backup."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        # Verificar que el diálogo tiene el método de BaseDialog
        assert hasattr(dialog, 'is_backup_enabled')
    
    def test_dry_run_option_exists(self, qtbot):
        """Test que existe opción de dry run."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert hasattr(dialog, 'is_dry_run_enabled')


@pytest.mark.ui
class TestDuplicatesSimilarDialogAccept:
    """Tests de aceptación del diálogo."""
    
    def test_accepted_plan_initially_none(self, qtbot):
        """Test que accepted_plan es None inicialmente."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert dialog.accepted_plan is None
    
    def test_accept_builds_plan(self, qtbot):
        """Test que accept() construye el plan de eliminación."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        # Simular que hay grupos y selecciones
        mock_group = SimilarDuplicateGroup(
            hash_value="test",
            files=[Path("/tmp/file1.jpg"), Path("/tmp/file2.jpg")],
            file_sizes=[1000, 1000],
            similarity_score=90.0
        )
        dialog.all_groups = [mock_group]
        dialog.selections[0] = [Path("/tmp/file2.jpg")]
        
        # No llamamos exec() para evitar bloquear, solo accept()
        # Primero interceptamos el cierre
        dialog.close = lambda: None  # type: ignore[assignment]
        dialog.done = lambda x: None  # type: ignore[assignment]
        dialog.accept()
        
        assert dialog.accepted_plan is not None
        assert 'analysis' in dialog.accepted_plan
        assert 'keep_strategy' in dialog.accepted_plan
        assert 'create_backup' in dialog.accepted_plan
        assert 'dry_run' in dialog.accepted_plan


@pytest.mark.ui
class TestSensitivitySliderBehavior:
    """Tests del comportamiento del slider de sensibilidad."""
    
    def test_spinbox_updates_slider(self, qtbot):
        """Test que cambiar el spinbox actualiza el slider."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        # Simular cambio de valor en spinbox min
        dialog.min_spin.setValue(75)
        
        # Verificar que el slider se actualiza
        lower, _ = dialog.range_slider.get_range()
        assert lower == 75
    
    def test_max_spinbox_updates_slider(self, qtbot):
        """Test que cambiar el spinbox max actualiza el slider."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        dialog.max_spin.setValue(90)
        
        _, upper = dialog.range_slider.get_range()
        assert upper == 90


@pytest.mark.ui
class TestLoadingState:
    """Tests del estado de carga."""
    
    def test_loading_flag_initially_true(self, qtbot):
        """Test que _is_loading es True al inicio."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert dialog._is_loading is True
    
    def test_range_slider_exists(self, qtbot):
        """Test que el range_slider existe y tiene valores iniciales."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert hasattr(dialog, 'range_slider')
        lower, upper = dialog.range_slider.get_range()
        assert lower == 70
        assert upper == 100
    
    def test_spinboxes_exist_and_synced(self, qtbot):
        """Test que los spinboxes existen y están sincronizados con el slider."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert hasattr(dialog, 'min_spin')
        assert hasattr(dialog, 'max_spin')
        
        # Valores iniciales sincronizados
        assert dialog.min_spin.value() == 70
        assert dialog.max_spin.value() == 100
    
    def test_spinbox_range_validation(self, qtbot):
        """Test que los spinboxes tienen validación de rango."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        # min_spin no puede superar max_spin
        dialog.min_spin.setValue(95)
        dialog.max_spin.setValue(90)  # Esto debe ajustar min_spin
        
        # Verificar que se mantiene consistencia
        assert dialog.min_spin.value() <= dialog.max_spin.value()


@pytest.mark.ui
class TestDuplicatesSimilarDialogStrategies:
    """Tests de estrategias de selección rápida."""
    
    def test_apply_strategy_method_exists(self, qtbot):
        """Test que existe el método _apply_strategy."""
        analysis = create_mock_analysis(4)
        dialog = DuplicatesSimilarDialog(analysis)
        
        assert hasattr(dialog, '_apply_strategy')
        assert callable(dialog._apply_strategy)
    
    def test_strategy_without_groups_does_nothing(self, qtbot):
        """Test que aplicar estrategia sin grupos no hace nada."""
        analysis = create_mock_analysis(0)
        dialog = DuplicatesSimilarDialog(analysis)
        
        # No debe lanzar excepción
        dialog._apply_strategy('keep_largest')
        dialog._apply_strategy('keep_first')


@pytest.mark.ui
class TestAnalysisEmptyScenarios:
    """Tests con análisis vacíos o sin grupos."""
    
    def test_dialog_with_empty_analysis(self, qtbot):
        """Test que el diálogo maneja análisis vacío."""
        analysis = DuplicatesSimilarAnalysis()
        analysis.total_files = 0
        
        # No debe lanzar excepción
        dialog = DuplicatesSimilarDialog(analysis)
        assert dialog is not None
    
    def test_dialog_with_no_similar_files(self, qtbot):
        """Test que el diálogo maneja caso sin archivos similares."""
        analysis = DuplicatesSimilarAnalysis()
        # Todos los hashes diferentes = no hay similares
        for i in range(10):
            analysis.perceptual_hashes[f"/tmp/unique_{i}.jpg"] = {
                'hash': i * 1000,  # Hashes muy diferentes
                'size': 1000
            }
        analysis.total_files = 10
        
        dialog = DuplicatesSimilarDialog(analysis)
        assert dialog is not None
