import requests


import streamlit as st
import json


from pathlib import Path
from joblib import Memory

# 1. Google Search
memory = Memory(location=Path(".cache"), verbose=0)
GOOGLE_SEARCH_ENDPOINT = "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items"


@memory.cache
def google_search(
    queries: str,
    results_per_page: int,
    max_pages_per_query: int,
):
    payload = {
        "queries": queries,
        "resultsPerPage": results_per_page,
        "maxPagesPerQuery": max_pages_per_query,
        "countryCode": "jp",
        "searchLanguage": "ja",
        "languageCode": "ja"
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f'Bearer {st.secrets["apify"]["token"]}'
    }
    try:
        # Send API request
        response = requests.request("POST", GOOGLE_SEARCH_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes

        # Print response
        try:
            response_text = response.text  # Get response text
            response_json_pages = json.loads(response_text)  # Parse text as JSON
            return response_json_pages
        except json.JSONDecodeError as e:
            st.error(f"Error parsing response text as JSON: {e}")

    except requests.exceptions.RequestException as e:
        st.error(f"Error making API request: {e}")
    except ValueError as e:
        st.error(f"Error parsing response: {e}")