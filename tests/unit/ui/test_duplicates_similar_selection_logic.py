# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests específicos para la lógica de selección automática y manual
en DuplicatesSimilarDialog con filtros.

Escenarios cubiertos:
1. Selección automática aplica SOLO a grupos filtrados
2. Selección manual se preserva al cambiar filtros
3. Mezcla de selección automática + manual
4. Métricas del header con grupos filtrados vs vacíos
5. Índice real vs índice filtrado
"""

import pytest
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from services.duplicates_similar_service import DuplicatesSimilarAnalysis
from services.result_types import SimilarDuplicateGroup, SimilarDuplicateAnalysisResult


# ============== FIXTURES Y HELPERS ==============

def create_mock_group(
    group_id: str,
    files: List[str],
    sizes: List[int],
    similarity: float = 85.0
) -> SimilarDuplicateGroup:
    """Crea un grupo de prueba."""
    return SimilarDuplicateGroup(
        hash_value=group_id,
        files=[Path(f) for f in files],
        file_sizes=sizes,
        similarity_score=similarity
    )


def create_mock_analysis_with_groups(
    groups: List[SimilarDuplicateGroup]
) -> DuplicatesSimilarAnalysis:
    """Crea un análisis con grupos predefinidos."""
    analysis = DuplicatesSimilarAnalysis()
    
    # Poblar perceptual_hashes para simular el análisis
    for group in groups:
        for i, file_path in enumerate(group.files):
            analysis.perceptual_hashes[str(file_path)] = {
                'hash': hash(group.hash_value),
                'size': group.file_sizes[i] if i < len(group.file_sizes) else 1000,
                'modified': datetime.now().timestamp()
            }
    
    analysis.total_files = sum(len(g.files) for g in groups)
    analysis.analysis_timestamp = datetime.now()
    return analysis


class MockDialog:
    """Mock simplificado del diálogo para testear lógica sin UI."""
    
    def __init__(self, all_groups: List[SimilarDuplicateGroup]):
        self.all_groups = all_groups
        self.filtered_groups = all_groups.copy()
        self.selections: Dict[int, List[Path]] = {}
        self.current_group_index = 0
    
    def _get_real_group_index(self, filtered_index: int):
        """Obtiene el índice real en all_groups a partir del índice en filtered_groups."""
        if not 0 <= filtered_index < len(self.filtered_groups):
            return None
        
        if not self.filtered_groups or self.filtered_groups == self.all_groups:
            return filtered_index
        
        target_group = self.filtered_groups[filtered_index]
        for idx, group in enumerate(self.all_groups):
            if id(group) == id(target_group):
                return idx
        return None
    
    def _get_file_size(self, file_path: Path) -> int:
        """Simula obtener tamaño del archivo."""
        # Buscar en grupos
        for group in self.all_groups:
            if file_path in group.files:
                idx = group.files.index(file_path)
                if idx < len(group.file_sizes):
                    return group.file_sizes[idx]
        return 0
    
    def _get_files_to_delete_by_size(self, files: list, keep_largest: bool = True) -> list:
        """Determina qué archivos eliminar según tamaño."""
        sizes = [(f, self._get_file_size(f)) for f in files]
        sorted_files = sorted(sizes, key=lambda x: x[1], reverse=keep_largest)
        return [f for f, _ in sorted_files[1:]]
    
    def _apply_strategy_to_filtered_groups(self, strategy: str):
        """Aplica estrategia SOLO a los grupos filtrados actualmente.
        
        IMPORTANTE: Si filtered_groups está vacío, NO hace nada (no usa all_groups como fallback).
        """
        # Si no hay grupos filtrados, no hacer nada
        if not self.filtered_groups:
            return
        
        groups_to_apply = self.filtered_groups
        filtered_groups_set = set(id(g) for g in groups_to_apply)
        
        for idx, group in enumerate(self.all_groups):
            if id(group) not in filtered_groups_set:
                continue
            
            files = group.files
            if len(files) < 2:
                continue
            
            to_delete = []
            if strategy == 'keep_largest':
                to_delete = self._get_files_to_delete_by_size(files, keep_largest=True)
            
            if to_delete:
                self.selections[idx] = list(to_delete)
            else:
                if idx in self.selections:
                    del self.selections[idx]
    
    def apply_filter(self, min_similarity: float, max_similarity: float):
        """Aplica filtro por similitud."""
        self.filtered_groups = [
            g for g in self.all_groups
            if min_similarity <= g.similarity_score <= max_similarity
        ]
    
    def toggle_selection(self, filtered_index: int, file_path: Path, selected: bool):
        """Alterna la selección de un archivo."""
        real_index = self._get_real_group_index(filtered_index)
        if real_index is None:
            return
        
        if real_index not in self.selections:
            self.selections[real_index] = []
        
        if selected and file_path not in self.selections[real_index]:
            self.selections[real_index].append(file_path)
        elif not selected and file_path in self.selections[real_index]:
            self.selections[real_index].remove(file_path)


# ============== TESTS ==============

class TestAutoSelectionAppliesToFilteredGroupsOnly:
    """Tests de selección automática aplicada solo a grupos filtrados."""
    
    def test_auto_selection_with_all_groups(self):
        """Test: selección automática sin filtros afecta a todos los grupos."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg"], [3000, 1500], 85.0),
            create_mock_group("G3", ["/tmp/g3_a.jpg", "/tmp/g3_b.jpg"], [1000, 500], 75.0),
        ]
        dialog = MockDialog(groups)
        
        # Sin filtros, aplicar estrategia
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # Todos los grupos deben tener selecciones
        assert 0 in dialog.selections  # G1
        assert 1 in dialog.selections  # G2
        assert 2 in dialog.selections  # G3
        
        # El archivo más pequeño de cada grupo debe estar seleccionado para eliminar
        assert Path("/tmp/g1_b.jpg") in dialog.selections[0]  # 1000 < 2000
        assert Path("/tmp/g2_b.jpg") in dialog.selections[1]  # 1500 < 3000
        assert Path("/tmp/g3_b.jpg") in dialog.selections[2]  # 500 < 1000
    
    def test_auto_selection_with_filter_applies_only_to_filtered(self):
        """Test: selección automática con filtro afecta SOLO a grupos filtrados."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg"], [3000, 1500], 85.0),
            create_mock_group("G3", ["/tmp/g3_a.jpg", "/tmp/g3_b.jpg"], [1000, 500], 75.0),
        ]
        dialog = MockDialog(groups)
        
        # Filtrar: solo grupos con similitud >= 85%
        dialog.apply_filter(85.0, 100.0)
        assert len(dialog.filtered_groups) == 2  # G1 (90%) y G2 (85%)
        
        # Aplicar estrategia
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # Solo G1 y G2 deben tener selecciones (no G3 porque está filtrado)
        assert 0 in dialog.selections  # G1
        assert 1 in dialog.selections  # G2
        assert 2 not in dialog.selections  # G3 NO debe tener selección
    
    def test_filter_change_preserves_unfiltered_selections(self):
        """Test: cambiar filtros preserva selecciones de grupos no filtrados."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg"], [3000, 1500], 85.0),
            create_mock_group("G3", ["/tmp/g3_a.jpg", "/tmp/g3_b.jpg"], [1000, 500], 75.0),
        ]
        dialog = MockDialog(groups)
        
        # Paso 1: Filtrar y seleccionar grupos de alta similitud (90%+)
        dialog.apply_filter(90.0, 100.0)
        assert len(dialog.filtered_groups) == 1  # Solo G1
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        assert 0 in dialog.selections  # G1 tiene selección
        assert 1 not in dialog.selections  # G2 no tiene selección
        assert 2 not in dialog.selections  # G3 no tiene selección
        
        # Paso 2: Cambiar filtro a baja similitud (70-80%)
        dialog.apply_filter(70.0, 80.0)
        assert len(dialog.filtered_groups) == 1  # Solo G3
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # G1 debe CONSERVAR su selección previa
        assert 0 in dialog.selections
        assert Path("/tmp/g1_b.jpg") in dialog.selections[0]
        
        # G3 ahora debe tener selección
        assert 2 in dialog.selections
        assert Path("/tmp/g3_b.jpg") in dialog.selections[2]
        
        # G2 sigue sin selección
        assert 1 not in dialog.selections
    
    def test_auto_selection_with_no_filtered_groups_does_nothing(self):
        """Test: selección automática con 0 grupos filtrados NO modifica nada.
        
        Este test verifica el bug donde, si los filtros hacían que no hubiera
        ningún grupo visible, la selección automática aplicaba a todos los grupos
        en lugar de no hacer nada.
        """
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg"], [3000, 1500], 85.0),
            create_mock_group("G3", ["/tmp/g3_a.jpg", "/tmp/g3_b.jpg"], [1000, 500], 75.0),
        ]
        dialog = MockDialog(groups)
        
        # Filtrar con rango que no incluye ningún grupo (50-60%)
        dialog.apply_filter(50.0, 60.0)
        assert len(dialog.filtered_groups) == 0  # Ningún grupo
        
        # Aplicar estrategia automática
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # NINGÚN grupo debe tener selecciones
        assert len(dialog.selections) == 0
        assert 0 not in dialog.selections
        assert 1 not in dialog.selections
        assert 2 not in dialog.selections
    
    def test_auto_selection_with_no_filtered_preserves_existing_selections(self):
        """Test: selección automática con 0 grupos filtrados preserva selecciones existentes."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg"], [3000, 1500], 85.0),
        ]
        dialog = MockDialog(groups)
        
        # Paso 1: Hacer selecciones con todos los grupos visibles
        dialog.apply_filter(70.0, 100.0)
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # Verificar que hay selecciones
        assert 0 in dialog.selections
        assert 1 in dialog.selections
        original_selections = {k: list(v) for k, v in dialog.selections.items()}
        
        # Paso 2: Aplicar filtro que excluye todos los grupos
        dialog.apply_filter(50.0, 60.0)
        assert len(dialog.filtered_groups) == 0
        
        # Paso 3: Intentar aplicar selección automática
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # Las selecciones existentes deben mantenerse intactas
        assert dialog.selections == original_selections


class TestManualSelectionPersistence:
    """Tests de persistencia de selección manual al cambiar filtros."""
    
    def test_manual_selection_persists_after_filter_change(self):
        """Test: selección manual persiste cuando el grupo sale del filtro."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg"], [3000, 1500], 75.0),
        ]
        dialog = MockDialog(groups)
        
        # Paso 1: Ver todos los grupos (sin filtro)
        dialog.apply_filter(70.0, 100.0)  # Todos
        
        # Paso 2: Hacer selección manual en G2 (índice filtrado 1, real 1)
        dialog.toggle_selection(1, Path("/tmp/g2_a.jpg"), True)
        
        assert 1 in dialog.selections
        assert Path("/tmp/g2_a.jpg") in dialog.selections[1]
        
        # Paso 3: Filtrar para ver solo grupos de alta similitud (G1)
        dialog.apply_filter(85.0, 100.0)
        assert len(dialog.filtered_groups) == 1  # Solo G1
        
        # La selección de G2 debe persistir aunque G2 no esté visible
        assert 1 in dialog.selections
        assert Path("/tmp/g2_a.jpg") in dialog.selections[1]
        
        # Paso 4: Volver a ver todos los grupos
        dialog.apply_filter(70.0, 100.0)
        
        # La selección de G2 sigue ahí
        assert 1 in dialog.selections
        assert Path("/tmp/g2_a.jpg") in dialog.selections[1]
    
    def test_manual_selection_in_filtered_group_uses_correct_index(self):
        """Test: selección manual usa índice real, no filtrado."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg"], [3000, 1500], 85.0),
            create_mock_group("G3", ["/tmp/g3_a.jpg", "/tmp/g3_b.jpg"], [1000, 500], 75.0),
        ]
        dialog = MockDialog(groups)
        
        # Filtrar: solo G3 (75%)
        dialog.apply_filter(70.0, 80.0)
        assert len(dialog.filtered_groups) == 1
        assert dialog.filtered_groups[0].hash_value == "G3"
        
        # Selección manual: índice filtrado es 0, pero índice real es 2
        dialog.toggle_selection(0, Path("/tmp/g3_a.jpg"), True)
        
        # La selección debe estar en índice REAL 2, no en 0
        assert 0 not in dialog.selections  # No en índice 0
        assert 2 in dialog.selections  # Sí en índice real 2
        assert Path("/tmp/g3_a.jpg") in dialog.selections[2]


class TestMixedAutoAndManualSelection:
    """Tests de combinación de selección automática y manual."""
    
    def test_auto_selection_does_not_clear_manual_in_other_groups(self):
        """Test: auto-selección no borra selección manual de grupos no filtrados."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg"], [3000, 1500], 85.0),
            create_mock_group("G3", ["/tmp/g3_a.jpg", "/tmp/g3_b.jpg"], [1000, 500], 75.0),
        ]
        dialog = MockDialog(groups)
        
        # Paso 1: Selección manual en G3 (todos los grupos visibles)
        dialog.apply_filter(70.0, 100.0)
        dialog.toggle_selection(2, Path("/tmp/g3_a.jpg"), True)  # Selección manual
        
        # Paso 2: Filtrar para ver solo G1 y G2 (alta similitud)
        dialog.apply_filter(85.0, 100.0)
        
        # Paso 3: Aplicar auto-selección
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # Verificar que G1 y G2 tienen auto-selección
        assert 0 in dialog.selections
        assert 1 in dialog.selections
        
        # Verificar que G3 CONSERVA su selección manual
        assert 2 in dialog.selections
        assert Path("/tmp/g3_a.jpg") in dialog.selections[2]
    
    def test_auto_selection_overwrites_manual_in_same_filtered_group(self):
        """Test: auto-selección SÍ sobreescribe selección manual en grupos filtrados."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg", "/tmp/g1_c.jpg"], 
                             [2000, 1500, 1000], 90.0),
        ]
        dialog = MockDialog(groups)
        
        # Selección manual: seleccionar el más grande para eliminar
        dialog.toggle_selection(0, Path("/tmp/g1_a.jpg"), True)
        assert Path("/tmp/g1_a.jpg") in dialog.selections[0]
        
        # Auto-selección: keep_largest selecciona los más pequeños para eliminar
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # La auto-selección debe haber cambiado la selección
        # El más grande (g1_a.jpg) NO debe estar seleccionado para eliminar
        assert Path("/tmp/g1_a.jpg") not in dialog.selections[0]
        # Los más pequeños SÍ deben estar seleccionados
        assert Path("/tmp/g1_b.jpg") in dialog.selections[0]
        assert Path("/tmp/g1_c.jpg") in dialog.selections[0]


class TestRealIndexMapping:
    """Tests del mapeo de índices filtrados a reales."""
    
    def test_get_real_index_without_filter(self):
        """Test: sin filtro, índice real = índice filtrado."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg"], [1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg"], [1000], 80.0),
        ]
        dialog = MockDialog(groups)
        
        assert dialog._get_real_group_index(0) == 0
        assert dialog._get_real_group_index(1) == 1
    
    def test_get_real_index_with_filter(self):
        """Test: con filtro, índice real puede diferir del filtrado."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg"], [1000], 90.0),  # índice real 0
            create_mock_group("G2", ["/tmp/g2_a.jpg"], [1000], 75.0),  # índice real 1
            create_mock_group("G3", ["/tmp/g3_a.jpg"], [1000], 70.0),  # índice real 2
        ]
        dialog = MockDialog(groups)
        
        # Filtrar: solo G2 y G3 (similitud < 80%)
        dialog.apply_filter(70.0, 80.0)
        assert len(dialog.filtered_groups) == 2  # G2 y G3
        
        # Índice filtrado 0 = G2 = índice real 1
        assert dialog._get_real_group_index(0) == 1
        
        # Índice filtrado 1 = G3 = índice real 2
        assert dialog._get_real_group_index(1) == 2
    
    def test_get_real_index_out_of_bounds(self):
        """Test: índice fuera de rango retorna None."""
        groups = [create_mock_group("G1", ["/tmp/g1_a.jpg"], [1000], 90.0)]
        dialog = MockDialog(groups)
        
        assert dialog._get_real_group_index(-1) is None
        assert dialog._get_real_group_index(5) is None


class TestHeaderMetricsWithFilters:
    """Tests de métricas del header con filtros."""
    
    def test_metrics_with_no_filtered_groups_show_zero(self):
        """Test: métricas muestran 0 cuando no hay grupos filtrados."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg"], [3000, 1500], 85.0),
        ]
        dialog = MockDialog(groups)
        
        # Filtro que excluye todos los grupos
        dialog.apply_filter(50.0, 60.0)  # Ningún grupo tiene esta similitud
        
        assert len(dialog.filtered_groups) == 0
        
        # Las métricas deben basarse en filtered_groups (vacío = 0)
        total_groups = len(dialog.filtered_groups)
        total_similar = sum(len(g.files) - 1 for g in dialog.filtered_groups)
        
        assert total_groups == 0
        assert total_similar == 0
    
    def test_metrics_reflect_filtered_groups_not_all(self):
        """Test: métricas reflejan grupos filtrados, no todos."""
        groups = [
            create_mock_group("G1", ["/tmp/g1_a.jpg", "/tmp/g1_b.jpg"], [2000, 1000], 90.0),
            create_mock_group("G2", ["/tmp/g2_a.jpg", "/tmp/g2_b.jpg", "/tmp/g2_c.jpg"], 
                             [3000, 1500, 1000], 85.0),
            create_mock_group("G3", ["/tmp/g3_a.jpg", "/tmp/g3_b.jpg"], [1000, 500], 75.0),
        ]
        dialog = MockDialog(groups)
        
        # Total sin filtro: 3 grupos, 4 similares (1+2+1)
        assert len(dialog.all_groups) == 3
        
        # Filtrar: solo alta similitud
        dialog.apply_filter(85.0, 100.0)
        assert len(dialog.filtered_groups) == 2  # G1 y G2
        
        # Métricas deben reflejar solo grupos filtrados
        total_groups = len(dialog.filtered_groups)
        total_similar = sum(len(g.files) - 1 for g in dialog.filtered_groups)
        
        assert total_groups == 2  # No 3
        assert total_similar == 3  # G1: 1, G2: 2 (no G3: 1)


class TestKeepLargestStrategy:
    """Tests específicos de la estrategia 'keep_largest' (Mejor imagen)."""
    
    def test_keep_largest_selects_smaller_files_for_deletion(self):
        """Test: keep_largest marca archivos más pequeños para eliminación."""
        groups = [
            create_mock_group(
                "G1", 
                ["/tmp/largest.jpg", "/tmp/medium.jpg", "/tmp/smallest.jpg"], 
                [5000, 3000, 1000], 
                90.0
            ),
        ]
        dialog = MockDialog(groups)
        
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # El más grande NO debe estar seleccionado para eliminar
        assert Path("/tmp/largest.jpg") not in dialog.selections[0]
        
        # Los más pequeños SÍ deben estar seleccionados para eliminar
        assert Path("/tmp/medium.jpg") in dialog.selections[0]
        assert Path("/tmp/smallest.jpg") in dialog.selections[0]
    
    def test_keep_largest_with_equal_sizes(self):
        """Test: keep_largest con tamaños iguales mantiene el primero."""
        groups = [
            create_mock_group(
                "G1", 
                ["/tmp/first.jpg", "/tmp/second.jpg"], 
                [1000, 1000],  # Mismo tamaño
                90.0
            ),
        ]
        dialog = MockDialog(groups)
        
        dialog._apply_strategy_to_filtered_groups('keep_largest')
        
        # Con tamaños iguales, el orden de sort determina cuál se conserva
        # El comportamiento esperado es que se elimine el segundo (estable sort)
        assert len(dialog.selections[0]) == 1
