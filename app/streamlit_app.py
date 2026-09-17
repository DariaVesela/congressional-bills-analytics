import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from config import WAREHOUSE_URL
from queries import (
    BILL_STATUSES,
    Filters,
    get_bill_volume_by_policy,
    get_committee_prioritization,
    get_introduced_date_bounds,
    get_median_days_to_first_committee_action,
    get_median_days_to_furthest_stage_by_policy,
    get_percent_advanced,
    get_percent_became_law,
    get_policy_areas,
    get_sponsor_parties,
    get_stage_distribution,
    get_stage_transition_durations,
    get_total_bills_tracked,
)

CHAMBERS = ["House", "Senate"]
PARTY_LABELS = {"D": "Democrat", "R": "Republican", "I": "Independent"}


def _format_percent(value):
    return "N/A" if value is None else f"{value:.0f}%"


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

# --- Sidebar filters ---

min_date, max_date = get_introduced_date_bounds(con)

with st.sidebar:
    st.header("Filters")
    selected_policy_areas = st.multiselect("Policy area", get_policy_areas(con))
    selected_chamber = st.selectbox("Chamber", ["All"] + CHAMBERS)
    selected_party = st.selectbox(
        "Sponsor party",
        ["All"] + get_sponsor_parties(con),
        format_func=lambda p: PARTY_LABELS.get(p, p),
    )
    selected_status = st.selectbox("Bill status", ["All"] + BILL_STATUSES)
    selected_date_range = st.date_input(
        "Introduced date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

introduced_after, introduced_before = None, None
if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
    introduced_after, introduced_before = selected_date_range

filters = Filters(
    policy_areas=selected_policy_areas,
    chamber=None if selected_chamber == "All" else selected_chamber,
    sponsor_party=None if selected_party == "All" else selected_party,
    bill_status=None if selected_status == "All" else selected_status,
    introduced_after=introduced_after,
    introduced_before=introduced_before,
)

# --- KPI strip ---

col1, col2, col3, col4 = st.columns(4)
col1.metric("Bills Tracked", get_total_bills_tracked(con, filters))
col2.metric("Bills Past Committee", _format_percent(get_percent_advanced(con, filters)))
col3.metric("Became Law", _format_percent(get_percent_became_law(con, filters)))
median_days = get_median_days_to_first_committee_action(con, filters)
col4.metric(
    "Median Days to First Action",
    round(median_days) if median_days is not None else "N/A",
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
        node={"label": labels, "pad": 20, "thickness": 20},
        link={
                "source": [0, 0, 1, 1, 2, 2],
                "target": [1, 4, 2, 5, 3, 6],
                "value": [
                    reached_floor_or_beyond,   # Committee -> Floor
                    committee,                  # Committee -> Stalled at Committee
                    reached_passed_or_beyond,  # Floor -> Passed Chamber
                    floor,                      # Floor -> Stalled at Floor
                    became_law,                 # Passed Chamber -> Became Law
                    passed,                     # Passed Chamber -> Stalled after Passing
    ],
},
    ))
    return fig

stage_df = get_stage_distribution(con, filters)
fig_sankey = build_sankey_figure(stage_df)
st.plotly_chart(fig_sankey)

# --- Graph 2: bill volume by policy area ---
volume_df = get_bill_volume_by_policy(con, filters)
fig_volume = px.bar(
    volume_df,
    x="primary_policy_area",
    y="bill_volume",
    labels={"primary_policy_area": "Policy area", "bill_volume": "Bills"},
)
st.plotly_chart(fig_volume)

# --- Graph 3: median days to furthest stage by policy area ---
speed_df = get_median_days_to_furthest_stage_by_policy(con, filters)
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

bottleneck_df = get_stage_transition_durations(con, filters)
fig_bottleneck = px.bar(
    bottleneck_df,
    x="stage",
    y=["median_days", "p90_days"],
    barmode="group",
    labels={"stage": "Stage", "value": "Days", "variable": ""},
)
st.plotly_chart(fig_bottleneck)

scatter_df = get_committee_prioritization(con, filters)

fig_prioritization = px.scatter(
    scatter_df,
    x="median_dwell_days",
    y="advancement_rate",
    size="bill_count",
    hover_name="primary_policy_area",
    hover_data=["bill_count"],
    labels={
        "median_dwell_days": "Median days in Committee",
        "advancement_rate": "Advancement rate (%)",
        "primary_policy_area": "Policy area",
    },
)
st.plotly_chart(fig_prioritization)