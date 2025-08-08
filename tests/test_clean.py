"""
Test suite for growthkit.utils.style.clean module.

This module tests the filename sanitization functionality which:
- Replaces spaces with hyphens
- Removes non-alphanumeric characters except dots and hyphens  
- Converts to lowercase
- Removes consecutive hyphens
- Strips leading/trailing hyphens
"""

import pytest
from growthkit.utils.style.clean import up


class TestFilenameCleanUp:
    """Test cases for the up() function that sanitizes filenames."""

    def test_basic_space_replacement(self):
        """Test that spaces are replaced with hyphens."""
        assert up("hello world") == "hello-world"
        assert up("multiple   spaces") == "multiple-spaces"

    def test_special_character_removal(self):
        """Test that special characters are removed except dots, hyphens, and underscores."""
        assert up("hello@world#test") == "helloworldtest"
        assert up("file!name$with%symbols") == "filenamewithsymbols"
        assert up("test&file*name") == "testfilename"

    def test_preserve_dots_hyphens_underscores(self):
        """Test that dots, hyphens, and underscores are preserved."""
        assert up("file-name.txt") == "file-name.txt"
        assert up("some.file-name.backup") == "some.file-name.backup"

    def test_lowercase_conversion(self):
        """Test that uppercase letters are converted to lowercase."""
        assert up("UPPERCASE") == "uppercase"
        assert up("MixedCase") == "mixedcase"
        assert up("CamelCaseFile") == "camelcasefile"

    def test_consecutive_hyphen_removal(self):
        """Test that consecutive hyphens are collapsed to single hyphens."""
        assert up("hello--world") == "hello-world"
        assert up("multiple---hyphens") == "multiple-hyphens"
        assert up("file----name") == "file-name"

    def test_leading_trailing_hyphen_removal(self):
        """Test that leading and trailing hyphens are stripped."""
        assert up("-leading-hyphen") == "leading-hyphen"
        assert up("trailing-hyphen-") == "trailing-hyphen"
        assert up("-both-sides-") == "both-sides"

    def test_empty_and_whitespace_strings(self):
        """Test edge cases with empty and whitespace-only strings."""
        assert up("") == ""
        assert up("   ") == ""
        assert up("\t\n") == ""

    def test_numbers_and_underscores(self):
        """Test that numbers and underscores are preserved."""
        assert up("file_123.txt") == "file_123.txt"
        assert up("test_file_2024") == "test_file_2024"
        assert up("version2.1_backup") == "version2.1_backup"

    def test_complex_filename_scenarios(self):
        """Test realistic complex filename scenarios."""
        # Typical messy filename
        assert up("My Document (Copy 1).docx") == "my-document-copy-1.docx"

        # Filename with multiple issues
        assert up("  --File@Name#With$Issues--.txt  ") == "filenamewithissues-.txt"

        # Social media style filename
        assert up("IMG_20240101_123456(1).jpg") == "img_20240101_1234561.jpg"

        # Technical filename with version
        assert up("backup-v2.1.3_FINAL(2).sql") == "backup-v2.1.3_final2.sql"

    def test_unicode_and_special_cases(self):
        """Test unicode characters and other special cases."""
        # Unicode characters should be removed
        assert up("café-résumé") == "caf-rsum"
        assert up("文件名.txt") == ".txt"

        # Mixed scenarios
        assert up("file🎉name.txt") == "filename.txt"

    def test_only_special_characters(self):
        """Test strings with only special characters."""
        assert up("@#$%^&*()") == ""
        assert up("!!!???") == ""
        assert up("---") == ""

    def test_file_extensions(self):
        """Test various file extensions are handled correctly."""
        assert up("document.PDF") == "document.pdf"
        assert up("script.py") == "script.py"
        assert up("archive.tar.gz") == "archive.tar.gz"
        assert up("data.json.backup") == "data.json.backup"


class TestEdgeCases:
    """Additional edge case tests for the up() function."""

    def test_very_long_filename(self):
        """Test with very long filename."""
        long_name = "a" * 100 + " " + "b" * 100
        result = up(long_name)
        assert len(result) == 201  # 100 + 1 hyphen + 100
        assert result == "a" * 100 + "-" + "b" * 100

    def test_alternating_special_characters(self):
        """Test alternating valid and invalid characters."""
        assert up("a@b#c$d") == "abcd"
        assert up("1!2@3#4") == "1234"

    def test_mixed_spaces_and_hyphens(self):
        """Test mixed spaces and existing hyphens."""
        assert up("hello - world - test") == "hello-world-test"
        assert up("file -  name") == "file-name"

    def test_preserve_underscores_in_context(self):
        """Test that underscores are preserved in various contexts."""
        assert up("snake_case_file") == "snake_case_file"
        assert up("__private__file") == "__private__file"
        assert up("test_file_v1_2") == "test_file_v1_2"


if __name__ == "__main__":
    # Allow running tests directly with python
    pytest.main([__file__, "-v"])
