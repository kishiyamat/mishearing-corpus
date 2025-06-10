import streamlit as st
import duckdb

# Initialize DuckDB connection
db_connection = duckdb.connect(database=':memory:')

# Streamlit app title
st.title("Tag-Based Search App")

# Sidebar for query composition
st.sidebar.header("Compose Your Query")
selected_tags = st.sidebar.multiselect("Select Tags", options=["tag1", "tag2", "tag3"], default=[])
query_text = st.sidebar.text_input("Search Text (Future Feature)", "")

# Query execution
if st.sidebar.button("Search"):
    query = "SELECT * FROM data WHERE tags IN ({})".format(", ".join([f"'{tag}'" for tag in selected_tags]))
    try:
        results = db_connection.execute(query).fetchall()
        st.write("Results:", results)
    except Exception as e:
        st.error(f"Error executing query: {e}")

# Footer
st.sidebar.write("Powered by DuckDB and Streamlit")