from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd

# Canonical bill-status taxonomy, ordered by stage_order (see Decisions Log
# Section 5). Hardcoded rather than queried distinct, so a stage with no bills
# in the current pull (e.g. "Passed Chamber") still appears as a valid filter
# option.
BILL_STATUSES = ["Committee", "Floor", "Passed Chamber", "Became Law"]


@dataclass
class Filters:
    policy_areas: list[str] = field(default_factory=list)
    chamber: Optional[str] = None
    sponsor_party: Optional[str] = None
    bill_status: Optional[str] = None
    introduced_after: Optional[date] = None
    introduced_before: Optional[date] = None


def _dim_bills_conditions(filters: Optional[Filters], alias: str) -> tuple[list[str], list]:
    """Build WHERE conditions + params against dim_bills columns, given an alias."""
    if filters is None:
        return [], []

    conditions = []
    params = []

    if filters.policy_areas:
        placeholders = ", ".join(["?"] * len(filters.policy_areas))
        conditions.append(f"{alias}.primary_policy_area IN ({placeholders})")
        params.extend(filters.policy_areas)
    if filters.chamber:
        conditions.append(f"{alias}.origin_chamber = ?")
        params.append(filters.chamber)
    if filters.sponsor_party:
        conditions.append(f"{alias}.sponsor_party = ?")
        params.append(filters.sponsor_party)
    if filters.bill_status:
        conditions.append(f"{alias}.furthest_stage_reached = ?")
        params.append(filters.bill_status)
    if filters.introduced_after:
        conditions.append(f"{alias}.introduced_date >= ?")
        params.append(filters.introduced_after)
    if filters.introduced_before:
        conditions.append(f"{alias}.introduced_date <= ?")
        params.append(filters.introduced_before)

    return conditions, params


def _where_clause(filters: Optional[Filters], alias: str = "dim_bills") -> tuple[str, list]:
    """A ready-to-splice ' AND <cond> AND <cond>' fragment (or '' if no filters)."""
    conditions, params = _dim_bills_conditions(filters, alias)
    if not conditions:
        return "", []
    return " AND " + " AND ".join(conditions), params


def _bill_id_subquery(filters: Optional[Filters]) -> tuple[str, list]:
    """A 'bill_id IN (SELECT bill_id FROM dim_bills WHERE ...)' fragment for
    queries that filter fct_bill_actions before any join to dim_bills exists.
    Returns ('', []) when there's nothing to filter on, so callers can splice
    it in conditionally rather than always paying for a subquery."""
    conditions, params = _dim_bills_conditions(filters, "dim_bills")
    if not conditions:
        return "", []
    clause = f"bill_id IN (SELECT bill_id FROM dim_bills WHERE {' AND '.join(conditions)})"
    return clause, params


def get_total_bills_tracked(con, filters: Optional[Filters] = None) -> int:
    where, params = _where_clause(filters)
    query = f"SELECT COUNT(*) FROM dim_bills WHERE 1=1{where}"
    return con.execute(query, params).fetchone()[0]


def get_percent_advanced(con, filters: Optional[Filters] = None) -> float:
    where, params = _where_clause(filters)
    query = f"""
        SELECT AVG(CASE WHEN furthest_stage_order > 2 THEN 1.0 ELSE 0.0 END) * 100
        FROM dim_bills
        WHERE 1=1{where}
    """
    return con.execute(query, params).fetchone()[0]


def get_percent_became_law(con, filters: Optional[Filters] = None) -> float:
    where, params = _where_clause(filters)
    # Filters against the literal 'Became Law' stage, not the max stage_order
    # present in the (possibly filtered) population. The old dynamic-MAX
    # version broke under the bill_status filter: filtering to e.g. "Committee"
    # made Committee the max stage within that population, so every bill in it
    # trivially reported as "became law" even though none of them did.
    query = f"""
        SELECT AVG(CASE WHEN furthest_stage_reached = 'Became Law' THEN 1.0 ELSE 0.0 END) * 100
        FROM dim_bills
        WHERE 1=1{where}
    """
    return con.execute(query, params).fetchone()[0]


def get_median_days_to_first_committee_action(con, filters: Optional[Filters] = None) -> float:
    where, params = _where_clause(filters)
    query = f"""
        WITH committee_stage AS (
            SELECT bill_id, MIN(action_date) AS first_committee_date
            FROM fct_bill_actions
            WHERE canonical_stage = 'Committee' AND action_type != 'IntroReferral'
            GROUP BY bill_id
        )
        SELECT MEDIAN(date_diff('day', dim_bills.introduced_date, committee_stage.first_committee_date)) AS median_days
        FROM committee_stage
        JOIN dim_bills
        USING (bill_id)
        WHERE 1=1{where}
    """
    return con.execute(query, params).fetchone()[0]


def get_bill_volume_by_policy(con, filters: Optional[Filters] = None) -> pd.DataFrame:
    where, params = _where_clause(filters)
    query = f"""
        SELECT COUNT(*) AS bill_volume,
        primary_policy_area
        FROM dim_bills
        WHERE 1=1{where}
        GROUP BY primary_policy_area
        ORDER BY bill_volume DESC LIMIT 10
    """
    return con.execute(query, params).df()


def get_median_days_to_furthest_stage_by_policy(con, filters: Optional[Filters] = None) -> pd.DataFrame:
    where, params = _where_clause(filters)
    query = f"""
        WITH furthest_action AS (
            SELECT
                bill_id, stage_order, action_date,
                ROW_NUMBER() OVER (
                    PARTITION BY bill_id
                    ORDER BY stage_order DESC, action_date DESC
                ) AS rn
            FROM fct_bill_actions
        ),
        furthest_stage_date AS (
            SELECT bill_id, action_date AS furthest_date
            FROM furthest_action
            WHERE rn = 1
        )
        SELECT
            dim_bills.primary_policy_area,
            MEDIAN(date_diff('day', dim_bills.introduced_date, furthest_stage_date.furthest_date)) AS median_days,
            COUNT(*) AS bill_count
        FROM furthest_stage_date
        JOIN dim_bills USING (bill_id)
        WHERE 1=1{where}
        GROUP BY dim_bills.primary_policy_area
        ORDER BY median_days ASC
    """
    return con.execute(query, params).df()


def get_stage_distribution(con, filters: Optional[Filters] = None) -> pd.DataFrame:
    where, params = _where_clause(filters)
    query = f"""
        SELECT
            furthest_stage_order,
            furthest_stage_reached,
            COUNT(*) AS bill_count
        FROM dim_bills
        WHERE 1=1{where}
        GROUP BY furthest_stage_order, furthest_stage_reached
        ORDER BY furthest_stage_order
    """
    return con.execute(query, params).df()


def get_stage_transition_durations(con, filters: Optional[Filters] = None) -> pd.DataFrame:
    bill_id_filter, params = _bill_id_subquery(filters)
    where = f"WHERE {bill_id_filter}" if bill_id_filter else ""
    query = f"""
        WITH per_bill_stage_dates AS (
            SELECT
                bill_id,
                MIN(action_date) FILTER (WHERE stage_order = 2) AS committee_entry,
                MIN(action_date) FILTER (WHERE stage_order = 3) AS floor_entry,
                MIN(action_date) FILTER (WHERE stage_order = 4) AS passed_entry,
                MIN(action_date) FILTER (WHERE stage_order = 5) AS became_law_entry
            FROM fct_bill_actions
            {where}
            GROUP BY bill_id
        ),
        transition_durations AS (
            SELECT
                bill_id,
                date_diff('day', committee_entry, floor_entry) AS committee_to_floor_days,
                date_diff('day', floor_entry, passed_entry) AS floor_to_passed_days,
                date_diff('day', passed_entry, became_law_entry) AS passed_to_law_days
            FROM per_bill_stage_dates
        ),
        labeled_durations AS (
            SELECT 'Committee' AS stage, committee_to_floor_days AS days FROM transition_durations
            UNION ALL
            SELECT 'Floor' AS stage, floor_to_passed_days AS days FROM transition_durations
            UNION ALL
            SELECT 'Passed Chamber' AS stage, passed_to_law_days AS days FROM transition_durations
        )
        SELECT
            stage,
            MEDIAN(days) AS median_days,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY days) AS slowest_10pct_days,
            COUNT(days) AS sample_size
        FROM labeled_durations
        WHERE days IS NOT NULL
        GROUP BY stage
    """
    return con.execute(query, params).df()


def get_committee_prioritization(con, filters: Optional[Filters] = None) -> pd.DataFrame:
    advancement_where, advancement_params = _where_clause(filters, alias="dim_bills")
    dwell_where, dwell_params = _where_clause(filters, alias="dim_bills")
    query = f"""
        WITH advancement AS (
            SELECT
                primary_policy_area,
                AVG(CASE WHEN furthest_stage_order > 2 THEN 1.0 ELSE 0.0 END) * 100 AS advancement_rate,
                COUNT(*) AS bill_count
            FROM dim_bills
            WHERE 1=1{advancement_where}
            GROUP BY primary_policy_area
        ),
        per_bill_dwell AS (
            SELECT
                bill_id,
                date_diff(
                    'day',
                    MIN(action_date) FILTER (WHERE stage_order = 2),
                    MIN(action_date) FILTER (WHERE stage_order = 3)
                ) AS dwell_days
            FROM fct_bill_actions
            GROUP BY bill_id
        ),
        dwell_by_policy AS (
            SELECT
                dim_bills.primary_policy_area,
                MEDIAN(per_bill_dwell.dwell_days) AS median_dwell_days
            FROM per_bill_dwell
            JOIN dim_bills USING (bill_id)
            WHERE per_bill_dwell.dwell_days IS NOT NULL{dwell_where}
            GROUP BY dim_bills.primary_policy_area
        )
        SELECT
            advancement.primary_policy_area,
            advancement.advancement_rate,
            advancement.bill_count,
            dwell_by_policy.median_dwell_days
        FROM advancement
        LEFT JOIN dwell_by_policy USING (primary_policy_area)
    """
    return con.execute(query, advancement_params + dwell_params).df()


def get_policy_areas(con) -> list[str]:
    result = con.sql("""
        SELECT DISTINCT primary_policy_area
        FROM dim_bills
        ORDER BY primary_policy_area
    """).df()
    return result["primary_policy_area"].tolist()


def get_introduced_date_bounds(con) -> tuple[date, date]:
    result = con.sql("SELECT MIN(introduced_date), MAX(introduced_date) FROM dim_bills").fetchone()
    return result[0], result[1]


def get_sponsor_parties(con) -> list[str]:
    result = con.sql("""
        SELECT DISTINCT sponsor_party
        FROM dim_bills
        ORDER BY sponsor_party
    """).df()
    return result["sponsor_party"].tolist()
