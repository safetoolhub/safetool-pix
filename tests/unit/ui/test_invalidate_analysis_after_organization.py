# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para la invalidación de análisis previos después de ejecutar herramientas
de organización (file_organizer, file_renamer).

Bug corregido: Cuando se ejecutaba file_organizer o file_renamer, los análisis
previos de otras herramientas (duplicates_similar, duplicates_exact, etc.) no se
invalidaban. Esto causaba segfault porque esos análisis contenían rutas de archivos
que ya no existían (habían sido movidos/renombrados).

La corrección extiende _invalidate_related_analysis_results() para que también
invalide todos los análisis cuando se ejecutan herramientas organizativas.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Optional, Any, List

from services.result_types import (
    ScanSnapshot,
    DirectoryScanResult,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_main_window():
    """Crea un mock de MainWindow con los atributos necesarios."""
    window = MagicMock()
    window.centralWidget.return_value = MagicMock()
    window.main_layout = MagicMock()
    return window


@pytest.fixture
def scan_snapshot():
    """Crea un ScanSnapshot con datos de análisis simulados en todos los campos."""
    scan = DirectoryScanResult(
        total_files=100,
        images=[Path(f'/tmp/photos/img_{i}.jpg') for i in range(50)],
        videos=[Path(f'/tmp/photos/vid_{i}.mp4') for i in range(30)],
        others=[Path(f'/tmp/photos/doc_{i}.txt') for i in range(20)],
        total_size=1024 * 1024 * 500,  # 500 MB
    )
    
    snapshot = ScanSnapshot(
        directory=Path('/tmp/photos'),
        scan=scan,
    )
    
    # Simular que ya se han ejecutado análisis previos
    snapshot.live_photos = MagicMock(name='live_photos_result')
    snapshot.heic = MagicMock(name='heic_result')
    snapshot.duplicates = MagicMock(name='duplicates_result')
    snapshot.duplicates_similar = MagicMock(name='duplicates_similar_result')
    snapshot.visual_identical = MagicMock(name='visual_identical_result')
    snapshot.zero_byte = MagicMock(name='zero_byte_result')
    snapshot.organization = MagicMock(name='organization_result')
    snapshot.renaming = MagicMock(name='renaming_result')
    
    return snapshot


@pytest.fixture
def base_stage(mock_main_window, scan_snapshot):
    """Crea una instancia de BaseStage con analysis_results poblados."""
    from ui.screens.base_stage import BaseStage
    
    stage = BaseStage(mock_main_window)
    stage.analysis_results = scan_snapshot
    return stage


# ============================================================================
# Tests: file_organizer invalida todos los análisis
# ============================================================================

class TestFileOrganizerInvalidatesAllAnalyses:
    """
    Verifica que file_organizer invalida TODOS los análisis previos,
    incluyendo su propio resultado de organización.
    
    Razón: file_organizer mueve archivos a nuevas carpetas, cambiando sus rutas.
    Cualquier análisis previo que contenga rutas antiguas es inválido.
    """

    def test_invalidates_live_photos(self, base_stage):
        """file_organizer debe invalidar análisis de live_photos."""
        assert base_stage.analysis_results.live_photos is not None
        base_stage._invalidate_related_analysis_results('file_organizer')
        assert base_stage.analysis_results.live_photos is None

    def test_invalidates_heic(self, base_stage):
        """file_organizer debe invalidar análisis de heic."""
        assert base_stage.analysis_results.heic is not None
        base_stage._invalidate_related_analysis_results('file_organizer')
        assert base_stage.analysis_results.heic is None

    def test_invalidates_duplicates_exact(self, base_stage):
        """file_organizer debe invalidar análisis de duplicados exactos."""
        assert base_stage.analysis_results.duplicates is not None
        base_stage._invalidate_related_analysis_results('file_organizer')
        assert base_stage.analysis_results.duplicates is None

    def test_invalidates_duplicates_similar(self, base_stage):
        """file_organizer debe invalidar análisis de duplicados similares."""
        assert base_stage.analysis_results.duplicates_similar is not None
        base_stage._invalidate_related_analysis_results('file_organizer')
        assert base_stage.analysis_results.duplicates_similar is None

    def test_invalidates_visual_identical(self, base_stage):
        """file_organizer debe invalidar análisis de copias visuales idénticas."""
        assert base_stage.analysis_results.visual_identical is not None
        base_stage._invalidate_related_analysis_results('file_organizer')
        assert base_stage.analysis_results.visual_identical is None

    def test_invalidates_zero_byte(self, base_stage):
        """file_organizer debe invalidar análisis de archivos vacíos."""
        assert base_stage.analysis_results.zero_byte is not None
        base_stage._invalidate_related_analysis_results('file_organizer')
        assert base_stage.analysis_results.zero_byte is None

    def test_invalidates_own_organization_result(self, base_stage):
        """file_organizer debe invalidar su propio resultado de organización."""
        assert base_stage.analysis_results.organization is not None
        base_stage._invalidate_related_analysis_results('file_organizer')
        assert base_stage.analysis_results.organization is None

    def test_invalidates_renaming_result(self, base_stage):
        """file_organizer debe invalidar el resultado de renombrado."""
        assert base_stage.analysis_results.renaming is not None
        base_stage._invalidate_related_analysis_results('file_organizer')
        assert base_stage.analysis_results.renaming is None

    def test_invalidates_all_at_once(self, base_stage):
        """file_organizer debe invalidar TODOS los análisis en una sola llamada."""
        base_stage._invalidate_related_analysis_results('file_organizer')
        
        assert base_stage.analysis_results.live_photos is None
        assert base_stage.analysis_results.heic is None
        assert base_stage.analysis_results.duplicates is None
        assert base_stage.analysis_results.duplicates_similar is None
        assert base_stage.analysis_results.visual_identical is None
        assert base_stage.analysis_results.zero_byte is None
        assert base_stage.analysis_results.organization is None
        assert base_stage.analysis_results.renaming is None


# ============================================================================
# Tests: file_renamer invalida todos los análisis
# ============================================================================

class TestFileRenamerInvalidatesAllAnalyses:
    """
    Verifica que file_renamer invalida TODOS los análisis previos,
    incluyendo su propio resultado de renombrado.
    
    Razón: file_renamer cambia los nombres de los archivos. Cualquier análisis
    previo que contenga nombres/rutas antiguas es inválido y causa segfault.
    """

    def test_invalidates_live_photos(self, base_stage):
        """file_renamer debe invalidar análisis de live_photos."""
        assert base_stage.analysis_results.live_photos is not None
        base_stage._invalidate_related_analysis_results('file_renamer')
        assert base_stage.analysis_results.live_photos is None

    def test_invalidates_heic(self, base_stage):
        """file_renamer debe invalidar análisis de heic."""
        assert base_stage.analysis_results.heic is not None
        base_stage._invalidate_related_analysis_results('file_renamer')
        assert base_stage.analysis_results.heic is None

    def test_invalidates_duplicates_exact(self, base_stage):
        """file_renamer debe invalidar análisis de duplicados exactos."""
        assert base_stage.analysis_results.duplicates is not None
        base_stage._invalidate_related_analysis_results('file_renamer')
        assert base_stage.analysis_results.duplicates is None

    def test_invalidates_duplicates_similar(self, base_stage):
        """file_renamer debe invalidar análisis de duplicados similares."""
        assert base_stage.analysis_results.duplicates_similar is not None
        base_stage._invalidate_related_analysis_results('file_renamer')
        assert base_stage.analysis_results.duplicates_similar is None

    def test_invalidates_visual_identical(self, base_stage):
        """file_renamer debe invalidar análisis de copias visuales idénticas."""
        assert base_stage.analysis_results.visual_identical is not None
        base_stage._invalidate_related_analysis_results('file_renamer')
        assert base_stage.analysis_results.visual_identical is None

    def test_invalidates_zero_byte(self, base_stage):
        """file_renamer debe invalidar análisis de archivos vacíos."""
        assert base_stage.analysis_results.zero_byte is not None
        base_stage._invalidate_related_analysis_results('file_renamer')
        assert base_stage.analysis_results.zero_byte is None

    def test_invalidates_own_renaming_result(self, base_stage):
        """file_renamer debe invalidar su propio resultado de renombrado."""
        assert base_stage.analysis_results.renaming is not None
        base_stage._invalidate_related_analysis_results('file_renamer')
        assert base_stage.analysis_results.renaming is None

    def test_invalidates_organization_result(self, base_stage):
        """file_renamer debe invalidar el resultado de organización."""
        assert base_stage.analysis_results.organization is not None
        base_stage._invalidate_related_analysis_results('file_renamer')
        assert base_stage.analysis_results.organization is None

    def test_invalidates_all_at_once(self, base_stage):
        """file_renamer debe invalidar TODOS los análisis en una sola llamada."""
        base_stage._invalidate_related_analysis_results('file_renamer')
        
        assert base_stage.analysis_results.live_photos is None
        assert base_stage.analysis_results.heic is None
        assert base_stage.analysis_results.duplicates is None
        assert base_stage.analysis_results.duplicates_similar is None
        assert base_stage.analysis_results.visual_identical is None
        assert base_stage.analysis_results.zero_byte is None
        assert base_stage.analysis_results.organization is None
        assert base_stage.analysis_results.renaming is None


# ============================================================================
# Tests: Herramientas destructivas NO invalidan su propio resultado
# ============================================================================

class TestDestructiveToolsPreserveOwnResult:
    """
    Verifica que las herramientas destructivas (no organizativas) invalidan
    los análisis de OTRAS herramientas pero NO su propio resultado.
    
    Esto permite que el usuario vea el resultado actualizado de la herramienta
    que acaba de ejecutar sin necesidad de re-analizar.
    """

    @pytest.mark.parametrize("tool_id,own_attr", [
        ('live_photos', 'live_photos'),
        ('heic', 'heic'),
        ('duplicates_exact', 'duplicates'),
        ('duplicates_similar', 'duplicates_similar'),
        ('visual_identical', 'visual_identical'),
        ('zero_byte', 'zero_byte'),
    ])
    def test_destructive_tool_preserves_own_result(self, base_stage, tool_id, own_attr):
        """Herramientas destructivas preservan su propio análisis."""
        original_value = getattr(base_stage.analysis_results, own_attr)
        assert original_value is not None
        
        base_stage._invalidate_related_analysis_results(tool_id)
        
        # El propio resultado NO debe ser invalidado
        assert getattr(base_stage.analysis_results, own_attr) is original_value

    @pytest.mark.parametrize("tool_id", [
        'live_photos', 'heic', 'duplicates_exact',
        'duplicates_similar', 'visual_identical', 'zero_byte',
    ])
    def test_destructive_tool_invalidates_others(self, base_stage, tool_id):
        """Herramientas destructivas invalidan los análisis de las demás."""
        base_stage._invalidate_related_analysis_results(tool_id)
        
        # Verificar que al menos algunos otros análisis fueron invalidados
        all_attrs = ['live_photos', 'heic', 'duplicates', 'duplicates_similar',
                     'visual_identical', 'zero_byte']
        
        # Mapeo tool_id -> attr_name
        tool_to_attr = {
            'live_photos': 'live_photos',
            'heic': 'heic',
            'duplicates_exact': 'duplicates',
            'duplicates_similar': 'duplicates_similar',
            'visual_identical': 'visual_identical',
            'zero_byte': 'zero_byte',
        }
        own_attr = tool_to_attr[tool_id]
        
        # Todos los demás deben ser None
        for attr in all_attrs:
            if attr != own_attr:
                assert getattr(base_stage.analysis_results, attr) is None, \
                    f"{tool_id} should have invalidated {attr}"


# ============================================================================
# Tests: Diferencia clave entre organizativas y destructivas
# ============================================================================

class TestOrganizationVsDestructiveBehavior:
    """
    Verifica la diferencia fundamental entre herramientas organizativas y destructivas:
    - Organizativas (file_organizer, file_renamer): invalidan TODO, incluido su propio resultado
    - Destructivas (live_photos, heic, etc.): invalidan todo EXCEPTO su propio resultado
    """

    def test_file_organizer_invalidates_own_result(self, base_stage):
        """file_organizer invalida su propio resultado (organization)."""
        assert base_stage.analysis_results.organization is not None
        base_stage._invalidate_related_analysis_results('file_organizer')
        assert base_stage.analysis_results.organization is None

    def test_file_renamer_invalidates_own_result(self, base_stage):
        """file_renamer invalida su propio resultado (renaming)."""
        assert base_stage.analysis_results.renaming is not None
        base_stage._invalidate_related_analysis_results('file_renamer')
        assert base_stage.analysis_results.renaming is None

    def test_destructive_tool_does_not_invalidate_own(self, base_stage):
        """duplicates_exact NO invalida su propio resultado."""
        assert base_stage.analysis_results.duplicates is not None
        base_stage._invalidate_related_analysis_results('duplicates_exact')
        assert base_stage.analysis_results.duplicates is not None


# ============================================================================
# Tests: Edge cases
# ============================================================================

class TestInvalidationEdgeCases:
    """Tests de casos límite para la invalidación."""

    def test_no_crash_when_analysis_results_is_none(self, mock_main_window):
        """No debe crashear si analysis_results es None."""
        from ui.screens.base_stage import BaseStage
        stage = BaseStage(mock_main_window)
        stage.analysis_results = None
        
        # No debe lanzar excepción
        stage._invalidate_related_analysis_results('file_organizer')
        stage._invalidate_related_analysis_results('file_renamer')

    def test_no_crash_when_no_analysis_results_attr(self, mock_main_window):
        """No debe crashear si no existe el atributo analysis_results."""
        from ui.screens.base_stage import BaseStage
        stage = BaseStage(mock_main_window)
        # No asignar analysis_results
        
        # No debe lanzar excepción
        stage._invalidate_related_analysis_results('file_organizer')

    def test_partial_results_only_invalidates_existing(self, base_stage):
        """Solo invalida los análisis que realmente existen (no None)."""
        # Simular que solo algunos análisis se han ejecutado
        base_stage.analysis_results.live_photos = None
        base_stage.analysis_results.heic = None
        base_stage.analysis_results.zero_byte = None
        
        # Los que sí tienen datos
        assert base_stage.analysis_results.duplicates is not None
        assert base_stage.analysis_results.duplicates_similar is not None
        
        base_stage._invalidate_related_analysis_results('file_organizer')
        
        # Los que tenían datos deben ser invalidados
        assert base_stage.analysis_results.duplicates is None
        assert base_stage.analysis_results.duplicates_similar is None
        
        # Los que ya eran None siguen siendo None (sin error)
        assert base_stage.analysis_results.live_photos is None
        assert base_stage.analysis_results.heic is None

    def test_unknown_tool_does_not_invalidate(self, base_stage):
        """Una herramienta desconocida no invalida nada."""
        base_stage._invalidate_related_analysis_results('unknown_tool')
        
        # Nada debe cambiar
        assert base_stage.analysis_results.live_photos is not None
        assert base_stage.analysis_results.heic is not None
        assert base_stage.analysis_results.duplicates is not None
        assert base_stage.analysis_results.duplicates_similar is not None
        assert base_stage.analysis_results.visual_identical is not None
        assert base_stage.analysis_results.zero_byte is not None
        assert base_stage.analysis_results.organization is not None
        assert base_stage.analysis_results.renaming is not None

    def test_scan_result_not_affected(self, base_stage):
        """El resultado del scan inicial nunca se invalida."""
        original_scan = base_stage.analysis_results.scan
        
        base_stage._invalidate_related_analysis_results('file_organizer')
        
        # El scan debe permanecer intacto
        assert base_stage.analysis_results.scan is original_scan
        assert base_stage.analysis_results.scan.total_files == 100

    def test_idempotent_invalidation(self, base_stage):
        """Llamar a invalidar múltiples veces no causa error."""
        base_stage._invalidate_related_analysis_results('file_organizer')
        # Segunda llamada con todo ya None
        base_stage._invalidate_related_analysis_results('file_organizer')
        
        # Todo sigue None sin error
        assert base_stage.analysis_results.duplicates is None
        assert base_stage.analysis_results.duplicates_similar is None


# ============================================================================
# Tests: Escenario completo del bug (regresión)
# ============================================================================

class TestBugScenarioOrganizationThenSimilar:
    """
    Test de regresión para el bug original:
    
    1. Usuario analiza archivos similares → duplicates_similar tiene datos con rutas
    2. Usuario ejecuta file_organizer → archivos se mueven a nuevas carpetas
    3. Usuario hace clic en "similares" → intenta usar rutas antiguas → segfault
    
    La corrección asegura que en el paso 2, duplicates_similar se invalida,
    forzando un re-análisis fresco en el paso 3.
    """

    def test_similar_analysis_invalidated_after_organizer(self, base_stage):
        """
        Después de file_organizer, duplicates_similar debe ser None,
        forzando re-análisis cuando el usuario haga clic en la herramienta.
        """
        # Simular que duplicates_similar tiene datos con rutas antiguas
        mock_similar = MagicMock()
        mock_similar.perceptual_hashes = {
            Path('/tmp/photos/img_1.jpg'): 'hash1',
            Path('/tmp/photos/img_2.jpg'): 'hash2',
        }
        base_stage.analysis_results.duplicates_similar = mock_similar
        
        # Ejecutar file_organizer (mueve archivos)
        base_stage._invalidate_related_analysis_results('file_organizer')
        
        # duplicates_similar debe ser None → forzará re-análisis
        assert base_stage.analysis_results.duplicates_similar is None

    def test_similar_analysis_invalidated_after_renamer(self, base_stage):
        """
        Después de file_renamer, duplicates_similar debe ser None,
        forzando re-análisis cuando el usuario haga clic en la herramienta.
        """
        # Simular que duplicates_similar tiene datos con nombres antiguos
        mock_similar = MagicMock()
        mock_similar.perceptual_hashes = {
            Path('/tmp/photos/IMG_20240101_120000.jpg'): 'hash1',
            Path('/tmp/photos/IMG_20240101_120001.jpg'): 'hash2',
        }
        base_stage.analysis_results.duplicates_similar = mock_similar
        
        # Ejecutar file_renamer (renombra archivos)
        base_stage._invalidate_related_analysis_results('file_renamer')
        
        # duplicates_similar debe ser None → forzará re-análisis
        assert base_stage.analysis_results.duplicates_similar is None

    def test_exact_duplicates_invalidated_after_organizer(self, base_stage):
        """
        Después de file_organizer, duplicates (exactos) debe ser None.
        Los grupos de duplicados contienen rutas que ya no son válidas.
        """
        mock_exact = MagicMock()
        mock_exact.total_groups = 5
        base_stage.analysis_results.duplicates = mock_exact
        
        base_stage._invalidate_related_analysis_results('file_organizer')
        
        assert base_stage.analysis_results.duplicates is None

    def test_visual_identical_invalidated_after_renamer(self, base_stage):
        """
        Después de file_renamer, visual_identical debe ser None.
        Los grupos visuales contienen rutas con nombres antiguos.
        """
        mock_visual = MagicMock()
        mock_visual.total_groups = 3
        base_stage.analysis_results.visual_identical = mock_visual
        
        base_stage._invalidate_related_analysis_results('file_renamer')
        
        assert base_stage.analysis_results.visual_identical is None
