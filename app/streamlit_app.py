from typing import Optional

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from captions import (
    describe_bill_volume,
    describe_prioritization,
    describe_speed_by_policy,
    describe_stage_bottleneck,
    describe_stage_distribution,
)
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

# Single categorical blue, used for every single-series chart so the dashboard
# reads as one system rather than each chart picking its own default hue.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
BLUE_SCALE = [[0, "#cde2fb"], [1, "#0d366b"]]  # sequential: magnitude, light -> dark
MUTED = "#898781"
CHART_HEIGHT = 380

px.defaults.template = "plotly_white"


def _format_percent(value):
    return "N/A" if value is None else f"{value:.0f}%"


def _show_table(df: pd.DataFrame, rename: dict, column_config: Optional[dict] = None):
    # Pinned to CHART_HEIGHT so a table tab is the same size as its card's
    # chart tabs — st.dataframe otherwise sizes itself to the row count,
    # which made cards resize both across tabs and against each other (e.g.
    # the 3-row bottleneck table vs. the 23-row prioritization table).
    st.dataframe(
        df.rename(columns=rename),
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        height=CHART_HEIGHT,
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
    layout="wide",
    initial_sidebar_state="expanded",
)
st.title("🏛️ US Bills Progression Analysis")
st.caption(
    "Tracking bills through the 119th Congress, from introduction through "
    "committee, floor action, and passage."
)

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

# --- KPI strip: 4 cards ---

median_days = get_median_days_to_first_committee_action(con, filters)

kpis = [
    ("Bills Tracked", get_total_bills_tracked(con, filters)),
    ("Bills Past Committee", _format_percent(get_percent_advanced(con, filters))),
    ("Became Law", _format_percent(get_percent_became_law(con, filters))),
    (
        "Median Days to First Action",
        round(median_days) if median_days is not None else "N/A",
    ),
]
for col, (label, value) in zip(st.columns(4), kpis):
    with col.container(border=True):
        st.metric(label, value)

st.divider()

# --- Bill progression (Sankey) — full-width narrative centerpiece ---

st.subheader("🔀 Bill Progression")
st.caption("Where tracked bills currently stand, from introduction through becoming law.")


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

    # Progression nodes (0-3) step through the sequential blue ramp, darkest at
    # "Became Law"; stalled/exit nodes (4-6) recede in a shared neutral gray.
    node_colors = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b", MUTED, MUTED, MUTED]

    fig = go.Figure(go.Sankey(
        node={"label": labels, "color": node_colors, "pad": 20, "thickness": 20},
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
    fig.update_layout(height=CHART_HEIGHT, margin={"t": 10, "b": 10})
    return fig


with st.container(border=True):
    stage_df = get_stage_distribution(con, filters)
    # A Sankey has no meaningful alternate chart type, so this is chart + table only.
    tab_chart, tab_table = st.tabs(["Chart", "Table"])
    with tab_chart:
        fig_sankey = build_sankey_figure(stage_df)
        st.plotly_chart(fig_sankey, use_container_width=True, key="sankey_chart")
    with tab_table:
        _show_table(
            stage_df,
            {
                "furthest_stage_order": "Stage order",
                "furthest_stage_reached": "Furthest stage",
                "bill_count": "Bills",
            },
        )
    st.caption(describe_stage_distribution(stage_df))

st.divider()

# --- Supporting graphs: 2x2 grid for direct side-by-side comparison ---

st.subheader("📊 Policy Area Breakdown")
st.caption("Volume, speed, bottlenecks, and prioritization across policy areas.")

row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2 = st.columns(2)

with row1_col1.container(border=True):
    st.markdown("**Bill Volume by Policy Area**")
    volume_df = get_bill_volume_by_policy(con, filters)
    tab_bar, tab_hbar, tab_treemap, tab_table = st.tabs(["Bar", "Horizontal Bar", "Treemap", "Table"])
    with tab_bar:
        fig_volume = px.bar(
            volume_df,
            x="primary_policy_area",
            y="bill_volume",
            color_discrete_sequence=[BLUE],
            labels={"primary_policy_area": "Policy area", "bill_volume": "Bills"},
            height=CHART_HEIGHT,
        )
        st.plotly_chart(fig_volume, use_container_width=True, key="volume_bar")
    with tab_hbar:
        # Horizontal orientation sidesteps the ~45deg rotated category labels
        # the vertical version above has with 10 policy areas on the x-axis.
        fig_volume_h = px.bar(
            volume_df,
            x="bill_volume",
            y="primary_policy_area",
            orientation="h",
            color_discrete_sequence=[BLUE],
            labels={"primary_policy_area": "Policy area", "bill_volume": "Bills"},
            height=CHART_HEIGHT,
        )
        fig_volume_h.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_volume_h, use_container_width=True, key="volume_hbar")
    with tab_treemap:
        fig_volume_treemap = px.treemap(
            volume_df,
            path=["primary_policy_area"],
            values="bill_volume",
            color="bill_volume",
            color_continuous_scale=BLUE_SCALE,
            labels={"primary_policy_area": "Policy area", "bill_volume": "Bills"},
            height=CHART_HEIGHT,
        )
        fig_volume_treemap.update_layout(margin={"t": 10, "b": 10, "l": 10, "r": 10})
        st.plotly_chart(fig_volume_treemap, use_container_width=True, key="volume_treemap")
    with tab_table:
        _show_table(volume_df, {"primary_policy_area": "Policy area", "bill_volume": "Bills"})
    st.caption(describe_bill_volume(volume_df))

def build_lollipop_figure(speed_df: pd.DataFrame):
    df = speed_df.sort_values("median_days")
    fig = go.Figure()
    for _, row in df.iterrows():
        fig.add_shape(
            type="line",
            x0=0, x1=row["median_days"],
            y0=row["primary_policy_area"], y1=row["primary_policy_area"],
            line={"color": MUTED, "width": 2},
        )
    fig.add_trace(go.Scatter(
        x=df["median_days"],
        y=df["primary_policy_area"],
        mode="markers",
        marker={"size": 10, "color": BLUE},
        customdata=df["bill_count"],
        hovertemplate="%{y}<br>Median days: %{x}<br>Bills: %{customdata}<extra></extra>",
    ))
    fig.update_layout(
        height=CHART_HEIGHT,
        xaxis_title="Median days",
        yaxis_title="Policy area",
        showlegend=False,
        margin={"t": 10, "b": 10},
    )
    return fig


with row1_col2.container(border=True):
    st.markdown("**Speed to Furthest Stage**")
    speed_df = get_median_days_to_furthest_stage_by_policy(con, filters)
    tab_bar, tab_lollipop, tab_table = st.tabs(["Bar", "Lollipop", "Table"])
    with tab_bar:
        fig_speed = px.bar(
            speed_df,
            x="primary_policy_area",
            y="median_days",
            color="bill_count",
            color_continuous_scale=BLUE_SCALE,
            hover_data=["bill_count"],
            labels={"primary_policy_area": "Policy area", "median_days": "Median days", "bill_count": "Bills"},
            height=CHART_HEIGHT,
        )
        # The ~23 long, rotated policy-area labels eat most of the figure's
        # vertical space via Plotly's automargin, which shrinks the plot
        # domain the colorbar's "len" is a *fraction of* down to a few
        # pixels. Pin the colorbar to an absolute pixel length instead so it
        # stays readable regardless of how much room the x-axis needs.
        fig_speed.update_layout(
            coloraxis_colorbar={
                "len": 220,
                "lenmode": "pixels",
                "thickness": 15,
                "thicknessmode": "pixels",
                "tickfont": {"size": 11},
                "y": 1,
                "yanchor": "top",
            }
        )
        st.plotly_chart(fig_speed, use_container_width=True, key="speed_bar")
    with tab_lollipop:
        # Horizontal layout (policy areas on the y-axis) sidesteps the same
        # rotated-label problem as the horizontal bar in the Volume section.
        fig_speed_lollipop = build_lollipop_figure(speed_df)
        st.plotly_chart(fig_speed_lollipop, use_container_width=True, key="speed_lollipop")
    with tab_table:
        _show_table(
            speed_df,
            {"primary_policy_area": "Policy area", "median_days": "Median days", "bill_count": "Bills"},
        )
    st.caption(describe_speed_by_policy(speed_df))

with row2_col1.container(border=True):
    st.markdown("**Stage Bottlenecks**")
    bottleneck_df = get_stage_transition_durations(con, filters)
    # A true box plot (full distribution) is a stretch goal deferred until a
    # query change returns raw per-bill durations instead of pre-aggregated
    # median/p90 — see E05-S07F. Chart + table only for now.
    tab_bar, tab_table = st.tabs(["Bar", "Table"])
    with tab_bar:
        fig_bottleneck = px.bar(
            bottleneck_df,
            x="stage",
            y=["median_days", "p90_days"],
            barmode="group",
            color_discrete_sequence=[BLUE, ORANGE],
            labels={"stage": "Stage", "value": "Days", "variable": ""},
            height=CHART_HEIGHT,
        )
        st.plotly_chart(fig_bottleneck, use_container_width=True, key="bottleneck_bar")
    with tab_table:
        _show_table(
            bottleneck_df,
            {
                "stage": "Stage",
                "median_days": "Median days",
                "p90_days": "90th percentile days",
                "sample_size": "Sample size",
            },
        )
    st.caption(describe_stage_bottleneck(bottleneck_df))

def build_prioritization_scatter(scatter_df: pd.DataFrame):
    return px.scatter(
        scatter_df,
        x="median_dwell_days",
        y="advancement_rate",
        size="bill_count",
        color_discrete_sequence=[BLUE],
        hover_name="primary_policy_area",
        hover_data=["bill_count"],
        labels={
            "median_dwell_days": "Median days in Committee",
            "advancement_rate": "Advancement rate (%)",
            "primary_policy_area": "Policy area",
        },
        height=CHART_HEIGHT,
    )


def build_quadrant_figure(scatter_df: pd.DataFrame):
    fig = build_prioritization_scatter(scatter_df)

    valid = scatter_df.dropna(subset=["median_dwell_days"])
    if valid.empty:
        return fig

    median_x = valid["median_dwell_days"].median()
    median_y = scatter_df["advancement_rate"].median()
    fig.add_vline(x=median_x, line_dash="dot", line_color=MUTED)
    fig.add_hline(y=median_y, line_dash="dot", line_color=MUTED)

    x_min, x_max = valid["median_dwell_days"].min(), valid["median_dwell_days"].max()
    y_min, y_max = scatter_df["advancement_rate"].min(), scatter_df["advancement_rate"].max()
    label_style = {"showarrow": False, "font": {"color": MUTED, "size": 11}}
    fig.add_annotation(x=x_min, y=y_max, xanchor="left", yanchor="top", text="Fast-tracked", **label_style)
    fig.add_annotation(x=x_max, y=y_max, xanchor="right", yanchor="top", text="Slow but advancing", **label_style)
    fig.add_annotation(x=x_min, y=y_min, xanchor="left", yanchor="bottom", text="Quick dead-ends", **label_style)
    fig.add_annotation(x=x_max, y=y_min, xanchor="right", yanchor="bottom", text="Bottlenecked", **label_style)
    return fig


with row2_col2.container(border=True):
    st.markdown("**Committee Prioritization**")
    scatter_df = get_committee_prioritization(con, filters)
    tab_scatter, tab_quadrant, tab_table = st.tabs(["Scatter", "Quadrant View", "Table"])
    with tab_scatter:
        st.plotly_chart(
            build_prioritization_scatter(scatter_df), use_container_width=True, key="prioritization_scatter"
        )
    with tab_quadrant:
        st.plotly_chart(build_quadrant_figure(scatter_df), use_container_width=True, key="prioritization_quadrant")
    with tab_table:
        _show_table(
            scatter_df,
            {
                "primary_policy_area": "Policy area",
                "advancement_rate": "Advancement rate (%)",
                "bill_count": "Bills",
                "median_dwell_days": "Median days in Committee",
            },
            column_config={"Advancement rate (%)": st.column_config.NumberColumn(format="%.1f")},
        )
    st.caption(describe_prioritization(scatter_df))
