import subprocess
import pathlib
import sys

def test_check_filename_valid():
    valid = "tests/data/2025-06-05_test.csv"
    result = subprocess.run([
        sys.executable, "scripts/hooks/check_filename.py", valid
    ], capture_output=True)
    assert result.returncode == 0

def test_check_filename_invalid(tmp_path):
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
    result = subprocess.run([
        sys.executable, "scripts/build_datapackage.py"
    ], capture_output=True)
    assert result.returncode == 0
    assert pathlib.Path("datapackage.json").exists()

def test_frictionless_validate_on_test_csv():
    # frictionless validateでスキーマ適合を確認
    result = subprocess.run([
        "frictionless", "validate", "tests/data/2025-06-05_test.csv", "--schema", "schema/mishearing.schema.json"
    ], capture_output=True)
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()

def test_frictionless_validate_on_invalid_csv(tmp_path):
    # スキーマ不適合なCSVでfailすることを確認
    invalid_csv = tmp_path / "2025-06-05_invalid.csv"
    invalid_csv.write_text("MishearID,Src\nTST20250605_001,foo\n")  # 必須列が足りない
    result = subprocess.run([
        "frictionless", "validate", str(invalid_csv), "--schema", "schema/mishearing.schema.json"
    ], capture_output=True)
    assert result.returncode != 0
    assert b"error" in result.stdout.lower() or b"error" in result.stderr.lower()
