# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests unitarios para BaseService - Fase 2 de refactorización.

Valida la nueva infraestructura centralizada:
- _execute_operation() template method
- _parallel_processor() context manager
- _get_max_workers() configuración
- _validate_directory() validación
- _get_supported_files() recopilación
- _should_report_progress() helper
"""

import pytest
from pathlib import Path
from typing import Optional
from unittest.mock import Mock, patch, MagicMock
from services.base_service import BaseService, BackupCreationError
from services.result_types import BaseResult


class ConcreteService(BaseService):
    """Implementación concreta de BaseService para testing."""
    
    def __init__(self):
        super().__init__('TestService')
    
    def analyze(self, directory: Path, **kwargs):
        """Método stub para satisfacer ABC."""
        pass
    
    def execute(self, analysis_result, **kwargs):
        """Método stub para satisfacer ABC."""
        pass


@pytest.fixture
def service():
    """Fixture para instancia de servicio de prueba."""
    return ConcreteService()


@pytest.fixture
def temp_files(tmp_path):
    """Fixture para crear archivos temporales de prueba."""
    files = []
    for i in range(5):
        file = tmp_path / f"test_{i}.jpg"
        file.write_text(f"test content {i}")
        files.append(file)
    return files


# =============================================================================
# Tests para _execute_operation()
# =============================================================================

class TestExecuteOperation:
    """Test suite para método _execute_operation()."""
    
    def test_execute_operation_with_backup_success(self, service, temp_files):
        """Backup se crea y backup_path se popula en resultado."""
        # Mock de _create_backup_for_operation
        with patch.object(service, '_create_backup_for_operation') as mock_backup:
            mock_backup.return_value = Path('/fake/backup')
            
            # Función de ejecución mock que retorna resultado
            # Crear clase simple con backup_path para testing
            class TestResult(BaseResult):
                backup_path: Optional[Path] = None
            
            def execute_fn(dry_run):
                result = TestResult(
                    success=True,
                    message="Operación exitosa"
                )
                result.backup_path = None  # Debe ser poblado por _execute_operation
                return result
            
            # Ejecutar
            result = service._execute_operation(
                files=temp_files,
                operation_name='test_operation',
                execute_fn=execute_fn,
                create_backup=True,
                dry_run=False
            )
            
            # Validar
            assert result.success is True
            assert hasattr(result, 'backup_path')
            assert result.backup_path == Path('/fake/backup')
            mock_backup.assert_called_once()
    
    def test_execute_operation_without_backup(self, service, temp_files):
        """create_backup=False, no crea backup, backup_path es None."""
        with patch.object(service, '_create_backup_for_operation') as mock_backup:
            class TestResult(BaseResult):
                backup_path: Optional[Path] = None
            
            def execute_fn(dry_run):
                result = TestResult(success=True, message="OK")
                result.backup_path = None
                return result
            
            result = service._execute_operation(
                files=temp_files,
                operation_name='test_operation',
                execute_fn=execute_fn,
                create_backup=False,
                dry_run=False
            )
            
            # No debe llamar a backup
            mock_backup.assert_not_called()
            # Si tiene backup_path, debe ser None
            if hasattr(result, 'backup_path'):
                assert result.backup_path is None
    
    def test_execute_operation_dry_run_no_backup(self, service, temp_files):
        """dry_run=True, no crea backup incluso si create_backup=True."""
        with patch.object(service, '_create_backup_for_operation') as mock_backup:
            class TestResult(BaseResult):
                backup_path: Optional[Path] = None
            
            def execute_fn(dry_run):
                assert dry_run is True
                result = TestResult(success=True, message="Simulación")
                result.backup_path = None
                return result
            
            result = service._execute_operation(
                files=temp_files,
                operation_name='test_operation',
                execute_fn=execute_fn,
                create_backup=True,  # Solicita backup pero...
                dry_run=True  # ...dry_run tiene prioridad
            )
            
            # No debe crear backup en simulación
            mock_backup.assert_not_called()
            # Si tiene backup_path, debe ser None
            if hasattr(result, 'backup_path'):
                assert result.backup_path is None
    
    def test_execute_operation_handles_backup_error(self, service, temp_files):
        """BackupCreationError capturada, retorna resultado con error."""
        with patch.object(service, '_create_backup_for_operation') as mock_backup:
            # Simular error de backup
            mock_backup.side_effect = BackupCreationError("Error creando backup")
            
            def execute_fn(dry_run):
                pytest.fail("No debería ejecutarse si backup falla")
            
            result = service._execute_operation(
                files=temp_files,
                operation_name='test_operation',
                execute_fn=execute_fn,
                create_backup=True,
                dry_run=False
            )
            
            # Debe retornar error sin ejecutar
            assert result.success is False
            assert "backup" in result.message.lower()
    
    def test_execute_operation_propagates_execute_fn_exception(self, service, temp_files):
        """Excepciones de execute_fn se propagan correctamente."""
        with patch.object(service, '_create_backup_for_operation'):
            def execute_fn(dry_run):
                raise ValueError("Error en ejecución")
            
            # La excepción debe propagarse
            with pytest.raises(ValueError, match="Error en ejecución"):
                service._execute_operation(
                    files=temp_files,
                    operation_name='test_operation',
                    execute_fn=execute_fn,
                    create_backup=False,
                    dry_run=False
                )
    
    def test_execute_operation_with_progress_callback(self, service, temp_files):
        """Progress callback se pasa a backup y execute_fn."""
        callback = Mock()
        
        with patch.object(service, '_create_backup_for_operation') as mock_backup:
            mock_backup.return_value = Path('/backup')
            
            class TestResult(BaseResult):
                backup_path: Optional[Path] = None
            
            def execute_fn(dry_run):
                result = TestResult(success=True, message="OK")
                result.backup_path = None
                return result
            
            service._execute_operation(
                files=temp_files,
                operation_name='test',
                execute_fn=execute_fn,
                create_backup=True,
                dry_run=False,
                progress_callback=callback
            )
            
            # Callback debe pasarse a backup
            assert mock_backup.call_args[1]['progress_callback'] == callback


# =============================================================================
# Tests para _parallel_processor()
# =============================================================================

class TestParallelProcessor:
    """Test suite para context manager _parallel_processor()."""
    
    def test_parallel_processor_yields_executor(self, service):
        """Context manager yields ThreadPoolExecutor configurado."""
        from concurrent.futures import ThreadPoolExecutor
        
        with service._parallel_processor(io_bound=True) as executor:
            assert isinstance(executor, ThreadPoolExecutor)
    
    def test_parallel_processor_uses_correct_max_workers(self, service):
        """max_workers se obtiene correctamente según io_bound."""
        with patch.object(service, '_get_max_workers') as mock_get_workers:
            mock_get_workers.return_value = 8
            
            with service._parallel_processor(io_bound=True) as executor:
                # Verificar que se llamó con io_bound correcto
                mock_get_workers.assert_called_once_with(True)
    
    def test_parallel_processor_io_bound_vs_cpu_bound(self, service):
        """Diferentes valores de io_bound se pasan a _get_max_workers."""
        with patch.object(service, '_get_max_workers') as mock_get_workers:
            mock_get_workers.return_value = 4
            
            # Test IO-bound
            with service._parallel_processor(io_bound=True):
                assert mock_get_workers.call_args[0][0] is True
            
            mock_get_workers.reset_mock()
            
            # Test CPU-bound
            with service._parallel_processor(io_bound=False):
                assert mock_get_workers.call_args[0][0] is False


# =============================================================================
# Tests para _get_max_workers()
# =============================================================================

class TestGetMaxWorkers:
    """Test suite para configuración de workers."""
    
    @patch('config.Config')
    @patch('utils.settings_manager.settings_manager')
    def test_get_max_workers_with_user_override(self, mock_settings, mock_config, service):
        """Usuario puede override desde settings."""
        mock_settings.get_max_workers.return_value = 16
        mock_config.get_actual_worker_threads.return_value = 16
        
        result = service._get_max_workers(io_bound=True)
        
        assert result == 16
        mock_settings.get_max_workers.assert_called_once_with(0)
        mock_config.get_actual_worker_threads.assert_called_once_with(
            override=16,
            io_bound=True
        )
    
    @patch('config.Config')
    @patch('utils.settings_manager.settings_manager')
    def test_get_max_workers_default(self, mock_settings, mock_config, service):
        """Sin override, usa configuración default."""
        mock_settings.get_max_workers.return_value = 0  # Sin override
        mock_config.get_actual_worker_threads.return_value = 4
        
        result = service._get_max_workers(io_bound=False)
        
        assert result == 4
        mock_config.get_actual_worker_threads.assert_called_once_with(
            override=0,
            io_bound=False
        )


# =============================================================================
# Tests para _validate_directory()
# =============================================================================

class TestValidateDirectory:
    """Test suite para validación de directorios."""
    
    def test_validate_directory_valid(self, service, tmp_path):
        """Directorio válido no lanza excepción."""
        # No debe lanzar excepción
        service._validate_directory(tmp_path, must_exist=True)
    
    def test_validate_directory_not_exists(self, service, tmp_path):
        """Directorio inexistente lanza ValueError."""
        non_existent = tmp_path / "no_existe"
        
        with pytest.raises(ValueError, match="does not exist"):
            service._validate_directory(non_existent, must_exist=True)
    
    def test_validate_directory_not_dir(self, service, tmp_path):
        """Path que no es directorio lanza ValueError."""
        file_path = tmp_path / "archivo.txt"
        file_path.write_text("contenido")
        
        with pytest.raises(ValueError, match="Not a directory"):
            service._validate_directory(file_path, must_exist=True)
    
    def test_validate_directory_must_exist_false(self, service, tmp_path):
        """must_exist=False permite directorios no existentes."""
        non_existent = tmp_path / "no_existe"
        
        # No debe lanzar excepción
        service._validate_directory(non_existent, must_exist=False)


# =============================================================================
# Tests para _get_supported_files()
# =============================================================================

class TestGetSupportedFiles:
    """Test suite para recopilación de archivos soportados."""
    
    def test_get_supported_files_filters_correctly(self, service, tmp_path):
        """Solo retorna archivos multimedia soportados."""
        # Crear archivos soportados
        (tmp_path / "foto.jpg").write_text("jpg")
        (tmp_path / "video.mp4").write_text("mp4")
        
        # Crear archivos NO soportados
        (tmp_path / "documento.txt").write_text("txt")
        (tmp_path / "programa.exe").write_text("exe")
        
        with patch('config.Config.SUPPORTED_IMAGE_EXTENSIONS', ['.jpg']), \
             patch('config.Config.SUPPORTED_VIDEO_EXTENSIONS', ['.mp4']):
            
            files = service._get_supported_files(tmp_path, recursive=False)
            
            # Solo debe retornar 2 archivos
            assert len(files) == 2
            assert all(f.suffix in ['.jpg', '.mp4'] for f in files)
    
    def test_get_supported_files_respects_recursive(self, service, tmp_path):
        """recursive=False no busca en subdirectorios."""
        # Archivo en raíz
        (tmp_path / "raiz.jpg").write_text("root")
        
        # Archivo en subdirectorio
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "sub.jpg").write_text("sub")
        
        with patch('config.Config.SUPPORTED_IMAGE_EXTENSIONS', ['.jpg']), \
             patch('config.Config.SUPPORTED_VIDEO_EXTENSIONS', []):
            
            # Recursive=False: solo raíz
            files = service._get_supported_files(tmp_path, recursive=False)
            assert len(files) == 1
            assert files[0].name == "raiz.jpg"
            
            # Recursive=True: ambos
            files = service._get_supported_files(tmp_path, recursive=True)
            assert len(files) == 2
    
    def test_get_supported_files_supports_cancellation(self, service, tmp_path):
        """Callback puede cancelar scan de archivos."""
        # Crear varios archivos
        for i in range(10):
            (tmp_path / f"file_{i}.jpg").write_text(str(i))
        
        # Callback que cancela después de 5 llamadas
        call_count = [0]
        
        def cancel_callback(current, total, message):
            call_count[0] += 1
            return call_count[0] < 3  # Cancelar en tercera llamada
        
        with patch('config.Config') as mock_config:
            mock_config.is_supported_file = lambda x: True
            mock_config.UI_UPDATE_INTERVAL = 1  # Reportar cada archivo
            
            files = service._get_supported_files(
                tmp_path,
                recursive=False,
                progress_callback=cancel_callback
            )
            
            # Debe haber procesado menos archivos debido a cancelación
            # (El número exacto depende del orden de glob)
            assert len(files) < 10
    
    def test_get_supported_files_with_progress_callback(self, service, tmp_path):
        """Progress callback se llama durante scan."""
        for i in range(5):
            (tmp_path / f"file_{i}.jpg").write_text(str(i))
        
        callback = Mock(return_value=True)
        
        with patch('config.Config') as mock_config:
            mock_config.is_supported_file = lambda x: True
            mock_config.UI_UPDATE_INTERVAL = 1  # Reportar cada archivo
            
            service._get_supported_files(
                tmp_path,
                recursive=False,
                progress_callback=callback
            )
            
            # Callback debe haberse llamado
            assert callback.call_count > 0


# =============================================================================
# Tests para _should_report_progress()
# =============================================================================

class TestShouldReportProgress:
    """Test suite para helper de intervalos de progreso."""
    
    @patch('config.Config')
    def test_should_report_progress_default_interval(self, mock_config, service):
        """Usa Config.UI_UPDATE_INTERVAL por defecto."""
        mock_config.UI_UPDATE_INTERVAL = 10
        
        # Múltiplos de 10
        assert service._should_report_progress(0) is True
        assert service._should_report_progress(10) is True
        assert service._should_report_progress(20) is True
        
        # No múltiplos
        assert service._should_report_progress(1) is False
        assert service._should_report_progress(15) is False
    
    def test_should_report_progress_custom_interval(self, service):
        """Permite especificar intervalo custom."""
        # Intervalo de 5
        assert service._should_report_progress(0, interval=5) is True
        assert service._should_report_progress(5, interval=5) is True
        assert service._should_report_progress(10, interval=5) is True
        
        assert service._should_report_progress(3, interval=5) is False
        assert service._should_report_progress(7, interval=5) is False


# =============================================================================
# Tests para _format_operation_summary() (validación)
# =============================================================================

class TestFormatOperationSummary:
    """Test suite para formateo de resúmenes."""
    
    def test_format_operation_summary_basic(self, service):
        """Formato básico sin espacio."""
        result = service._format_operation_summary(
            "Renombrado",
            10,
            space_amount=0,
            dry_run=False
        )
        
        assert "Renombrado" in result
        assert "10 archivos procesados" in result
    
    def test_format_operation_summary_with_space(self, service):
        """Formato con espacio liberado."""
        result = service._format_operation_summary(
            "Eliminación",
            5,
            space_amount=5242880,  # 5 MB
            dry_run=False
        )
        
        assert "5 archivos procesados" in result
        assert "liberados" in result
    
    def test_format_operation_summary_dry_run(self, service):
        """Verbos condicionales en dry_run."""
        result = service._format_operation_summary(
            "Eliminación",
            10,
            space_amount=1048576,
            dry_run=True
        )
        
        assert "se procesarían" in result
        assert "se liberarían" in result


# =============================================================================
# Tests de Integración
# =============================================================================

class TestBaseServiceIntegration:
    """Tests de integración de múltiples métodos."""
    
    def test_full_workflow_with_backup(self, service, tmp_path):
        """Workflow completo: validar, escanear, ejecutar con backup."""
        # Setup: crear archivos
        for i in range(3):
            (tmp_path / f"file_{i}.jpg").write_text(str(i))
        
        # 1. Validar directorio
        service._validate_directory(tmp_path)
        
        # 2. Escanear archivos
        with patch('config.Config.SUPPORTED_IMAGE_EXTENSIONS', ['.jpg']), \
             patch('config.Config.SUPPORTED_VIDEO_EXTENSIONS', []):
            files = service._get_supported_files(tmp_path)
        
        assert len(files) == 3
        
        # 3. Ejecutar con backup
        with patch.object(service, '_create_backup_for_operation') as mock_backup:
            mock_backup.return_value = Path('/backup')
            
            class TestResult(BaseResult):
                backup_path: Optional[Path] = None
            
            def execute_fn(dry_run):
                result = TestResult(success=True, message="OK")
                result.backup_path = None
                return result
            
            result = service._execute_operation(
                files=files,
                operation_name='test',
                execute_fn=execute_fn,
                create_backup=True,
                dry_run=False
            )
        
        assert result.success is True
        assert result.backup_path == Path('/backup')


class TestBackupFiltersMissingFiles:
    """Tests para validar que el backup filtra archivos que ya no existen."""
    
    def test_backup_filters_missing_files(self, service, tmp_path):
        """Verifica que archivos eliminados entre análisis y ejecución son filtrados."""
        # Crear 3 archivos
        file1 = tmp_path / "file1.jpg"
        file2 = tmp_path / "file2.jpg"
        file3 = tmp_path / "file3.jpg"
        
        file1.write_text("content1")
        file2.write_text("content2")
        file3.write_text("content3")
        
        # Simular que file2 fue eliminado después del análisis
        file2.unlink()
        
        # El backup solo debe incluir file1 y file3
        with patch('utils.file_utils.launch_backup_creation') as mock_backup:
            mock_backup.return_value = Path('/backup')
            
            result = service._create_backup_for_operation(
                [file1, file2, file3],
                'test_operation'
            )
            
            # Verificar que launch_backup_creation recibió solo los archivos existentes
            mock_backup.assert_called_once()
            call_args = mock_backup.call_args
            backed_up_files = call_args[0][0]  # Primer argumento posicional
            
            assert len(backed_up_files) == 2
            assert file1 in backed_up_files
            assert file2 not in backed_up_files  # Este fue eliminado
            assert file3 in backed_up_files
    
    def test_backup_returns_none_if_all_files_missing(self, service, tmp_path):
        """Si todos los archivos fueron eliminados, backup retorna None."""
        # Crear y eliminar archivo
        file1 = tmp_path / "file1.jpg"
        file1.write_text("content")
        file1.unlink()
        
        result = service._create_backup_for_operation(
            [file1],
            'test_operation'
        )
        
        assert result is None
    
    def test_backup_logs_warning_for_missing_files(self, service, tmp_path, caplog):
        """Verifica que se logea warning cuando hay archivos faltantes."""
        import logging
        caplog.set_level(logging.WARNING)
        
        file1 = tmp_path / "exists.jpg"
        file2 = tmp_path / "missing.jpg"
        
        file1.write_text("content")
        # file2 no se crea - simula archivo eliminado
        
        with patch('utils.file_utils.launch_backup_creation') as mock_backup:
            mock_backup.return_value = Path('/backup')
            
            service._create_backup_for_operation(
                [file1, file2],
                'test_operation'
            )
        
        # Verificar que se logeó el warning
        assert "files skipped from backup" in caplog.text.lower() or \
               "no longer exist" in caplog.text.lower()
