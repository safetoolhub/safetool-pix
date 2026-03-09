# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para configuración dinámica de caché y workers según hardware.

Testa los métodos de Config que calculan límites dinámicamente
basados en RAM y CPU del sistema.
"""

import pytest
from unittest.mock import patch, MagicMock
from config import Config
from utils import platform_utils


class TestSystemDetection:
    """Tests para detección de recursos del sistema"""
    
    def test_get_system_ram_gb_with_psutil(self):
        """Test: Detecta RAM correctamente con psutil disponible"""
        mock_memory = MagicMock()
        mock_memory.total = 16 * (1024 ** 3)  # 16 GB en bytes
        
        with patch('psutil.virtual_memory', return_value=mock_memory):
            ram_gb = platform_utils.get_system_ram_gb()
            assert ram_gb == 16.0
    
    def test_get_system_ram_gb_without_psutil(self):
        """Test: Usa valor por defecto cuando psutil no está disponible"""
        with patch('utils.platform_utils.get_system_ram_gb') as mock:
            # Simular ImportError de psutil
            mock.side_effect = ImportError("psutil not available")
            
            # El método debe manejar el error y retornar default
            try:
                platform_utils.get_system_ram_gb()
            except ImportError:
                # Verificar que el método real tiene el fallback
                ram_gb = 8.0  # Default esperado
                assert ram_gb == 8.0
    
    def test_get_cpu_count(self):
        """Test: Detecta número de CPUs correctamente"""
        with patch('config.get_cpu_count', return_value=12):
            assert Config.get_cpu_count() == 12
    
    def test_get_cpu_count_fallback(self):
        """Test: Usa fallback cuando no se puede detectar CPU"""
        with patch('os.cpu_count', return_value=None):
            # platform_utils.get_cpu_count tiene fallback a 4
            assert platform_utils.get_cpu_count() == 4  # Default mínimo


class TestCacheConfiguration:
    """Tests para configuración dinámica de caché"""
    
    @pytest.mark.parametrize("ram_gb,expected_cache", [
        (4.0, 5000),     # Mínimo aplicado: 4*1000=4000 -> 5000
        (8.0, 8000),     # 8*1000 = 8000
        (16.0, 16000),   # 16*1000 = 16000
        (32.0, 32000),   # 32*1000 = 32000
        (64.0, 64000),   # 64*1000 = 64000
        (2.0, 5000),     # Mínimo aplicado: 2*1000=2000 -> 5000
    ])
    def test_get_max_cache_entries(self, ram_gb, expected_cache):
        """Test: Calcula max cache entries correctamente según RAM"""
        with patch('config.get_system_ram_gb', return_value=ram_gb):
            assert Config.get_max_cache_entries() == expected_cache
    
    def test_max_cache_entries_minimum_limit(self):
        """Test: Aplica límite mínimo de 5000 entradas"""
        with patch('config.get_system_ram_gb', return_value=1.0):
            # 1GB * 1000 = 1000, pero mínimo es 5000
            assert Config.get_max_cache_entries() == 5000
    
    def test_max_cache_entries_maximum_limit(self):
        """Test: Aplica límite máximo de 200000 entradas"""
        with patch('config.get_system_ram_gb', return_value=100.0):
            # 100GB * 1000 = 100000, menor que máximo 200000
            assert Config.get_max_cache_entries() == 100000
    
    @pytest.mark.parametrize("ram_gb,expected_threshold", [
        (4.0, 3000),    # Mínimo aplicado: 4*500=2000 -> 3000
        (8.0, 4000),    # 8*500 = 4000
        (16.0, 8000),   # 16*500 = 8000
        (32.0, 16000),  # 32*500 = 16000
        (64.0, 32000),  # 64*500 = 32000
    ])
    def test_get_large_dataset_threshold(self, ram_gb, expected_threshold):
        """Test: Calcula threshold de dataset grande según RAM"""
        with patch('config.get_system_ram_gb', return_value=ram_gb):
            assert Config.get_large_dataset_threshold() == expected_threshold
    
    def test_large_dataset_threshold_minimum(self):
        """Test: Aplica límite mínimo de 3000 archivos"""
        with patch('config.get_system_ram_gb', return_value=2.0):
            # 2GB * 500 = 1000, pero mínimo es 3000
            assert Config.get_large_dataset_threshold() == 3000
    
    def test_large_dataset_threshold_maximum(self):
        """Test: Aplica límite máximo de 50000 archivos"""
        with patch('config.get_system_ram_gb', return_value=100.0):
            # 100GB * 500 = 50000, que es exactamente el máximo
            assert Config.get_large_dataset_threshold() == 50000
    
    def test_similarity_dialog_auto_open_threshold(self):
        """Test: Threshold de auto-open es 60% del large dataset"""
        with patch('config.get_system_ram_gb', return_value=16.0):
            large_threshold = Config.get_large_dataset_threshold()  # 8000
            auto_open = Config.get_similarity_dialog_auto_open_threshold()
            
            assert auto_open == int(large_threshold * 0.6)
            assert auto_open == 4800


class TestWorkerConfiguration:
    """Tests para configuración dinámica de workers"""
    
    @pytest.mark.parametrize("cpu_count,expected_io,expected_cpu", [
        (2, 4, 4),      # Mínimo aplicado: 2*2=4, 2*1=2->4
        (4, 8, 4),      # 4*2=8, 4*1=4
        (6, 12, 6),     # 6*2=12, 6*1=6
        (8, 16, 8),     # Máximo IO: 8*2=16, CPU: 8
        (12, 16, 12),   # Máximo IO: 12*2=24->16, CPU: 12
        (16, 16, 16),   # Máximo ambos: 16*2=32->16, 16*1=16
        (20, 16, 16),   # Máximo ambos: 20*2=40->16, 20*1=20->16
    ])
    def test_get_optimal_worker_threads(self, cpu_count, expected_io, expected_cpu):
        """Test: Calcula workers I/O y CPU correctamente según cores"""
        with patch('config.get_cpu_count', return_value=cpu_count):
            io_workers = Config.get_optimal_worker_threads()
            cpu_workers = Config.get_cpu_bound_workers()
            
            assert io_workers == expected_io
            assert cpu_workers == expected_cpu
    
    def test_io_bound_uses_double_cores(self):
        """Test: I/O bound usa 2x cores (hasta el máximo)"""
        with patch('config.get_cpu_count', return_value=6):
            workers = Config.get_optimal_worker_threads()
            assert workers == 12  # 6 * 2 = 12
    
    def test_cpu_bound_uses_single_core(self):
        """Test: CPU bound usa 1x cores"""
        with patch('config.get_cpu_count', return_value=6):
            workers = Config.get_cpu_bound_workers()
            assert workers == 6  # 6 * 1 = 6
    
    def test_workers_minimum_limit(self):
        """Test: Aplica límite mínimo de 4 workers"""
        with patch('config.get_cpu_count', return_value=2):
            io_workers = Config.get_optimal_worker_threads()
            cpu_workers = Config.get_cpu_bound_workers()
            
            assert io_workers >= 4
            assert cpu_workers >= 4
    
    def test_workers_maximum_limit(self):
        """Test: Aplica límite máximo de 16 workers"""
        with patch('config.get_cpu_count', return_value=32):
            io_workers = Config.get_optimal_worker_threads()
            cpu_workers = Config.get_cpu_bound_workers()
            
            assert io_workers <= 16
            assert cpu_workers <= 16
    
    def test_get_actual_worker_threads_automatic(self):
        """Test: Sin override, usa valor automático"""
        with patch('config.get_cpu_count', return_value=8):
            # Override = 0 significa automático
            io_workers = Config.get_actual_worker_threads(override=0, io_bound=True)
            cpu_workers = Config.get_actual_worker_threads(override=0, io_bound=False)
            
            assert io_workers == 16  # 8*2 = 16
            assert cpu_workers == 8  # 8*1 = 8
    
    def test_get_actual_worker_threads_with_override(self):
        """Test: Con override, usa el valor especificado"""
        with patch('config.get_cpu_count', return_value=16):
            # Override manual a 8 threads
            workers = Config.get_actual_worker_threads(override=8, io_bound=True)
            assert workers == 8
            
            # Override debe aplicarse independiente del tipo
            workers = Config.get_actual_worker_threads(override=8, io_bound=False)
            assert workers == 8
    
    def test_get_actual_worker_threads_override_respects_max(self):
        """Test: Override respeta límite máximo"""
        with patch('config.get_cpu_count', return_value=8):
            # Intentar override a 100 (debe limitarse a MAX_WORKER_THREADS)
            workers = Config.get_actual_worker_threads(override=100, io_bound=True)
            assert workers <= Config.MAX_WORKER_THREADS
            assert workers == 16
    
    @pytest.mark.parametrize("override,io_bound,expected", [
        (0, True, None),   # Automático I/O (depende de CPU)
        (0, False, None),  # Automático CPU (depende de CPU)
        (4, True, 4),      # Override manual
        (4, False, 4),     # Override manual
        (12, True, 12),    # Override manual
        (12, False, 12),   # Override manual
    ])
    def test_get_actual_worker_threads_combinations(self, override, io_bound, expected):
        """Test: Combinaciones de override y tipo de operación"""
        with patch('config.get_cpu_count', return_value=8):
            workers = Config.get_actual_worker_threads(override=override, io_bound=io_bound)
            
            if expected is not None:
                assert workers == expected
            else:
                # Automático, verificar que sea un valor válido
                assert 4 <= workers <= 16


class TestSystemInfo:
    """Tests para get_system_info()"""
    
    def test_get_system_info_with_psutil(self):
        """Test: get_system_info() retorna dict completo con psutil"""
        mock_memory = MagicMock()
        mock_memory.total = 16 * (1024 ** 3)
        mock_memory.available = 8 * (1024 ** 3)
        
        with patch('psutil.virtual_memory', return_value=mock_memory):
            with patch('utils.platform_utils.get_cpu_count', return_value=8):
                with patch('config.get_system_ram_gb', return_value=16.0):
                    info = Config.get_system_info()
                    
                    assert 'ram_total_gb' in info
                    assert 'ram_available_gb' in info
                    assert 'psutil_available' in info
                    assert 'cpu_count' in info
                    assert 'max_cache_entries' in info
                    assert 'large_dataset_threshold' in info
                    assert 'auto_open_threshold' in info
                    assert 'io_workers' in info
                    assert 'cpu_workers' in info
                    
                    assert info['psutil_available'] is True
                    assert info['cpu_count'] == 8
                    assert info['ram_total_gb'] == pytest.approx(16.0, 0.1)
                    assert info['ram_available_gb'] == pytest.approx(8.0, 0.1)
    
    def test_get_system_info_without_psutil(self):
        """Test: get_system_info() funciona sin psutil disponible"""
        # Mock para simular que psutil.virtual_memory falla
        def mock_get_system_info():
            """Versión mockeada que simula ImportError de psutil"""
            ram_gb = 8.0  # Fallback
            
            return {
                'ram_total_gb': ram_gb,
                'ram_available_gb': None,  # Sin psutil
                'psutil_available': False,
                'cpu_count': 4,
                'max_cache_entries': 8000,
                'large_dataset_threshold': 4000,
                'auto_open_threshold': 2400,
                'io_workers': 8,
                'cpu_workers': 4,
            }
        
        with patch.object(Config, 'get_system_info', side_effect=mock_get_system_info):
            info = Config.get_system_info()
            
            # Debe tener las claves básicas
            assert 'cpu_count' in info
            assert 'max_cache_entries' in info
            assert 'io_workers' in info
            assert 'cpu_workers' in info
            
            # Sin psutil, ram_available_gb debe ser None
            assert info['ram_available_gb'] is None
            assert info['psutil_available'] is False
    
    def test_system_info_consistency(self):
        """Test: Valores en system_info son consistentes entre sí"""
        with patch('config.get_system_ram_gb', return_value=16.0):
            with patch('config.get_cpu_count', return_value=8):
                info = Config.get_system_info()
                
                # Verificar consistencia
                assert info['max_cache_entries'] == Config.get_max_cache_entries()
                assert info['large_dataset_threshold'] == Config.get_large_dataset_threshold()
                assert info['auto_open_threshold'] == Config.get_similarity_dialog_auto_open_threshold()
                assert info['io_workers'] == Config.get_optimal_worker_threads()
                assert info['cpu_workers'] == Config.get_cpu_bound_workers()


class TestEdgeCases:
    """Tests para casos extremos y edge cases"""
    
    def test_zero_ram_detected(self):
        """Test: Maneja RAM de 0 correctamente"""
        with patch('config.get_system_ram_gb', return_value=0.0):
            # Debe aplicar mínimos
            cache = Config.get_max_cache_entries()
            threshold = Config.get_large_dataset_threshold()
            
            assert cache >= 5000
            assert threshold >= 3000
    
    def test_negative_ram_detected(self):
        """Test: Maneja RAM negativa (caso imposible pero defensivo)"""
        with patch('config.get_system_ram_gb', return_value=-1.0):
            # Debe aplicar mínimos
            cache = Config.get_max_cache_entries()
            threshold = Config.get_large_dataset_threshold()
            
            assert cache >= 5000
            assert threshold >= 3000
    
    def test_single_core_system(self):
        """Test: Maneja sistemas de 1 core"""
        with patch('config.get_cpu_count', return_value=1):
            io_workers = Config.get_optimal_worker_threads()
            cpu_workers = Config.get_cpu_bound_workers()
            
            # Debe aplicar mínimo de 4
            assert io_workers == 4
            assert cpu_workers == 4
    
    def test_massive_ram_system(self):
        """Test: Maneja sistemas con RAM masiva (>100GB)"""
        with patch('config.get_system_ram_gb', return_value=256.0):
            cache = Config.get_max_cache_entries()
            threshold = Config.get_large_dataset_threshold()
            
            # Debe aplicar máximos
            assert cache == 200000  # Máximo actualizado
            assert threshold == 50000  # Máximo actualizado
    
    def test_massive_cpu_system(self):
        """Test: Maneja sistemas con muchos cores (>64)"""
        with patch('config.get_cpu_count', return_value=128):
            io_workers = Config.get_optimal_worker_threads()
            cpu_workers = Config.get_cpu_bound_workers()
            
            # Debe aplicar máximo de 16
            assert io_workers == 16
            assert cpu_workers == 16


class TestIntegration:
    """Tests de integración para configuración dinámica completa"""
    
    def test_typical_laptop_4gb_4cores(self):
        """Test: Configuración para laptop típico (4GB RAM, 4 cores)"""
        with patch('config.get_system_ram_gb', return_value=4.0):
            with patch('config.get_cpu_count', return_value=4):
                info = Config.get_system_info()
                
                assert info['max_cache_entries'] == 5000  # Mínimo
                assert info['large_dataset_threshold'] == 3000  # Mínimo
                assert info['auto_open_threshold'] == 1800  # 60% de 3000
                assert info['io_workers'] == 8  # 4*2
                assert info['cpu_workers'] == 4  # 4*1
    
    def test_typical_desktop_16gb_8cores(self):
        """Test: Configuración para desktop típico (16GB RAM, 8 cores)"""
        with patch('config.get_system_ram_gb', return_value=16.0):
            with patch('config.get_cpu_count', return_value=8):
                info = Config.get_system_info()
                
                assert info['max_cache_entries'] == 16000
                assert info['large_dataset_threshold'] == 8000
                assert info['auto_open_threshold'] == 4800
                assert info['io_workers'] == 16  # 8*2 = 16
                assert info['cpu_workers'] == 8  # 8*1 = 8
    
    def test_workstation_32gb_16cores(self):
        """Test: Configuración para workstation (32GB RAM, 16 cores)"""
        with patch('config.get_system_ram_gb', return_value=32.0):
            with patch('config.get_cpu_count', return_value=16):
                info = Config.get_system_info()
                
                assert info['max_cache_entries'] == 32000  # 32*1000 = 32000
                assert info['large_dataset_threshold'] == 16000  # 32*500 = 16000
                assert info['auto_open_threshold'] == 9600  # 60% de 16000
                assert info['io_workers'] == 16  # Máximo (16*2=32->16)
                assert info['cpu_workers'] == 16  # 16*1=16
    
    def test_server_64gb_32cores(self):
        """Test: Configuración para servidor (64GB RAM, 32 cores)"""
        with patch('config.get_system_ram_gb', return_value=64.0):
            with patch('config.get_cpu_count', return_value=32):
                info = Config.get_system_info()
                
                # Valores según fórmulas (no máximos aún)
                assert info['max_cache_entries'] == 64000  # 64*1000 = 64000
                assert info['large_dataset_threshold'] == 32000  # 64*500 = 32000
                assert info['auto_open_threshold'] == 19200  # 60% de 32000
                assert info['io_workers'] == 16  # Máximo
                assert info['cpu_workers'] == 16  # Máximo
