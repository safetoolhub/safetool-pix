# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para FileOrganizerService
Verifica la funcionalidad de organización de archivos, incluyendo
la opción de mover archivos no soportados a 'other/' y la corrección
del bug de auto-conflicto (_001 suffix).
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from services.file_organizer_service import FileOrganizerService, OrganizationType, FileMove
from services.result_types import OrganizationAnalysisResult
from services.file_metadata_repository_cache import FileInfoRepositoryCache, PopulationStrategy
from services.file_metadata import FileMetadata


class TestFileOrganizerServiceBasics:
    """Tests básicos de inicialización y herencia"""

    def test_service_initialization(self):
        """El servicio debe inicializarse correctamente"""
        service = FileOrganizerService()
        assert service is not None
        assert hasattr(service, 'analyze')
        assert hasattr(service, 'execute')

    def test_service_inherits_from_base(self):
        """Debe heredar de BaseService"""
        from services.base_service import BaseService
        service = FileOrganizerService()
        assert isinstance(service, BaseService)


class TestFileOrganizerMoveUnsupported:
    """Tests para la funcionalidad de mover archivos no soportados a 'other/'"""

    def setup_method(self):
        """Limpiar el repositorio antes de cada test"""
        repo = FileInfoRepositoryCache.get_instance()
        repo.clear()

    def _create_test_structure(self, tmp_path):
        """Crea una estructura de directorios con archivos soportados y no soportados."""
        # Archivos soportados (imágenes)
        img1 = tmp_path / "subdir1" / "photo.jpg"
        img1.parent.mkdir(parents=True, exist_ok=True)
        img1.write_bytes(b"fake jpg content 1")

        img2 = tmp_path / "subdir2" / "photo2.png"
        img2.parent.mkdir(parents=True, exist_ok=True)
        img2.write_bytes(b"fake png content 2")

        # Archivos no soportados
        gif1 = tmp_path / "subdir1" / "animation.gif"
        gif1.write_bytes(b"fake gif content")

        txt1 = tmp_path / "subdir2" / "notes.txt"
        txt1.write_bytes(b"some text notes")

        doc1 = tmp_path / "readme.md"
        doc1.write_bytes(b"# readme")

        # Archivo no soportado en subdirectorio profundo
        deep_file = tmp_path / "subdir1" / "nested" / "data.csv"
        deep_file.parent.mkdir(parents=True, exist_ok=True)
        deep_file.write_bytes(b"col1,col2\nval1,val2")

        # Registrar archivos soportados en la caché
        repo = FileInfoRepositoryCache.get_instance()
        for img_path in [img1, img2]:
            metadata = FileMetadata(
                path=img_path,
                fs_size=img_path.stat().st_size,
                fs_ctime=1234567890.0,
                fs_mtime=1234567890.0,
                fs_atime=1234567890.0,
            )
            repo.add_file(img_path, metadata)

        return {
            'supported': [img1, img2],
            'unsupported': [gif1, txt1, doc1, deep_file]
        }

    def test_analyze_without_move_unsupported_ignores_other_files(self, tmp_path):
        """Sin la opción activada, los archivos no soportados no se incluyen"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=False
        )

        assert isinstance(result, OrganizationAnalysisResult)
        # Solo archivos soportados deben estar en el plan
        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']
        assert len(unsupported_moves) == 0

    def test_analyze_with_move_unsupported_includes_other_files(self, tmp_path):
        """Con la opción activada, los archivos no soportados se mueven a 'other/'"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        assert isinstance(result, OrganizationAnalysisResult)
        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']
        assert len(unsupported_moves) == len(files['unsupported'])

    def test_unsupported_files_target_other_folder(self, tmp_path):
        """Los archivos no soportados deben ir a 'other/' con su estructura preservada"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']

        for move in unsupported_moves:
            # Todos deben ir dentro de 'other/'
            relative_target = move.target_path.relative_to(tmp_path)
            assert str(relative_target).startswith("other/") or str(relative_target).startswith("other\\")
            # El nombre del archivo debe conservarse
            assert move.original_name == move.source_path.name
            assert move.new_name == move.source_path.name

    def test_unsupported_preserves_directory_structure(self, tmp_path):
        """La estructura de carpetas relativa debe mantenerse dentro de 'other/'"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']
        move_map = {m.source_path.name: m for m in unsupported_moves}

        # animation.gif de subdir1 -> other/subdir1/animation.gif
        gif_move = move_map['animation.gif']
        assert gif_move.target_path == tmp_path / "other" / "subdir1" / "animation.gif"

        # notes.txt de subdir2 -> other/subdir2/notes.txt
        txt_move = move_map['notes.txt']
        assert txt_move.target_path == tmp_path / "other" / "subdir2" / "notes.txt"

        # readme.md de raíz -> other/readme.md
        md_move = move_map['readme.md']
        assert md_move.target_path == tmp_path / "other" / "readme.md"

        # data.csv de subdir1/nested -> other/subdir1/nested/data.csv
        csv_move = move_map['data.csv']
        assert csv_move.target_path == tmp_path / "other" / "subdir1" / "nested" / "data.csv"

    def test_unsupported_target_folder_set_correctly(self, tmp_path):
        """El campo target_folder debe reflejar la ruta correcta"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']
        move_map = {m.source_path.name: m for m in unsupported_moves}

        # Archivo en raíz -> target_folder = "other"
        assert move_map['readme.md'].target_folder == "other"

        # Archivo en subdir1 -> target_folder = "other/subdir1" (or os-specific separator)
        assert move_map['animation.gif'].target_folder == str(Path("other/subdir1"))

        # Archivo en subdir1/nested -> target_folder = "other/subdir1/nested"
        assert move_map['data.csv'].target_folder == str(Path("other/subdir1/nested"))

    def test_files_already_in_other_are_skipped(self, tmp_path):
        """Archivos ya dentro de 'other/' no deben incluirse"""
        files = self._create_test_structure(tmp_path)

        # Crear archivos dentro de una carpeta 'other/' existente
        other_file = tmp_path / "other" / "existing.txt"
        other_file.parent.mkdir(parents=True, exist_ok=True)
        other_file.write_bytes(b"already in other")

        service = FileOrganizerService()
        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']
        source_paths = [m.source_path for m in unsupported_moves]

        # El archivo que ya está en 'other/' no debe estar en el plan
        assert other_file not in source_paths

    def test_move_unsupported_works_with_by_type(self, tmp_path):
        """La opción funciona con organización por tipo"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_TYPE,
            move_unsupported_to_other=True
        )

        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']
        assert len(unsupported_moves) == len(files['unsupported'])

    def test_move_unsupported_works_with_to_root(self, tmp_path):
        """La opción funciona con mover todo al raíz"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.TO_ROOT,
            move_unsupported_to_other=True
        )

        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']
        assert len(unsupported_moves) == len(files['unsupported'])

    def test_result_has_move_unsupported_flag(self, tmp_path):
        """El resultado debe guardar el flag move_unsupported_to_other"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        assert result.move_unsupported_to_other is True

    def test_result_flag_false_when_disabled(self, tmp_path):
        """El resultado debe reflejar cuando la opción está deshabilitada"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=False
        )

        assert result.move_unsupported_to_other is False

    def test_unsupported_files_have_correct_size(self, tmp_path):
        """Los archivos no soportados deben tener size correcto"""
        files = self._create_test_structure(tmp_path)
        service = FileOrganizerService()

        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']
        for move in unsupported_moves:
            expected_size = move.source_path.stat().st_size
            assert move.size == expected_size

    def test_no_unsupported_files_returns_empty(self, tmp_path):
        """Si no hay archivos no soportados, no se generan movimientos extra"""
        # Solo crear archivos soportados
        img = tmp_path / "subdir" / "photo.jpg"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"fake jpg")

        repo = FileInfoRepositoryCache.get_instance()
        metadata = FileMetadata(
            path=img,
            fs_size=img.stat().st_size,
            fs_ctime=1234567890.0,
            fs_mtime=1234567890.0,
            fs_atime=1234567890.0,
        )
        repo.add_file(img, metadata)

        service = FileOrganizerService()
        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        unsupported_moves = [m for m in result.move_plan if m.file_type == 'OTHER']
        assert len(unsupported_moves) == 0


class TestFileOrganizerExecuteUnsupported:
    """Tests de ejecución con archivos no soportados"""

    def setup_method(self):
        """Limpiar el repositorio antes de cada test"""
        repo = FileInfoRepositoryCache.get_instance()
        repo.clear()

    def test_execute_moves_unsupported_files(self, tmp_path):
        """Execute debe mover físicamente los archivos no soportados"""
        # Crear estructura
        img = tmp_path / "subdir" / "photo.jpg"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"fake jpg")

        gif = tmp_path / "subdir" / "anim.gif"
        gif.write_bytes(b"fake gif content")

        repo = FileInfoRepositoryCache.get_instance()
        metadata = FileMetadata(
            path=img,
            fs_size=img.stat().st_size,
            fs_ctime=1234567890.0,
            fs_mtime=1234567890.0,
            fs_atime=1234567890.0,
        )
        repo.add_file(img, metadata)

        service = FileOrganizerService()
        analysis = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        # Verificar que hay un move para el gif
        unsupported_moves = [m for m in analysis.move_plan if m.file_type == 'OTHER']
        assert len(unsupported_moves) == 1
        assert unsupported_moves[0].source_path == gif

        # Ejecutar en modo real (sin backup para simplificar)
        result = service.execute(analysis, create_backup=False, dry_run=False)

        # El gif debe haberse movido
        assert not gif.exists()
        expected_target = tmp_path / "other" / "subdir" / "anim.gif"
        assert expected_target.exists()
        assert result.success

    def test_execute_dry_run_does_not_move_unsupported(self, tmp_path):
        """En modo simulación, los archivos no soportados no deben moverse"""
        img = tmp_path / "subdir" / "photo.jpg"
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"fake jpg")

        gif = tmp_path / "subdir" / "anim.gif"
        gif.write_bytes(b"fake gif content")

        repo = FileInfoRepositoryCache.get_instance()
        metadata = FileMetadata(
            path=img,
            fs_size=img.stat().st_size,
            fs_ctime=1234567890.0,
            fs_mtime=1234567890.0,
            fs_atime=1234567890.0,
        )
        repo.add_file(img, metadata)

        service = FileOrganizerService()
        analysis = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
            move_unsupported_to_other=True
        )

        result = service.execute(analysis, create_backup=False, dry_run=True)

        # El gif NO debe haberse movido
        assert gif.exists()
        assert not (tmp_path / "other" / "subdir" / "anim.gif").exists()
        assert result.dry_run is True


class TestFileOrganizerSelfConflict:
    """Tests para el bug de auto-conflicto (_001 suffix).
    
    Cuando se ejecuta el organizador dos veces con el mismo modo, los archivos
    que ya están en su carpeta destino correcta NO deben ser renombrados con
    sufijo _001. El plan debe excluirlos (movimiento no-op).
    """

    def setup_method(self):
        """Limpiar el repositorio antes de cada test"""
        repo = FileInfoRepositoryCache.get_instance()
        repo.clear()

    def _register_file_in_cache(self, file_path: Path, best_date: datetime = None):
        """Helper: registra un archivo en la caché con metadatos mínimos"""
        repo = FileInfoRepositoryCache.get_instance()
        metadata = FileMetadata(
            path=file_path,
            fs_size=file_path.stat().st_size,
            fs_ctime=1234567890.0,
            fs_mtime=1234567890.0,
            fs_atime=1234567890.0,
            best_date=best_date,
            best_date_source='EXIF' if best_date else None,
        )
        repo.add_file(file_path, metadata)

    def test_no_self_conflict_by_month_files_already_in_place(self, tmp_path):
        """Archivos ya en su carpeta by_month correcta no deben generar movimientos"""
        # Simular estado post-organización: archivos ya en 2025_01/
        target_dir = tmp_path / "2025_01"
        target_dir.mkdir()
        
        img1 = target_dir / "IMG_001.JPG"
        img1.write_bytes(b"photo data 1")
        img2 = target_dir / "IMG_002.JPG"
        img2.write_bytes(b"photo data 2")

        date_jan = datetime(2025, 1, 15, 10, 0, 0)
        self._register_file_in_cache(img1, best_date=date_jan)
        self._register_file_in_cache(img2, best_date=date_jan)

        service = FileOrganizerService()
        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
        )

        # No debe haber movimientos: archivos ya están donde deben
        assert len(result.move_plan) == 0

    def test_no_self_conflict_by_year_month_files_already_in_place(self, tmp_path):
        """Archivos ya en su carpeta by_year_month correcta no deben generar movimientos"""
        target_dir = tmp_path / "2025" / "01"
        target_dir.mkdir(parents=True)

        img1 = target_dir / "IMG_001.JPG"
        img1.write_bytes(b"photo data 1")

        date_jan = datetime(2025, 1, 15, 10, 0, 0)
        self._register_file_in_cache(img1, best_date=date_jan)

        service = FileOrganizerService()
        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_YEAR_MONTH,
        )

        assert len(result.move_plan) == 0

    def test_no_self_conflict_by_year_files_already_in_place(self, tmp_path):
        """Archivos ya en su carpeta by_year correcta no deben generar movimientos"""
        target_dir = tmp_path / "2025"
        target_dir.mkdir()

        img1 = target_dir / "IMG_001.JPG"
        img1.write_bytes(b"photo data 1")

        date_jan = datetime(2025, 1, 15, 10, 0, 0)
        self._register_file_in_cache(img1, best_date=date_jan)

        service = FileOrganizerService()
        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_YEAR,
        )

        assert len(result.move_plan) == 0

    def test_no_self_conflict_by_type_files_already_in_place(self, tmp_path):
        """Files already in their correct by_type folder should not generate moves"""
        photos_dir = tmp_path / "Photos"
        photos_dir.mkdir()

        img1 = photos_dir / "IMG_001.JPG"
        img1.write_bytes(b"photo data 1")

        self._register_file_in_cache(img1)

        service = FileOrganizerService()
        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_TYPE,
        )

        assert len(result.move_plan) == 0

    def test_no_self_conflict_to_root_files_already_in_root(self, tmp_path):
        """Archivos ya en root no deben generar movimientos con TO_ROOT"""
        img1 = tmp_path / "IMG_001.JPG"
        img1.write_bytes(b"photo data 1")

        self._register_file_in_cache(img1)

        service = FileOrganizerService()
        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.TO_ROOT,
        )

        # Archivos ya en root son root_files, no subdirectory files,
        # por lo que TO_ROOT no los incluye en el plan
        assert len(result.move_plan) == 0

    def test_files_not_renamed_on_second_run_by_month(self, tmp_path):
        """Simula ejecutar organización by_month dos veces: la segunda no debe renombrar"""
        # Primera ejecución: archivos en subdirectorio se mueven a carpeta de fecha
        subdir = tmp_path / "original_folder"
        subdir.mkdir()

        img1 = subdir / "IMG_001.JPG"
        img1.write_bytes(b"photo data 1")
        img2 = subdir / "IMG_002.JPG"
        img2.write_bytes(b"photo data 2")

        date_jan = datetime(2025, 1, 15, 10, 0, 0)
        self._register_file_in_cache(img1, best_date=date_jan)
        self._register_file_in_cache(img2, best_date=date_jan)

        service = FileOrganizerService()

        # Primera ejecución
        result1 = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
        )
        assert len(result1.move_plan) == 2
        exec_result1 = service.execute(result1, create_backup=False, dry_run=False)
        assert exec_result1.success

        # Verificar que los archivos se movieron correctamente
        target_dir = tmp_path / "2025_01"
        assert (target_dir / "IMG_001.JPG").exists()
        assert (target_dir / "IMG_002.JPG").exists()

        # Actualizar caché para segunda ejecución
        repo = FileInfoRepositoryCache.get_instance()
        repo.clear()
        for f in target_dir.iterdir():
            if f.is_file():
                self._register_file_in_cache(f, best_date=date_jan)

        # Segunda ejecución: NO debe generar movimientos
        result2 = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
        )
        assert len(result2.move_plan) == 0

        # Verificar que los archivos mantienen su nombre original (sin _001)
        assert (target_dir / "IMG_001.JPG").exists()
        assert (target_dir / "IMG_002.JPG").exists()
        assert not (target_dir / "IMG_001_001.JPG").exists()
        assert not (target_dir / "IMG_002_001.JPG").exists()

    def test_mixed_self_conflict_and_real_conflict(self, tmp_path):
        """Archivos ya en destino se omiten, pero archivos nuevos con mismo nombre sí generan conflicto"""
        target_dir = tmp_path / "2025_01"
        target_dir.mkdir()

        # Archivo ya en destino correcto
        existing_img = target_dir / "IMG_001.JPG"
        existing_img.write_bytes(b"existing photo data")

        # Archivo con mismo nombre en otro subdirectorio (conflicto real)
        other_subdir = tmp_path / "camera_import"
        other_subdir.mkdir()
        new_img = other_subdir / "IMG_001.JPG"
        new_img.write_bytes(b"new photo data")

        date_jan = datetime(2025, 1, 15, 10, 0, 0)
        self._register_file_in_cache(existing_img, best_date=date_jan)
        self._register_file_in_cache(new_img, best_date=date_jan)

        service = FileOrganizerService()
        result = service.analyze(
            root_directory=tmp_path,
            organization_type=OrganizationType.BY_MONTH,
        )

        # Solo el archivo nuevo debe estar en el plan (el existente es no-op)
        assert len(result.move_plan) == 1
        move = result.move_plan[0]
        assert move.source_path == new_img
        # Debe tener conflicto y obtener sufijo _001 (conflicto real con el archivo existente)
        assert move.has_conflict is True
        assert "_001" in move.new_name

    def test_no_self_conflict_by_source(self, tmp_path):
        """Archivos ya en su carpeta by_source correcta no deben generar movimientos"""
        source_dir = tmp_path / "iPhone"
        source_dir.mkdir()

        img1 = source_dir / "IMG_001.JPG"
        img1.write_bytes(b"photo data 1")

        self._register_file_in_cache(img1)

        service = FileOrganizerService()
        with patch('services.file_organizer_service.detect_file_source', return_value='iPhone'):
            result = service.analyze(
                root_directory=tmp_path,
                organization_type=OrganizationType.BY_SOURCE,
            )

        assert len(result.move_plan) == 0

    def test_execute_skips_noop_moves(self, tmp_path):
        """Execute debe omitir movimientos donde source == target (defensa en profundidad)"""
        img1 = tmp_path / "IMG_001.JPG"
        img1.write_bytes(b"photo data 1")

        # Crear un FileMove artificial donde source == target
        noop_move = FileMove(
            source_path=img1,
            target_path=img1,
            original_name="IMG_001.JPG",
            new_name="IMG_001.JPG",
            subdirectory="<root>",
            file_type="PHOTO",
            size=12,
        )

        analysis = OrganizationAnalysisResult(
            move_plan=[noop_move],
            root_directory=str(tmp_path),
            organization_type="by_month",
            subdirectories={},
        )

        service = FileOrganizerService()
        result = service.execute(analysis, create_backup=False, dry_run=False)

        # El archivo debe seguir existiendo con su nombre original
        assert img1.exists()
        assert not (tmp_path / "IMG_001_001.JPG").exists()
        assert result.success
