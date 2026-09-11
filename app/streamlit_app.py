import duckdb
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from config import WAREHOUSE_URL
from queries import (
    get_total_bills_tracked,
    get_percent_advanced,
    get_percent_became_law,
    get_median_days_to_first_committee_action,
    get_bill_volume_by_policy,
    get_median_days_to_furthest_stage_by_policy,
    get_stage_distribution
)


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

# --- KPI strip ---

col1, col2, col3, col4 = st.columns(4)
col1.metric("Bills Tracked", get_total_bills_tracked(con))
col2.metric("Bills Past Committee", f"{get_percent_advanced(con):.0f}%")
col3.metric("Became Law", f"{get_percent_became_law(con):.0f}%")
col4.metric(
    "Median Days to First Action",
    round(get_median_days_to_first_committee_action(con)),
)

# --- Graph 4: sankey chart showing bill progression ---

def build_sankey_figure(stage_df: pd.DataFrame):
    counts = dict(zip(stage_df["furthest_stage_order"], stage_df["bill_count"]))
    committee = counts.get(2, 0)
    floor = counts.get(3, 0)
    passed = counts.get(4, 0)
    became_law = counts.get(5, 0)

    reached_floor_or_beyond = floor + passed + became_law
    reached_passed_or_beyond = passed + became_law

    labels = [
        "Committee", "Floor", "Passed Chamber", "Became Law",
        "Stalled at Committee", "Stalled at Floor", "Stalled after Passing",
    ]
    #            0            1          2                3            4                       5                   6

    fig = go.Figure(go.Sankey(
        node=dict(label=labels, pad=20, thickness=20),
        link=dict(
            source=[0, 0, 1, 1, 2, 2],
            target=[1, 4, 2, 5, 3, 6],
            value=[
                reached_floor_or_beyond,   # Committee -> Floor
                committee,                  # Committee -> Stalled at Committee
                reached_passed_or_beyond,  # Floor -> Passed Chamber
                floor,                      # Floor -> Stalled at Floor
                became_law,                 # Passed Chamber -> Became Law
                passed,                     # Passed Chamber -> Stalled after Passing
            ],
        ),
    ))
    return fig

stage_df = get_stage_distribution(con)
fig_sankey = build_sankey_figure(stage_df)
st.plotly_chart(fig_sankey)

# --- Graph 2: bill volume by policy area ---
volume_df = get_bill_volume_by_policy(con)
fig_volume = px.bar(
    volume_df,
    x="primary_policy_area",
    y="bill_volume",
    labels={"primary_policy_area": "Policy area", "bill_volume": "Bills"},
)
st.plotly_chart(fig_volume)

# --- Graph 3: median days to furthest stage by policy area ---
speed_df = get_median_days_to_furthest_stage_by_policy(con)
fig_speed = px.bar(
    speed_df,
    x="primary_policy_area",
    y="median_days",
    color="bill_count",
    color_continuous_scale="Blues",
    hover_data=["bill_count"],
    labels={"primary_policy_area": "Policy area", "median_days": "Median days", "bill_count": "Bills"},
)
st.plotly_chart(fig_speed)