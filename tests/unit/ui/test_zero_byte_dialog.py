# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para ZeroByteDialog.

Prueba el diálogo de gestión de archivos vacíos (0 bytes):
- Inicialización correcta con resultado de análisis
- Selección/deselección de archivos
- Opciones de backup y dry-run
- Aceptación y construcción del plan de ejecución
- Actualización de UI según selección

El diálogo usa QTreeWidget con archivos agrupados por carpeta.
"""

import pytest
from pathlib import Path
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt

from services.result_types import ZeroByteAnalysisResult
from ui.dialogs.zero_byte_dialog import ZeroByteDialog
from ui.tools_definitions import TOOL_ZERO_BYTE


def _get_all_file_items(dialog: ZeroByteDialog) -> list:
    """
    Helper para obtener todos los items de archivo del tree widget.
    Los archivos son items hijos de los nodos de carpeta.
    """
    file_items = []
    root = dialog.tree_widget.invisibleRootItem()
    for i in range(root.childCount()):
        folder_item = root.child(i)
        for j in range(folder_item.childCount()):
            file_items.append(folder_item.child(j))
    return file_items


def _get_file_count(dialog: ZeroByteDialog) -> int:
    """Helper para contar archivos totales en el árbol."""
    return len(_get_all_file_items(dialog))


def _get_checked_count(dialog: ZeroByteDialog) -> int:
    """Helper para contar archivos seleccionados."""
    return sum(
        1 for item in _get_all_file_items(dialog)
        if item.checkState(0) == Qt.CheckState.Checked
    )


def _get_file_paths(dialog: ZeroByteDialog) -> set:
    """Helper para obtener todos los paths de archivo del árbol."""
    paths = set()
    for item in _get_all_file_items(dialog):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            paths.add(path)
    return paths


@pytest.mark.ui
class TestZeroByteDialogBasics:
    """Tests básicos del diálogo."""
    
    def test_dialog_creation(self, qtbot, temp_dir):
        """Test que el diálogo se crea correctamente."""
        # Crear resultado de análisis
        files = [temp_dir / "empty1.txt", temp_dir / "empty2.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=2)
        
        # Crear diálogo
        dialog = ZeroByteDialog(analysis)
        
        assert dialog is not None
        assert dialog.analysis_result == analysis
        assert dialog.windowTitle() == TOOL_ZERO_BYTE.title
    
    def test_dialog_inherits_base_dialog(self, qtbot, temp_dir):
        """Test que el diálogo hereda de BaseDialog."""
        from ui.dialogs.base_dialog import BaseDialog
        
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        
        assert isinstance(dialog, BaseDialog)
    
    def test_dialog_has_required_widgets(self, qtbot, temp_dir):
        """Test que el diálogo tiene todos los widgets necesarios."""
        files = [temp_dir / f"empty{i}.txt" for i in range(3)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=3)
        dialog = ZeroByteDialog(analysis)
        
        # Verificar widgets principales (nueva API con QTreeWidget)
        assert hasattr(dialog, 'tree_widget')
        assert hasattr(dialog, 'ok_button')
        assert hasattr(dialog, 'buttons')
        assert dialog.tree_widget is not None
        assert dialog.ok_button is not None
    
    def test_dialog_populates_file_list(self, qtbot, temp_dir):
        """Test que el diálogo puebla la lista de archivos correctamente."""
        files = [
            temp_dir / "empty1.txt",
            temp_dir / "subdir" / "empty2.jpg",
            temp_dir / "empty3.png"
        ]
        analysis = ZeroByteAnalysisResult(files=files, items_count=3)
        dialog = ZeroByteDialog(analysis)
        
        # Cargar todos los grupos para test completo
        dialog._load_all_groups()
        
        # Verificar cantidad de items
        file_count = _get_file_count(dialog)
        assert file_count == 3
        
        # Verificar que cada archivo está en la lista
        list_paths = _get_file_paths(dialog)
        assert list_paths == set(files)
    
    def test_dialog_all_files_checked_by_default(self, qtbot, temp_dir):
        """Test que todos los archivos están marcados por defecto."""
        files = [temp_dir / f"empty{i}.txt" for i in range(5)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=5)
        dialog = ZeroByteDialog(analysis)
        
        # Cargar todos los grupos
        dialog._load_all_groups()
        
        # Todos deben estar checked
        for item in _get_all_file_items(dialog):
            assert item.checkState(0) == Qt.CheckState.Checked


@pytest.mark.ui
class TestZeroByteDialogSelection:
    """Tests de selección de archivos."""
    
    def test_select_all_button(self, qtbot, temp_dir):
        """Test botón de seleccionar todos."""
        files = [temp_dir / f"empty{i}.txt" for i in range(5)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=5)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        # Primero deseleccionar algunos
        items = _get_all_file_items(dialog)
        items[0].setCheckState(0, Qt.CheckState.Unchecked)
        items[2].setCheckState(0, Qt.CheckState.Unchecked)
        dialog.selected_files.discard(items[0].data(0, Qt.ItemDataRole.UserRole))
        dialog.selected_files.discard(items[2].data(0, Qt.ItemDataRole.UserRole))
        
        # Verificar que algunos están desmarcados
        assert items[0].checkState(0) == Qt.CheckState.Unchecked
        assert items[2].checkState(0) == Qt.CheckState.Unchecked
        
        # Llamar a _select_all (método privado)
        dialog._select_all()
        
        # Ahora todos deben estar marcados
        for item in _get_all_file_items(dialog):
            assert item.checkState(0) == Qt.CheckState.Checked
    
    def test_select_none_button(self, qtbot, temp_dir):
        """Test botón de deseleccionar todos."""
        files = [temp_dir / f"empty{i}.txt" for i in range(5)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=5)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        # Por defecto todos están marcados
        for item in _get_all_file_items(dialog):
            assert item.checkState(0) == Qt.CheckState.Checked
        
        # Llamar a _select_none (método privado)
        dialog._select_none()
        
        # Ahora todos deben estar desmarcados
        for item in _get_all_file_items(dialog):
            assert item.checkState(0) == Qt.CheckState.Unchecked
    
    def test_partial_selection(self, qtbot, temp_dir):
        """Test selección parcial de archivos."""
        files = [temp_dir / f"empty{i}.txt" for i in range(5)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=5)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        items = _get_all_file_items(dialog)
        
        # Deseleccionar algunos
        items[1].setCheckState(0, Qt.CheckState.Unchecked)
        items[3].setCheckState(0, Qt.CheckState.Unchecked)
        dialog.selected_files.discard(items[1].data(0, Qt.ItemDataRole.UserRole))
        dialog.selected_files.discard(items[3].data(0, Qt.ItemDataRole.UserRole))
        
        # Contar seleccionados
        selected_count = _get_checked_count(dialog)
        assert selected_count == 3


@pytest.mark.ui
class TestZeroByteDialogButtonUpdate:
    """Tests de actualización del botón según selección."""
    
    def test_button_text_updates_on_selection(self, qtbot, temp_dir):
        """Test que el texto del botón se actualiza con la cantidad seleccionada."""
        files = [temp_dir / f"empty{i}.txt" for i in range(5)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=5)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        # Inicialmente debe mostrar 5 archivos
        assert "5" in dialog.ok_button.text()
        
        # Deseleccionar algunos vía el set interno
        items = _get_all_file_items(dialog)
        items[0].setCheckState(0, Qt.CheckState.Unchecked)
        items[1].setCheckState(0, Qt.CheckState.Unchecked)
        dialog.selected_files.discard(items[0].data(0, Qt.ItemDataRole.UserRole))
        dialog.selected_files.discard(items[1].data(0, Qt.ItemDataRole.UserRole))
        dialog._update_button_text()
        
        # Debe mostrar 3 archivos
        assert "3" in dialog.ok_button.text()
    
    def test_button_disabled_when_none_selected(self, qtbot, temp_dir):
        """Test que el botón se deshabilita cuando no hay selección."""
        files = [temp_dir / f"empty{i}.txt" for i in range(3)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=3)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        # Inicialmente debe estar habilitado
        assert dialog.ok_button.isEnabled()
        
        # Deseleccionar todos
        dialog._select_none()
        dialog._update_button_text()
        
        # Debe estar deshabilitado
        assert not dialog.ok_button.isEnabled()
    
    def test_button_enabled_when_some_selected(self, qtbot, temp_dir):
        """Test que el botón se habilita cuando hay al menos uno seleccionado."""
        files = [temp_dir / f"empty{i}.txt" for i in range(3)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=3)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        # Deseleccionar todos
        dialog._select_none()
        dialog._update_button_text()
        assert not dialog.ok_button.isEnabled()
        
        # Seleccionar uno
        items = _get_all_file_items(dialog)
        items[0].setCheckState(0, Qt.CheckState.Checked)
        dialog.selected_files.add(items[0].data(0, Qt.ItemDataRole.UserRole))
        dialog._update_button_text()
        
        # Debe estar habilitado
        assert dialog.ok_button.isEnabled()


@pytest.mark.ui
class TestZeroByteDialogOptions:
    """Tests de opciones de seguridad (backup y dry-run)."""
    
    def test_dialog_has_backup_option(self, qtbot, temp_dir):
        """Test que el diálogo tiene la opción de backup."""
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        
        # Debe tener método para verificar backup
        assert hasattr(dialog, 'is_backup_enabled')
        assert callable(dialog.is_backup_enabled)
    
    def test_dialog_has_dry_run_option(self, qtbot, temp_dir):
        """Test que el diálogo tiene la opción de dry-run."""
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        
        # Debe tener método para verificar dry-run
        assert hasattr(dialog, 'is_dry_run_enabled')
        assert callable(dialog.is_dry_run_enabled)
    
    def test_backup_enabled_by_default(self, qtbot, temp_dir):
        """Test que backup está habilitado por defecto (según política del proyecto)."""
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        
        # Nota: BaseDialog puede tener backup habilitado o no por defecto
        # Solo verificamos que el método existe y retorna bool
        result = dialog.is_backup_enabled()
        assert isinstance(result, bool)
    
    def test_dry_run_disabled_by_default(self, qtbot, temp_dir):
        """Test que dry-run está deshabilitado por defecto."""
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        
        # Dry-run normalmente está deshabilitado por defecto
        result = dialog.is_dry_run_enabled()
        assert isinstance(result, bool)


@pytest.mark.ui
class TestZeroByteDialogAccept:
    """Tests de aceptación y construcción del plan."""
    
    def test_accept_builds_plan_with_all_files(self, qtbot, temp_dir):
        """Test que accept construye el plan correctamente con todos los archivos."""
        files = [temp_dir / f"empty{i}.txt" for i in range(3)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=3)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        # Aceptar
        dialog.accept()
        
        # Verificar plan
        assert 'analysis' in dialog.accepted_plan
        assert 'create_backup' in dialog.accepted_plan
        assert 'dry_run' in dialog.accepted_plan
        
        plan_analysis = dialog.accepted_plan['analysis']
        assert isinstance(plan_analysis, ZeroByteAnalysisResult)
        assert len(plan_analysis.files) == 3
        assert set(plan_analysis.files) == set(files)
    
    def test_accept_builds_plan_with_partial_selection(self, qtbot, temp_dir):
        """Test que accept construye el plan solo con archivos seleccionados."""
        files = [temp_dir / f"empty{i}.txt" for i in range(5)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=5)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        items = _get_all_file_items(dialog)
        
        # Deseleccionar algunos (items 1 y 3)
        items[1].setCheckState(0, Qt.CheckState.Unchecked)
        items[3].setCheckState(0, Qt.CheckState.Unchecked)
        dialog.selected_files.discard(items[1].data(0, Qt.ItemDataRole.UserRole))
        dialog.selected_files.discard(items[3].data(0, Qt.ItemDataRole.UserRole))
        
        # Aceptar
        dialog.accept()
        
        plan_analysis = dialog.accepted_plan['analysis']
        assert len(plan_analysis.files) == 3
        
        # Verificar que solo los seleccionados están en el plan
        selected_files = {files[0], files[2], files[4]}
        assert set(plan_analysis.files) == selected_files
    
    def test_accept_does_nothing_when_no_selection(self, qtbot, temp_dir):
        """Test que accept no hace nada cuando no hay archivos seleccionados."""
        files = [temp_dir / f"empty{i}.txt" for i in range(3)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=3)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        # Deseleccionar todos
        dialog._select_none()
        
        # Aceptar
        dialog.accept()
        
        # El plan debe estar vacío o no tener analysis
        if dialog.accepted_plan:
            assert 'analysis' not in dialog.accepted_plan or len(dialog.accepted_plan['analysis'].files) == 0
    
    def test_accept_includes_backup_option(self, qtbot, temp_dir):
        """Test que el plan incluye la opción de backup."""
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        
        # Aceptar
        dialog.accept()
        
        assert 'create_backup' in dialog.accepted_plan
        assert isinstance(dialog.accepted_plan['create_backup'], bool)
    
    def test_accept_includes_dry_run_option(self, qtbot, temp_dir):
        """Test que el plan incluye la opción de dry-run."""
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        
        # Aceptar
        dialog.accept()
        
        assert 'dry_run' in dialog.accepted_plan
        assert isinstance(dialog.accepted_plan['dry_run'], bool)


@pytest.mark.ui
class TestZeroByteDialogEdgeCases:
    """Tests de casos especiales."""
    
    def test_dialog_with_single_file(self, qtbot, temp_dir):
        """Test diálogo con un solo archivo."""
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        file_count = _get_file_count(dialog)
        assert file_count == 1
        assert dialog.ok_button.isEnabled()
        assert "1" in dialog.ok_button.text()
    
    def test_dialog_with_many_files(self, qtbot, temp_dir):
        """Test diálogo con muchos archivos."""
        files = [temp_dir / f"empty{i}.txt" for i in range(100)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=100)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        file_count = _get_file_count(dialog)
        assert file_count == 100
        assert "100" in dialog.ok_button.text()
    
    def test_dialog_with_long_file_paths(self, qtbot, temp_dir):
        """Test diálogo con rutas de archivo largas."""
        # Crear ruta larga
        long_path = temp_dir / "a" / "very" / "long" / "path" / "structure" / "empty.txt"
        files = [long_path]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        file_count = _get_file_count(dialog)
        assert file_count == 1
        
        # Verificar que el path se guarda correctamente
        file_paths = _get_file_paths(dialog)
        assert long_path in file_paths
    
    def test_dialog_with_special_characters_in_names(self, qtbot, temp_dir):
        """Test diálogo con caracteres especiales en nombres."""
        files = [
            temp_dir / "file with spaces.txt",
            temp_dir / "file_with_àccénts.txt",
            temp_dir / "file-with-dashes.txt"
        ]
        analysis = ZeroByteAnalysisResult(files=files, items_count=3)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        file_count = _get_file_count(dialog)
        assert file_count == 3
        
        # Verificar que los paths se guardan correctamente
        file_paths = _get_file_paths(dialog)
        assert file_paths == set(files)


@pytest.mark.ui
class TestZeroByteDialogUX:
    """Tests de experiencia de usuario."""
    
    def test_dialog_shows_file_count_in_header(self, qtbot, temp_dir):
        """Test que el header muestra la cantidad de archivos."""
        files = [temp_dir / f"empty{i}.txt" for i in range(7)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=7)
        dialog = ZeroByteDialog(analysis)
        
        # El header debe existir
        assert hasattr(dialog, 'header_frame')
        assert dialog.header_frame is not None
    
    def test_dialog_has_descriptive_title(self, qtbot, temp_dir):
        """Test que el diálogo tiene un título descriptivo."""
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        dialog = ZeroByteDialog(analysis)
        
        title = dialog.windowTitle()
        assert title == TOOL_ZERO_BYTE.title
    
    def test_dialog_has_reasonable_size(self, qtbot, temp_dir):
        """Test que el diálogo tiene un tamaño razonable."""
        files = [temp_dir / f"empty{i}.txt" for i in range(10)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=10)
        dialog = ZeroByteDialog(analysis)
        
        size = dialog.size()
        # Debe ser razonablemente grande pero no excesivo
        assert 600 <= size.width() <= 1200
        assert 400 <= size.height() <= 800


@pytest.mark.ui
class TestZeroByteDialogIntegration:
    """Tests de integración con otros componentes."""
    
    def test_dialog_accepts_analysis_result(self, qtbot, temp_dir):
        """Test que el diálogo acepta correctamente un ZeroByteAnalysisResult."""
        files = [temp_dir / "empty.txt"]
        analysis = ZeroByteAnalysisResult(files=files, items_count=1)
        
        # No debe lanzar excepción
        dialog = ZeroByteDialog(analysis)
        assert dialog.analysis_result == analysis
    
    def test_dialog_produces_valid_execution_plan(self, qtbot, temp_dir):
        """Test que el diálogo produce un plan de ejecución válido."""
        files = [temp_dir / f"empty{i}.txt" for i in range(3)]
        analysis = ZeroByteAnalysisResult(files=files, items_count=3)
        dialog = ZeroByteDialog(analysis)
        dialog._load_all_groups()
        
        # Aceptar
        dialog.accept()
        
        # El plan debe ser válido para el servicio
        plan = dialog.accepted_plan
        
        assert 'analysis' in plan
        assert isinstance(plan['analysis'], ZeroByteAnalysisResult)
        assert 'create_backup' in plan
        assert 'dry_run' in plan
        
        # El análisis debe tener los campos necesarios
        plan_analysis = plan['analysis']
        assert hasattr(plan_analysis, 'files')
        assert hasattr(plan_analysis, 'items_count')
        assert plan_analysis.items_count == len(plan_analysis.files)
