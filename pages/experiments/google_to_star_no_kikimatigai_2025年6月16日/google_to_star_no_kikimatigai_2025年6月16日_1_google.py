import streamlit as st
from pages.experiments.src.google_to_star_no_kikimatigai import run_apify_actor

st.write("""
## Google Search Integration

This tab allows you to run a Google search using the Apify Actor.
It uses cache to make the search faster, more efficient and replicable.
""")

st.write("This tab is for Apify integration. Currently, it is not implemented.")
queries = st.text_input("Google Search Query", '"と*の聞き間違"')
results_per_page = st.number_input("results_per_page", 10)
max_pages_per_query = st.number_input("max_pages_per_query (1しか動かない)",1)
if not queries:
    st.warning("Please enter a query to run the Apify Actor.")
else: 
    if st.button("Run Apify Actor"):
        # Initialize the ApifyClient with your Apify API token
        # Replace '<YOUR_API_TOKEN>' with your token.
        run_input = {
            "queries": queries,
            "results_per_page": results_per_page,
            "max_pages_per_query": max_pages_per_query,
        }
        dataset = run_apify_actor(**run_input)
        items = []
        for item in dataset:
            items.extend(item["organicResults"]) 
        st.write(len(items))
        # You can add your Apify-related code here if needed.
        # organicResults に検索結果が入っているので、そこから必要な情報を抽出して表示することができます。