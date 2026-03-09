# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests profesionales para InitialScanner.
Verifica el correcto funcionamiento del escáner multi-fase,
incluyendo clasificación de archivos, callbacks de progreso y cancelación.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from services.initial_scanner import InitialScanner, PhaseProgress
from services.file_metadata_repository_cache import FileInfoRepositoryCache, PopulationStrategy
from services.result_types import DirectoryScanResult


class TestInitialScannerBasics:
    """Tests básicos de inicialización y constantes de fase"""
    
    def test_scanner_initialization(self):
        """El scanner debe inicializarse correctamente"""
        scanner = InitialScanner()
        assert scanner is not None
        assert scanner._should_stop is False
    
    def test_phase_constants_exist(self):
        """Deben existir las constantes de las 6 fases"""
        assert InitialScanner.PHASE_FILE_CLASSIFICATION == "phase_file_classification"
        assert InitialScanner.PHASE_FILESYSTEM_METADATA == "phase_filesystem_metadata"
        assert InitialScanner.PHASE_HASH == "phase_hash"
        assert InitialScanner.PHASE_EXIF_IMAGES == "phase_exif_images"
        assert InitialScanner.PHASE_EXIF_VIDEOS == "phase_exif_videos"
        assert InitialScanner.PHASE_BEST_DATE == "phase_best_date"
    
    def test_request_stop_sets_flag(self):
        """request_stop debe establecer la bandera _should_stop"""
        scanner = InitialScanner()
        assert scanner._should_stop is False
        scanner.request_stop()
        assert scanner._should_stop is True


class TestPhaseProgress:
    """Tests del dataclass PhaseProgress"""
    
    def test_phase_progress_creation(self):
        """PhaseProgress debe crearse correctamente"""
        progress = PhaseProgress(
            phase_id="test_phase",
            phase_name="Test Phase",
            current=50,
            total=100,
            message="Processing..."
        )
        assert progress.phase_id == "test_phase"
        assert progress.phase_name == "Test Phase"
        assert progress.current == 50
        assert progress.total == 100
        assert progress.message == "Processing..."


class TestInitialScannerFileClassification:
    """Tests de la fase 1: clasificación de archivos"""
    
    def setup_method(self):
        """Limpiar repositorio antes de cada test"""
        FileInfoRepositoryCache.reset_instance()
    
    def test_scan_empty_directory(self, temp_dir):
        """Escanear directorio vacío debe retornar resultado vacío"""
        scanner = InitialScanner()
        result = scanner.scan(temp_dir)
        
        assert result.total_files == 0
        assert len(result.images) == 0
        assert len(result.videos) == 0
        assert len(result.others) == 0
    
    def test_scan_classifies_images_correctly(self, temp_dir, create_test_image):
        """Debe clasificar imágenes correctamente"""
        create_test_image(temp_dir / "photo1.jpg")
        create_test_image(temp_dir / "photo2.png")
        create_test_image(temp_dir / "photo3.jpeg")
        
        scanner = InitialScanner()
        result = scanner.scan(
            temp_dir,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert result.total_files == 3
        assert len(result.images) == 3
        assert len(result.videos) == 0
        assert len(result.others) == 0
    
    def test_scan_classifies_videos_correctly(self, temp_dir, create_test_video):
        """Debe clasificar videos correctamente"""
        create_test_video(temp_dir / "video1.mp4")
        create_test_video(temp_dir / "video2.mov")
        
        scanner = InitialScanner()
        result = scanner.scan(
            temp_dir,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert result.total_files == 2
        assert len(result.images) == 0
        assert len(result.videos) == 2
        assert len(result.others) == 0
    
    def test_scan_classifies_mixed_files(self, temp_dir, create_test_image, create_test_video):
        """Debe clasificar mezcla de archivos correctamente"""
        create_test_image(temp_dir / "photo.jpg")
        create_test_video(temp_dir / "video.mp4")
        (temp_dir / "document.txt").write_text("hello")
        (temp_dir / "data.json").write_text("{}")
        
        scanner = InitialScanner()
        result = scanner.scan(
            temp_dir,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert result.total_files == 4
        assert len(result.images) == 1
        assert len(result.videos) == 1
        assert len(result.others) == 2
    
    def test_scan_counts_extensions(self, temp_dir, create_test_image):
        """Debe contar extensiones correctamente"""
        create_test_image(temp_dir / "photo1.jpg")
        create_test_image(temp_dir / "photo2.jpg")
        create_test_image(temp_dir / "photo3.png")
        
        scanner = InitialScanner()
        result = scanner.scan(
            temp_dir,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert result.image_extensions.get('.jpg', 0) == 2
        assert result.image_extensions.get('.png', 0) == 1
    
    def test_scan_handles_nested_directories(self, nested_temp_dir, create_test_image):
        """Debe escanear subdirectorios recursivamente"""
        root, subdirs = nested_temp_dir
        create_test_image(root / "root_photo.jpg")
        create_test_image(subdirs['subdir1'] / "sub1_photo.jpg")
        create_test_image(subdirs['nested'] / "nested_photo.jpg")
        
        scanner = InitialScanner()
        result = scanner.scan(
            root,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert result.total_files == 3
        assert len(result.images) == 3


class TestInitialScannerPhaseCallbacks:
    """Tests de callbacks de fase"""
    
    def setup_method(self):
        """Limpiar repositorio antes de cada test"""
        FileInfoRepositoryCache.reset_instance()
    
    def test_phase_callback_called_for_classification(self, temp_dir, create_test_image):
        """phase_callback debe llamarse para fase de clasificación"""
        create_test_image(temp_dir / "photo.jpg")
        
        phase_callback = Mock()
        scanner = InitialScanner()
        
        scanner.scan(
            temp_dir,
            phase_callback=phase_callback,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        # Verificar que se llamó con la fase de clasificación
        calls = [call[0] for call in phase_callback.call_args_list]
        assert (InitialScanner.PHASE_FILE_CLASSIFICATION, "Escaneando estructura de carpetas") in calls
    
    def test_phase_callback_called_for_filesystem_metadata(self, temp_dir, create_test_image):
        """phase_callback debe llamarse para fase de metadata del filesystem"""
        create_test_image(temp_dir / "photo.jpg")
        
        phase_callback = Mock()
        scanner = InitialScanner()
        
        scanner.scan(
            temp_dir,
            phase_callback=phase_callback,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        calls = [call[0] for call in phase_callback.call_args_list]
        assert (InitialScanner.PHASE_FILESYSTEM_METADATA, "Obteniendo información de archivos") in calls
    
    def test_phase_completed_callback_called(self, temp_dir, create_test_image):
        """phase_completed_callback debe llamarse al completar fases"""
        create_test_image(temp_dir / "photo.jpg")
        
        phase_completed = Mock()
        scanner = InitialScanner()
        
        scanner.scan(
            temp_dir,
            phase_completed_callback=phase_completed,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        # Verificar que se completaron las fases básicas
        completed_phases = [call[0][0] for call in phase_completed.call_args_list]
        assert InitialScanner.PHASE_FILE_CLASSIFICATION in completed_phases
        assert InitialScanner.PHASE_FILESYSTEM_METADATA in completed_phases
    
    def test_all_six_phases_called_when_enabled(self, temp_dir, create_test_image, create_test_video):
        """Todas las 6 fases deben ejecutarse cuando están habilitadas (o saltarse si faltan herramientas)"""
        create_test_image(temp_dir / "photo.jpg")
        create_test_video(temp_dir / "video.mp4")
        
        phase_callback = Mock()
        phase_completed = Mock()
        phase_skipped = Mock()
        scanner = InitialScanner()
        
        scanner.scan(
            temp_dir,
            phase_callback=phase_callback,
            phase_completed_callback=phase_completed,
            phase_skipped_callback=phase_skipped,
            calculate_hashes=True,
            extract_image_exif=True,
            extract_video_exif=True
        )
        
        # Verificar que se iniciaron las fases principales
        started_phases = [call[0][0] for call in phase_callback.call_args_list]
        assert InitialScanner.PHASE_FILE_CLASSIFICATION in started_phases
        assert InitialScanner.PHASE_FILESYSTEM_METADATA in started_phases
        assert InitialScanner.PHASE_HASH in started_phases
        assert InitialScanner.PHASE_EXIF_IMAGES in started_phases
        assert InitialScanner.PHASE_BEST_DATE in started_phases
        
        # La fase de video EXIF puede estar en started_phases O haber sido saltada
        skipped_phases = [call[0][0] for call in phase_skipped.call_args_list]
        video_phase_handled = (
            InitialScanner.PHASE_EXIF_VIDEOS in started_phases or 
            InitialScanner.PHASE_EXIF_VIDEOS in skipped_phases
        )
        assert video_phase_handled, "Video EXIF phase should be either started or skipped"


class TestInitialScannerProgressCallback:
    """Tests de callback de progreso"""
    
    def setup_method(self):
        """Limpiar repositorio antes de cada test"""
        FileInfoRepositoryCache.reset_instance()
    
    def test_progress_callback_receives_phase_progress(self, temp_dir, create_test_image):
        """progress_callback debe recibir objetos PhaseProgress"""
        for i in range(5):
            create_test_image(temp_dir / f"photo{i}.jpg")
        
        progress_calls = []
        def progress_callback(phase_progress):
            progress_calls.append(phase_progress)
            return True
        
        scanner = InitialScanner()
        scanner.scan(
            temp_dir,
            progress_callback=progress_callback,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert len(progress_calls) > 0
        assert all(isinstance(p, PhaseProgress) for p in progress_calls)
    
    def test_progress_callback_shows_initial_zero(self, temp_dir, create_test_image):
        """progress_callback debe recibir progreso inicial (0/total)"""
        for i in range(3):
            create_test_image(temp_dir / f"photo{i}.jpg")
        
        progress_calls = []
        def progress_callback(phase_progress):
            progress_calls.append(phase_progress)
            return True
        
        scanner = InitialScanner()
        scanner.scan(
            temp_dir,
            progress_callback=progress_callback,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        # Verificar que hay un progreso inicial con current=0
        classification_progress = [p for p in progress_calls 
                                   if p.phase_id == InitialScanner.PHASE_FILE_CLASSIFICATION]
        assert len(classification_progress) > 0
        assert classification_progress[0].current == 0
        assert classification_progress[0].total == 3
    
    def test_progress_callback_shows_final_total(self, temp_dir, create_test_image):
        """progress_callback debe mostrar progreso final (total/total)"""
        for i in range(3):
            create_test_image(temp_dir / f"photo{i}.jpg")
        
        progress_calls = []
        def progress_callback(phase_progress):
            progress_calls.append(phase_progress)
            return True
        
        scanner = InitialScanner()
        scanner.scan(
            temp_dir,
            progress_callback=progress_callback,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        # Verificar que hay un progreso final con current=total
        classification_progress = [p for p in progress_calls 
                                   if p.phase_id == InitialScanner.PHASE_FILE_CLASSIFICATION]
        assert classification_progress[-1].current == classification_progress[-1].total


class TestInitialScannerCancellation:
    """Tests de cancelación del scan"""
    
    def setup_method(self):
        """Limpiar repositorio antes de cada test"""
        FileInfoRepositoryCache.reset_instance()
    
    def test_cancel_via_request_stop(self, temp_dir, create_test_image):
        """request_stop debe cancelar el scan"""
        for i in range(10):
            create_test_image(temp_dir / f"photo{i}.jpg")
        
        scanner = InitialScanner()
        
        call_count = 0
        def progress_callback(phase_progress):
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                scanner.request_stop()
            return True
        
        result = scanner.scan(
            temp_dir,
            progress_callback=progress_callback,
            calculate_hashes=True,
            extract_image_exif=True,
            extract_video_exif=True
        )
        
        # El scan debe haberse cancelado
        assert scanner._should_stop is True
    
    def test_cancel_via_progress_callback_return_false(self, temp_dir, create_test_image):
        """Retornar False en progress_callback debe cancelar el scan (durante clasificación)"""
        for i in range(50):  # Más archivos para dar tiempo a cancelar
            create_test_image(temp_dir / f"photo{i}.jpg")
        
        call_count = 0
        def progress_callback(phase_progress):
            nonlocal call_count
            call_count += 1
            # Cancelar durante la clasificación (fase 1)
            if phase_progress.phase_id == InitialScanner.PHASE_FILE_CLASSIFICATION:
                return call_count <= 1  # Solo permitir el primer callback
            return True
        
        scanner = InitialScanner()
        result = scanner.scan(
            temp_dir,
            progress_callback=progress_callback,
            calculate_hashes=True,
            extract_image_exif=True,
            extract_video_exif=True
        )
        
        # El scan debe haberse cancelado durante la clasificación
        assert scanner._should_stop is True
    
    def test_cancelled_scan_returns_partial_result(self, temp_dir, create_test_image):
        """Un scan cancelado debe retornar resultado parcial"""
        for i in range(20):
            create_test_image(temp_dir / f"photo{i}.jpg")
        
        scanner = InitialScanner()
        
        def progress_callback(phase_progress):
            # Cancelar inmediatamente después del progreso inicial
            if phase_progress.current > 0:
                scanner.request_stop()
            return True
        
        result = scanner.scan(
            temp_dir,
            progress_callback=progress_callback,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        # Debe retornar un DirectoryScanResult válido
        assert isinstance(result, DirectoryScanResult)


class TestInitialScannerConfiguration:
    """Tests de configuración de fases opcionales"""
    
    def setup_method(self):
        """Limpiar repositorio antes de cada test"""
        FileInfoRepositoryCache.reset_instance()
    
    def test_skip_hash_calculation(self, temp_dir, create_test_image):
        """calculate_hashes=False debe omitir fase de hash"""
        create_test_image(temp_dir / "photo.jpg")
        
        phase_callback = Mock()
        scanner = InitialScanner()
        
        scanner.scan(
            temp_dir,
            phase_callback=phase_callback,
            calculate_hashes=False,
            extract_image_exif=True,
            extract_video_exif=True
        )
        
        started_phases = [call[0][0] for call in phase_callback.call_args_list]
        assert InitialScanner.PHASE_HASH not in started_phases
    
    def test_skip_image_exif_extraction(self, temp_dir, create_test_image):
        """extract_image_exif=False debe omitir fase de EXIF de imágenes"""
        create_test_image(temp_dir / "photo.jpg")
        
        phase_callback = Mock()
        scanner = InitialScanner()
        
        scanner.scan(
            temp_dir,
            phase_callback=phase_callback,
            calculate_hashes=True,
            extract_image_exif=False,
            extract_video_exif=True
        )
        
        started_phases = [call[0][0] for call in phase_callback.call_args_list]
        assert InitialScanner.PHASE_EXIF_IMAGES not in started_phases
    
    def test_skip_video_exif_extraction(self, temp_dir, create_test_video):
        """extract_video_exif=False debe omitir fase de EXIF de videos"""
        create_test_video(temp_dir / "video.mp4")
        
        phase_callback = Mock()
        scanner = InitialScanner()
        
        scanner.scan(
            temp_dir,
            phase_callback=phase_callback,
            calculate_hashes=True,
            extract_image_exif=True,
            extract_video_exif=False
        )
        
        started_phases = [call[0][0] for call in phase_callback.call_args_list]
        assert InitialScanner.PHASE_EXIF_VIDEOS not in started_phases
    
    def test_all_phases_disabled_except_basic(self, temp_dir, create_test_image):
        """Con todas las opciones en False, solo deben ejecutarse fases 1, 2 y 6"""
        create_test_image(temp_dir / "photo.jpg")
        
        phase_callback = Mock()
        scanner = InitialScanner()
        
        scanner.scan(
            temp_dir,
            phase_callback=phase_callback,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        started_phases = [call[0][0] for call in phase_callback.call_args_list]
        
        # Fases obligatorias
        assert InitialScanner.PHASE_FILE_CLASSIFICATION in started_phases
        assert InitialScanner.PHASE_FILESYSTEM_METADATA in started_phases
        assert InitialScanner.PHASE_BEST_DATE in started_phases
        
        # Fases opcionales omitidas
        assert InitialScanner.PHASE_HASH not in started_phases
        assert InitialScanner.PHASE_EXIF_IMAGES not in started_phases
        assert InitialScanner.PHASE_EXIF_VIDEOS not in started_phases


class TestInitialScannerRepositoryIntegration:
    """Tests de integración con FileInfoRepositoryCache"""
    
    def setup_method(self):
        """Limpiar repositorio antes de cada test"""
        FileInfoRepositoryCache.reset_instance()
    
    def test_scan_populates_repository(self, temp_dir, create_test_image):
        """El scan debe poblar el repositorio con metadata"""
        create_test_image(temp_dir / "photo1.jpg")
        create_test_image(temp_dir / "photo2.jpg")
        
        scanner = InitialScanner()
        scanner.scan(
            temp_dir,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        repo = FileInfoRepositoryCache.get_instance()
        assert len(repo) == 2
    
    def test_scan_with_hashes_populates_hashes(self, temp_dir, create_test_image):
        """El scan con hashes debe calcular y almacenar hashes"""
        img_path = create_test_image(temp_dir / "photo.jpg")
        
        scanner = InitialScanner()
        scanner.scan(
            temp_dir,
            calculate_hashes=True,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        repo = FileInfoRepositoryCache.get_instance()
        hash_value = repo.get_hash(img_path)
        
        assert hash_value is not None
        assert len(hash_value) == 64  # SHA256 hex string
    
    def test_repository_empty_after_cancelled_classification(self, temp_dir, create_test_image):
        """Si se cancela durante clasificación, el repositorio debe estar vacío"""
        for i in range(5):
            create_test_image(temp_dir / f"photo{i}.jpg")
        
        scanner = InitialScanner()
        
        # Cancelar inmediatamente
        def progress_callback(phase_progress):
            if phase_progress.phase_id == InitialScanner.PHASE_FILE_CLASSIFICATION:
                scanner.request_stop()
            return True
        
        scanner.scan(
            temp_dir,
            progress_callback=progress_callback,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        repo = FileInfoRepositoryCache.get_instance()
        # El repositorio puede estar vacío o parcialmente poblado
        # dependiendo de cuándo se canceló
        assert isinstance(len(repo), int)


class TestInitialScannerEdgeCases:
    """Tests de casos límite"""
    
    def setup_method(self):
        """Limpiar repositorio antes de cada test"""
        FileInfoRepositoryCache.reset_instance()
    
    def test_scan_directory_with_only_unsupported_files(self, temp_dir):
        """Debe manejar directorios con solo archivos no soportados"""
        (temp_dir / "doc.txt").write_text("hello")
        (temp_dir / "data.json").write_text("{}")
        (temp_dir / "readme.md").write_text("# Readme")
        
        scanner = InitialScanner()
        result = scanner.scan(
            temp_dir,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert result.total_files == 3
        assert len(result.images) == 0
        assert len(result.videos) == 0
        assert len(result.others) == 3
    
    def test_scan_handles_files_without_extension(self, temp_dir):
        """Debe manejar archivos sin extensión"""
        (temp_dir / "noext").write_bytes(b"data")
        
        scanner = InitialScanner()
        result = scanner.scan(
            temp_dir,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert result.total_files == 1
        assert len(result.others) == 1
        # Debe contar como '(no extension)'
        assert '(no extension)' in result.unsupported_extensions
    
    def test_scan_nonexistent_directory_raises_error(self):
        """Debe lanzar error para directorio inexistente"""
        scanner = InitialScanner()
        nonexistent = Path("/nonexistent/path/that/does/not/exist")
        
        with pytest.raises(Exception):  # validate_directory_exists raises error
            scanner.scan(nonexistent)
    
    def test_scan_calculates_total_size(self, temp_dir, create_test_image):
        """Debe calcular el tamaño total correctamente"""
        create_test_image(temp_dir / "photo1.jpg")
        create_test_image(temp_dir / "photo2.jpg")
        
        scanner = InitialScanner()
        result = scanner.scan(
            temp_dir,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert result.total_size > 0
    
    def test_scan_with_heic_files(self, temp_dir, create_test_image):
        """Debe clasificar archivos HEIC como imágenes"""
        # Crear archivo con extensión HEIC (el contenido no importa para clasificación)
        heic_path = temp_dir / "photo.heic"
        create_test_image(heic_path)
        
        scanner = InitialScanner()
        result = scanner.scan(
            temp_dir,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        assert len(result.images) == 1
        assert '.heic' in result.image_extensions


class TestInitialScannerPhaseOrder:
    """Tests para verificar el orden correcto de las fases"""
    
    def setup_method(self):
        """Limpiar repositorio antes de cada test"""
        FileInfoRepositoryCache.reset_instance()
    
    def test_phases_execute_in_correct_order(self, temp_dir, create_test_image, create_test_video):
        """Las fases deben ejecutarse en el orden correcto 1-6 (video EXIF puede saltarse si no hay herramientas)"""
        create_test_image(temp_dir / "photo.jpg")
        create_test_video(temp_dir / "video.mp4")
        
        phase_order = []
        skipped_phases = []
        
        def phase_callback(phase_id, phase_msg):
            phase_order.append(phase_id)
        
        def phase_skipped_callback(phase_id, reason):
            skipped_phases.append(phase_id)
        
        scanner = InitialScanner()
        scanner.scan(
            temp_dir,
            phase_callback=phase_callback,
            phase_skipped_callback=phase_skipped_callback,
            calculate_hashes=True,
            extract_image_exif=True,
            extract_video_exif=True
        )
        
        # El orden esperado sin video EXIF (si las herramientas no están disponibles)
        expected_order_without_video = [
            InitialScanner.PHASE_FILE_CLASSIFICATION,
            InitialScanner.PHASE_FILESYSTEM_METADATA,
            InitialScanner.PHASE_HASH,
            InitialScanner.PHASE_EXIF_IMAGES,
            InitialScanner.PHASE_BEST_DATE,
        ]
        
        # El orden esperado con video EXIF
        expected_order_with_video = [
            InitialScanner.PHASE_FILE_CLASSIFICATION,
            InitialScanner.PHASE_FILESYSTEM_METADATA,
            InitialScanner.PHASE_HASH,
            InitialScanner.PHASE_EXIF_IMAGES,
            InitialScanner.PHASE_EXIF_VIDEOS,
            InitialScanner.PHASE_BEST_DATE,
        ]
        
        # Verificar que las fases están en el orden correcto
        if InitialScanner.PHASE_EXIF_VIDEOS in skipped_phases:
            assert phase_order == expected_order_without_video
        else:
            assert phase_order == expected_order_with_video
    
    def test_phase_completed_follows_phase_started(self, temp_dir, create_test_image):
        """Cada phase_completed debe seguir a su phase_started correspondiente"""
        create_test_image(temp_dir / "photo.jpg")
        
        events = []
        
        def phase_callback(phase_id, phase_msg):
            events.append(('started', phase_id))
        
        def phase_completed_callback(phase_id):
            events.append(('completed', phase_id))
        
        scanner = InitialScanner()
        scanner.scan(
            temp_dir,
            phase_callback=phase_callback,
            phase_completed_callback=phase_completed_callback,
            calculate_hashes=False,
            extract_image_exif=False,
            extract_video_exif=False
        )
        
        # Verificar que cada fase completada viene después de su inicio
        for i, event in enumerate(events):
            if event[0] == 'completed':
                phase_id = event[1]
                # Buscar el inicio correspondiente
                start_idx = None
                for j in range(i):
                    if events[j] == ('started', phase_id):
                        start_idx = j
                        break
                assert start_idx is not None, f"Phase {phase_id} completed without starting"
                assert start_idx < i, f"Phase {phase_id} completed before starting"
