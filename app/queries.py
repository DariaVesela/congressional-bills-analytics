def get_total_bills_tracked(con) -> int:
    return con.sql("SELECT COUNT(*) FROM dim_bills").fetchone()[0]


def get_percent_advanced(con) -> float:
    result = con.sql("""
        SELECT AVG(CASE WHEN furthest_stage_order > 2 THEN 1.0 ELSE 0.0 END) * 100
        FROM dim_bills
    """).fetchone()[0]
    return result


def get_percent_became_law(con) -> float:
    result = con.sql(
        """
        WITH max_stage AS (
            SELECT MAX(furthest_stage_order) AS max_order
            FROM dim_bills
        )
        SELECT AVG(
            CASE WHEN furthest_stage_order = (SELECT max_order FROM max_stage)
                 THEN 1.0 ELSE 0.0 END
        ) * 100
        FROM dim_bills
    """
    ).fetchone()[0]
    return result


def get_median_days_to_first_committee_action(con) -> float:
    result = con.sql("""
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
    """).fetchone()[0]
    return result
