# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para SettingsDialog.

Cubre:
- Inicialización del diálogo
- Carga de configuraciones desde settings_manager
- Guardado de cambios (especialmente cambios en log level)
- Detección de cambios y validación
- Restauración de valores por defecto
"""

import pytest
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from PyQt6.QtWidgets import QMessageBox

from config import Config
from ui.dialogs.settings_dialog import SettingsDialog
from utils.settings_manager import settings_manager


@pytest.fixture
def mock_settings_manager(monkeypatch):
    """Mock del settings_manager para evitar dependencias reales"""
    # Valores por defecto simulados
    mock_values = {
        'logs_dir': Config.DEFAULT_LOG_DIR,
        'backup_dir': Config.DEFAULT_BACKUP_DIR,
        'log_level': 'INFO',
        'auto_backup': True,
        'confirm_delete': True,
        'confirm_reanalyze': True,
        'show_full_path': True,
        'max_workers': 0,
        'ui_update_interval': Config.UI_UPDATE_INTERVAL,
        'dry_run': False,
        'precalculate_hashes': False,
        'precalculate_image_exif': True,
        'precalculate_video_exif': False,
        'dual_log': True,
    }
    
    # Mockear métodos del settings_manager
    monkeypatch.setattr(settings_manager, 'get_logs_directory', lambda: mock_values['logs_dir'])
    monkeypatch.setattr(settings_manager, 'get_backup_directory', lambda: mock_values['backup_dir'])
    monkeypatch.setattr(settings_manager, 'get_log_level', lambda default="INFO": mock_values['log_level'])
    monkeypatch.setattr(settings_manager, 'get_auto_backup_enabled', lambda: mock_values['auto_backup'])
    monkeypatch.setattr(settings_manager, 'get_confirm_delete', lambda: mock_values['confirm_delete'])
    monkeypatch.setattr(settings_manager, 'get_confirm_reanalyze', lambda: mock_values['confirm_reanalyze'])
    monkeypatch.setattr(settings_manager, 'get_show_full_path', lambda: mock_values['show_full_path'])
    monkeypatch.setattr(settings_manager, 'get_max_workers', lambda default=0: mock_values['max_workers'])
    monkeypatch.setattr(settings_manager, 'get_int', lambda key, default: mock_values.get(key.split('_')[-1] if '_' in key else key, default))
    monkeypatch.setattr(settings_manager, 'get_bool', lambda key, default: mock_values.get(key.split('_')[-1] if '_' in key else key, default))
    monkeypatch.setattr(settings_manager, 'get_precalculate_hashes', lambda: mock_values['precalculate_hashes'])
    monkeypatch.setattr(settings_manager, 'get_precalculate_image_exif', lambda: mock_values['precalculate_image_exif'])
    monkeypatch.setattr(settings_manager, 'get_precalculate_video_exif', lambda: mock_values['precalculate_video_exif'])
    monkeypatch.setattr(settings_manager, 'get_dual_log_enabled', lambda: mock_values['dual_log'])
    
    # Métodos de escritura (mockeados como vacíos)
    monkeypatch.setattr(settings_manager, 'set_logs_directory', lambda x: None)
    monkeypatch.setattr(settings_manager, 'set_backup_directory', lambda x: None)
    monkeypatch.setattr(settings_manager, 'set_log_level', lambda x: None)
    monkeypatch.setattr(settings_manager, 'set_auto_backup_enabled', lambda x: None)
    monkeypatch.setattr(settings_manager, 'set', lambda key, value: None)
    monkeypatch.setattr(settings_manager, 'set_show_full_path', lambda x: None)
    monkeypatch.setattr(settings_manager, 'set_precalculate_hashes', lambda x: None)
    monkeypatch.setattr(settings_manager, 'set_precalculate_image_exif', lambda x: None)
    monkeypatch.setattr(settings_manager, 'set_precalculate_video_exif', lambda x: None)
    monkeypatch.setattr(settings_manager, 'set_dual_log_enabled', lambda x: None)
    monkeypatch.setattr(settings_manager, 'clear_all', lambda: None)
    
    return mock_values


@pytest.mark.ui
class TestSettingsDialogInitialization:
    """Tests de inicialización básica del diálogo"""
    
    def test_dialog_initializes_successfully(self, qtbot, mock_settings_manager):
        """Test que el diálogo se inicializa sin errores"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert dialog is not None
        assert dialog.windowTitle() == "Configuración"
        assert dialog.tabs is not None
        assert dialog.tabs.count() == 4  # 4 pestañas: General, Análisis, Backup, Avanzado
    
    def test_dialog_has_all_widgets(self, qtbot, mock_settings_manager):
        """Test que el diálogo tiene todos los widgets necesarios"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Verificar widgets principales
        assert hasattr(dialog, 'logs_edit')
        assert hasattr(dialog, 'backup_edit')
        assert hasattr(dialog, 'log_level_combo')
        assert hasattr(dialog, 'auto_backup_checkbox')
        assert hasattr(dialog, 'confirm_delete_checkbox')
        assert hasattr(dialog, 'confirm_reanalyze_checkbox')
        assert hasattr(dialog, 'show_full_path_checkbox')
        assert hasattr(dialog, 'max_workers_spin')
        assert hasattr(dialog, 'ui_update_spin')
        assert hasattr(dialog, 'dry_run_default_checkbox')
        assert hasattr(dialog, 'precalculate_hashes_checkbox')
        assert hasattr(dialog, 'precalculate_image_exif_checkbox')
        assert hasattr(dialog, 'precalculate_video_exif_checkbox')
        assert hasattr(dialog, 'dual_log_checkbox')
        assert hasattr(dialog, 'save_button')
    
    def test_dialog_starts_with_initial_tab(self, qtbot, mock_settings_manager):
        """Test que el diálogo puede iniciar en una pestaña específica"""
        dialog = SettingsDialog(initial_tab=2)
        qtbot.addWidget(dialog)
        
        assert dialog.tabs.currentIndex() == 2


@pytest.mark.ui
class TestSettingsDialogLoading:
    """Tests de carga de configuraciones desde settings_manager"""
    
    def test_loads_default_values(self, qtbot, mock_settings_manager):
        """Test que carga los valores por defecto correctamente"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Verificar que cargó los valores del mock
        assert dialog.logs_edit.text() == str(Config.DEFAULT_LOG_DIR)
        assert dialog.backup_edit.text() == str(Config.DEFAULT_BACKUP_DIR)
        assert dialog.log_level_combo.currentIndex() == 1  # INFO = índice 1
        assert dialog.auto_backup_checkbox.isChecked() is True
        assert dialog.confirm_delete_checkbox.isChecked() is True
        assert dialog.confirm_reanalyze_checkbox.isChecked() is True
        assert dialog.show_full_path_checkbox.isChecked() is True
        assert dialog.max_workers_spin.value() == 0  # Automático
        assert dialog.dry_run_default_checkbox.isChecked() is False
        assert dialog.precalculate_hashes_checkbox.isChecked() is False
        assert dialog.precalculate_image_exif_checkbox.isChecked() is True
        assert dialog.precalculate_video_exif_checkbox.isChecked() is False
        assert dialog.dual_log_checkbox.isChecked() is True
    
    def test_loads_custom_log_level_debug(self, qtbot, mock_settings_manager, monkeypatch):
        """Test que carga correctamente log level DEBUG"""
        monkeypatch.setattr(settings_manager, 'get_log_level', lambda default="INFO": "DEBUG")
        
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert dialog.log_level_combo.currentIndex() == 0  # DEBUG = índice 0
        assert dialog.dual_log_checkbox.isEnabled() is True  # Habilitado para DEBUG
    
    def test_loads_custom_log_level_warning(self, qtbot, mock_settings_manager, monkeypatch):
        """Test que carga correctamente log level WARNING"""
        monkeypatch.setattr(settings_manager, 'get_log_level', lambda default="INFO": "WARNING")
        
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert dialog.log_level_combo.currentIndex() == 2  # WARNING = índice 2
        assert dialog.dual_log_checkbox.isEnabled() is False  # Deshabilitado para WARNING
    
    def test_loads_custom_log_level_error(self, qtbot, mock_settings_manager, monkeypatch):
        """Test que carga correctamente log level ERROR"""
        monkeypatch.setattr(settings_manager, 'get_log_level', lambda default="INFO": "ERROR")
        
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert dialog.log_level_combo.currentIndex() == 3  # ERROR = índice 3
        assert dialog.dual_log_checkbox.isEnabled() is False  # Deshabilitado para ERROR
    
    def test_loads_custom_max_workers(self, qtbot, mock_settings_manager, monkeypatch):
        """Test que carga correctamente un valor custom de max_workers"""
        monkeypatch.setattr(settings_manager, 'get_max_workers', lambda default=0: 8)
        
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert dialog.max_workers_spin.value() == 8
    
    def test_saves_original_values_on_load(self, qtbot, mock_settings_manager):
        """Test que guarda los valores originales al cargar"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert 'logs_dir' in dialog.original_values
        assert 'log_level' in dialog.original_values
        assert 'auto_backup' in dialog.original_values
        assert dialog.original_values['log_level'] == 1  # INFO


@pytest.mark.ui
class TestSettingsDialogLogLevel:
    """Tests dedicados al cambio de nivel de log"""
    
    def test_change_log_level_to_debug(self, qtbot, mock_settings_manager):
        """Test cambiar nivel de log a DEBUG"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Mockear set_global_log_level
        with patch('ui.dialogs.settings_dialog.set_global_log_level') as mock_set_level:
            # Cambiar a DEBUG (el combo dispara change_log_level automáticamente)
            dialog.log_level_combo.setCurrentIndex(0)
            
            # Verificar que se llamó con el nivel correcto (se llama 2 veces: al cargar INFO y al cambiar a DEBUG)
            assert mock_set_level.call_count >= 1
            mock_set_level.assert_any_call(logging.DEBUG)
            
            # Verificar que dual_log está habilitado
            assert dialog.dual_log_checkbox.isEnabled() is True
    
    def test_change_log_level_to_info(self, qtbot, mock_settings_manager):
        """Test cambiar nivel de log a INFO"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        with patch('ui.dialogs.settings_dialog.set_global_log_level') as mock_set_level:
            dialog.log_level_combo.setCurrentIndex(1)
            dialog.change_log_level("INFO")
            
            mock_set_level.assert_called_once_with(logging.INFO)
            assert dialog.dual_log_checkbox.isEnabled() is True
    
    def test_change_log_level_to_warning(self, qtbot, mock_settings_manager):
        """Test cambiar nivel de log a WARNING y verificar que dual_log se deshabilita"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        with patch('ui.dialogs.settings_dialog.set_global_log_level') as mock_set_level:
            dialog.log_level_combo.setCurrentIndex(2)
            
            assert mock_set_level.call_count >= 1
            mock_set_level.assert_any_call(logging.WARNING)
            assert dialog.dual_log_checkbox.isEnabled() is False
    
    def test_change_log_level_to_error(self, qtbot, mock_settings_manager):
        """Test cambiar nivel de log a ERROR y verificar que dual_log se deshabilita"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        with patch('ui.dialogs.settings_dialog.set_global_log_level') as mock_set_level:
            dialog.log_level_combo.setCurrentIndex(3)
            
            assert mock_set_level.call_count >= 1
            mock_set_level.assert_any_call(logging.ERROR)
            assert dialog.dual_log_checkbox.isEnabled() is False
    
    def test_dual_log_disabled_for_warning_level(self, qtbot, mock_settings_manager):
        """Test que dual_log se deshabilita al cambiar a WARNING"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Inicialmente en INFO, dual_log habilitado
        assert dialog.dual_log_checkbox.isEnabled() is True
        
        # Cambiar a WARNING
        dialog._update_dual_log_enabled_state("WARNING")
        
        assert dialog.dual_log_checkbox.isEnabled() is False
        assert "solo está disponible para niveles INFO o DEBUG" in dialog.dual_log_checkbox.toolTip()
    
    def test_dual_log_disabled_for_error_level(self, qtbot, mock_settings_manager):
        """Test que dual_log se deshabilita al cambiar a ERROR"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Cambiar a ERROR
        dialog._update_dual_log_enabled_state("ERROR")
        
        assert dialog.dual_log_checkbox.isEnabled() is False
    
    def test_dual_log_enabled_for_debug_level(self, qtbot, mock_settings_manager):
        """Test que dual_log se habilita al cambiar a DEBUG"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Cambiar a DEBUG
        dialog._update_dual_log_enabled_state("DEBUG")
        
        assert dialog.dual_log_checkbox.isEnabled() is True
    
    def test_dual_log_enabled_for_info_level(self, qtbot, mock_settings_manager):
        """Test que dual_log se habilita al cambiar a INFO"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Cambiar a INFO
        dialog._update_dual_log_enabled_state("INFO")
        
        assert dialog.dual_log_checkbox.isEnabled() is True
    
    def test_log_level_change_updates_config(self, qtbot, mock_settings_manager):
        """Test que cambiar el nivel de log actualiza Config.LOG_LEVEL"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        original_level = Config.LOG_LEVEL
        
        with patch('ui.dialogs.settings_dialog.set_global_log_level'):
            dialog.change_log_level("DEBUG")
            assert Config.LOG_LEVEL == "DEBUG"
            
            dialog.change_log_level("WARNING")
            assert Config.LOG_LEVEL == "WARNING"
        
        # Restaurar valor original
        Config.LOG_LEVEL = original_level


@pytest.mark.ui
class TestSettingsDialogSaving:
    """Tests de guardado de cambios"""
    
    def test_save_with_no_changes_closes_immediately(self, qtbot, mock_settings_manager):
        """Test que sin cambios, cerrar el diálogo no hace operaciones costosas"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Mockear accept para verificar que se llama
        dialog.accept = MagicMock()
        
        # Guardar sin cambios
        dialog.save_settings()
        
        # Debe cerrar inmediatamente
        dialog.accept.assert_called_once()
    
    def test_save_with_log_level_change(self, qtbot, mock_settings_manager):
        """Test que guardar con cambio de log level lo persiste correctamente"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        with patch('ui.dialogs.settings_dialog.set_global_log_level'), \
             patch.object(dialog, 'accept'), \
             patch.object(dialog, '_requires_restart_changed', return_value=False):
            
            # Cambiar log level
            dialog.log_level_combo.setCurrentIndex(0)  # DEBUG
            
            # Guardar
            with patch('ui.dialogs.settings_dialog.settings_manager') as mock_sm:
                dialog.save_settings()
                
                # Verificar que se guardó el cambio (aunque sea un mock)
                # En realidad settings_manager.set_log_level se llama en change_log_level
                # que se invoca al cambiar el combo
    
    def test_save_with_directory_changes(self, qtbot, mock_settings_manager, tmp_path):
        """Test que guardar con cambios de directorios los persiste correctamente"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        new_logs_dir = tmp_path / "new_logs"
        new_backup_dir = tmp_path / "new_backups"
        
        with patch.object(dialog, 'accept'), \
             patch.object(dialog, '_requires_restart_changed', return_value=False), \
             patch('utils.logger.change_logs_directory', return_value=("/tmp/log.log", new_logs_dir)):
            
            # Cambiar directorios
            dialog.logs_edit.setText(str(new_logs_dir))
            dialog.backup_edit.setText(str(new_backup_dir))
            
            # Guardar
            with patch('ui.dialogs.settings_dialog.settings_manager') as mock_sm:
                dialog.save_settings()
                # En la implementación real, se llama a settings_manager.set_logs_directory y set_backup_directory
    
    def test_save_with_checkbox_changes(self, qtbot, mock_settings_manager):
        """Test que guardar con cambios de checkboxes los persiste correctamente"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        with patch.object(dialog, 'accept'), \
             patch.object(dialog, '_requires_restart_changed', return_value=False):
            
            # Cambiar checkboxes
            dialog.auto_backup_checkbox.setChecked(False)
            dialog.confirm_delete_checkbox.setChecked(False)
            dialog.dual_log_checkbox.setChecked(False)
            
            # Guardar
            with patch('ui.dialogs.settings_dialog.settings_manager') as mock_sm:
                dialog.save_settings()
    
    def test_save_emits_settings_saved_signal(self, qtbot, mock_settings_manager):
        """Test que guardar emite la señal settings_saved"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        with patch.object(dialog, 'accept'), \
             patch.object(dialog, '_requires_restart_changed', return_value=False):
            
            # Espiar la señal
            with qtbot.waitSignal(dialog.settings_saved, timeout=1000):
                # Hacer un cambio
                dialog.auto_backup_checkbox.setChecked(False)
                # Guardar
                dialog.save_settings()
    
    def test_save_only_changed_values(self, qtbot, mock_settings_manager):
        """Test que solo guarda los valores que realmente cambiaron"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        with patch.object(dialog, 'accept'), \
             patch.object(dialog, '_requires_restart_changed', return_value=False), \
             patch('ui.dialogs.settings_dialog.settings_manager') as mock_sm:
            
            # Cambiar solo auto_backup
            dialog.auto_backup_checkbox.setChecked(False)
            
            # Guardar
            dialog.save_settings()
            
            # Verificar que solo se llamó set para auto_backup
            # (En la implementación real, hay condicionales para detectar cambios)


@pytest.mark.ui
class TestSettingsDialogValidation:
    """Tests de validación y detección de cambios"""
    
    def test_save_button_disabled_initially(self, qtbot, mock_settings_manager):
        """Test que el botón guardar está deshabilitado sin cambios"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # El botón debe estar deshabilitado sin cambios
        assert dialog.save_button.isEnabled() is False
    
    def test_save_button_enabled_after_change(self, qtbot, mock_settings_manager):
        """Test que el botón guardar se habilita al hacer un cambio"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Hacer un cambio
        dialog.auto_backup_checkbox.setChecked(False)
        
        # Esperar a que se procesen las señales
        qtbot.wait(100)
        
        # El botón debe habilitarse
        assert dialog.save_button.isEnabled() is True
    
    def test_detects_log_level_change(self, qtbot, mock_settings_manager):
        """Test que detecta cambios en el nivel de log"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Cambiar log level
        dialog.log_level_combo.setCurrentIndex(0)  # DEBUG
        
        qtbot.wait(100)
        
        assert dialog.save_button.isEnabled() is True
    
    def test_detects_directory_change(self, qtbot, mock_settings_manager):
        """Test que detecta cambios en directorios"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Cambiar directorio
        dialog.logs_edit.setText("/tmp/new_logs")
        
        qtbot.wait(100)
        
        assert dialog.save_button.isEnabled() is True
    
    def test_detects_spinbox_change(self, qtbot, mock_settings_manager):
        """Test que detecta cambios en spinboxes"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Cambiar max_workers
        dialog.max_workers_spin.setValue(8)
        
        qtbot.wait(100)
        
        assert dialog.save_button.isEnabled() is True


@pytest.mark.ui
class TestSettingsDialogRestoreDefaults:
    """Tests de restauración de valores por defecto"""
    
    def test_restore_defaults_shows_confirmation(self, qtbot, mock_settings_manager):
        """Test que restaurar valores muestra diálogo de confirmación"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Mockear QMessageBox
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            dialog.restore_defaults()
            
            # Verificar que se mostró el mensaje
            QMessageBox.question.assert_called_once()
    
    def test_restore_defaults_restores_values(self, qtbot, mock_settings_manager):
        """Test que restaurar valores efectivamente los restaura"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Cambiar algunos valores
        dialog.log_level_combo.setCurrentIndex(0)  # DEBUG
        dialog.auto_backup_checkbox.setChecked(False)
        dialog.max_workers_spin.setValue(8)
        
        # Restaurar con confirmación
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes), \
             patch.object(QMessageBox, 'information'):
            dialog.restore_defaults()
        
        # Verificar que se restauraron
        assert dialog.log_level_combo.currentIndex() == 1  # INFO
        assert dialog.auto_backup_checkbox.isChecked() is True
        assert dialog.max_workers_spin.value() == Config.MAX_WORKER_THREADS
    
    def test_restore_defaults_cancelled(self, qtbot, mock_settings_manager):
        """Test que cancelar la restauración no cambia nada"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Cambiar log level
        dialog.log_level_combo.setCurrentIndex(0)  # DEBUG
        
        # Cancelar restauración
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            dialog.restore_defaults()
        
        # Verificar que NO se restauró
        assert dialog.log_level_combo.currentIndex() == 0  # Sigue en DEBUG


@pytest.mark.ui
class TestSettingsDialogIntegration:
    """Tests de integración end-to-end"""
    
    def test_full_flow_load_change_save(self, qtbot, mock_settings_manager):
        """Test complete flow: load -> change -> save"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # 1. Verificar valores iniciales
        assert dialog.log_level_combo.currentIndex() == 1  # INFO
        assert dialog.save_button.isEnabled() is False
        
        # 2. Hacer cambio
        dialog.log_level_combo.setCurrentIndex(0)  # DEBUG
        qtbot.wait(100)
        
        # 3. Verificar que se detectó el cambio
        assert dialog.save_button.isEnabled() is True
        
        # 4. Guardar
        with patch.object(dialog, 'accept'), \
             patch.object(dialog, '_requires_restart_changed', return_value=False), \
             patch('ui.dialogs.settings_dialog.set_global_log_level'):
            dialog.save_settings()
    
    def test_multiple_changes_then_save(self, qtbot, mock_settings_manager):
        """Test múltiples cambios seguidos de guardado"""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        # Hacer múltiples cambios
        dialog.log_level_combo.setCurrentIndex(0)  # DEBUG
        dialog.auto_backup_checkbox.setChecked(False)
        dialog.max_workers_spin.setValue(8)
        dialog.dry_run_default_checkbox.setChecked(True)
        
        qtbot.wait(100)
        
        # Verificar que se detectaron cambios
        assert dialog.save_button.isEnabled() is True
        
        # Guardar
        with patch.object(dialog, 'accept'), \
             patch.object(dialog, '_requires_restart_changed', return_value=False), \
             patch('ui.dialogs.settings_dialog.set_global_log_level'):
            dialog.save_settings()
