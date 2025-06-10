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

    return pd.concat(merged_dataframes, ignore_index=True)

# Paths to the directories
mishearing_path = "data/mishearing"
tag_path = "data/tag"

# Streamlit app
st.title("Merged CSV Viewer")

try:
    merged_data = merge_files(mishearing_path, tag_path)

    # Extract unique tags
    unique_tags = merged_data["Tags"].explode().dropna().unique()

    # Multi-select for tags (multiple selection)
    selected_tags = st.multiselect("Select Tags to Filter", options=unique_tags)
    filter_mode = st.radio("Filter Mode", ("AND", "OR"), horizontal=True)

    if selected_tags:
        if filter_mode == "AND":
            filtered_data = merged_data[merged_data["Tags"].apply(lambda tags: all(tag in tags for tag in selected_tags) if tags else False)]
        else:  # OR mode
            filtered_data = merged_data[merged_data["Tags"].apply(lambda tags: any(tag in tags for tag in selected_tags) if tags else False)]

        st.write("### Filtered Data")
        st.write(filtered_data)
    else:
        st.write("### Merged Data (Preview)")
        st.write(merged_data.head())
except Exception as e:
    st.error(f"An error occurred: {e}")