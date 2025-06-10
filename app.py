import pandas as pd
import glob
import os
import streamlit as st

# Function to merge files using left join on MishearID
def merge_files(mishearing_path, tag_path):
    mishearing_files = glob.glob(os.path.join(mishearing_path, "*/*.csv"))
    tag_files = glob.glob(os.path.join(tag_path, "*/*.csv"))

    merged_dataframes = []

    for mishearing_file in mishearing_files:
        filename = os.path.basename(mishearing_file)
        matching_tag_file = next((tag_file for tag_file in tag_files if os.path.basename(tag_file) == filename), None)

        mishearing_df = pd.read_csv(mishearing_file)

        if matching_tag_file:
            tag_df = pd.read_csv(matching_tag_file)

            # Perform left join on MishearID
            merged_df = mishearing_df.merge(tag_df, how="left", on="MishearID")

            # Group TagID into a list if there are multiple rows for the same MishearID
            if "TagID" in merged_df.columns:
                tags_series = merged_df.groupby("MishearID")["TagID"].apply(lambda x: list(x.dropna()) if not x.empty else None)
                merged_df = merged_df.drop(columns="TagID").drop_duplicates()
                merged_df = merged_df.merge(tags_series.rename("Tags"), on="MishearID", how="left")

            merged_dataframes.append(merged_df)
        else:
            merged_dataframes.append(mishearing_df)

    return merged_dataframes

# Paths to the directories
mishearing_path = "data/mishearing"
tag_path = "data/tag"

# Streamlit app
st.title("Merged CSV Viewer")

try:
    merged_dataframes = merge_files(mishearing_path, tag_path)
    for idx, df in enumerate(merged_dataframes):
        filename = os.path.basename(glob.glob(os.path.join(mishearing_path, "*/*.csv"))[idx])
        st.write(f"### Merged DataFrame: {filename}")
        st.write(df)
except Exception as e:
    st.error(f"An error occurred: {e}")