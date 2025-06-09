import os
import csv

def get_csv_files(directory):
    csv_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.csv'):
                relative_path = os.path.relpath(os.path.join(root, file), directory)
                csv_files.append(relative_path)
    return csv_files

def get_mishear_ids(file_path):
    mishear_ids = set()
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mishear_ids.add(row['MishearID'])
    return mishear_ids

def test_tags_mishear_ids_exist_in_mishearing():
    mishearing_dir = '/home/kishiyamat/mishearing-corpus/data/mishearing'
    tags_dir = '/home/kishiyamat/mishearing-corpus/data/tags'

    mishearing_files = get_csv_files(mishearing_dir)
    tags_files = get_csv_files(tags_dir)

    for tags_file in tags_files:
        tags_path = os.path.join(tags_dir, tags_file)
        mishearing_path = os.path.join(mishearing_dir, tags_file)

        if not os.path.exists(mishearing_path):
            continue

        tags_mishear_ids = get_mishear_ids(tags_path)
        mishearing_mishear_ids = get_mishear_ids(mishearing_path)

        missing_ids = tags_mishear_ids - mishearing_mishear_ids

        assert not missing_ids, f"The following MishearIDs in {tags_file} do not exist in the corresponding mishearing file: {missing_ids}"