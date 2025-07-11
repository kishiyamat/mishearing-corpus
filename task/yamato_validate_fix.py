import os
import pandas as pd
import argparse

def main(dir1, dir2):
    # Retrieve all CSV files from both directories
    files_dir1 = [f for f in os.listdir(dir1) if f.endswith('.csv')]
    files_dir2 = [f for f in os.listdir(dir2) if f.endswith('.csv')]

    # Compare files (双方向)
    for file in files_dir1:
        if file in files_dir2:  # Check if the file exists in both directories
            file_path1 = os.path.join(dir1, file)
            file_path2 = os.path.join(dir2, file)

            # Read the CSV files
            df1 = pd.read_csv(file_path1)
            df2 = pd.read_csv(file_path2)

            # Check if 'Tgt' and 'Src' columns exist in both files
            if {'Tgt', 'Src'}.issubset(df1.columns) and {'Tgt', 'Src'}.issubset(df2.columns):
                # Compare the columns
                if not df1[['Tgt', 'Src']].equals(df2[['Tgt', 'Src']]):
                    print(f"Discrepancy found in file: {file}")
            else:
                print(f"Missing 'Tgt' or 'Src' columns in file: {file}")
        else:
            print(f"File {file} is not present in both directories.")

if __name__ == "__main__":
    d_1 = "./data/mishearing/yamato_gochou/relevant/"
    d_2 = "./data/mishearing/yamato_gochou/relevant/fixed/"

    parser = argparse.ArgumentParser(description="Compare CSV files in two directories.")
    parser.add_argument("dir1", nargs="?", default=d_1, help="Path to the first directory (default: ./dir1)")
    parser.add_argument("dir2", nargs="?", default=d_2, help="Path to the second directory (default: ./dir2)")
    args = parser.parse_args()

    main(args.dir1, args.dir2)