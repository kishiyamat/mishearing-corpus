import os

def get_csv_files(directory):
    """
    Recursively retrieves all CSV files in the given directory.

    Args:
        directory (str): The directory to search for CSV files.

    Returns:
        set: A set of relative paths to CSV files found in the directory.
    """
    csv_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.csv'):
                relative_path = os.path.relpath(os.path.join(root, file), directory)
                csv_files.append(relative_path)
    return set(csv_files)