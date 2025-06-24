import subprocess
import pytest
from pathlib import Path
import os

def test_valid_filenames():
    valid_files = ["valid-file.csv", "another-valid-file.csv", "valid_file.csv"]
    for file in valid_files:
        Path(file).touch()

    script_path = os.path.abspath("scripts/hooks/check_filename.py")

    try:
        result = subprocess.run([
            "python3", script_path, *valid_files
        ], capture_output=True)
        assert result.returncode == 0
    finally:
        for file in valid_files:
            Path(file).unlink()

def test_invalid_filenames():
    invalid_files = ["invalid file.csv", "invalid@file.csv", "invalid.file.csv"]
    for file in invalid_files:
        Path(file).touch()

    script_path = os.path.abspath("scripts/hooks/check_filename.py")

    try:
        result = subprocess.run([
            "python3", script_path, *invalid_files
        ], capture_output=True)
        assert result.returncode == 1
        assert b"Invalid CSV filenames:" in result.stdout
    finally:
        for file in invalid_files:
            Path(file).unlink()