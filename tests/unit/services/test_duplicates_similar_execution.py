# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests de ejecución específicos para DuplicatesSimilarService.
Verifica que la eliminación manual respeta la lista de archivos seleccionados.
Usa archivos reales temporales para evitar problemas con mocks globales.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import shutil
import os

from services.duplicates_similar_service import DuplicatesSimilarService
from services.result_types import SimilarDuplicateGroup, SimilarDuplicateAnalysisResult

class TestDuplicatesSimilarExecution:
    """Tests de ejecución con escenarios complejos."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        self.service = DuplicatesSimilarService()
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        
        # Mock SOLO de funciones auxiliares que no afectan el sistema de archivos base
        # Como get_all_metadata_from_file que podría intentar leer exif y fallar o ser lento
        self.mock_get_metadata = patch('utils.date_utils.get_all_metadata_from_file').start()
        mock_meta = MagicMock()
        mock_meta.fs_size = 1000
        self.mock_get_metadata.return_value = mock_meta
        
        patch('utils.date_utils.select_best_date_from_file', return_value=(None, None)).start()

    def teardown_method(self):
        """Cleanup después de cada test."""
        patch.stopall()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def create_real_file(self, filename):
        """Crea un archivo real en el directorio temporal."""
        file_path = self.temp_dir / filename
        # Crear archivo vacío
        with open(file_path, 'w') as f:
            f.write("content")
        return file_path

    def create_mock_group(self, group_id, num_files=2):
        """Crea un grupo con archivos REALES."""
        files = []
        for i in range(num_files):
            file_path = self.create_real_file(f"group{group_id}_file{i}.jpg")
            files.append(file_path)
        
        return SimilarDuplicateGroup(
            hash_value=f"hash_{group_id}",
            files=files,
            file_sizes=[1000] * num_files,
            similarity_score=90.0
        )

    def test_execute_manual_specific_files_multiple_groups(self):
        """
        Escenario: Usuario selecciona manualmente archivos de varios grupos.
        Debe borrar SOLO los seleccionados.
        """
        # Crear 2 grupos con 3 archivos reales cada uno
        group1 = self.create_mock_group(1, num_files=3)
        group2 = self.create_mock_group(2, num_files=3)
        
        analysis = SimilarDuplicateAnalysisResult(
            groups=[group1, group2],
            total_groups=2,
            space_recoverable=0
        )
        
        # Seleccionar borrar: g1_f1 y g2_f2
        files_to_delete = [group1.files[1], group2.files[2]]
        
        # Ejecutar
        result = self.service.execute(
            analysis,
            keep_strategy='manual',
            files_to_delete=files_to_delete,
            create_backup=False,
            dry_run=False
        )
        
        assert result.success is True
        
        # Verificar: g1_f1 y g2_f2 deben NO existir. Los demás deben existir.
        assert not group1.files[1].exists(), "g1_f1 should be deleted"
        assert not group2.files[2].exists(), "g2_f2 should be deleted"
        
        assert group1.files[0].exists(), "g1_f0 should be kept"
        assert group1.files[2].exists(), "g1_f2 should be kept"
        assert group2.files[0].exists(), "g2_f0 should be kept"
        assert group2.files[1].exists(), "g2_f1 should be kept"

    def test_execute_manual_auto_simulation(self):
        """
        Escenario: Simulación de modo 'Auto'.
        """
        group1 = self.create_mock_group(1, num_files=3)
        
        # Auto selecciona g1_f1 y g1_f2 para borrar
        files_to_delete = [group1.files[1], group1.files[2]]
        
        analysis = SimilarDuplicateAnalysisResult(
            groups=[group1],
            
            
            total_groups=1,
            space_recoverable=0
        )
        
        result = self.service.execute(
            analysis,
            keep_strategy='manual',
            files_to_delete=files_to_delete,
            create_backup=False,
            dry_run=False
        )
        
        assert result.success is True
        
        assert not group1.files[1].exists()
        assert not group1.files[2].exists()
        assert group1.files[0].exists()

    def test_execute_manual_no_selection(self):
        """
        Escenario: Modo manual sin selección.
        """
        group1 = self.create_mock_group(1, num_files=2)
        
        files_to_delete = []
        
        analysis = SimilarDuplicateAnalysisResult(
            groups=[group1],
            
            
            total_groups=1,
            space_recoverable=0
        )
        
        result = self.service.execute(
            analysis,
            keep_strategy='manual',
            files_to_delete=files_to_delete,
            create_backup=False,
            dry_run=False
        )
        
        assert result.success is True
        
        # Nada borrado
        assert group1.files[0].exists()
        assert group1.files[1].exists()

    def test_execute_manual_delete_all_in_group(self):
        """
        Escenario: Borrar TODOS los archivos de un grupo.
        """
        group1 = self.create_mock_group(1, num_files=2)
        
        files_to_delete = group1.files
        
        analysis = SimilarDuplicateAnalysisResult(
            groups=[group1],
            
            
            total_groups=1,
            space_recoverable=0
        )
        
        result = self.service.execute(
            analysis,
            keep_strategy='manual',
            files_to_delete=files_to_delete,
            create_backup=False,
            dry_run=False
        )
        
        assert result.success is True
        
        assert not group1.files[0].exists()
        assert not group1.files[1].exists()
