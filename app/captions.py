import pandas as pd


def _bills(n: int) -> str:
    return "bill" if n == 1 else "bills"


def describe_stage_distribution(stage_df: pd.DataFrame) -> str:
    total = int(stage_df["bill_count"].sum())
    if total == 0:
        return "No bills match the current filters."

    became_law = int(
        stage_df.loc[stage_df["furthest_stage_reached"] == "Became Law", "bill_count"].sum()
    )
    still_active = total - became_law
    top_stage = stage_df.loc[stage_df["bill_count"].idxmax(), "furthest_stage_reached"]

    if still_active == 0:
        return f"All {total} tracked {_bills(total)} have become law."
    return (
        f"{still_active} of {total} tracked {_bills(total)} "
        f"({still_active / total * 100:.0f}%) are still working through the process, "
        f"most commonly stalled at {top_stage}. "
        f"{became_law} {_bills(became_law)} have become law so far."
    )


def describe_bill_volume(volume_df: pd.DataFrame) -> str:
    if volume_df.empty:
        return "No bills match the current filters."

    top = volume_df.iloc[0]
    if len(volume_df) == 1:
        return (
            f"{top['primary_policy_area']} is the only policy area represented, "
            f"with {int(top['bill_volume'])} {_bills(int(top['bill_volume']))}."
        )

    second = volume_df.iloc[1]
    return (
        f"{top['primary_policy_area']} leads by volume with {int(top['bill_volume'])} "
        f"{_bills(int(top['bill_volume']))}, followed by {second['primary_policy_area']} "
        f"({int(second['bill_volume'])})."
    )


def describe_speed_by_policy(speed_df: pd.DataFrame) -> str:
    if speed_df.empty:
        return "No bills match the current filters."

    fastest = speed_df.iloc[0]
    if len(speed_df) == 1:
        return (
            f"{fastest['primary_policy_area']} bills reach their furthest stage in a "
            f"median of {fastest['median_days']:.0f} days."
        )

    slowest = speed_df.iloc[-1]
    return (
        f"{fastest['primary_policy_area']} moves fastest, reaching its furthest stage in "
        f"a median of {fastest['median_days']:.0f} days — {slowest['primary_policy_area']} "
        f"is slowest at {slowest['median_days']:.0f} days."
    )


def describe_stage_bottleneck(bottleneck_df: pd.DataFrame) -> str:
    if bottleneck_df.empty:
        return "No completed stage transitions in the current selection — bills here haven't moved between stages yet."

    bottleneck = bottleneck_df.loc[bottleneck_df["median_days"].idxmax()]
    return (
        f"The {bottleneck['stage']} stage is the biggest bottleneck, taking a median of "
        f"{bottleneck['median_days']:.0f} days to clear (up to {bottleneck['slowest_10pct_days']:.0f} "
        f"days for the slowest 10%), based on {int(bottleneck['sample_size'])} completed "
        f"transitions."
    )


def describe_prioritization(scatter_df: pd.DataFrame) -> str:
    if scatter_df.empty:
        return "No bills match the current filters."

    with_dwell = scatter_df.dropna(subset=["median_dwell_days"])
    if with_dwell.empty:
        return "No policy area in the current selection has moved past Committee yet, so dwell time can't be measured."

    top = with_dwell.sort_values(
        ["advancement_rate", "median_dwell_days"], ascending=[False, True]
    ).iloc[0]
    return (
        f"{top['primary_policy_area']} bills advance most often "
        f"({top['advancement_rate']:.0f}%) and spend a median of "
        f"{top['median_dwell_days']:.0f} days in Committee before moving on."
    )
