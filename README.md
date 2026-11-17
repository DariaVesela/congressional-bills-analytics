# Congressional Bill Analytics

An end-to-end data pipeline that ingests official U.S. Congressional bill data every day, models it into a star schema with dbt, and serves a Streamlit dashboard. The dashboard shows how far bills get through the legislative process, and where they stall.

**Stack:** Python · DuckDB · dbt · GitHub Actions · Streamlit · Plotly

**Link to Dashboard:** https://congressional-bills-analytics.streamlit.app/
## 📚 Project documentation

This project is documented in detail in Notion - find the Kanban board, design decisions and process as well as a changelog:

**[Congressional Bill Analytics: Project Documentation](https://app.notion.com/p/41863fb2df318063bcb4ca871cb1bc75)**

The documentation includes:

- **Project overview:** the questions, data source, architecture diagram, data model and dashboard walkthrough
- **Design document:** pipeline architecture, dbt layering, testing strategy (organized by data quality dimension) and dashboard design
- **Decisions log:** the significant decisions and trade-offs, what was ruled out and why, data discoveries that changed the plan, and production incident write-ups
- **Kanban board:** the project broken into six epics and their tickets

## Repository layout

```text
extract/        # Python extraction: BILLSTATUS XML parsing and DuckDB load
dbt_project/    # dbt models: staging → intermediate → marts
app/            # Streamlit dashboard
tests/          # unit tests and XML fixtures
.github/        # daily pipeline and PR CI workflows
```

## Data source

[GovInfo.gov Bulk Data](https://www.govinfo.gov/bulkdata): `BILLSTATUS` XML for House (HR) and Senate (S) bills in the 119th Congress. Public domain.
