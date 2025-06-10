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

def test_tag_mishear_ids_exist_in_mishearing():
    mishearing_dir = os.getenv('MISHEARING_DIR', os.path.join(os.path.dirname(__file__), '../data/mishearing'))
    tag_dir = os.getenv('TAG_DIR', os.path.join(os.path.dirname(__file__), '../data/tag'))

    mishearing_files = get_csv_files(mishearing_dir)
    tag_files = get_csv_files(tag_dir)

    for tag_file in tag_files:
        tag_path = os.path.join(tag_dir, tag_file)
        mishearing_path = os.path.join(mishearing_dir, tag_file)

        if not os.path.exists(mishearing_path):
            continue

        tag_mishear_ids = get_mishear_ids(tag_path)
        mishearing_mishear_ids = get_mishear_ids(mishearing_path)

        missing_ids = tag_mishear_ids - mishearing_mishear_ids

        assert not missing_ids, f"The following MishearIDs in {tag_file} do not exist in the corresponding mishearing file: {missing_ids}"