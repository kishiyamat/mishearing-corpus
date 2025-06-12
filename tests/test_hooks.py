import subprocess
import pathlib
import sys

def test_check_filename_valid():
    """
    Test the validity of a filename using the `check_filename.py` script.

    This test verifies that the `check_filename.py` script correctly identifies
    a valid filename and exits with a return code of 0.

    Steps:
    1. Define a valid filename (`valid`) that adheres to the expected format.
    2. Run the `check_filename.py` script using `subprocess.run` with the valid filename as an argument.
    3. Assert that the script exits successfully with a return code of 0.

    Raises:
        AssertionError: If the script does not exit with a return code of 0.
    """
    valid = "tests/data/2025-06-05_test.csv"
    result = subprocess.run([
        sys.executable, "scripts/hooks/check_filename.py", valid
    ], capture_output=True)
    assert result.returncode == 0

def test_check_filename_invalid(tmp_path):
    """
    Test the behavior of the `check_filename.py` script when provided with an invalid CSV filename.

    This test creates a temporary directory and simulates the following scenarios:
    1. An invalid CSV file is created outside the `mishearing` directory.
    2. A subdirectory named `mishearing` is created, and an invalid CSV file is placed inside it.

    The script `check_filename.py` is expected to:
    - Return a non-zero exit code when the filename is invalid.
    - Output an error message indicating "Invalid CSV filenames" in either stdout or stderr.

    Args:
        tmp_path (pathlib.Path): A temporary directory provided by pytest for creating test files.
    """
    # 一時的に不正なファイルを作成してテスト
    invalid = tmp_path / "20250605test.csv"
    invalid.write_text("dummy")
    # mishearingディレクトリ配下でないとスキップされる仕様なので、サブディレクトリを作成
    mishearing_dir = tmp_path / "mishearing"
    mishearing_dir.mkdir()
    invalid_path = mishearing_dir / "20250605test.csv"
    invalid_path.write_text("dummy")
    result = subprocess.run([
        sys.executable, "scripts/hooks/check_filename.py", str(invalid_path)
    ], capture_output=True)
    assert result.returncode != 0
    assert b"Invalid CSV filenames" in result.stdout or result.stderr

def test_build_datapackage_runs():
    """
    Test the execution of the `build_datapackage.py` script.

    This test verifies that the script runs successfully and generates
    the expected `datapackage.json` file.

    Assertions:
        - The script exits with a return code of 0, indicating success.
        - The `datapackage.json` file is created in the current working directory.
    """
    result = subprocess.run([
        sys.executable, "scripts/build_datapackage.py"
    ], capture_output=True)
    assert result.returncode == 0
    assert pathlib.Path("datapackage.json").exists()

def test_frictionless_validate_on_test_csv():
    """
    Tests the validation of a CSV file against a predefined schema using the Frictionless framework.

    This function runs the `frictionless validate` command to check if the CSV file located at 
    `tests/data/2025-06-05_test.csv` conforms to the schema defined in `schema/mishearing.schema.json`.
    It asserts that the validation process completes successfully (return code 0).

    Raises:
        AssertionError: If the validation fails, the error message from the command's output is included.
    """
    # frictionless validateでスキーマ適合を確認
    result = subprocess.run([
        "frictionless", "validate", "tests/data/2025-06-05_test.csv", "--schema", "schema/mishearing.schema.json"
    ], capture_output=True)
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()

def test_frictionless_validate_on_invalid_csv(tmp_path):
    """
    Test the validation of an invalid CSV file using the Frictionless framework.

    This test ensures that the `frictionless validate` command fails when provided
    with a CSV file that does not conform to the specified schema. The test creates
    a temporary invalid CSV file with missing required columns and validates it
    against a schema file.

    Args:
        tmp_path (pathlib.Path): A temporary directory provided by pytest for creating
                                 temporary files during the test.

    Assertions:
        - The `frictionless validate` command should return a non-zero exit code.
        - The output (stdout or stderr) should contain the word "error", indicating
          validation failure.
    """
    # スキーマ不適合なCSVでfailすることを確認
    invalid_csv = tmp_path / "2025-06-05_invalid.csv"
    invalid_csv.write_text("MishearID,Src\nTST20250605_001,foo\n")  # 必須列が足りない
    result = subprocess.run([
        "frictionless", "validate", str(invalid_csv), "--schema", "schema/mishearing.schema.json"
    ], capture_output=True)
    assert result.returncode != 0
    assert b"error" in result.stdout.lower() or b"error" in result.stderr.lower()
