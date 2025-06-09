import os

def get_csv_files(directory):
    csv_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.csv'):
                relative_path = os.path.relpath(os.path.join(root, file), directory)
                csv_files.append(relative_path)
    return set(csv_files)

def test_matching_filenames():
    mishearing_dir = '/home/kishiyamat/mishearing-corpus/data/mishearing'
    tags_dir = '/home/kishiyamat/mishearing-corpus/data/tags'

    mishearing_files = get_csv_files(mishearing_dir)
    tags_files = get_csv_files(tags_dir)

    missing_files = tags_files - mishearing_files

    assert not missing_files, f"The following files in tags/**/.*.csv do not have corresponding files in mishearing/**/.*.csv: {missing_files}"