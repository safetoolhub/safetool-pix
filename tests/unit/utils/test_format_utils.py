# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Tests para utils/format_utils.py
"""
import pytest
from utils.format_utils import (
    format_size,
    format_number,
    format_file_count,
)


@pytest.mark.unit
class TestFormatSize:
    """Tests para format_size()"""
    
    def test_format_bytes(self):
        assert format_size(0) == "0 B"
        assert format_size(100) == "100 B"
        assert format_size(1023) == "1023 B"
    
    def test_format_kilobytes(self):
        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"
        assert format_size(102400) == "100.0 KB"
    
    def test_format_megabytes(self):
        assert format_size(1048576) == "1.0 MB"
        assert format_size(5242880) == "5.0 MB"
    
    def test_format_gigabytes(self):
        assert format_size(1073741824) == "1.00 GB"
        assert format_size(5368709120) == "5.00 GB"
    
    def test_none_value(self):
        assert format_size(None) == "0 B"
    
    def test_negative_value(self):
        result = format_size(-1024)
        assert result.startswith("-")
        assert "KB" in result
    
    def test_invalid_value(self):
        assert format_size("invalid") == "0 B"


@pytest.mark.unit
class TestFormatNumber:
    """Tests para format_number()"""
    
    def test_small_numbers(self):
        assert format_number(0) == "0"
        assert format_number(123) == "123"
        assert format_number(999) == "999"
    
    def test_thousands(self):
        assert format_number(1000) == "1.0K"
        assert format_number(1500) == "1.5K"
        assert format_number(9999) == "10.0K"
    
    def test_large_thousands(self):
        assert format_number(10000) == "10K"
        assert format_number(50000) == "50K"
        assert format_number(999999) == "999K"
    
    def test_millions(self):
        assert format_number(1000000) == "1.0M"
        assert format_number(5500000) == "5.5M"
    
    def test_none_value(self):
        assert format_number(None) == "0"
    
    def test_negative_value(self):
        result = format_number(-1500)
        assert result.startswith("-")
        assert "K" in result


@pytest.mark.unit
class TestFormatFileCount:
    """Tests para format_file_count()"""
    
    def test_small_count(self):
        assert format_file_count(0) == "0"
        assert format_file_count(100) == "100"
    
    def test_thousands_separator(self):
        assert format_file_count(1000) == "1,000"
        assert format_file_count(1500) == "1,500"
        assert format_file_count(1000000) == "1,000,000"
    
    def test_none_value(self):
        assert format_file_count(None) == "0"
    
    def test_invalid_value(self):
        assert format_file_count("invalid") == "0"
