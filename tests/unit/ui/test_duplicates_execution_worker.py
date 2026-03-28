# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Test para verificar el fix de DuplicatesExecutionWorker.
Asegura que files_to_delete se pasa correctamente al servicio.
"""
import pytest
from unittest.mock import MagicMock, ANY
from pathlib import Path
from ui.workers.execution_workers import DuplicatesExecutionWorker

def test_duplicates_execution_worker_passes_files_to_delete():
    """Test que verifica que files_to_delete llega al método execute del detector."""
    # Setup
    mock_detector = MagicMock()
    mock_analysis = MagicMock()
    files_to_delete = [Path("/tmp/file1.jpg"), Path("/tmp/file2.jpg")]
    
    # Crear worker con files_to_delete
    worker = DuplicatesExecutionWorker(
        detector=mock_detector,
        analysis=mock_analysis,
        keep_strategy='manual',
        create_backup=True,
        dry_run=False,
        files_to_delete=files_to_delete
    )
    
    # Ejecutar worker
    worker.run()
    
    # Verificar que execute fue llamado con files_to_delete en kwargs
    mock_detector.execute.assert_called_once()
    
    # Verificar argumentos llamados
    call_args = mock_detector.execute.call_args
    kwargs = call_args.kwargs
    
    assert 'files_to_delete' in kwargs
    assert kwargs['files_to_delete'] == files_to_delete
    assert kwargs['keep_strategy'] == 'manual'

def test_duplicates_execution_worker_default_none():
    """Test que verifica el comportamiento por defecto (None)."""
    mock_detector = MagicMock()
    mock_analysis = MagicMock()
    
    worker = DuplicatesExecutionWorker(
        detector=mock_detector,
        analysis=mock_analysis,
        keep_strategy='oldest'
    )
    
    worker.run()
    
    call_args = mock_detector.execute.call_args
    kwargs = call_args.kwargs
    
    assert kwargs['files_to_delete'] is None
