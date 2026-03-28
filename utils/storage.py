# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Abstracción de almacenamiento persistente.
Permite usar diferentes backends (JSON, QSettings, etc.) sin acoplar el código a PyQt6.
"""
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from utils.logger import get_logger


class StorageBackend(ABC):
    """Interfaz abstracta para backends de almacenamiento persistente.
    
    Permite implementar diferentes estrategias de persistencia (JSON, QSettings,
    base de datos, etc.) manteniendo la misma API.
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor del almacenamiento.
        
        Args:
            key: Clave del valor a obtener
            default: Valor por defecto si la clave no existe
            
        Returns:
            Valor almacenado o default
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Guarda un valor en el almacenamiento.
        
        Args:
            key: Clave bajo la cual guardar
            value: Valor a guardar
        """
        pass

    @abstractmethod
    def remove(self, key: str) -> None:
        """Elimina una clave del almacenamiento.
        
        Args:
            key: Clave a eliminar
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Elimina todos los datos del almacenamiento."""
        pass

    @abstractmethod
    def contains(self, key: str) -> bool:
        """Verifica si existe una clave.
        
        Args:
            key: Clave a verificar
            
        Returns:
            True si la clave existe
        """
        pass

    @abstractmethod
    def sync(self) -> None:
        """Fuerza la escritura de cambios pendientes al almacenamiento persistente."""
        pass


class JsonStorageBackend(StorageBackend):
    """Backend de almacenamiento usando archivos JSON.
    
    Perfecto para uso sin PyQt6 (CLI, tests, scripts).
    Almacena la configuración en un archivo JSON en el directorio especificado.
    """

    def __init__(self, file_path: Optional[Path] = None):
        """Inicializa el backend JSON.
        
        Args:
            file_path: Ruta al archivo JSON. Si es None, usa ~/.safetool_pix/settings.json
        """
        self.logger = get_logger('JsonStorageBackend')
        
        if file_path is None:
            config_dir = Path.home() / ".safetool_pix"
            config_dir.mkdir(parents=True, exist_ok=True)
            file_path = config_dir / "settings.json"
        
        self.file_path = Path(file_path)
        self._data = {}
        self._load()
        
        self.logger.debug(f"JsonStorageBackend initialized. File: {self.file_path}")

    def _load(self) -> None:
        """Carga datos desde el archivo JSON."""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                self.logger.debug(f"Data loaded from {self.file_path}")
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Error loading {self.file_path}: {e}")
                self._data = {}
        else:
            self.logger.debug(f"File {self.file_path} does not exist, starting empty")
            self._data = {}

    def _save(self) -> None:
        """Guarda datos al archivo JSON."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Data saved to {self.file_path}")
        except IOError as e:
            self.logger.error(f"Error saving {self.file_path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor usando notación de punto para claves anidadas.
        
        Ejemplo: get("directories/logs") accede a {"directories": {"logs": "..."}}
        """
        keys = key.split('/')
        value = self._data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value

    def set(self, key: str, value: Any) -> None:
        """Guarda un valor usando notación de punto para claves anidadas."""
        keys = key.split('/')
        data = self._data
        
        # Navegar/crear estructura anidada
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        
        # Establecer el valor final
        data[keys[-1]] = value
        self._save()

    def remove(self, key: str) -> None:
        """Elimina una clave usando notación de punto."""
        keys = key.split('/')
        data = self._data
        
        # Navegar hasta el penúltimo nivel
        for k in keys[:-1]:
            if isinstance(data, dict) and k in data:
                data = data[k]
            else:
                return  # La clave no existe
        
        # Eliminar la clave final
        if isinstance(data, dict) and keys[-1] in data:
            del data[keys[-1]]
            self._save()

    def clear(self) -> None:
        """Elimina todos los datos."""
        self._data = {}
        self._save()

    def contains(self, key: str) -> bool:
        """Verifica si existe una clave usando notación de punto."""
        keys = key.split('/')
        value = self._data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return False
        
        return True

    def sync(self) -> None:
        """Fuerza el guardado al archivo."""
        self._save()


class QSettingsBackend(StorageBackend):
    """Backend de almacenamiento usando QSettings de PyQt6.
    
    Mantiene compatibilidad con el comportamiento original de SettingsManager.
    Usa el almacenamiento nativo de Qt (registry en Windows, plist en macOS, etc.)
    """

    def __init__(self, organization: str = "SafeToolPix", application: str = "SafeTool Pix"):
        """Inicializa el backend QSettings.
        
        Args:
            organization: Nombre de la organización
            application: Nombre de la aplicación
        """
        # Import aquí para no requerir PyQt6 si no se usa este backend
        from PyQt6.QtCore import QSettings
        
        self.qsettings = QSettings(organization, application)
        self.logger = get_logger('QSettingsBackend')
        self.logger.debug(f"QSettingsBackend initialized. File: {self.qsettings.fileName()}")

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor de QSettings."""
        return self.qsettings.value(key, default)

    def set(self, key: str, value: Any) -> None:
        """Guarda un valor en QSettings."""
        self.qsettings.setValue(key, value)
        self.qsettings.sync()

    def remove(self, key: str) -> None:
        """Elimina una clave de QSettings."""
        self.qsettings.remove(key)
        self.qsettings.sync()

    def clear(self) -> None:
        """Elimina todos los datos de QSettings."""
        self.qsettings.clear()
        self.qsettings.sync()

    def contains(self, key: str) -> bool:
        """Verifica si existe una clave en QSettings."""
        return self.qsettings.contains(key)

    def sync(self) -> None:
        """Fuerza la escritura de QSettings."""
        self.qsettings.sync()
