import os
from scripts.utils import get_csv_files

def test_matching_filenames():
    script_dir = os.path.dirname(__file__)
    mishearing_dir = os.path.join(script_dir, '../data/mishearing')
    tag_dir = os.path.join(script_dir, '../data/tag')

    mishearing_files = get_csv_files(mishearing_dir)
    tag_files = get_csv_files(tag_dir)

    missing_files = tag_files - mishearing_files

    assert not missing_files, f"The following files in tag/**/.*.csv do not have corresponding files in mishearing/**/.*.csv: {missing_files}"