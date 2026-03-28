# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para utils/platform_utils.py
"""
import pytest
from pathlib import Path
from utils.platform_utils import (
    open_file_with_default_app,
    open_folder_in_explorer,
    # System tools detection
    ToolStatus,
    find_executable,
    get_tool_version,
    check_ffprobe,
    check_exiftool,
    are_video_tools_available,
    check_all_video_tools,
    get_install_instructions,
    get_current_os_install_hint,
)


@pytest.mark.unit
class TestOpenFile:
    """Tests para open_file_with_default_app"""
    
    def test_open_nonexistent_file_calls_error_callback(self):
        """Test que archivo inexistente llama error callback"""
        errors = []
        
        def error_callback(msg):
            errors.append(msg)
        
        nonexistent = Path("/nonexistent/file.txt")
        open_file_with_default_app(nonexistent, error_callback=error_callback)
        
        assert len(errors) > 0
    





@pytest.mark.unit
class TestOpenFolder:
    """Tests para open_folder_in_explorer"""
    
    def test_open_nonexistent_folder_calls_error_callback(self):
        """Test que carpeta inexistente llama error callback"""
        errors = []
        
        def error_callback(msg):
            errors.append(msg)
        
        nonexistent = Path("/nonexistent/folder")
        open_folder_in_explorer(nonexistent, error_callback=error_callback)
        
        assert len(errors) > 0


@pytest.mark.unit
class TestSystemToolsDetection:
    """Tests para detección de herramientas del sistema"""
    
    def test_tool_status_dataclass(self):
        """Test que ToolStatus tiene los campos correctos"""
        status = ToolStatus(
            name='test_tool',
            available=True,
            path='/usr/bin/test_tool',
            version='1.0.0'
        )
        assert status.name == 'test_tool'
        assert status.available is True
        assert status.path == '/usr/bin/test_tool'
        assert status.version == '1.0.0'
        assert status.error is None
    
    def test_tool_status_unavailable(self):
        """Test ToolStatus para herramienta no disponible"""
        status = ToolStatus(
            name='missing_tool',
            available=False,
            error='No instalado'
        )
        assert status.available is False
        assert status.path is None
        assert status.version is None
        assert status.error == 'No instalado'
    
    def test_find_executable_returns_none_for_nonexistent(self):
        """Test que find_executable retorna None para ejecutable inexistente"""
        result = find_executable('nonexistent_command_xyz123')
        assert result is None
    
    def test_find_executable_returns_string_for_common_command(self):
        """Test que find_executable encuentra comandos comunes del sistema"""
        # 'python' o 'ls' deberían existir en cualquier sistema
        python_path = find_executable('python') or find_executable('python3')
        assert python_path is not None or find_executable('ls') is not None or find_executable('cmd') is not None
    
    def test_check_ffprobe_returns_tool_status(self):
        """Test que check_ffprobe retorna ToolStatus"""
        result = check_ffprobe()
        assert isinstance(result, ToolStatus)
        assert result.name == 'ffprobe'
        assert isinstance(result.available, bool)
    
    def test_check_exiftool_returns_tool_status(self):
        """Test que check_exiftool retorna ToolStatus"""
        result = check_exiftool()
        assert isinstance(result, ToolStatus)
        assert result.name == 'exiftool'
        assert isinstance(result.available, bool)
    
    def test_are_video_tools_available_returns_bool(self):
        """Test que are_video_tools_available retorna bool"""
        result = are_video_tools_available()
        assert isinstance(result, bool)
    
    def test_check_all_video_tools_returns_tuple(self):
        """Test que check_all_video_tools retorna tupla de ToolStatus"""
        ffprobe_status, exiftool_status = check_all_video_tools()
        assert isinstance(ffprobe_status, ToolStatus)
        assert isinstance(exiftool_status, ToolStatus)
        assert ffprobe_status.name == 'ffprobe'
        assert exiftool_status.name == 'exiftool'
    
    def test_get_install_instructions_has_required_keys(self):
        """Test que get_install_instructions tiene las claves esperadas"""
        instructions = get_install_instructions()
        assert 'linux_debian' in instructions
        assert 'macos' in instructions
        assert 'windows' in instructions
    
    def test_get_current_os_install_hint_returns_string(self):
        """Test que get_current_os_install_hint retorna string no vacío"""
        hint = get_current_os_install_hint()
        assert isinstance(hint, str)
        assert len(hint) > 0
    
    def test_are_video_tools_consistent_with_individual_checks(self):
        """Test que are_video_tools_available es consistente con checks individuales"""
        ffprobe = check_ffprobe()
        exiftool = check_exiftool()
        combined = are_video_tools_available()
        
        # Si alguna herramienta está disponible, combined debe ser True
        expected = ffprobe.available or exiftool.available
        assert combined == expected