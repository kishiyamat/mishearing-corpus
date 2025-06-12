import os
from scripts.utils import get_csv_files
from loguru import logger

def test_matching_filenames():
    """
    Test to ensure that all CSV files in the 'tag' and 'environment' directories
    have corresponding files in the 'mishearing' directory, excluding 'translation.csv'.

    This function performs the following checks:
    1. Collects all CSV files from the 'mishearing', 'tag', and 'environment' directories,
       excluding 'translation.csv'.
    2. Compares the filenames in the 'tag' and 'environment' directories against the
       filenames in the 'mishearing' directory.
    3. Asserts that there are no missing files in the 'tag' and 'environment' directories
       when compared to the 'mishearing' directory.

    Raises:
        AssertionError: If there are files in 'tag' or 'environment' directories that
                        do not have corresponding files in the 'mishearing' directory.
    """
    script_dir = os.path.dirname(__file__)
    mishearing_dir = os.path.join(script_dir, '../data/mishearing')
    tag_dir = os.path.join(script_dir, '../data/tag')
    environment_dir = os.path.join(script_dir, '../data/environment')

    mishearing_files = {f for f in get_csv_files(mishearing_dir) if os.path.basename(f) != 'translation.csv'}
    tag_files = {f for f in get_csv_files(tag_dir) if os.path.basename(f) != 'translation.csv'}
    environment_files = {f for f in get_csv_files(environment_dir) if os.path.basename(f) != 'translation.csv'}

    logger.info("Excluded 'translation.csv' from mishearing_files, tag_files, and environment_files.")

    missing_tag_files = tag_files - mishearing_files
    missing_environment_files = environment_files - mishearing_files

    assert not missing_tag_files, f"The following files in tag/**/.*.csv do not have corresponding files in mishearing/**/.*.csv: {missing_tag_files}"
    assert not missing_environment_files, f"The following files in environment/**/.*.csv do not have corresponding files in mishearing/**/.*.csv: {missing_environment_files}"
