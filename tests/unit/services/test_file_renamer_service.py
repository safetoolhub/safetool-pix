# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para FileRenamerService
"""
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
import pytest

from services.file_renamer_service import FileRenamerService
from services.result_types import RenameAnalysisResult, RenameExecutionResult, RenamePlanItem
from services.file_metadata_repository_cache import FileInfoRepositoryCache
from services.file_metadata import FileMetadata


class TestFileRenamerServiceBasics:
    """Tests básicos del servicio"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.service = FileRenamerService()
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
    
    def test_service_initialization(self):
        """Test: servicio se inicializa correctamente"""
        assert self.service is not None
        assert self.service.logger is not None
    
    def test_service_inheritance(self):
        """Test: hereda de BaseService"""
        from services.base_service import BaseService
        assert isinstance(self.service, BaseService)


class TestFileRenamerServiceAnalyze:
    """Tests para el método analyze"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.service = FileRenamerService()
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
        self.test_dir = Path('/tmp/test_rename')
    
    def test_analyze_empty_directory(self):
        """Test: análisis con directorio sin archivos en caché"""
        result = self.service.analyze(self.test_dir)
        
        assert isinstance(result, RenameAnalysisResult)
        assert result.renaming_plan == []
        assert result.already_renamed == 0
        assert result.conflicts == 0
        assert result.items_count == 0
    
    def test_analyze_with_files_needing_rename(self, tmp_path):
        """Test: análisis con archivos que necesitan renombre"""
        # Crear archivos temporales
        test_dir = tmp_path / "photos"
        test_dir.mkdir()
        
        file1 = test_dir / "IMG_001.jpg"
        file2 = test_dir / "VID_002.mp4"
        file1.touch()
        file2.touch()
        
        # Añadir al repositorio con best_date incluido
        date1 = datetime(2023, 1, 15, 10, 30, 0)
        date2 = datetime(2023, 2, 20, 14, 45, 0)
        
        meta1 = FileMetadata(
            path=file1,
            fs_size=1000,
            fs_ctime=date1.timestamp(),
            fs_mtime=date1.timestamp(),
            fs_atime=date1.timestamp(),
            exif_DateTimeOriginal=date1.isoformat(),
            best_date=date1,
            best_date_source='EXIF'
        )
        meta2 = FileMetadata(
            path=file2,
            fs_size=2000,
            fs_ctime=date2.timestamp(),
            fs_mtime=date2.timestamp(),
            fs_atime=date2.timestamp(),
            exif_DateTimeOriginal=date2.isoformat(),
            best_date=date2,
            best_date_source='EXIF'
        )
        
        self.repo.add_file(file1, meta1)
        self.repo.add_file(file2, meta2)
        
        result = self.service.analyze(test_dir)
        
        assert isinstance(result, RenameAnalysisResult)
        assert len(result.renaming_plan) == 2
        assert result.already_renamed == 0
        assert result.conflicts == 0
        
        # Verificar plan de renombrado (usar set para orden indeterminado)
        names = {item.new_name for item in result.renaming_plan}
        assert '20230115_103000_PHOTO.JPG' in names
        assert '20230220_144500_VIDEO.MP4' in names
    
    def test_analyze_with_already_renamed_files(self, tmp_path):
        """Test: análisis detecta archivos ya renombrados"""
        test_dir = tmp_path / "renamed"
        test_dir.mkdir()
        
        # Archivo con formato ya renombrado
        file1 = test_dir / "20230115_103000_PHOTO.JPG"
        file1.touch()
        
        date1 = datetime(2023, 1, 15, 10, 30, 0)
        meta1 = FileMetadata(
            path=file1,
            fs_size=1000,
            fs_ctime=date1.timestamp(),
            fs_mtime=date1.timestamp(),
            fs_atime=date1.timestamp(),
            best_date=date1,
            best_date_source='EXIF'
        )
        
        self.repo.add_file(file1, meta1)
        
        result = self.service.analyze(test_dir)
        
        assert result.already_renamed == 1
        assert len(result.renaming_plan) == 0
    
    def test_analyze_with_conflicts(self, tmp_path):
        """Test: análisis detecta conflictos de nombre"""
        test_dir = tmp_path / "conflicts"
        test_dir.mkdir()
        
        # Dos archivos con la misma fecha -> conflicto
        file1 = test_dir / "IMG_001.jpg"
        file2 = test_dir / "IMG_002.jpg"
        file1.touch()
        file2.touch()
        
        # Misma fecha para ambos
        date = datetime(2023, 1, 15, 10, 30, 0)
        
        meta1 = FileMetadata(
            path=file1,
            fs_size=1000,
            fs_ctime=date.timestamp(),
            fs_mtime=date.timestamp(),
            fs_atime=date.timestamp(),
            best_date=date,
            best_date_source='EXIF'
        )
        meta2 = FileMetadata(
            path=file2,
            fs_size=1000,
            fs_ctime=date.timestamp(),
            fs_mtime=date.timestamp(),
            fs_atime=date.timestamp(),
            best_date=date,
            best_date_source='EXIF'
        )
        
        self.repo.add_file(file1, meta1)
        self.repo.add_file(file2, meta2)
        
        result = self.service.analyze(test_dir)
        
        assert result.conflicts >= 1  # Al menos un conflicto
        assert len(result.renaming_plan) == 2
        
        # Uno debe tener secuencia
        sequences = [item.sequence for item in result.renaming_plan]
        assert any(s is not None for s in sequences)
    
    def test_analyze_with_no_date_files(self, tmp_path):
        """Test: archivos sin fecha van a issues"""
        test_dir = tmp_path / "no_dates"
        test_dir.mkdir()
        
        file1 = test_dir / "IMG_001.jpg"
        file1.touch()
        
        # Metadata sin fechas
        meta1 = FileMetadata(
            path=file1,
            fs_size=1000,
            fs_ctime=0.0,
            fs_mtime=0.0,
            fs_atime=0.0
        )
        self.repo.add_file(file1, meta1)
        
        result = self.service.analyze(test_dir)
        
        assert len(result.issues) > 0
        assert len(result.renaming_plan) == 0
    
    def test_analyze_progress_callback(self, tmp_path):
        """Test: callback de progreso se llama durante análisis"""
        test_dir = tmp_path / "progress"
        test_dir.mkdir()
        
        # Crear muchos archivos para probar progreso
        for i in range(10):
            file = test_dir / f"IMG_{i:03d}.jpg"
            file.touch()
            date = datetime(2023, 1, 15 + i, 10, 30, 0)
            meta = FileMetadata(
                path=file,
                fs_size=1000,
                fs_ctime=date.timestamp(),
                fs_mtime=date.timestamp(),
                fs_atime=date.timestamp(),
                best_date=date,
                best_date_source='EXIF'
            )
            self.repo.add_file(file, meta)
        
        progress_calls = []
        def progress_callback(processed, total, message):
            progress_calls.append((processed, total, message))
            return True
        
        result = self.service.analyze(test_dir, progress_callback=progress_callback)
        
        assert len(result.renaming_plan) == 10
        # Puede haber llamadas de progreso si hay suficientes archivos
    
    def test_analyze_cancellation(self, tmp_path):
        """Test: análisis puede ser cancelado"""
        test_dir = tmp_path / "cancel"
        test_dir.mkdir()
        
        for i in range(5):
            file = test_dir / f"IMG_{i:03d}.jpg"
            file.touch()
            date = datetime(2023, 1, 15 + i, 10, 30, 0)
            meta = FileMetadata(
                path=file,
                fs_size=1000,
                fs_ctime=date.timestamp(),
                fs_mtime=date.timestamp(),
                fs_atime=date.timestamp(),
                best_date=date,
                best_date_source='EXIF'
            )
            self.repo.add_file(file, meta)
        
        def cancel_callback(processed, total, message):
            return False  # Cancelar inmediatamente
        
        result = self.service.analyze(test_dir, progress_callback=cancel_callback)
        
        # Debe retornar resultado vacío
        assert isinstance(result, RenameAnalysisResult)


class TestFileRenamerServiceExecute:
    """Tests para el método execute"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.service = FileRenamerService()
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
    
    def test_execute_empty_analysis(self):
        """Test: ejecutar con análisis vacío"""
        empty_analysis = RenameAnalysisResult(
            renaming_plan=[],
            already_renamed=0,
            conflicts=0,
            files_by_year={},
            issues=[]
        )
        
        result = self.service.execute(empty_analysis, create_backup=False, dry_run=True)
        
        assert isinstance(result, RenameExecutionResult)
        assert result.success is True
        assert result.items_processed == 0
    
    def test_execute_dry_run(self, tmp_path):
        """Test: modo dry_run no modifica archivos"""
        test_dir = tmp_path / "dry_run"
        test_dir.mkdir()
        
        # Crear archivo
        original_file = test_dir / "IMG_001.jpg"
        original_file.write_text("test content")
        original_name = original_file.name
        
        date = datetime(2023, 1, 15, 10, 30, 0)
        meta = FileMetadata(
            path=original_file,
            fs_size=12,
            fs_ctime=date.timestamp(),
            fs_mtime=date.timestamp(),
            fs_atime=date.timestamp(),
            best_date=date,
            best_date_source='EXIF'
        )
        self.repo.add_file(original_file, meta)
        
        # Analizar
        analysis = self.service.analyze(test_dir)
        assert len(analysis.renaming_plan) == 1
        
        # Ejecutar dry_run
        result = self.service.execute(analysis, create_backup=False, dry_run=True)
        
        assert result.success is True
        assert result.dry_run is True
        assert result.items_processed == 1
        
        # Verificar que el archivo NO fue renombrado
        assert original_file.exists()
        assert original_file.name == original_name
    
    def test_execute_real_rename(self, tmp_path):
        """Test: renombrado real modifica archivos"""
        test_dir = tmp_path / "real_rename"
        test_dir.mkdir()
        
        original_file = test_dir / "IMG_001.jpg"
        original_file.write_text("test content")
        
        date = datetime(2023, 1, 15, 10, 30, 0)
        meta = FileMetadata(
            path=original_file,
            fs_size=12,
            fs_ctime=date.timestamp(),
            fs_mtime=date.timestamp(),
            fs_atime=date.timestamp(),
            best_date=date,
            best_date_source='EXIF'
        )
        self.repo.add_file(original_file, meta)
        
        # Analizar y ejecutar
        analysis = self.service.analyze(test_dir)
        result = self.service.execute(analysis, create_backup=False, dry_run=False)
        
        assert result.success is True
        assert result.dry_run is False
        assert result.items_processed == 1
        assert len(result.renamed_files) == 1
        
        # Verificar que el archivo fue renombrado
        assert not original_file.exists()
        new_file = test_dir / "20230115_103000_PHOTO.JPG"
        assert new_file.exists()
        assert new_file.read_text() == "test content"
    
    def test_execute_updates_repository_cache(self, tmp_path):
        """Test: execute actualiza el repositorio caché"""
        test_dir = tmp_path / "cache_update"
        test_dir.mkdir()
        
        original_file = test_dir / "IMG_001.jpg"
        original_file.touch()
        
        date = datetime(2023, 1, 15, 10, 30, 0)
        meta = FileMetadata(
            path=original_file,
            fs_size=0,
            fs_ctime=date.timestamp(),
            fs_mtime=date.timestamp(),
            fs_atime=date.timestamp(),
            best_date=date,
            best_date_source='EXIF'
        )
        self.repo.add_file(original_file, meta)
        
        # Verificar que está en caché
        assert self.repo.get_file_metadata(original_file) is not None
        
        # Renombrar
        analysis = self.service.analyze(test_dir)
        result = self.service.execute(analysis, create_backup=False, dry_run=False)
        
        assert result.success is True
        
        # Verificar que la caché fue actualizada
        new_path = test_dir / "20230115_103000_PHOTO.JPG"
        assert self.repo.get_file_metadata(original_file) is None  # Ruta vieja eliminada
        assert self.repo.get_file_metadata(new_path) is not None  # Nueva ruta existe
    
    def test_execute_with_conflict_resolution(self, tmp_path):
        """Test: ejecutar resuelve conflictos dinámicamente"""
        test_dir = tmp_path / "conflicts"
        test_dir.mkdir()
        
        # Crear archivo existente con nombre objetivo
        existing_file = test_dir / "20230115_103000_PHOTO.JPG"
        existing_file.write_text("existing")
        
        # Crear archivo a renombrar
        original_file = test_dir / "IMG_001.jpg"
        original_file.write_text("new")
        
        date = datetime(2023, 1, 15, 10, 30, 0)
        meta = FileMetadata(
            path=original_file,
            fs_size=3,
            fs_ctime=date.timestamp(),
            fs_mtime=date.timestamp(),
            fs_atime=date.timestamp(),
            best_date=date,
            best_date_source='EXIF'
        )
        self.repo.add_file(original_file, meta)
        
        # Analizar y ejecutar
        analysis = self.service.analyze(test_dir)
        result = self.service.execute(analysis, create_backup=False, dry_run=False)
        
        assert result.success is True
        assert result.conflicts_resolved >= 1
        
        # Debe existir con secuencia _001 (el existente no tiene número)
        sequenced_file = test_dir / "20230115_103000_PHOTO_001.JPG"
        assert sequenced_file.exists()
    
    def test_execute_with_backup(self, tmp_path):
        """Test: ejecutar con backup crea el directorio de backup"""
        test_dir = tmp_path / "backup_test"
        test_dir.mkdir()
        
        original_file = test_dir / "IMG_001.jpg"
        original_file.touch()
        
        date = datetime(2023, 1, 15, 10, 30, 0)
        meta = FileMetadata(
            path=original_file,
            fs_size=0,
            fs_ctime=date.timestamp(),
            fs_mtime=date.timestamp(),
            fs_atime=date.timestamp(),
            best_date=date,
            best_date_source='EXIF'
        )
        self.repo.add_file(original_file, meta)
        
        analysis = self.service.analyze(test_dir)
        result = self.service.execute(analysis, create_backup=True, dry_run=False)
        
        assert result.success is True
        # Verificar que se creó un backup
        assert result.backup_path is not None
        assert result.backup_path.exists()


class TestFileRenamerServiceEdgeCases:
    """Tests para casos extremos"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.service = FileRenamerService()
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
    
    def test_execute_with_missing_file(self, tmp_path):
        """Test: ejecutar cuando archivo fue eliminado"""
        test_dir = tmp_path / "missing"
        test_dir.mkdir()
        
        # Crear análisis con archivo inexistente
        fake_file = test_dir / "IMG_001.jpg"
        
        analysis = RenameAnalysisResult(
            renaming_plan=[RenamePlanItem(
                original_path=fake_file,
                new_name='20230115_103000_PHOTO.JPG',
                date=datetime(2023, 1, 15, 10, 30, 0),
                date_source='EXIF',
                has_conflict=False,
                sequence=None
            )],
            already_renamed=0,
            conflicts=0,
            files_by_year={2023: 1},
            issues=[]
        )
        
        # Ejecutar sin el archivo presente
        result = self.service.execute(analysis, create_backup=False, dry_run=False)
        
        # No debería crashear, simplemente omitir el archivo
        assert result.items_processed == 0


class TestFileRenamerServiceIntegration:
    """Tests de integración para operaciones consecutivas"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.service = FileRenamerService()
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
    
    def test_consecutive_analysis(self, tmp_path):
        """Test: múltiples análisis consecutivos del mismo directorio"""
        test_dir = tmp_path / "consecutive"
        test_dir.mkdir()
        
        # Crear archivos
        for i in range(3):
            file = test_dir / f"IMG_{i:03d}.jpg"
            file.touch()
            date = datetime(2023, 1, 15 + i, 10, 30, 0)
            meta = FileMetadata(
                path=file,
                fs_size=0,
                fs_ctime=date.timestamp(),
                fs_mtime=date.timestamp(),
                fs_atime=date.timestamp(),
                best_date=date,
                best_date_source='EXIF'
            )
            self.repo.add_file(file, meta)
        
        # Primer análisis
        result1 = self.service.analyze(test_dir)
        assert len(result1.renaming_plan) == 3
        
        # Segundo análisis (sin cambios)
        result2 = self.service.analyze(test_dir)
        assert len(result2.renaming_plan) == 3
        # Comparar nombres independientemente del orden
        names1 = {item.new_name for item in result1.renaming_plan}
        names2 = {item.new_name for item in result2.renaming_plan}
        assert names1 == names2
    
    def test_analyze_execute_analyze_sequence(self, tmp_path):
        """Test: analyze -> execute -> analyze again"""
        test_dir = tmp_path / "sequence"
        test_dir.mkdir()
        
        # Crear archivos
        files = []
        for i in range(3):
            file = test_dir / f"IMG_{i:03d}.jpg"
            file.touch()
            files.append(file)
            date = datetime(2023, 1, 15 + i, 10, 30, 0)
            meta = FileMetadata(
                path=file,
                fs_size=0,
                fs_ctime=date.timestamp(),
                fs_mtime=date.timestamp(),
                fs_atime=date.timestamp(),
                best_date=date,
                best_date_source='EXIF'
            )
            self.repo.add_file(file, meta)
        
        # 1. Analizar
        analysis1 = self.service.analyze(test_dir)
        assert len(analysis1.renaming_plan) == 3
        assert analysis1.already_renamed == 0
        
        # 2. Ejecutar renombrado
        exec_result = self.service.execute(analysis1, create_backup=False, dry_run=False)
        assert exec_result.success is True
        assert exec_result.items_processed == 3
        
        # 3. Analizar nuevamente (ahora deberían estar renombrados)
        analysis2 = self.service.analyze(test_dir)
        assert len(analysis2.renaming_plan) == 0
        assert analysis2.already_renamed == 3
    
    def test_multiple_executions_idempotent(self, tmp_path):
        """Test: múltiples ejecuciones consecutivas son idempotentes"""
        test_dir = tmp_path / "idempotent"
        test_dir.mkdir()
        
        file = test_dir / "IMG_001.jpg"
        file.touch()
        date = datetime(2023, 1, 15, 10, 30, 0)
        meta = FileMetadata(
            path=file,
            fs_size=0,
            fs_ctime=date.timestamp(),
            fs_mtime=date.timestamp(),
            fs_atime=date.timestamp(),
            best_date=date,
            best_date_source='EXIF'
        )
        self.repo.add_file(file, meta)
        
        # Primera ejecución
        analysis1 = self.service.analyze(test_dir)
        exec1 = self.service.execute(analysis1, create_backup=False, dry_run=False)
        assert exec1.items_processed == 1
        
        # Segunda ejecución (no debería renombrar nada)
        analysis2 = self.service.analyze(test_dir)
        assert len(analysis2.renaming_plan) == 0
        
        exec2 = self.service.execute(analysis2, create_backup=False, dry_run=False)
        assert exec2.items_processed == 0
