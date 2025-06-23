import streamlit as st
from pages.src.google_to_star_no_kikimatigai import run_apify_actor
from pages.src.google_to_star_no_kikimatigai import scrape

st.write("""This tab is for Apify integration.
まず、GoogleのAPIを使って検索を行い、結果を取得します。

            """)
queries = st.text_input("Query to apply loop")
save_path = st.text_input("base path (Loop): ", "/home/kishiyamat/mishearing-corpus/directory")
results_per_page = st.number_input("results_per_page (loop)", 10)
max_pages_per_query = st.number_input("max_pages_per_query (loop)",1)
if not queries:
    st.warning("Please enter a query to run the Apify Actor.")
else: 
    if st.button("Run Apify Actor Loop"):
        # Initialize the ApifyClient with your Apify API token
        # Replace '<YOUR_API_TOKEN>' with your token.
        run_input = {
            "queries": queries,
            "results_per_page": results_per_page,
            "max_pages_per_query": max_pages_per_query,
        }
        dataset = run_apify_actor(**run_input)
        for item in dataset:
            for organic_result in item["organicResults"]:
                st.write(organic_result["url"])
                scrape(organic_result["url"], save_path)
        # You can add your Apify-related code here if needed.
        # organicResults に検索結果が入っているので、そこから必要な情報を抽出して表示することができます。
