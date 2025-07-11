import os
import csv
import re
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


def test_envid_tagid_format():
    """
    Test to ensure that all EnvIDs and TagIDs in the translation.csv files
    conform to the [A-Z], [0-9], _, and - character range.
    """
    invalid_ids = []

    # Check EnvID in environment/translation.csv
    with open(ENV_TRANSLATION_PATH, 'r', encoding='utf-8') as env_file:
        reader = csv.DictReader(env_file)
        for row in reader:
            if not re.match(r'^[A-Z0-9_-]+$', row['EnvID']):
                invalid_ids.append(("EnvID", row['EnvID'], ENV_TRANSLATION_PATH))

    # Check TagID in tag/translation.csv
    with open(TAG_TRANSLATION_PATH, 'r', encoding='utf-8') as tag_file:
        reader = csv.DictReader(tag_file)
        for row in reader:
            if not re.match(r'^[A-Z0-9_-]+$', row['TagID']):
                invalid_ids.append(("TagID", row['TagID'], TAG_TRANSLATION_PATH))

    if invalid_ids:
        for id_type, invalid_id, file_path in invalid_ids:
            logger.error(f"Invalid {id_type} '{invalid_id}' found in file: {file_path}")

        # Additional step: List files in environment/ or tag/ containing invalid IDs
        files_with_invalid_ids = []
        for root, _, files in os.walk(ENVIRONMENT_DIR):
            for file in files:
                if file.endswith('.csv') and file != 'translation.csv':
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as csv_file:
                        reader = csv.DictReader(csv_file)
                        for row in reader:
                            if row.get('EnvID') in [invalid_id for id_type, invalid_id, _ in invalid_ids if id_type == "EnvID"]:
                                files_with_invalid_ids.append(file_path)
                                break

        for root, _, files in os.walk(TAG_DIR):
            for file in files:
                if file.endswith('.csv') and file != 'translation.csv':
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as csv_file:
                        reader = csv.DictReader(csv_file)
                        for row in reader:
                            if row.get('TagID') in [invalid_id for id_type, invalid_id, _ in invalid_ids if id_type == "TagID"]:
                                files_with_invalid_ids.append(file_path)
                                break

        if files_with_invalid_ids:
            logger.error(f"Files in environment/ or tag/ containing invalid IDs: {files_with_invalid_ids}")

    assert not invalid_ids, f"Invalid IDs found: {invalid_ids}"

def test_tag_environment_exist():
    """
    Test to verify the existence of corresponding 'tag' and 'environment' files 
    for each file in the MISHEARING_FILES list.

    This function checks if the required files are present in their respective 
    directories (TAG_DIR and ENVIRONMENT_DIR). If either the 'tag' or 'environment' 
    file is missing for a given file, a warning is logged, and an AssertionError 
    is raised to indicate the missing files.

    Raises:
        AssertionError: If the corresponding 'tag' or 'environment' file is missing 
                        for any file in MISHEARING_FILES.
    """
    # other columns: tag, environment
    for file_i in MISHEARING_FILES:
        tag_path = os.path.join(TAG_DIR, file_i)
        environment_path = os.path.join(ENVIRONMENT_DIR, file_i)

        if not os.path.exists(tag_path) or not os.path.exists(environment_path):
            logger.warning(f"Skipping {file_i} as corresponding mishearing or environment file is missing.")
            raise AssertionError(f"Missing corresponding files for {file_i}. Ensure all files are present in the directories.")

def test_mishear_ids_exist_in_other_columns():
    """
    Test function to verify that all `MishearID` values in the mishearing files exist in the corresponding tag and environment files.

    This function iterates through a list of mishearing files, checks the presence of `MishearID` values in the corresponding tag and environment files, 
    and logs errors for any missing IDs. It also asserts that there are no missing IDs, ensuring data consistency across the files.

    Steps:
    1. For each file in `MISHEARING_FILES`, construct paths for the mishearing, tag, and environment files.
    2. Extract `MishearID` values from each file using the `get_ids` function.
    3. Compare `MishearID` values from the mishearing file against those in the tag and environment files.
    4. Log errors for any missing IDs and raise assertion errors if discrepancies are found.

    Assertions:
    - Ensures that all `MishearID` values in the mishearing file exist in the corresponding tag file.
    - Ensures that all `MishearID` values in the mishearing file exist in the corresponding environment file.

    Raises:
    - AssertionError: If any `MishearID` values are missing in the tag or environment files.

    Logging:
    - Logs the processing of each file.
    - Logs errors for missing `MishearID` values in the tag and environment files.

    Dependencies:
    - `MISHEARING_FILES`: List of filenames to process.
    - `MISHEARING_DIR`, `TAG_DIR`, `ENVIRONMENT_DIR`: Directories containing the respective files.
    - `get_ids`: Function to extract IDs from a file.
    - `logger`: Logger instance for logging information and errors.
    """
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
            logger.error(f"The following MishearIDs in Tag{file_i} (Tags) do not exist in the corresponding tag file: {missing_in_tag}")
        if missing_in_environment:
            logger.error(f"The following MishearIDs in {file_i} (Envs) do not exist in the corresponding environment file: {missing_in_environment}")

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

    env_translation_ids = get_ids(ENV_TRANSLATION_PATH, 'EnvID')
    tag_translation_ids = get_ids(TAG_TRANSLATION_PATH, 'TagID')

    for file_i in environment_files:
        if file_i != 'translation.csv':
            env_id = get_ids(os.path.join(ENVIRONMENT_DIR, file_i), 'EnvID')
            env_ids.update(env_id)
            # 個別にしりたければ、以下のコメントアウトを有効にする
            # assert env_id.issubset(env_translation_ids), f"EnvID {env_id} in {file_i} is not in translation.csv"

    for file_i in tag_files:
        if file_i != 'translation.csv':
            tag_id = get_ids(os.path.join(TAG_DIR, file_i), 'TagID')
            tag_ids.update(tag_id)
            # 個別にしりたければ、以下のコメントアウトを有効にする
            # assert tag_id.issubset(tag_translation_ids), f"TagID {tag_id} in {file_i} is not in translation.csv"

    missing_env_ids = env_ids - env_translation_ids
    missing_tag_ids = tag_ids - tag_translation_ids

    if missing_env_ids:
        logger.error(f"The following EnvIDs are missing in environment translation.csv: {missing_env_ids}")
    if missing_tag_ids:
        logger.error(f"The following TagIDs are missing in tag translation.csv: {missing_tag_ids}")

    assert not missing_env_ids, f"The following EnvIDs are missing in environment translation.csv: {missing_env_ids}"
    assert not missing_tag_ids, f"The following TagIDs are missing in tag translation.csv: {missing_tag_ids}"

def test_no_japanese_in_csv():
    """
    Test to ensure that no Japanese characters exist in any CSV files
    under TAG_DIR and ENVIRONMENT_DIR, excluding translation.csv files.
    """
    invalid_files = []

    # Define a regex pattern to detect Japanese characters
    japanese_pattern = re.compile(r'[\u3040-\u30FF\u4E00-\u9FFF]+')

    # Check all CSV files in TAG_DIR
    for root, _, files in os.walk(TAG_DIR):
        for file in files:
            if file.endswith('.csv') and file != 'translation.csv':
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as csv_file:
                    for line in csv_file:
                        if japanese_pattern.search(line):
                            invalid_files.append(file_path)
                            break

    # Check all CSV files in ENVIRONMENT_DIR
    for root, _, files in os.walk(ENVIRONMENT_DIR):
        for file in files:
            if file.endswith('.csv') and file != 'translation.csv':
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as csv_file:
                    for line in csv_file:
                        if japanese_pattern.search(line):
                            invalid_files.append(file_path)
                            break

    if invalid_files:
        for file_path in invalid_files:
            logger.error(f"Japanese characters found in file: {file_path}")
    assert not invalid_files, f"Japanese characters found in the following files: {invalid_files}"
