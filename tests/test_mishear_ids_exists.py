import os
import csv
from scripts.utils import get_csv_files
from loguru import logger


def get_ids(file_path, column_name):
    """
    Extracts unique values from a specified column in a CSV file.

    Args:
        file_path (str): The path to the CSV file.
        column_name (str): The name of the column to extract values from.

    Returns:
        set: A set containing unique values from the specified column.

    Raises:
        FileNotFoundError: If the file at the given path does not exist.
        KeyError: If the specified column name is not found in the CSV file.
    """
    ids = set()
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.add(row[column_name])
    return ids

SCRIPT_DIR = os.path.dirname(__file__)
MISHEARING_DIR = os.path.join(SCRIPT_DIR, '../data/mishearing')
TAG_DIR = os.path.join(SCRIPT_DIR, '../data/tag')
ENVIRONMENT_DIR = os.path.join(SCRIPT_DIR, '../data/environment')

MISHEARING_FILES = get_csv_files(MISHEARING_DIR)
ENV_TRANSLATION_PATH = os.path.join(ENVIRONMENT_DIR, 'translation.csv')
TAG_TRANSLATION_PATH = os.path.join(TAG_DIR, 'translation.csv')

def test_tag_environment_exist():
    # other columns: tag, environment
    for file_i in MISHEARING_FILES:
        tag_path = os.path.join(TAG_DIR, file_i)
        environment_path = os.path.join(ENVIRONMENT_DIR, file_i)

        if not os.path.exists(tag_path) or not os.path.exists(environment_path):
            logger.warning(f"Skipping {file_i} as corresponding mishearing or environment file is missing.")
            raise AssertionError(f"Missing corresponding files for {file_i}. Ensure all files are present in the directories.")

def test_mishear_ids_exist_in_other_columns():
    for file_i in MISHEARING_FILES:
        mishearing_path = os.path.join(MISHEARING_DIR, file_i)
        tag_path = os.path.join(TAG_DIR, file_i)
        environment_path = os.path.join(ENVIRONMENT_DIR, file_i)

        logger.info(f"Processing file: {file_i}")
        mishearing_mishear_ids = get_ids(mishearing_path, 'MishearID')
        tag_mishear_ids = get_ids(tag_path, 'MishearID')
        environment_mishear_ids = get_ids(environment_path, 'MishearID')

        missing_in_tag = mishearing_mishear_ids - tag_mishear_ids
        missing_in_environment = mishearing_mishear_ids - environment_mishear_ids

        if missing_in_tag:
            logger.error(f"The following MishearIDs in {file_i} do not exist in the corresponding tag file: {missing_in_tag}")
        if missing_in_environment:
            logger.error(f"The following MishearIDs in {file_i} do not exist in the corresponding environment file: {missing_in_environment}")

        assert not missing_in_tag, f"The following MishearIDs in {file_i} do not exist in the corresponding tag file: {missing_in_tag}"
        assert not missing_in_environment, f"The following MishearIDs in {file_i} do not exist in the corresponding environment file: {missing_in_environment}"

def test_translation_exists():
    """
    Test to verify that all EnvIDs and TagIDs from the environment and tag CSV files 
    exist in their respective translation CSV files.

    This test performs the following checks:
    1. Collects all EnvIDs from environment CSV files (excluding 'translation.csv').
    2. Collects all TagIDs from tag CSV files (excluding 'translation.csv').
    3. Retrieves EnvIDs and TagIDs from their respective translation CSV files.
    4. Identifies any EnvIDs or TagIDs that are missing in the translation files.
    5. Logs errors for missing IDs and asserts that no IDs are missing.

    Raises:
        AssertionError: If any EnvIDs or TagIDs are missing in their respective translation CSV files.
    """
    environment_files = get_csv_files(ENVIRONMENT_DIR)
    tag_files = get_csv_files(TAG_DIR)

    env_ids = set()
    tag_ids = set()

    for file_i in environment_files:
        if file_i != 'translation.csv':
            env_ids.update(get_ids(os.path.join(ENVIRONMENT_DIR, file_i), 'EnvID'))

    for file_i in tag_files:
        if file_i != 'translation.csv':
            tag_ids.update(get_ids(os.path.join(TAG_DIR, file_i), 'TagID'))

    env_translation_ids = get_ids(ENV_TRANSLATION_PATH, 'EnvID')
    tag_translation_ids = get_ids(TAG_TRANSLATION_PATH, 'TagID')

    missing_env_ids = env_ids - env_translation_ids
    missing_tag_ids = tag_ids - tag_translation_ids

    if missing_env_ids:
        logger.error(f"The following EnvIDs are missing in environment translation.csv: {missing_env_ids}")
    if missing_tag_ids:
        logger.error(f"The following TagIDs are missing in tag translation.csv: {missing_tag_ids}")

    assert not missing_env_ids, f"The following EnvIDs are missing in environment translation.csv: {missing_env_ids}"
    assert not missing_tag_ids, f"The following TagIDs are missing in tag translation.csv: {missing_tag_ids}"
