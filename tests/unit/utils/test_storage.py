# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para utils/storage.py
"""
import pytest
from pathlib import Path
from utils.storage import JsonStorageBackend, QSettingsBackend, StorageBackend


@pytest.mark.unit
class TestJsonStorageBackend:
    """Tests para JsonStorageBackend"""
    
    def test_init_creates_file(self, tmp_path):
        """Test que inicialización crea archivo"""
        file_path = tmp_path / "test_settings.json"
        backend = JsonStorageBackend(file_path)
        
        assert backend.file_path == file_path
    
    def test_get_set_simple_value(self, tmp_path):
        """Test get/set de valor simple"""
        file_path = tmp_path / "test_settings.json"
        backend = JsonStorageBackend(file_path)
        
        backend.set("test_key", "test_value")
        assert backend.get("test_key") == "test_value"
    
    def test_get_default_value(self, tmp_path):
        """Test que get retorna default para clave inexistente"""
        file_path = tmp_path / "test_settings.json"
        backend = JsonStorageBackend(file_path)
        
        assert backend.get("nonexistent", "default") == "default"
    
    def test_nested_keys(self, tmp_path):
        """Test claves anidadas con notación de punto"""
        file_path = tmp_path / "test_settings.json"
        backend = JsonStorageBackend(file_path)
        
        backend.set("parent/child/key", "value")
        assert backend.get("parent/child/key") == "value"
    
    def test_remove_key(self, tmp_path):
        """Test eliminación de clave"""
        file_path = tmp_path / "test_settings.json"
        backend = JsonStorageBackend(file_path)
        
        backend.set("test_key", "value")
        assert backend.contains("test_key")
        
        backend.remove("test_key")
        assert not backend.contains("test_key")
    
    def test_clear_all(self, tmp_path):
        """Test limpieza de todos los datos"""
        file_path = tmp_path / "test_settings.json"
        backend = JsonStorageBackend(file_path)
        
        backend.set("key1", "value1")
        backend.set("key2", "value2")
        
        backend.clear()
        
        assert not backend.contains("key1")
        assert not backend.contains("key2")
    
    def test_contains(self, tmp_path):
        """Test verificación de existencia de clave"""
        file_path = tmp_path / "test_settings.json"
        backend = JsonStorageBackend(file_path)
        
        backend.set("existing_key", "value")
        
        assert backend.contains("existing_key")
        assert not backend.contains("nonexistent_key")
    
    def test_sync_persists_data(self, tmp_path):
        """Test que sync persiste datos a disco"""
        file_path = tmp_path / "test_settings.json"
        
        backend = JsonStorageBackend(file_path)
        backend.set("key", "value")
        backend.sync()
        
        # Crear nuevo backend para verificar persistencia
        backend2 = JsonStorageBackend(file_path)
        assert backend2.get("key") == "value"
    
    def test_persistence_across_instances(self, tmp_path):
        """Test que datos persisten entre instancias"""
        file_path = tmp_path / "test_settings.json"
        
        # Primera instancia
        backend1 = JsonStorageBackend(file_path)
        backend1.set("persistent_key", "persistent_value")
        
        # Segunda instancia debe cargar los datos
        backend2 = JsonStorageBackend(file_path)
        assert backend2.get("persistent_key") == "persistent_value"


@pytest.mark.unit
class TestQSettingsBackend:
    """Tests para QSettingsBackend"""
    
    def test_init_creates_qsettings(self):
        """Test que inicialización crea QSettings"""
        try:
            backend = QSettingsBackend("TestOrg", "TestApp")
            assert backend.qsettings is not None
        except ImportError:
            pytest.skip("PyQt6 no disponible")
    
    def test_get_set_value(self):
        """Test get/set de valores"""
        try:
            backend = QSettingsBackend("TestOrg", "TestApp")
            
            backend.set("test_key", "test_value")
            assert backend.get("test_key") == "test_value"
            
            # Cleanup
            backend.clear()
        except ImportError:
            pytest.skip("PyQt6 no disponible")
    
    def test_contains(self):
        """Test verificación de existencia de clave"""
        try:
            backend = QSettingsBackend("TestOrg", "TestApp")
            
            backend.set("existing_key", "value")
            
            assert backend.contains("existing_key")
            assert not backend.contains("nonexistent_key")
            
            # Cleanup
            backend.clear()
        except ImportError:
            pytest.skip("PyQt6 no disponible")
    
    def test_remove_key(self):
        """Test eliminación de clave"""
        try:
            backend = QSettingsBackend("TestOrg", "TestApp")
            
            backend.set("test_key", "value")
            assert backend.contains("test_key")
            
            backend.remove("test_key")
            assert not backend.contains("test_key")
            
            # Cleanup
            backend.clear()
        except ImportError:
            pytest.skip("PyQt6 no disponible")
