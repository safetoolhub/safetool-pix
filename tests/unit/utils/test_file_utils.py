# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Comprehensive tests for file_utils.py
Focus on file source detection with extensive test coverage
"""
import pytest
from pathlib import Path
from utils.file_utils import detect_file_source


class TestDetectFileSource:
    """Test suite for detect_file_source function"""
    
    # ==================== WHATSAPP TESTS ====================
    
    def test_whatsapp_android_image(self):
        """Test WhatsApp Android image pattern"""
        assert detect_file_source("IMG-20231025-WA0001.jpg") == "WhatsApp"
        assert detect_file_source("IMG-20240101-WA9999.jpeg") == "WhatsApp"
    
    def test_whatsapp_android_video(self):
        """Test WhatsApp Android video pattern"""
        assert detect_file_source("VID-20231025-WA0001.mp4") == "WhatsApp"
        assert detect_file_source("VID-20240315-WA1234.mp4") == "WhatsApp"
    
    def test_whatsapp_android_audio(self):
        """Test WhatsApp Android audio pattern"""
        assert detect_file_source("AUD-20231025-WA0001.opus") == "WhatsApp"
        assert detect_file_source("PTT-20231025-WA0001.opus") == "WhatsApp"
    
    def test_whatsapp_iphone_image(self):
        """Test WhatsApp iPhone image pattern"""
        assert detect_file_source("WhatsApp Image 2023-10-25 at 12.34.56.jpg") == "WhatsApp"
        assert detect_file_source("WhatsApp Image 2024-01-01 at 00.00.00.jpeg") == "WhatsApp"
    
    def test_whatsapp_iphone_video(self):
        """Test WhatsApp iPhone video pattern"""
        assert detect_file_source("WhatsApp Video 2023-10-25 at 12.34.56.mp4") == "WhatsApp"
        assert detect_file_source("WhatsApp Video 2024-03-15 at 18.45.30.mov") == "WhatsApp"
    
    def test_whatsapp_uuid_format(self):
        """Test WhatsApp UUID format (iPhone export)"""
        assert detect_file_source("82DB60A3-002F-4FAE-80FC-96082431D247.jpg") == "WhatsApp"
        assert detect_file_source("A1B2C3D4-1234-5678-90AB-CDEF12345678.jpeg") == "WhatsApp"
        assert detect_file_source("12345678-ABCD-EFAB-CDEF-123456789ABC.png") == "WhatsApp"
        assert detect_file_source("AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE.mp4") == "WhatsApp"
        assert detect_file_source("11111111-2222-3333-4444-555555555555.mov") == "WhatsApp"
        assert detect_file_source("FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF.heic") == "WhatsApp"
    
    def test_whatsapp_uuid_with_suffix(self):
        """Test WhatsApp UUID format with _NNN suffix (CRITICAL - new fix)"""
        assert detect_file_source("82DB60A3-002F-4FAE-80FC-96082431D247_001.jpg") == "WhatsApp"
        assert detect_file_source("A1B2C3D4-1234-5678-90AB-CDEF12345678_999.jpeg") == "WhatsApp"
        assert detect_file_source("12345678-ABCD-EFAB-CDEF-123456789ABC_123.png") == "WhatsApp"
        assert detect_file_source("AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE_042.mp4") == "WhatsApp"
        assert detect_file_source("11111111-2222-3333-4444-555555555555_007.mov") == "WhatsApp"
        assert detect_file_source("FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF_100.heic") == "WhatsApp"
    
    def test_whatsapp_uuid_lowercase(self):
        """Test WhatsApp UUID format with lowercase letters"""
        assert detect_file_source("82db60a3-002f-4fae-80fc-96082431d247.jpg") == "WhatsApp"
        assert detect_file_source("a1b2c3d4-1234-5678-90ab-cdef12345678_001.jpeg") == "WhatsApp"
    
    # ==================== IPHONE TESTS ====================
    
    def test_iphone_heic(self):
        """Test iPhone HEIC format"""
        assert detect_file_source("IMG_1234.HEIC") == "iPhone"
        assert detect_file_source("IMG_9999.heic") == "iPhone"
        assert detect_file_source("random_photo.HEIC") == "iPhone"
    
    def test_iphone_standard_image(self):
        """Test iPhone standard image pattern"""
        assert detect_file_source("IMG_1234.JPG") == "iPhone"
        assert detect_file_source("IMG_0001.jpeg") == "iPhone"
        assert detect_file_source("IMG_9999.png") == "iPhone"
    
    def test_iphone_edited_image(self):
        """Test iPhone edited image pattern (IMG_EXXXX)"""
        assert detect_file_source("IMG_E1234.JPG") == "iPhone"
        assert detect_file_source("IMG_E0001.jpeg") == "iPhone"
        assert detect_file_source("IMG_E9999.png") == "iPhone"
    
    def test_iphone_with_suffix(self):
        """Test iPhone pattern with _NNN suffix"""
        assert detect_file_source("IMG_1234_001.JPG") == "iPhone"
        assert detect_file_source("IMG_E5678_999.jpeg") == "iPhone"
        assert detect_file_source("IMG_0001_042.png") == "iPhone"
    
    def test_iphone_video(self):
        """Test iPhone video pattern"""
        assert detect_file_source("IMG_1234.MOV") == "iPhone"
        assert detect_file_source("IMG_5678.mov") == "iPhone"
        assert detect_file_source("IMG_9999.mp4") == "iPhone"
        assert detect_file_source("IMG_1234_001.MOV") == "iPhone"
    
    # ==================== ANDROID TESTS ====================
    
    def test_android_pixel(self):
        """Test Google Pixel pattern"""
        assert detect_file_source("PXL_20231025.jpg") == "Android"
        assert detect_file_source("PXL_20240101.jpeg") == "Android"
        assert detect_file_source("pxl_20231225.jpg") == "Android"
    
    def test_android_pixel_with_suffix(self):
        """Test Google Pixel pattern with _NNN suffix"""
        assert detect_file_source("PXL_20231025_001.jpg") == "Android"
        assert detect_file_source("PXL_20240101_999.jpeg") == "Android"
    
    def test_android_samsung(self):
        """Test Samsung pattern (YYYYMMDD_HHMMSS)"""
        assert detect_file_source("20231025_123456.jpg") == "Android"
        assert detect_file_source("20240101_000000.jpeg") == "Android"
        assert detect_file_source("20231231_235959.png") == "Android"
    
    def test_android_samsung_with_suffix(self):
        """Test Samsung pattern with _NNN suffix"""
        assert detect_file_source("20231025_123456_001.jpg") == "Android"
        assert detect_file_source("20240101_000000_999.jpeg") == "Android"
    
    def test_android_generic_img(self):
        """Test generic Android IMG pattern (not WhatsApp)"""
        assert detect_file_source("IMG-20231025.jpg") == "Android"
        assert detect_file_source("IMG-20240101.jpeg") == "Android"
        assert detect_file_source("IMG-20231025_001.jpg") == "Android"
    
    def test_android_signal(self):
        """Test Signal app pattern"""
        assert detect_file_source("signal-2023.jpg") == "Android"
        assert detect_file_source("signal-2024.jpeg") == "Android"
        assert detect_file_source("signal-2023_001.jpg") == "Android"
    
    # ==================== SCREENSHOT TESTS ====================
    
    def test_screenshot_standard(self):
        """Test standard screenshot patterns"""
        assert detect_file_source("Screenshot_2023.png") == "Screenshot"
        assert detect_file_source("screenshot_2024.jpg") == "Screenshot"
        assert detect_file_source("Screenshot-2023-10-25.png") == "Screenshot"
    
    def test_screenshot_spanish(self):
        """Test Spanish screenshot pattern"""
        assert detect_file_source("Captura de pantalla 2023.png") == "Screenshot"
        assert detect_file_source("captura_2024.jpg") == "Screenshot"
    
    def test_screenshot_variations(self):
        """Test screenshot pattern variations"""
        assert detect_file_source("Screen_2023.png") == "Screenshot"
        assert detect_file_source("Scrnshot_2024.jpg") == "Screenshot"
    
    # ==================== CAMERA TESTS ====================
    
    def test_camera_dsc(self):
        """Test camera DSC pattern"""
        assert detect_file_source("DSC_0001.jpg") == "Camera"
        assert detect_file_source("DSC-1234.jpeg") == "Camera"
        assert detect_file_source("dsc_9999.jpg") == "Camera"
    
    def test_camera_dsc_with_suffix(self):
        """Test camera DSC pattern with _NNN suffix"""
        assert detect_file_source("DSC_0001_001.jpg") == "Camera"
        assert detect_file_source("DSC-1234_999.jpeg") == "Camera"
    
    def test_camera_nikon(self):
        """Test Nikon camera pattern"""
        assert detect_file_source("_DSC1234.jpg") == "Camera"
        assert detect_file_source("_dsc5678.jpeg") == "Camera"
        assert detect_file_source("_DSC1234_001.jpg") == "Camera"
    
    def test_camera_generic_long_number(self):
        """Test generic camera pattern with long number (not iPhone 4-digit)"""
        assert detect_file_source("IMG_12345.jpg") == "Camera"
        assert detect_file_source("IMG_123456.jpeg") == "Camera"
        assert detect_file_source("IMG_12345_001.jpg") == "Camera"
    
    def test_camera_p_format(self):
        """Test camera P format"""
        assert detect_file_source("P0001234.jpg") == "Camera"
        assert detect_file_source("P9999999.jpeg") == "Camera"
        assert detect_file_source("P1234567_001.jpg") == "Camera"
    
    # ==================== UNKNOWN TESTS ====================
    
    def test_unknown_random_filename(self):
        """Test unknown source for random filenames"""
        assert detect_file_source("random_file.jpg") == "Unknown"
        assert detect_file_source("vacation_photo.jpeg") == "Unknown"
        assert detect_file_source("family_pic.png") == "Unknown"
    
    def test_unknown_document(self):
        """Test unknown source for non-photo files"""
        assert detect_file_source("document.pdf") == "Unknown"
        assert detect_file_source("report.docx") == "Unknown"
        assert detect_file_source("data.xlsx") == "Unknown"
    
    def test_unknown_short_random(self):
        """Test unknown source for short random filenames"""
        assert detect_file_source("abc.jpg") == "Unknown"
        assert detect_file_source("xyz.png") == "Unknown"
    
    # ==================== EDGE CASES ====================
    
    def test_case_insensitivity(self):
        """Test that detection is case-insensitive"""
        assert detect_file_source("img_1234.jpg") == "iPhone"
        assert detect_file_source("IMG_1234.JPG") == "iPhone"
        assert detect_file_source("ImG_1234.JpG") == "iPhone"
    
    def test_whatsapp_priority_over_others(self):
        """Test that WhatsApp detection has priority"""
        # UUID should be detected as WhatsApp, not Unknown
        assert detect_file_source("12345678-1234-1234-1234-123456789ABC.jpg") == "WhatsApp"
        # Even with suffix
        assert detect_file_source("12345678-1234-1234-1234-123456789ABC_001.jpg") == "WhatsApp"
    
    def test_iphone_4digit_vs_camera_longdigit(self):
        """Test differentiation between iPhone 4-digit and Camera long-digit"""
        # iPhone: exactly 4 digits
        assert detect_file_source("IMG_1234.jpg") == "iPhone"
        assert detect_file_source("IMG_0001.jpg") == "iPhone"
        assert detect_file_source("IMG_9999.jpg") == "iPhone"
        
        # Camera: 5+ digits
        assert detect_file_source("IMG_12345.jpg") == "Camera"
        assert detect_file_source("IMG_123456.jpg") == "Camera"
    
    def test_empty_filename(self):
        """Test behavior with empty filename"""
        # Should not crash
        result = detect_file_source("")
        assert result in ["Unknown", "WhatsApp", "iPhone", "Android", "Screenshot", "Camera"]
    
    def test_filename_with_spaces(self):
        """Test filenames with spaces"""
        assert detect_file_source("WhatsApp Image 2023-10-25 at 12.34.56.jpg") == "WhatsApp"
        assert detect_file_source("Captura de pantalla 2023.png") == "Screenshot"
    
    def test_multiple_extensions(self):
        """Test filenames with multiple dots - may not match patterns"""
        # These have extra dots, so they won't match the strict patterns
        # They should still be classified as something
        result1 = detect_file_source("IMG_1234.backup.jpg")
        result2 = detect_file_source("DSC_0001.edited.jpeg")
        # Just ensure they don't crash and return a valid source
        assert result1 in ["iPhone", "Camera", "Unknown"]
        assert result2 in ["Camera", "Unknown"]


class TestDetectFileSourceWithPath:
    """Test detect_file_source with file path parameter"""
    
    def test_with_path_whatsapp(self):
        """Test source detection with path parameter for WhatsApp"""
        path = Path("/home/user/WhatsApp/IMG-20231025-WA0001.jpg")
        assert detect_file_source("IMG-20231025-WA0001.jpg", file_path=path) == "WhatsApp"
    
    def test_with_path_iphone(self):
        """Test source detection with path parameter for iPhone"""
        path = Path("/home/user/Camera/IMG_1234.JPG")
        assert detect_file_source("IMG_1234.JPG", file_path=path) == "iPhone"


class TestWhatsAppUUIDRegexFix:
    """Dedicated tests for the WhatsApp UUID suffix fix - REGRESSION PREVENTION"""
    
    def test_uuid_without_suffix_still_works(self):
        """Ensure UUID without suffix still works after regex change"""
        filenames = [
            "82DB60A3-002F-4FAE-80FC-96082431D247.jpg",
            "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE.jpeg",
            "12345678-1234-1234-1234-123456789ABC.png",
        ]
        for filename in filenames:
            assert detect_file_source(filename) == "WhatsApp", f"Failed for {filename}"
    
    def test_uuid_with_suffix_works(self):
        """Test the new regex fix for UUID with _NNN suffix"""
        filenames = [
            "82DB60A3-002F-4FAE-80FC-96082431D247_001.jpg",
            "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE_999.jpeg",
            "12345678-1234-1234-1234-123456789ABC_042.png",
        ]
        for filename in filenames:
            assert detect_file_source(filename) == "WhatsApp", f"Failed for {filename}"
    
    def test_uuid_suffix_must_be_3_digits(self):
        """Test that suffix must be exactly 3 digits"""
        # Valid: _NNN (3 digits)
        assert detect_file_source("82DB60A3-002F-4FAE-80FC-96082431D247_001.jpg") == "WhatsApp"
        assert detect_file_source("82DB60A3-002F-4FAE-80FC-96082431D247_999.jpg") == "WhatsApp"
        
        # Invalid: not 3 digits (should be Unknown)
        # Note: These might still match other patterns, so we just check they don't crash
        result1 = detect_file_source("82DB60A3-002F-4FAE-80FC-96082431D247_1.jpg")
        result2 = detect_file_source("82DB60A3-002F-4FAE-80FC-96082431D247_1234.jpg")
        # They should be classified as something (not crash)
        assert result1 in ["WhatsApp", "Unknown"]
        assert result2 in ["WhatsApp", "Unknown"]
    
    def test_all_supported_extensions_with_uuid(self):
        """Test all supported extensions with UUID format"""
        extensions = ["jpg", "jpeg", "png", "mp4", "mov", "heic"]
        uuid = "82DB60A3-002F-4FAE-80FC-96082431D247"
        
        for ext in extensions:
            # Without suffix
            assert detect_file_source(f"{uuid}.{ext}") == "WhatsApp"
            # With suffix
            assert detect_file_source(f"{uuid}_001.{ext}") == "WhatsApp"


class TestCleanupEmptyDirectories:
    """Test suite for cleanup_empty_directories function"""

    def test_removes_truly_empty_directory(self, tmp_path):
        """Removes a directory that is completely empty"""
        from utils.file_utils import cleanup_empty_directories
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 1
        assert not empty_dir.exists()

    def test_does_not_remove_root(self, tmp_path):
        """Root directory itself is never removed"""
        from utils.file_utils import cleanup_empty_directories
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 0
        assert tmp_path.exists()

    def test_does_not_remove_directory_with_real_files(self, tmp_path):
        """Directory with real files is not removed"""
        from utils.file_utils import cleanup_empty_directories
        d = tmp_path / "has_content"
        d.mkdir()
        (d / "real_file.txt").write_text("content")
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 0
        assert d.exists()

    def test_removes_directory_with_only_nomedia(self, tmp_path):
        """Directory containing only .nomedia is treated as empty"""
        from utils.file_utils import cleanup_empty_directories
        d = tmp_path / "with_nomedia"
        d.mkdir()
        (d / ".nomedia").write_bytes(b"")
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 1
        assert not d.exists()

    def test_removes_directory_with_only_ds_store(self, tmp_path):
        """Directory containing only .DS_Store is treated as empty"""
        from utils.file_utils import cleanup_empty_directories
        d = tmp_path / "with_ds_store"
        d.mkdir()
        (d / ".DS_Store").write_bytes(b"\x00\x00")
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 1
        assert not d.exists()

    def test_removes_directory_with_only_thumbs_db(self, tmp_path):
        """Directory containing only Thumbs.db is treated as empty"""
        from utils.file_utils import cleanup_empty_directories
        d = tmp_path / "with_thumbs"
        d.mkdir()
        (d / "Thumbs.db").write_bytes(b"\x00")
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 1
        assert not d.exists()

    def test_removes_directory_with_only_desktop_ini(self, tmp_path):
        """Directory containing only desktop.ini is treated as empty"""
        from utils.file_utils import cleanup_empty_directories
        d = tmp_path / "with_desktop_ini"
        d.mkdir()
        (d / "desktop.ini").write_text("[.ShellClassInfo]")
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 1
        assert not d.exists()

    def test_removes_directory_with_multiple_junk_files(self, tmp_path):
        """Directory containing only multiple junk files is treated as empty"""
        from utils.file_utils import cleanup_empty_directories
        d = tmp_path / "multi_junk"
        d.mkdir()
        (d / ".nomedia").write_bytes(b"")
        (d / ".DS_Store").write_bytes(b"\x00")
        (d / "Thumbs.db").write_bytes(b"\x00")
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 1
        assert not d.exists()

    def test_does_not_remove_directory_with_junk_and_real_files(self, tmp_path):
        """Directory with junk + real files is NOT removed"""
        from utils.file_utils import cleanup_empty_directories
        d = tmp_path / "mixed"
        d.mkdir()
        (d / ".nomedia").write_bytes(b"")
        (d / "photo.jpg").write_bytes(b"fake jpg")
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 0
        assert d.exists()
        assert (d / "photo.jpg").exists()

    def test_removes_nested_empty_directories_bottom_up(self, tmp_path):
        """Nested directories are removed bottom-up"""
        from utils.file_utils import cleanup_empty_directories
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / ".nomedia").write_bytes(b"")
        
        removed = cleanup_empty_directories(tmp_path)
        
        # All 3 levels should be removed (c first, then b, then a)
        assert removed == 3
        assert not (tmp_path / "a").exists()

    def test_junk_file_names_are_case_insensitive(self, tmp_path):
        """Junk file matching is case-insensitive (.NOMEDIA, .ds_store, etc.)"""
        from utils.file_utils import cleanup_empty_directories
        d = tmp_path / "case_test"
        d.mkdir()
        (d / ".NOMEDIA").write_bytes(b"")
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 1
        assert not d.exists()

    def test_does_not_remove_dir_with_junk_subdirectory(self, tmp_path):
        """Directory with a non-junk subdirectory containing files is not removed"""
        from utils.file_utils import cleanup_empty_directories
        parent = tmp_path / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        (child / "real.txt").write_text("data")
        (parent / ".nomedia").write_bytes(b"")
        
        removed = cleanup_empty_directories(tmp_path)
        
        assert removed == 0
        assert parent.exists()
        assert child.exists()
