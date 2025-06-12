import pandas as pd
import glob
import os
import streamlit as st

# Function to recursively load all CSV files in a directory
def load_all_csv(directory):
    csv_files = glob.glob(os.path.join(directory, "**/*.csv"), recursive=True)
    dataframes = [pd.read_csv(file) for file in csv_files]
    return pd.concat(dataframes, ignore_index=True)

# Function to create unique sets of Tags and Environments
def create_unique_sets(tag_path, env_path):
    tag_data = load_all_csv(tag_path)
    env_data = load_all_csv(env_path)

    tag_counts = tag_data['TagID'].value_counts()
    env_counts = env_data['EnvID'].value_counts()

    return tag_data, env_data, tag_counts, env_counts

# Function to apply translations
def apply_translation(items, translation_df, lang):
    translation_dict = translation_df[translation_df['Lang'] == lang].set_index(translation_df.columns[0])['Label'].to_dict()
    return [translation_dict.get(item, item) for item in items]

# Paths to the directories
mishearing_path = "data/mishearing"
tag_path = "data/tag"
env_path = "data/environment"
tag_translation_path = "data/tag/translation.csv"
env_translation_path = "data/environment/translation.csv"

# Streamlit app
st.title("Mishearing Corpus Viewer")

# Language selection
default_language = "Japanese"
selected_language = st.radio("Language", ("English", "Japanese"), horizontal=True, key="language", index=(0 if default_language == "English" else 1))

# Create unique sets of Tags and Environments
tag_data, env_data, tag_counts, env_counts = create_unique_sets(tag_path, env_path)

# Load translation tables
tag_translation = pd.read_csv(tag_translation_path)
env_translation = pd.read_csv(env_translation_path)

# Translate Tags and Environments
translated_tags = apply_translation(tag_counts.index.tolist(), tag_translation, selected_language)
translated_envs = apply_translation(env_counts.index.tolist(), env_translation, selected_language)

# Display distribution of Tags and Environments
st.write("### Tag Distribution")
tag_counts.index = translated_tags
st.bar_chart(tag_counts)

st.write("### Environment Distribution")
env_counts.index = translated_envs
st.bar_chart(env_counts)

# Multi-select for Tags and Environments
selected_tags = st.multiselect("Select Tags to Filter", options=translated_tags, default=None)
selected_envs = st.multiselect("Select Environments to Filter", options=translated_envs, default=None)

# Load Mishearing data
mishearing_data = load_all_csv(mishearing_path)

# Filter MishearID based on selected Tags and Environments
filtered_mishear_ids = mishearing_data['MishearID'][
    mishearing_data['MishearID'].isin(tag_data[tag_data['TagID'].isin(tag_counts.index.tolist() if not selected_tags else selected_tags)]['MishearID']) &
    mishearing_data['MishearID'].isin(env_data[env_data['EnvID'].isin(env_counts.index.tolist() if not selected_envs else selected_envs)]['MishearID'])
]

# Display filtered Mishearing data
st.write("### Filtered Mishearing Data")
st.write(mishearing_data[mishearing_data['MishearID'].isin(filtered_mishear_ids)])
