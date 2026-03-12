# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests unitarios para ZeroByteService.

Prueba el servicio de detección y eliminación de archivos vacíos (0 bytes):
- Análisis de archivos vacíos desde FileInfoRepository
- Ejecución de limpieza (real y dry-run)
- Creación de backups
- Actualización de caché después de eliminación
- Manejo de errores
- Callbacks de progreso
"""

import pytest
from pathlib import Path
from services.zero_byte_service import ZeroByteService
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from services.result_types import ZeroByteAnalysisResult, ZeroByteExecutionResult


@pytest.mark.unit
class TestZeroByteServiceBasics:
    """Tests básicos de funcionalidad del servicio."""
    
    def test_service_initialization(self):
        """Test que el servicio se inicializa correctamente."""
        service = ZeroByteService()
        
        assert service is not None
        assert service.logger is not None
        assert hasattr(service, 'analyze')
        assert hasattr(service, 'execute')
    
    def test_service_inherits_from_base_service(self):
        """Test que el servicio hereda correctamente de BaseService."""
        from services.base_service import BaseService
        service = ZeroByteService()
        
        assert isinstance(service, BaseService)


@pytest.mark.unit
class TestZeroByteServiceAnalysis:
    """Tests de análisis de archivos vacíos."""
    
    def test_analyze_empty_repository(self, temp_dir):
        """Test análisis cuando el repositorio está vacío."""
        repo = FileInfoRepositoryCache.get_instance()
        
        service = ZeroByteService()
        result = service.analyze()
        
        assert isinstance(result, ZeroByteAnalysisResult)
        assert result.success is True
        assert result.items_count == 0
        assert len(result.files) == 0
    
    def test_analyze_no_zero_byte_files(self, temp_dir):
        """Test análisis cuando no hay archivos de 0 bytes."""
        from services.file_metadata import FileMetadata
        
        # Crear archivos normales con contenido
        file1 = temp_dir / "image1.jpg"
        file1.write_bytes(b'\x00' * 1024)
        file2 = temp_dir / "video1.mp4"
        file2.write_bytes(b'\x00' * 2048)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan([file1, file2], PopulationStrategy.FILESYSTEM_METADATA)
        
        service = ZeroByteService()
        result = service.analyze()
        
        assert result.success is True
        assert result.items_count == 0
        assert len(result.files) == 0
    
    def test_analyze_finds_zero_byte_files(self, temp_dir):
        """Test análisis encuentra archivos de 0 bytes correctamente."""
        # Crear archivos vacíos
        zero_file1 = temp_dir / "empty1.jpg"
        zero_file1.touch()
        zero_file2 = temp_dir / "empty2.txt"
        zero_file2.touch()
        zero_file3 = temp_dir / "subdir" / "empty3.mp4"
        zero_file3.parent.mkdir(parents=True, exist_ok=True)
        zero_file3.touch()
        
        # Crear un archivo normal
        normal_file = temp_dir / "normal.jpg"
        normal_file.write_bytes(b'\x00' * 1024)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        all_files = [zero_file1, zero_file2, zero_file3, normal_file]
        repo.populate_from_scan(all_files, PopulationStrategy.FILESYSTEM_METADATA)
        
        service = ZeroByteService()
        result = service.analyze()
        
        assert result.success is True
        assert result.items_count == 3
        assert len(result.files) == 3
        
        # Verificar que solo los archivos vacíos están en el resultado
        result_paths = set(result.files)
        assert zero_file1 in result_paths
        assert zero_file2 in result_paths
        assert zero_file3 in result_paths
        assert normal_file not in result_paths
    
    def test_analyze_mixed_files(self, temp_dir):
        """Test análisis con mix de archivos vacíos y normales."""
        # Crear estructura con mix de archivos
        files_data = [
            ("image1.jpg", 1024),
            ("empty1.jpg", 0),
            ("video1.mp4", 2048),
            ("empty2.txt", 0),
            ("document.pdf", 512),
            ("empty3.png", 0),
        ]
        
        all_files = []
        empty_files = []
        
        for filename, size in files_data:
            file_path = temp_dir / filename
            if size == 0:
                file_path.touch()
                empty_files.append(file_path)
            else:
                file_path.write_bytes(b'\x00' * size)
            all_files.append(file_path)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan(all_files, PopulationStrategy.FILESYSTEM_METADATA)
        
        service = ZeroByteService()
        result = service.analyze()
        
        assert result.success is True
        assert result.items_count == 3
        assert len(result.files) == 3
        assert set(result.files) == set(empty_files)
    
    def test_analyze_with_progress_callback(self, temp_dir):
        """Test análisis con callback de progreso."""
        # Crear suficientes archivos para que se reporte progreso (intervalo=5000)
        all_files = []
        for i in range(10000):
            file_path = temp_dir / f"file_{i}.txt"
            if i % 2 == 0:  # La mitad vacíos
                file_path.touch()
            else:
                file_path.write_bytes(b'\x00' * 100)
            all_files.append(file_path)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan(all_files, PopulationStrategy.FILESYSTEM_METADATA)
        
        # Callback para capturar progreso
        progress_calls = []
        
        def progress_callback(current, total, message):
            progress_calls.append({
                'current': current,
                'total': total,
                'message': message
            })
            return True  # Continuar
        
        service = ZeroByteService()
        result = service.analyze(progress_callback=progress_callback)
        
        assert result.success is True
        assert result.items_count == 5000  # La mitad son vacíos
        
        # Verificar que se llamó al callback (intervalo 5000, así que al menos 1 vez)
        assert len(progress_calls) > 0
        # Verificar que el total es correcto
        assert progress_calls[0]['total'] == 10000
    
    def test_analyze_can_be_cancelled(self, temp_dir):
        """Test que el análisis puede ser cancelado vía callback."""
        # Crear archivos
        all_files = []
        for i in range(50):
            file_path = temp_dir / f"empty_{i}.txt"
            file_path.touch()
            all_files.append(file_path)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan(all_files, PopulationStrategy.FILESYSTEM_METADATA)
        
        # Callback que cancela después de algunos llamados
        call_count = [0]
        
        def cancel_callback(current, total, message):
            call_count[0] += 1
            if call_count[0] > 2:
                return False  # Cancelar
            return True
        
        service = ZeroByteService()
        result = service.analyze(progress_callback=cancel_callback)
        
        # El resultado debe ser parcial pero exitoso
        assert result.success is True
        # No necesariamente procesó todos los archivos


@pytest.mark.unit
class TestZeroByteServiceExecution:
    """Tests de ejecución de eliminación de archivos vacíos."""
    
    def test_execute_dry_run(self, temp_dir):
        """Test ejecución en modo simulación no elimina archivos."""
        # Crear archivos vacíos
        empty1 = temp_dir / "empty1.txt"
        empty1.touch()
        empty2 = temp_dir / "empty2.jpg"
        empty2.touch()
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan([empty1, empty2], PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar
        service = ZeroByteService()
        analysis = service.analyze()
        
        # Ejecutar en modo dry-run
        exec_result = service.execute(
            analysis_result=analysis,
            dry_run=True,
            create_backup=False
        )
        
        assert isinstance(exec_result, ZeroByteExecutionResult)
        assert exec_result.success is True
        assert exec_result.dry_run is True
        assert exec_result.items_processed == 2
        assert len(exec_result.files_affected) == 2
        
        # Los archivos NO deben haber sido eliminados
        assert empty1.exists()
        assert empty2.exists()
        
        # El repositorio debe seguir con los archivos
        assert empty1 in repo
        assert empty2 in repo
    
    def test_execute_real_deletion(self, temp_dir):
        """Test ejecución real elimina archivos."""
        # Crear archivos vacíos
        empty1 = temp_dir / "empty1.txt"
        empty1.touch()
        empty2 = temp_dir / "empty2.jpg"
        empty2.touch()
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan([empty1, empty2], PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar
        service = ZeroByteService()
        analysis = service.analyze()
        
        # Ejecutar eliminación real
        exec_result = service.execute(
            analysis_result=analysis,
            dry_run=False,
            create_backup=False
        )
        
        assert exec_result.success is True
        assert exec_result.dry_run is False
        assert exec_result.items_processed == 2
        assert len(exec_result.files_affected) == 2
        
        # Los archivos DEBEN haber sido eliminados
        assert not empty1.exists()
        assert not empty2.exists()
        
        # El repositorio debe haberse actualizado
        assert empty1 not in repo
        assert empty2 not in repo
    
    def test_execute_with_backup(self, temp_dir):
        """Test ejecución con creación de backup."""
        # Crear archivos vacíos
        empty1 = temp_dir / "empty1.txt"
        empty1.touch()
        empty2 = temp_dir / "empty2.jpg"
        empty2.touch()
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan([empty1, empty2], PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar
        service = ZeroByteService()
        analysis = service.analyze()
        
        # Ejecutar con backup
        exec_result = service.execute(
            analysis_result=analysis,
            dry_run=False,
            create_backup=True
        )
        
        assert exec_result.success is True
        assert exec_result.backup_path is not None
        assert Path(exec_result.backup_path).exists()
        
        # Los archivos deben haber sido eliminados
        assert not empty1.exists()
        assert not empty2.exists()
    
    def test_execute_partial_selection(self, temp_dir):
        """Test ejecución con selección parcial de archivos."""
        # Crear varios archivos vacíos
        empty1 = temp_dir / "empty1.txt"
        empty1.touch()
        empty2 = temp_dir / "empty2.jpg"
        empty2.touch()
        empty3 = temp_dir / "empty3.png"
        empty3.touch()
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan([empty1, empty2, empty3], PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar (encuentra 3)
        service = ZeroByteService()
        full_analysis = service.analyze()
        assert full_analysis.items_count == 3
        
        # Crear análisis parcial con solo 2 archivos
        from services.result_types import ZeroByteAnalysisResult
        partial_analysis = ZeroByteAnalysisResult(
            files=[empty1, empty3],  # Solo 2 de 3
            items_count=2
        )
        
        # Ejecutar solo con los 2 seleccionados
        exec_result = service.execute(
            analysis_result=partial_analysis,
            dry_run=False,
            create_backup=False
        )
        
        assert exec_result.success is True
        assert exec_result.items_processed == 2
        
        # Solo los seleccionados deben haber sido eliminados
        assert not empty1.exists()
        assert empty2.exists()  # No seleccionado
        assert not empty3.exists()
    
    def test_execute_with_progress_callback(self, temp_dir):
        """Test ejecución reporta progreso correctamente."""
        # Crear archivos
        empty_files = []
        for i in range(10):
            file_path = temp_dir / f"empty_{i}.txt"
            file_path.touch()
            empty_files.append(file_path)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan(empty_files, PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar
        service = ZeroByteService()
        analysis = service.analyze()
        
        # Callback para capturar progreso
        progress_calls = []
        
        def progress_callback(current, total, message):
            progress_calls.append({
                'current': current,
                'total': total,
                'message': message
            })
            return True
        
        # Ejecutar
        exec_result = service.execute(
            analysis_result=analysis,
            dry_run=True,
            create_backup=False,
            progress_callback=progress_callback
        )
        
        assert exec_result.success is True
        assert len(progress_calls) > 0
        
        # Verificar progreso incremental
        assert progress_calls[0]['total'] == 10
        assert progress_calls[-1]['current'] == progress_calls[-1]['total']
    
    def test_execute_can_be_cancelled(self, temp_dir):
        """Test que la ejecución puede ser cancelada vía callback."""
        # Crear archivos
        empty_files = []
        for i in range(20):
            file_path = temp_dir / f"empty_{i}.txt"
            file_path.touch()
            empty_files.append(file_path)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan(empty_files, PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar
        service = ZeroByteService()
        analysis = service.analyze()
        
        # Callback que cancela después de algunos archivos
        call_count = [0]
        
        def cancel_callback(current, total, message):
            call_count[0] += 1
            if call_count[0] > 5:
                return False  # Cancelar
            return True
        
        # Ejecutar
        exec_result = service.execute(
            analysis_result=analysis,
            dry_run=True,
            create_backup=False,
            progress_callback=cancel_callback
        )
        
        # La operación debe haberse detenido prematuramente
        assert exec_result.items_processed < 20
    
    def test_execute_handles_errors_gracefully(self, temp_dir):
        """Test que errores en archivos individuales no detienen la operación."""
        # Crear archivos
        empty1 = temp_dir / "empty1.txt"
        empty1.touch()
        empty2 = temp_dir / "empty2.txt"
        empty2.touch()
        empty3 = temp_dir / "empty3.txt"
        empty3.touch()
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan([empty1, empty2, empty3], PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar
        service = ZeroByteService()
        analysis = service.analyze()
        
        # Hacer que un archivo sea inaccesible (permisos)
        import os
        os.chmod(empty2, 0o000)
        
        try:
            # Ejecutar
            exec_result = service.execute(
                analysis_result=analysis,
                dry_run=False,
                create_backup=False
            )
            
            # Debe seguir siendo exitoso pero con errores reportados
            assert exec_result.items_processed >= 2  # Al menos 2 de 3
            
            # Si hay errores, deben estar registrados
            if exec_result.items_processed < 3:
                assert len(exec_result.errors) > 0
        
        finally:
            # Restaurar permisos
            try:
                os.chmod(empty2, 0o644)
            except:
                pass


@pytest.mark.unit
class TestZeroByteServiceEdgeCases:
    """Tests de casos especiales y límite."""
    
    def test_analyze_empty_result(self):
        """Test que ZeroByteAnalysisResult puede crearse vacío."""
        from services.result_types import ZeroByteAnalysisResult
        
        result = ZeroByteAnalysisResult(files=[], items_count=0)
        
        assert result.success is True
        assert result.items_count == 0
        assert len(result.files) == 0
    
    def test_execute_with_empty_analysis(self, temp_dir):
        """Test ejecución con análisis vacío no falla."""
        from services.result_types import ZeroByteAnalysisResult
        
        empty_analysis = ZeroByteAnalysisResult(files=[], items_count=0)
        
        service = ZeroByteService()
        exec_result = service.execute(
            analysis_result=empty_analysis,
            dry_run=False,
            create_backup=False
        )
        
        assert exec_result.success is True
        assert exec_result.items_processed == 0
        assert len(exec_result.files_affected) == 0
    
    def test_analyze_large_dataset(self, temp_dir):
        """Test análisis con dataset grande (performance)."""
        # Crear muchos archivos (mix de vacíos y normales)
        all_files = []
        for i in range(1000):
            file_path = temp_dir / f"file_{i}.txt"
            if i % 3 == 0:  # ~333 vacíos
                file_path.touch()
            else:
                file_path.write_bytes(b'\x00' * 100)
            all_files.append(file_path)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan(all_files, PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar
        service = ZeroByteService()
        result = service.analyze()
        
        assert result.success is True
        assert 330 <= result.items_count <= 334  # ~333 archivos vacíos
    
    def test_execute_with_nonexistent_file(self, temp_dir):
        """Test ejecución cuando un archivo ya no existe."""
        from services.result_types import ZeroByteAnalysisResult
        
        # Crear análisis con archivo que no existe
        fake_file = temp_dir / "nonexistent.txt"
        analysis = ZeroByteAnalysisResult(
            files=[fake_file],
            items_count=1
        )
        
        service = ZeroByteService()
        exec_result = service.execute(
            analysis_result=analysis,
            dry_run=False,
            create_backup=False
        )
        
        # Debe manejar el error graciosamente
        assert len(exec_result.errors) > 0 or exec_result.items_processed == 0
    
    def test_analyze_nested_directories(self, temp_dir):
        """Test análisis con archivos en directorios anidados."""
        # Crear estructura anidada
        nested_files = []
        for i in range(5):
            dir_path = temp_dir / f"level1/level2/level3_{i}"
            dir_path.mkdir(parents=True, exist_ok=True)
            
            file_path = dir_path / f"empty_{i}.txt"
            file_path.touch()
            nested_files.append(file_path)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan(nested_files, PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar
        service = ZeroByteService()
        result = service.analyze()
        
        assert result.success is True
        assert result.items_count == 5
        assert set(result.files) == set(nested_files)
    
    def test_analyze_files_with_special_characters(self, temp_dir):
        """Test análisis con nombres de archivo especiales."""
        # Crear archivos con nombres especiales
        special_files = []
        special_names = [
            "file with spaces.txt",
            "file_with_àccénts.txt",
            "file-with-dashes.txt",
            "file.multiple.dots.txt"
        ]
        
        for name in special_names:
            file_path = temp_dir / name
            file_path.touch()
            special_files.append(file_path)
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan(special_files, PopulationStrategy.FILESYSTEM_METADATA)
        
        # Analizar
        service = ZeroByteService()
        result = service.analyze()
        
        assert result.success is True
        assert result.items_count == len(special_names)
        assert set(result.files) == set(special_files)


@pytest.mark.unit
class TestZeroByteServiceIntegration:
    """Tests de integración con otros componentes."""
    
    def test_service_uses_repository_singleton(self, temp_dir):
        """Test que el servicio usa correctamente el singleton del repositorio."""
        # Crear archivos
        empty_file = temp_dir / "empty.txt"
        empty_file.touch()
        
        # Poblar repositorio
        repo1 = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo1.populate_from_scan([empty_file], PopulationStrategy.FILESYSTEM_METADATA)
        
        # El servicio debe usar el mismo repositorio
        service = ZeroByteService()
        result = service.analyze()
        
        assert result.items_count == 1
        
        # Verificar que es la misma instancia
        repo2 = FileInfoRepositoryCache.get_instance()
        assert repo1 is repo2
    
    def test_execution_updates_repository_cache(self, temp_dir):
        """Test que la ejecución actualiza correctamente el caché del repositorio."""
        # Crear archivos
        empty1 = temp_dir / "empty1.txt"
        empty1.touch()
        empty2 = temp_dir / "empty2.txt"
        empty2.touch()
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan([empty1, empty2], PopulationStrategy.FILESYSTEM_METADATA)
        
        initial_count = repo.get_file_count()
        assert initial_count == 2
        assert empty1 in repo
        assert empty2 in repo
        
        # Analizar y ejecutar
        service = ZeroByteService()
        analysis = service.analyze()
        exec_result = service.execute(
            analysis_result=analysis,
            dry_run=False,
            create_backup=False
        )
        
        # El repositorio debe haberse actualizado
        assert repo.get_file_count() == 0
        assert empty1 not in repo
        assert empty2 not in repo
    
    def test_dry_run_does_not_update_repository(self, temp_dir):
        """Test que dry-run NO actualiza el repositorio."""
        # Crear archivos
        empty1 = temp_dir / "empty1.txt"
        empty1.touch()
        empty2 = temp_dir / "empty2.txt"
        empty2.touch()
        
        # Poblar repositorio
        repo = FileInfoRepositoryCache.get_instance()
        from services.file_metadata_repository_cache import PopulationStrategy
        repo.populate_from_scan([empty1, empty2], PopulationStrategy.FILESYSTEM_METADATA)
        
        initial_count = repo.get_file_count()
        
        # Ejecutar en dry-run
        service = ZeroByteService()
        analysis = service.analyze()
        exec_result = service.execute(
            analysis_result=analysis,
            dry_run=True,
            create_backup=False
        )
        
        # El repositorio NO debe cambiar
        assert repo.get_file_count() == initial_count
        assert empty1 in repo
        assert empty2 in repo


@pytest.mark.unit
class TestZeroByteAnalysisResult:
    """Tests del dataclass ZeroByteAnalysisResult."""
    
    def test_result_creation(self):
        """Test creación básica del resultado."""
        from services.result_types import ZeroByteAnalysisResult
        
        files = [Path("/tmp/empty1.txt"), Path("/tmp/empty2.txt")]
        result = ZeroByteAnalysisResult(files=files, items_count=2)
        
        assert result.files == files
        assert result.items_count == 2
        assert result.success is True
        assert result.errors == []
    
    def test_result_with_errors(self):
        """Test resultado con errores."""
        from services.result_types import ZeroByteAnalysisResult
        
        result = ZeroByteAnalysisResult(files=[], items_count=0)
        result.add_error("Test error")
        
        assert len(result.errors) == 1
        assert "Test error" in result.errors


@pytest.mark.unit
class TestZeroByteExecutionResult:
    """Tests del dataclass ZeroByteExecutionResult."""
    
    def test_result_creation(self):
        """Test creación básica del resultado de ejecución."""
        from services.result_types import ZeroByteExecutionResult
        
        result = ZeroByteExecutionResult(dry_run=False)
        
        assert result.success is True
        assert result.dry_run is False
        assert result.items_processed == 0
        assert result.files_affected == []
        assert result.errors == []
    
    def test_result_dry_run(self):
        """Test resultado en modo dry-run."""
        from services.result_types import ZeroByteExecutionResult
        
        result = ZeroByteExecutionResult(dry_run=True)
        result.items_processed = 5
        result.files_affected = [Path(f"/tmp/file{i}.txt") for i in range(5)]
        
        assert result.dry_run is True
        assert result.items_processed == 5
        assert len(result.files_affected) == 5
