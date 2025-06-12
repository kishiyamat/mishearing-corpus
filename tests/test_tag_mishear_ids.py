import os
import csv
from scripts.utils import get_csv_files
from loguru import logger

def get_mishear_ids(file_path):
    mishear_ids = set()
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mishear_ids.add(row['MishearID'])
    return mishear_ids

SCRIPT_DIR = os.path.dirname(__file__)
MISHEARING_DIR = os.path.join(SCRIPT_DIR, '../data/mishearing')
TAG_DIR = os.path.join(SCRIPT_DIR, '../data/tag')
ENVIRONMENT_DIR = os.path.join(SCRIPT_DIR, '../data/environment')

MISHEARING_FILES = get_csv_files(MISHEARING_DIR)

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
        mishearing_mishear_ids = get_mishear_ids(mishearing_path)
        tag_mishear_ids = get_mishear_ids(tag_path)
        environment_mishear_ids = get_mishear_ids(environment_path)

        missing_in_tag = mishearing_mishear_ids - tag_mishear_ids
        missing_in_environment = mishearing_mishear_ids - environment_mishear_ids

        if missing_in_tag:
            logger.error(f"The following MishearIDs in {file_i} do not exist in the corresponding tag file: {missing_in_tag}")
        if missing_in_environment:
            logger.error(f"The following MishearIDs in {file_i} do not exist in the corresponding environment file: {missing_in_environment}")

        assert not missing_in_tag, f"The following MishearIDs in {file_i} do not exist in the corresponding tag file: {missing_in_tag}"
        assert not missing_in_environment, f"The following MishearIDs in {file_i} do not exist in the corresponding environment file: {missing_in_environment}"