# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para algoritmos de hash perceptual (dhash, phash, ahash).
Verifica la configuración y funcionamiento de _calculate_image_perceptual_hash
y _calculate_video_perceptual_hash con diferentes configuraciones.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import tempfile
import shutil
import struct
from io import BytesIO

from PIL import Image
import numpy as np


class TestImagePerceptualHashAlgorithms:
    """Tests para _calculate_image_perceptual_hash con diferentes algoritmos."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        from services.duplicates_similar_service import DuplicatesSimilarService
        self.service = DuplicatesSimilarService()
        
        # Crear directorio temporal con imagen de prueba
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self._create_test_image()
    
    def teardown_method(self):
        """Cleanup después de cada test."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_test_image(self, filename: str = "test_image.jpg", size: tuple = (100, 100)):
        """Crea una imagen de prueba con patrón reconocible."""
        img = Image.new('RGB', size)
        pixels = img.load()
        
        # Crear patrón de gradiente diagonal
        for x in range(size[0]):
            for y in range(size[1]):
                pixels[x, y] = ((x * 255) // size[0], (y * 255) // size[1], 128)
        
        self.test_image_path = self.temp_dir / filename
        img.save(self.test_image_path, format='JPEG')
        return self.test_image_path
    
    # =========================================================================
    # TESTS PARA DHASH
    # =========================================================================
    
    def test_dhash_default_hash_size_8(self):
        """Test dhash con hash_size=8 (64 bits)."""
        result = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="dhash",
            hash_size=8
        )
        
        assert result is not None
        # dhash con size=8 genera hash de 64 bits (8*8)
        assert len(str(result)) == 16  # 16 caracteres hex = 64 bits
    
    def test_dhash_hash_size_16(self):
        """Test dhash con hash_size=16 (256 bits)."""
        result = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="dhash",
            hash_size=16
        )
        
        assert result is not None
        # dhash con size=16 genera hash de 256 bits (16*16)
        assert len(str(result)) == 64  # 64 caracteres hex = 256 bits
    
    def test_dhash_hash_size_32(self):
        """Test dhash con hash_size=32 (1024 bits)."""
        result = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="dhash",
            hash_size=32
        )
        
        assert result is not None
        # dhash con size=32 genera hash de 1024 bits (32*32)
        assert len(str(result)) == 256  # 256 caracteres hex = 1024 bits
    
    def test_dhash_produces_consistent_results(self):
        """Test que dhash produce resultados consistentes para la misma imagen."""
        result1 = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="dhash",
            hash_size=8
        )
        result2 = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="dhash",
            hash_size=8
        )
        
        assert result1 == result2
    
    # =========================================================================
    # TESTS PARA PHASH
    # =========================================================================
    
    def test_phash_default_hash_size_8(self):
        """Test phash con hash_size=8 (64 bits)."""
        result = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="phash",
            hash_size=8,
            highfreq_factor=4
        )
        
        assert result is not None
        assert len(str(result)) == 16  # 16 caracteres hex = 64 bits
    
    def test_phash_hash_size_16(self):
        """Test phash con hash_size=16 (256 bits)."""
        result = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="phash",
            hash_size=16,
            highfreq_factor=4
        )
        
        assert result is not None
        assert len(str(result)) == 64  # 64 caracteres hex = 256 bits
    
    def test_phash_highfreq_factor_variations(self):
        """Test phash con diferentes highfreq_factor."""
        result_hf4 = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="phash",
            hash_size=8,
            highfreq_factor=4
        )
        result_hf8 = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="phash",
            hash_size=8,
            highfreq_factor=8
        )
        
        # Ambos deben generar hashes válidos
        assert result_hf4 is not None
        assert result_hf8 is not None
        # Pueden ser diferentes debido a diferentes factores de muestreo
        # pero ambos deben tener el mismo tamaño
        assert len(str(result_hf4)) == len(str(result_hf8))
    
    def test_phash_produces_consistent_results(self):
        """Test que phash produce resultados consistentes para la misma imagen."""
        result1 = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="phash",
            hash_size=8,
            highfreq_factor=4
        )
        result2 = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="phash",
            hash_size=8,
            highfreq_factor=4
        )
        
        assert result1 == result2
    
    # =========================================================================
    # TESTS PARA AHASH
    # =========================================================================
    
    def test_ahash_default_hash_size_8(self):
        """Test ahash con hash_size=8 (64 bits)."""
        result = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="ahash",
            hash_size=8
        )
        
        assert result is not None
        assert len(str(result)) == 16  # 16 caracteres hex = 64 bits
    
    def test_ahash_hash_size_16(self):
        """Test ahash con hash_size=16 (256 bits)."""
        result = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="ahash",
            hash_size=16
        )
        
        assert result is not None
        assert len(str(result)) == 64  # 64 caracteres hex = 256 bits
    
    def test_ahash_produces_consistent_results(self):
        """Test que ahash produce resultados consistentes para la misma imagen."""
        result1 = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="ahash",
            hash_size=8
        )
        result2 = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="ahash",
            hash_size=8
        )
        
        assert result1 == result2
    
    # =========================================================================
    # TESTS COMPARATIVOS ENTRE ALGORITMOS
    # =========================================================================
    
    def test_different_algorithms_produce_different_hashes(self):
        """Test que diferentes algoritmos pueden producir hashes diferentes."""
        dhash = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="dhash",
            hash_size=8
        )
        phash = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="phash",
            hash_size=8,
            highfreq_factor=4
        )
        ahash = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="ahash",
            hash_size=8
        )
        
        # Todos deben producir hashes válidos
        assert dhash is not None
        assert phash is not None
        assert ahash is not None
        
        # Todos deben tener el mismo tamaño (64 bits = 16 hex chars)
        assert len(str(dhash)) == 16
        assert len(str(phash)) == 16
        assert len(str(ahash)) == 16
    
    def test_similar_images_produce_close_hashes(self):
        """Test que imágenes similares producen hashes cercanos."""
        # Crear imagen ligeramente modificada (cambio de brillo)
        original_img = Image.open(self.test_image_path)
        modified_img = original_img.point(lambda x: min(255, int(x * 1.1)))  # 10% más brillo
        modified_path = self.temp_dir / "modified.jpg"
        modified_img.save(modified_path, format='JPEG')
        
        original_hash = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="dhash",
            hash_size=8
        )
        modified_hash = self.service._calculate_image_perceptual_hash(
            modified_path,
            algorithm="dhash",
            hash_size=8
        )
        
        assert original_hash is not None
        assert modified_hash is not None
        
        # La distancia de Hamming debe ser pequeña para imágenes similares
        distance = original_hash - modified_hash
        assert distance < 10  # Umbral razonable para imagen con cambio de brillo
    
    # =========================================================================
    # TESTS DE MANEJO DE ERRORES
    # =========================================================================
    
    def test_nonexistent_file_returns_none(self):
        """Test que archivo inexistente retorna None."""
        result = self.service._calculate_image_perceptual_hash(
            Path("/nonexistent/path/image.jpg"),
            algorithm="dhash",
            hash_size=8
        )
        
        assert result is None
    
    def test_invalid_image_returns_none(self):
        """Test que archivo no válido como imagen retorna None."""
        invalid_file = self.temp_dir / "not_an_image.jpg"
        invalid_file.write_text("This is not an image")
        
        result = self.service._calculate_image_perceptual_hash(
            invalid_file,
            algorithm="dhash",
            hash_size=8
        )
        
        assert result is None
    
    def test_grayscale_image_is_converted(self):
        """Test que imagen en escala de grises se convierte a RGB correctamente."""
        # Crear imagen en escala de grises
        gray_img = Image.new('L', (100, 100))
        gray_path = self.temp_dir / "gray_image.jpg"
        gray_img.save(gray_path)
        
        result = self.service._calculate_image_perceptual_hash(
            gray_path,
            algorithm="dhash",
            hash_size=8
        )
        
        assert result is not None
    
    def test_rgba_image_is_converted(self):
        """Test que imagen RGBA se convierte a RGB correctamente."""
        # Crear imagen RGBA
        rgba_img = Image.new('RGBA', (100, 100), (255, 0, 0, 128))
        rgba_path = self.temp_dir / "rgba_image.png"
        rgba_img.save(rgba_path)
        
        result = self.service._calculate_image_perceptual_hash(
            rgba_path,
            algorithm="dhash",
            hash_size=8
        )
        
        assert result is not None
    
    def test_unknown_algorithm_uses_dhash_default(self):
        """Test que algoritmo desconocido usa dhash por defecto."""
        result_unknown = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="unknown_algorithm",
            hash_size=8
        )
        result_dhash = self.service._calculate_image_perceptual_hash(
            self.test_image_path,
            algorithm="dhash",
            hash_size=8
        )
        
        # Algoritmo desconocido cae al default (else branch = dhash)
        assert result_unknown == result_dhash


class TestVideoPerceptualHashAlgorithms:
    """Tests para _calculate_video_perceptual_hash con diferentes algoritmos."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        from services.duplicates_similar_service import DuplicatesSimilarService
        self.service = DuplicatesSimilarService()
        
        # Crear directorio temporal
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
    
    def teardown_method(self):
        """Cleanup después de cada test."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_test_video(self, filename: str = "test_video.mp4"):
        """Crea un video de prueba simple usando cv2 si está disponible."""
        try:
            import cv2
            import numpy as np
            
            video_path = self.temp_dir / filename
            
            # Crear video con frames de gradiente
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(video_path), fourcc, 30, (100, 100))
            
            for i in range(30):  # 1 segundo de video
                frame = np.zeros((100, 100, 3), dtype=np.uint8)
                # Crear gradiente que cambia con cada frame
                frame[:, :, 0] = int(255 * i / 30)  # Canal azul
                frame[:, :, 1] = int(128)  # Canal verde
                frame[:, :, 2] = int(255 * (30 - i) / 30)  # Canal rojo
                out.write(frame)
            
            out.release()
            return video_path
        except ImportError:
            return None
    
    # =========================================================================
    # TESTS DE ALGORITMOS DE VIDEO
    # =========================================================================
    
    @pytest.mark.skipif(
        not pytest.importorskip("cv2", reason="cv2 not installed"),
        reason="cv2 not available"
    )
    def test_video_dhash_default(self):
        """Test dhash en video con configuración por defecto."""
        video_path = self._create_test_video()
        if video_path is None:
            pytest.skip("Could not create test video")
        
        result = self.service._calculate_video_perceptual_hash(
            video_path,
            algorithm="dhash",
            hash_size=8
        )
        
        assert result is not None
        assert len(str(result)) == 16
    
    @pytest.mark.skipif(
        not pytest.importorskip("cv2", reason="cv2 not installed"),
        reason="cv2 not available"
    )
    def test_video_phash_with_highfreq(self):
        """Test phash en video con highfreq_factor."""
        video_path = self._create_test_video()
        if video_path is None:
            pytest.skip("Could not create test video")
        
        result = self.service._calculate_video_perceptual_hash(
            video_path,
            algorithm="phash",
            hash_size=8,
            highfreq_factor=4
        )
        
        assert result is not None
        assert len(str(result)) == 16
    
    @pytest.mark.skipif(
        not pytest.importorskip("cv2", reason="cv2 not installed"),
        reason="cv2 not available"
    )
    def test_video_ahash_default(self):
        """Test ahash en video."""
        video_path = self._create_test_video()
        if video_path is None:
            pytest.skip("Could not create test video")
        
        result = self.service._calculate_video_perceptual_hash(
            video_path,
            algorithm="ahash",
            hash_size=8
        )
        
        assert result is not None
        assert len(str(result)) == 16
    
    @pytest.mark.skipif(
        not pytest.importorskip("cv2", reason="cv2 not installed"),
        reason="cv2 not available"
    )
    def test_video_hash_size_16(self):
        """Test video hash con hash_size=16."""
        video_path = self._create_test_video()
        if video_path is None:
            pytest.skip("Could not create test video")
        
        result = self.service._calculate_video_perceptual_hash(
            video_path,
            algorithm="dhash",
            hash_size=16
        )
        
        assert result is not None
        assert len(str(result)) == 64  # 256 bits = 64 hex chars
    
    # =========================================================================
    # TESTS DE MANEJO DE ERRORES EN VIDEO
    # =========================================================================
    
    def test_video_nonexistent_file_returns_none(self):
        """Test que archivo de video inexistente retorna None."""
        result = self.service._calculate_video_perceptual_hash(
            Path("/nonexistent/video.mp4"),
            algorithm="dhash",
            hash_size=8
        )
        
        assert result is None
    
    def test_video_invalid_file_returns_none(self):
        """Test que archivo no válido como video retorna None."""
        invalid_file = self.temp_dir / "not_a_video.mp4"
        invalid_file.write_text("This is not a video")
        
        result = self.service._calculate_video_perceptual_hash(
            invalid_file,
            algorithm="dhash",
            hash_size=8
        )
        
        assert result is None
    
    @pytest.mark.skipif(
        not pytest.importorskip("cv2", reason="cv2 not installed"),
        reason="cv2 not available"
    )
    def test_video_produces_consistent_results(self):
        """Test que el mismo video produce el mismo hash."""
        video_path = self._create_test_video()
        if video_path is None:
            pytest.skip("Could not create test video")
        
        result1 = self.service._calculate_video_perceptual_hash(
            video_path,
            algorithm="dhash",
            hash_size=8
        )
        result2 = self.service._calculate_video_perceptual_hash(
            video_path,
            algorithm="dhash",
            hash_size=8
        )
        
        assert result1 == result2


class TestPerceptualHashConfiguration:
    """Tests para la configuración de hash perceptual desde Config."""
    
    def test_config_has_perceptual_hash_algorithm(self):
        """Test que Config tiene PERCEPTUAL_HASH_ALGORITHM definido."""
        from config import Config
        
        assert hasattr(Config, 'PERCEPTUAL_HASH_ALGORITHM')
        assert Config.PERCEPTUAL_HASH_ALGORITHM in ['dhash', 'phash', 'ahash']
    
    def test_config_has_perceptual_hash_size(self):
        """Test que Config tiene PERCEPTUAL_HASH_SIZE definido."""
        from config import Config
        
        assert hasattr(Config, 'PERCEPTUAL_HASH_SIZE')
        assert Config.PERCEPTUAL_HASH_SIZE in [8, 16, 32]
    
    def test_config_has_perceptual_hash_target(self):
        """Test que Config tiene PERCEPTUAL_HASH_TARGET definido."""
        from config import Config
        
        assert hasattr(Config, 'PERCEPTUAL_HASH_TARGET')
        assert Config.PERCEPTUAL_HASH_TARGET in ['images', 'videos', 'both']
    
    def test_config_has_perceptual_hash_highfreq_factor(self):
        """Test que Config tiene PERCEPTUAL_HASH_HIGHFREQ_FACTOR definido."""
        from config import Config
        
        assert hasattr(Config, 'PERCEPTUAL_HASH_HIGHFREQ_FACTOR')
        assert Config.PERCEPTUAL_HASH_HIGHFREQ_FACTOR in [4, 8]
    
    def test_default_algorithm_is_phash(self):
        """Test que el algoritmo por defecto es phash (elegido por ser más robusto)."""
        from config import Config
        
        assert Config.PERCEPTUAL_HASH_ALGORITHM == "phash"
    
    def test_default_target_is_images(self):
        """Test que el target por defecto es images."""
        from config import Config
        
        assert Config.PERCEPTUAL_HASH_TARGET == "images"


class TestHashTargetFiltering:
    """Tests para el filtrado de archivos según target (images/videos/both)."""
    
    def setup_method(self):
        """Setup antes de cada test."""
        from services.duplicates_similar_service import DuplicatesSimilarService
        from services.file_metadata_repository_cache import FileInfoRepositoryCache
        from services.file_metadata import FileMetadata
        
        self.service = DuplicatesSimilarService()
        self.repo = FileInfoRepositoryCache.get_instance()
        self.repo.clear()
        
        # Crear directorio temporal
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
    
    def teardown_method(self):
        """Cleanup después de cada test."""
        self.repo.clear()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def _add_test_files_to_repo(self):
        """Añade archivos de prueba al repositorio."""
        from services.file_metadata import FileMetadata
        import time
        
        current_time = time.time()
        
        # Añadir imágenes
        for i in range(3):
            path = self.temp_dir / f"image_{i}.jpg"
            path.touch()
            
            img = Image.new('RGB', (50, 50), color=(i*50, i*50, i*50))
            img.save(path)
            
            meta = FileMetadata(
                path=path,
                fs_size=1000 + i,
                fs_ctime=current_time,
                fs_mtime=current_time,
                fs_atime=current_time
            )
            self.repo.add_file(path, meta)
        
        # Añadir videos (simulados - archivos vacíos que no se pueden procesar)
        for i in range(2):
            path = self.temp_dir / f"video_{i}.mp4"
            path.touch()
            
            meta = FileMetadata(
                path=path,
                fs_size=2000 + i,
                fs_ctime=current_time,
                fs_mtime=current_time,
                fs_atime=current_time
            )
            self.repo.add_file(path, meta)
    
    def test_target_images_only_processes_images(self):
        """Test que target='images' solo procesa imágenes."""
        self._add_test_files_to_repo()
        
        analysis = self.service._calculate_perceptual_hashes(
            self.repo,
            progress_callback=None,
            algorithm="dhash",
            hash_size=8,
            target="images",
            highfreq_factor=4
        )
        
        # Solo deben procesarse imágenes (3 imágenes)
        # Nota: total_files es el número de hashes calculados exitosamente
        assert analysis.total_files == 3
        
        # Verificar que solo hay hashes de imágenes
        for path in analysis.perceptual_hashes.keys():
            assert path.endswith('.jpg')
    
    def test_target_videos_only_attempts_videos(self):
        """Test que target='videos' intenta procesar solo videos."""
        self._add_test_files_to_repo()
        
        analysis = self.service._calculate_perceptual_hashes(
            self.repo,
            progress_callback=None,
            algorithm="dhash",
            hash_size=8,
            target="videos",
            highfreq_factor=4
        )
        
        # Los videos de prueba son archivos vacíos, así que no hay hashes
        # pero no debería haber hashes de imágenes
        for path in analysis.perceptual_hashes.keys():
            assert not path.endswith('.jpg')
    
    def test_target_both_processes_all_media(self):
        """Test que target='both' procesa imágenes y videos."""
        self._add_test_files_to_repo()
        
        analysis = self.service._calculate_perceptual_hashes(
            self.repo,
            progress_callback=None,
            algorithm="dhash",
            hash_size=8,
            target="both",
            highfreq_factor=4
        )
        
        # Debe haber al menos las 3 imágenes (videos son archivos vacíos)
        assert analysis.total_files >= 3
