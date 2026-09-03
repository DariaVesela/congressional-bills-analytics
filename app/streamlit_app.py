import duckdb
import queries
import requests
import streamlit as st
from config import WAREHOUSE_URL


@st.cache_resource  # download data once, store it
def get_connection():
    response = requests.get(WAREHOUSE_URL, timeout=30)
    response.raise_for_status()
    with open("warehouse.duckdb", "wb") as f:
        f.write(response.content)
    return duckdb.connect("warehouse.duckdb", read_only=True)


st.set_page_config(
    page_title="US Bills Progression Analysis",
    layout="centered",
    initial_sidebar_state="auto",
)
st.title("US Bills Progression Analysis")

con = get_connection()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Bills Tracked", queries.get_total_bills_tracked(con))
col2.metric("Bills Past Committee", f"{queries.get_percent_advanced(con):.0f}%")
col3.metric("Became Law", f"{queries.get_percent_became_law(con):.0f}%")
col4.metric(
    "Median Days to First Action",
    round(queries.get_median_days_to_first_committee_action(con)),
)
