import os
from scripts.utils import get_csv_files
from loguru import logger

def test_matching_filenames():
    script_dir = os.path.dirname(__file__)
    mishearing_dir = os.path.join(script_dir, '../data/mishearing')
    tag_dir = os.path.join(script_dir, '../data/tag')

    mishearing_files = {f for f in get_csv_files(mishearing_dir) if os.path.basename(f) != 'translation.csv'}
    tag_files = {f for f in get_csv_files(tag_dir) if os.path.basename(f) != 'translation.csv'}

    logger.info("Excluded 'translation.csv' from mishearing_files and tag_files.")

    missing_files = tag_files - mishearing_files

    assert not missing_files, f"The following files in tag/**/.*.csv do not have corresponding files in mishearing/**/.*.csv: {missing_files}"