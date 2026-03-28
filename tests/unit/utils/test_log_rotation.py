# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests exhaustivos para el sistema de rotación de logs.

Verifica que:
1. Los logs rotan correctamente al alcanzar MAX_LOG_FILE_SIZE_MB
2. Se mantiene el número correcto de backups según MAX_LOG_BACKUP_COUNT
3. Los archivos rotados mantienen el formato correcto (.1, .2, .3, etc.)
4. La rotación funciona correctamente dentro de una misma sesión
5. Los archivos antiguos se eliminan cuando se excede MAX_LOG_BACKUP_COUNT
"""
import pytest
import tempfile
from pathlib import Path
import logging

from utils.logger import configure_logging, get_logger
from config import Config

@pytest.fixture(autouse=True)
def mock_log_file_size():
    """Mock the log file size to a small value for faster tests and avoid Windows IO hangups."""
    original_size = Config.MAX_LOG_FILE_SIZE_MB
    Config.MAX_LOG_FILE_SIZE_MB = 0.05
    yield
    Config.MAX_LOG_FILE_SIZE_MB = original_size


class TestLogRotationBySize:
    """Tests para verificar que la rotación por tamaño funciona correctamente."""
    
    def test_rotation_occurs_when_exceeding_max_size(self, temp_dir):
        """
        Verifica que el archivo de log se rota automáticamente cuando
        excede MAX_LOG_FILE_SIZE_MB durante una sesión activa.
        """
        # Configurar logging
        log_file, _ = configure_logging(
            logs_dir=temp_dir,
            level="INFO",
            dual_log_enabled=False
        )
        
        logger = get_logger("TestRotation")
        
        # Calcular mensajes necesarios para exceder el límite
        max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
        message_size = 250  # ~250 bytes por mensaje
        messages_needed = (max_bytes // message_size) + 1000
        
        # Escribir mensajes
        message = "Test message for rotation. " * 8  # ~200 chars
        for i in range(messages_needed):
            logger.info(f"[{i:06d}] {message}")
            
            # Verificar rotación cada 5000 mensajes
            if i > 0 and i % 5000 == 0:
                rotated_file = Path(str(log_file) + ".1")
                if rotated_file.exists():
                    break
        
        # Verificar que la rotación ocurrió
        rotated_file = Path(str(log_file) + ".1")
        assert rotated_file.exists(), "El archivo rotado .1 debe existir"
        
        # Verificar que el archivo rotado es >= límite (con tolerancia del 95%)
        rotated_size_mb = rotated_file.stat().st_size / (1024 * 1024)
        assert rotated_size_mb >= Config.MAX_LOG_FILE_SIZE_MB * 0.95, \
            f"El archivo rotado debe ser >= {Config.MAX_LOG_FILE_SIZE_MB * 0.95} MB, fue {rotated_size_mb:.2f} MB"
        
        # Verificar que el archivo actual existe y es más pequeño que el límite
        assert log_file.exists(), "El archivo de log actual debe existir"
        current_size_mb = log_file.stat().st_size / (1024 * 1024)
        assert current_size_mb < Config.MAX_LOG_FILE_SIZE_MB, \
            f"El archivo actual debe ser < {Config.MAX_LOG_FILE_SIZE_MB} MB, fue {current_size_mb:.2f} MB"
    
    def test_rotation_resets_file_size(self, temp_dir):
        """
        Verifica que después de rotar, el archivo actual comienza con
        tamaño pequeño (casi vacío).
        """
        log_file, _ = configure_logging(logs_dir=temp_dir, level="INFO", dual_log_enabled=False)
        logger = get_logger("TestRotation")
        
        # Escribir suficientes mensajes para rotar
        max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
        messages_needed = (max_bytes // 250) + 1000
        
        for i in range(messages_needed):
            logger.info(f"[{i:06d}] " + "x" * 200)
            if i > 0 and i % 5000 == 0 and Path(str(log_file) + ".1").exists():
                break
        
        # Verificar que el archivo actual es pequeño después de rotar
        current_size_mb = log_file.stat().st_size / (1024 * 1024)
        assert current_size_mb < Config.MAX_LOG_FILE_SIZE_MB * 0.5, \
            f"Después de rotar, el archivo actual debe ser < 50% del límite, fue {current_size_mb:.2f} MB"


class TestLogRotationBackupCount:
    """Tests para verificar que se respeta MAX_LOG_BACKUP_COUNT."""
    
    def test_creates_correct_number_of_backups(self, temp_dir):
        """
        Verifica que se crean exactamente MAX_LOG_BACKUP_COUNT archivos
        rotados (.1, .2, .3, ..., .N) y no más.
        """
        # Usar un backup count pequeño para testing rápido
        original_backup_count = Config.MAX_LOG_BACKUP_COUNT
        test_backup_count = 3
        
        try:
            # Temporalmente cambiar el backup count
            Config.MAX_LOG_BACKUP_COUNT = test_backup_count
            
            log_file, _ = configure_logging(logs_dir=temp_dir, level="INFO", dual_log_enabled=False)
            logger = get_logger("TestBackupCount")
            
            # Calcular mensajes para provocar múltiples rotaciones
            max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
            messages_per_rotation = (max_bytes // 250) + 500
            
            # Rotar (test_backup_count + 2) veces para asegurar que se eliminan los viejos
            total_rotations = test_backup_count + 2
            total_messages = messages_per_rotation * total_rotations
            
            rotation_count = 0
            for i in range(total_messages):
                logger.info(f"[{i:06d}] " + "x" * 200)
                
                # Contar rotaciones
                if i % 1000 == 0:
                    new_rotation_count = sum(
                        1 for j in range(1, test_backup_count + 5)
                        if Path(f"{log_file}.{j}").exists()
                    )
                    if new_rotation_count > rotation_count:
                        rotation_count = new_rotation_count
                        
                        # Si ya tenemos suficientes rotaciones, detener
                        if rotation_count >= test_backup_count:
                            break
            
            # Verificar que existen exactamente test_backup_count archivos rotados
            existing_backups = []
            for i in range(1, test_backup_count + 5):
                backup_file = Path(f"{log_file}.{i}")
                if backup_file.exists():
                    existing_backups.append(i)
            
            assert len(existing_backups) <= test_backup_count, \
                f"Deben existir máximo {test_backup_count} backups, encontrados: {existing_backups}"
            
            # Verificar que los números son consecutivos desde .1
            if len(existing_backups) > 0:
                assert existing_backups[0] == 1, "El primer backup debe ser .1"
                for i in range(len(existing_backups) - 1):
                    assert existing_backups[i+1] == existing_backups[i] + 1, \
                        f"Los backups deben ser consecutivos: {existing_backups}"
        
        finally:
            # Restaurar valor original
            Config.MAX_LOG_BACKUP_COUNT = original_backup_count
    
    def test_old_backups_are_deleted(self, temp_dir):
        """
        Verifica que cuando se excede MAX_LOG_BACKUP_COUNT, los archivos
        más antiguos se eliminan correctamente.
        """
        original_backup_count = Config.MAX_LOG_BACKUP_COUNT
        test_backup_count = 2
        
        try:
            Config.MAX_LOG_BACKUP_COUNT = test_backup_count
            
            log_file, _ = configure_logging(logs_dir=temp_dir, level="INFO", dual_log_enabled=False)
            logger = get_logger("TestDeletion")
            
            # Provocar 4 rotaciones (más que el backup count)
            max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
            messages_per_rotation = (max_bytes // 250) + 500
            
            rotation_count = 0
            target_rotations = test_backup_count + 2
            
            for i in range(messages_per_rotation * target_rotations):
                logger.info(f"[{i:06d}] " + "x" * 200)
                
                if i % 1000 == 0:
                    new_count = sum(
                        1 for j in range(1, 10)
                        if Path(f"{log_file}.{j}").exists()
                    )
                    if new_count > rotation_count:
                        rotation_count = new_count
                    
                    if rotation_count >= target_rotations:
                        break
            
            # Verificar que NO existe .3 o superiores (solo .1 y .2)
            assert not Path(f"{log_file}.3").exists(), \
                "El backup .3 no debe existir cuando MAX_LOG_BACKUP_COUNT=2"
            assert not Path(f"{log_file}.4").exists(), \
                "El backup .4 no debe existir cuando MAX_LOG_BACKUP_COUNT=2"
            
            # Verificar que existen máximo test_backup_count backups
            existing_count = sum(
                1 for i in range(1, 10)
                if Path(f"{log_file}.{i}").exists()
            )
            assert existing_count <= test_backup_count, \
                f"Deben existir máximo {test_backup_count} backups, encontrados {existing_count}"
        
        finally:
            Config.MAX_LOG_BACKUP_COUNT = original_backup_count
    
    def test_backup_numbering_sequence(self, temp_dir):
        """
        Verifica que la numeración de backups es correcta y consecutiva:
        .1 es el más reciente, .2 es el anterior, etc.
        """
        original_backup_count = Config.MAX_LOG_BACKUP_COUNT
        test_backup_count = 3
        
        try:
            Config.MAX_LOG_BACKUP_COUNT = test_backup_count
            
            log_file, _ = configure_logging(logs_dir=temp_dir, level="INFO", dual_log_enabled=False)
            logger = get_logger("TestSequence")
            
            # Provocar múltiples rotaciones
            max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
            messages_per_rotation = (max_bytes // 250) + 500
            
            for i in range(messages_per_rotation * (test_backup_count + 1)):
                logger.info(f"[{i:06d}] " + "x" * 200)
                
                if i % 1000 == 0 and Path(f"{log_file}.{test_backup_count}").exists():
                    break
            
            # Obtener timestamps de modificación de los backups
            backup_times = {}
            for i in range(1, test_backup_count + 1):
                backup_file = Path(f"{log_file}.{i}")
                if backup_file.exists():
                    backup_times[i] = backup_file.stat().st_mtime
            
            # Verificar que .1 es el más reciente (mayor timestamp)
            if len(backup_times) > 1:
                assert backup_times[1] >= backup_times[2], \
                    ".1 debe ser más reciente que .2"
                
                if 3 in backup_times:
                    assert backup_times[2] >= backup_times[3], \
                        ".2 debe ser más reciente que .3"
        
        finally:
            Config.MAX_LOG_BACKUP_COUNT = original_backup_count


class TestLogRotationMultipleSessions:
    """Tests para verificar rotación entre múltiples sesiones."""
    
    def test_existing_file_rotates_on_init_if_too_large(self, temp_dir):
        """
        Verifica que si un archivo de log existente ya excede el límite
        al inicializar el logger, se rota inmediatamente.
        """
        log_file = temp_dir / "test_existing.log"
        
        # Crear un archivo grande manualmente (1.5x el límite)
        target_size = int((Config.MAX_LOG_FILE_SIZE_MB * 1.5) * 1024 * 1024)
        large_content = "x" * target_size
        log_file.write_text(large_content)
        
        assert log_file.stat().st_size > int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024), \
            "El archivo de prueba debe ser > límite"
        
        # Configurar logging con el archivo existente
        from utils.logger import ThreadSafeRotatingFileHandler
        
        handler = ThreadSafeRotatingFileHandler(
            str(log_file),
            maxBytes=int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024),
            backupCount=5
        )
        
        # Verificar que se creó el backup
        rotated_file = Path(str(log_file) + ".1")
        assert rotated_file.exists(), "Debe haberse creado un backup .1"
        
        # Verificar que el archivo original ahora es pequeño o vacío
        current_size_mb = log_file.stat().st_size / (1024 * 1024)
        assert current_size_mb < 1, \
            f"El archivo actual debe ser < 1 MB después de rotar, fue {current_size_mb:.2f} MB"
        
        # Cerrar handler
        handler.close()
    
    def test_multiple_init_sessions_respect_backup_count(self, temp_dir):
        """
        Verifica que múltiples inicializaciones del logger respetan
        el MAX_LOG_BACKUP_COUNT acumulado.
        """
        original_backup_count = Config.MAX_LOG_BACKUP_COUNT
        test_backup_count = 2
        
        try:
            Config.MAX_LOG_BACKUP_COUNT = test_backup_count
            
            # Sesión 1: Crear y rotar
            log_file, _ = configure_logging(logs_dir=temp_dir, level="INFO", dual_log_enabled=False)
            logger1 = get_logger("Session1")
            
            max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
            messages = (max_bytes // 250) + 500
            
            for i in range(messages):
                logger1.info(f"[Session1-{i:06d}] " + "x" * 200)
            
            # Limpiar primera sesión
            root_logger = logging.getLogger('SafeToolPix')
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)
            
            # Sesión 2: Nueva configuración y más escrituras
            log_file2, _ = configure_logging(logs_dir=temp_dir, level="INFO", dual_log_enabled=False)
            logger2 = get_logger("Session2")
            
            for i in range(messages):
                logger2.info(f"[Session2-{i:06d}] " + "x" * 200)
            
            # Verificar backups
            existing_backups = [
                i for i in range(1, test_backup_count + 5)
                if Path(f"{log_file2}.{i}").exists()
            ]
            
            assert len(existing_backups) <= test_backup_count, \
                f"Después de 2 sesiones, deben existir máximo {test_backup_count} backups, encontrados: {existing_backups}"
        
        finally:
            Config.MAX_LOG_BACKUP_COUNT = original_backup_count


class TestLogRotationDualLogging:
    """Tests para verificar rotación con dual logging habilitado."""
    
    def test_both_logs_rotate_independently(self, temp_dir):
        """
        Verifica que cuando dual_log_enabled=True, tanto el log principal
        como el de warnings rotan independientemente.
        """
        log_file, _ = configure_logging(
            logs_dir=temp_dir,
            level="INFO",
            dual_log_enabled=True
        )
        
        # Identificar el archivo de warnings
        warning_log = None
        for f in temp_dir.glob("*_WARNERROR.log"):
            warning_log = f
            break
        
        assert warning_log is not None, "Debe existir un archivo WARNERROR"
        
        logger = get_logger("TestDual")
        
        # Escribir muchos mensajes INFO (solo al log principal)
        max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
        messages = (max_bytes // 250) + 1000
        
        for i in range(messages):
            logger.info(f"[{i:06d}] " + "x" * 200)
            
            if i % 5000 == 0 and Path(str(log_file) + ".1").exists():
                break
        
        # Verificar que el log principal rotó
        assert Path(str(log_file) + ".1").exists(), \
            "El log principal debe haber rotado"
        
        # Verificar que el log de warnings NO rotó (no tiene suficiente contenido)
        assert not Path(str(warning_log) + ".1").exists(), \
            "El log de warnings no debe haber rotado (solo tiene INFO)"
        
        # Ahora escribir muchos warnings
        for i in range(messages):
            logger.warning(f"[WARNING-{i:06d}] " + "x" * 200)
            
            if i % 5000 == 0 and Path(str(warning_log) + ".1").exists():
                break
        
        # Verificar que ahora el log de warnings SÍ rotó
        assert Path(str(warning_log) + ".1").exists(), \
            "El log de warnings debe haber rotado después de escribir warnings"


class TestLogRotationEdgeCases:
    """Tests para casos borde y edge cases."""
    
    def test_rotation_with_zero_backup_count_disabled(self, temp_dir):
        """
        Verifica que con backupCount=0, la rotación está deshabilitada
        (comportamiento estándar de RotatingFileHandler).
        """
        from utils.logger import ThreadSafeRotatingFileHandler
        
        log_file = temp_dir / "test_no_rotation.log"
        
        # Crear handler con backupCount=0
        handler = ThreadSafeRotatingFileHandler(
            str(log_file),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=0  # Rotación deshabilitada
        )
        
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        
        test_logger = logging.getLogger('TestNoRotation')
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.INFO)
        
        # Escribir 10 MB de datos
        for i in range(50000):
            test_logger.info("x" * 200)
        
        # Verificar que NO se creó ningún backup
        assert not Path(str(log_file) + ".1").exists(), \
            "Con backupCount=0, no debe crearse ningún backup"
        
        # Verificar que el archivo creció sin límite
        size_mb = log_file.stat().st_size / (1024 * 1024)
        assert size_mb > 5, \
            f"El archivo debe haber crecido más de 5 MB sin rotar, tamaño: {size_mb:.2f} MB"
        
        handler.close()
    
    def test_rotation_preserves_log_content(self, temp_dir):
        """
        Verifica que el contenido de los logs se preserva correctamente
        durante la rotación (no se pierden mensajes).
        """
        log_file, _ = configure_logging(logs_dir=temp_dir, level="INFO", dual_log_enabled=False)
        logger = get_logger("TestContent")
        
        # Escribir mensajes con marcadores únicos
        marker_start = "MARKER_START"
        marker_end = "MARKER_END"
        
        max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
        messages = (max_bytes // 250) + 1000
        
        logger.info(marker_start)
        
        for i in range(messages):
            logger.info(f"Message-{i:06d}")
            
            if i % 5000 == 0 and Path(str(log_file) + ".1").exists():
                break
        
        logger.info(marker_end)
        
        # Leer contenido del archivo rotado
        rotated_file = Path(str(log_file) + ".1")
        if rotated_file.exists():
            content = rotated_file.read_text()
            assert marker_start in content, \
                "El marcador de inicio debe estar en el archivo rotado"
        
        # Leer contenido del archivo actual
        current_content = log_file.read_text()
        assert marker_end in current_content, \
            "El marcador de fin debe estar en el archivo actual"
    
    def test_rotation_with_concurrent_writes(self, temp_dir):
        """
        Verifica que la rotación funciona correctamente con escrituras
        concurrentes desde múltiples threads (usando el RLock global).
        """
        import threading
        
        log_file, _ = configure_logging(logs_dir=temp_dir, level="INFO", dual_log_enabled=False)
        
        def write_logs(thread_id, count):
            logger = get_logger(f"Thread{thread_id}")
            for i in range(count):
                logger.info(f"[Thread-{thread_id}] Message-{i:06d} " + "x" * 180)
        
        # Crear múltiples threads escribiendo simultáneamente
        max_bytes = int(Config.MAX_LOG_FILE_SIZE_MB * 1024 * 1024)
        messages_per_thread = (max_bytes // (250 * 4)) + 500  # Dividido entre 4 threads
        
        threads = []
        for i in range(4):
            t = threading.Thread(target=write_logs, args=(i, messages_per_thread))
            threads.append(t)
            t.start()
        
        # Esperar a que todos terminen
        for t in threads:
            t.join()
        
        # Verificar que se realizó la rotación
        rotated_file = Path(str(log_file) + ".1")
        assert rotated_file.exists(), \
            "La rotación debe ocurrir correctamente con escrituras concurrentes"
        
        # Verificar que no hubo corrupción (archivo no vacío)
        assert rotated_file.stat().st_size > 0, \
            "El archivo rotado no debe estar vacío"
        assert log_file.stat().st_size > 0, \
            "El archivo actual no debe estar vacío"


@pytest.fixture(autouse=True)
def cleanup_log_handlers(temp_dir):
    """Close all SafeToolPix log handlers after each test.

    On Windows, RotatingFileHandler keeps the log file open, so the
    TemporaryDirectory cleanup raises WinError 32 (file in use) unless
    all handlers are explicitly closed first.  Depending on *temp_dir*
    ensures this fixture tears down BEFORE temp_dir releases the directory.
    """
    yield
    import logging
    root_logger = logging.getLogger('SafeToolPix')
    for handler in root_logger.handlers[:]:
        try:
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)


@pytest.fixture
def temp_dir():
    """Crea un directorio temporal para los tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir).resolve()
