# CLAUDE.md

Context for Claude Code when working in this repo. Read this before making changes.

## Project

Congressional Bill Analytics — a portfolio data engineering pipeline that tracks US
Congressional bills (119th Congress, HR and S bill types) from introduction through
committee, floor action, and passage. 

Source of truth for requirements and status: Notion, under
**Tech learning > US bills pipeline** (Kanban Board, Development Brief, Decisions Log).
Always check the relevant ticket's description and acceptance criteria before starting
work — don't infer scope from the code alone.

## Stack — locked, do not add to it

- **Extraction:** Python — `requests`, `ElementTree`, `pydantic`
- **Storage:** DuckDB (local file)
- **Transformation:** dbt (run locally, not dbt Cloud)
- **App:** Streamlit, deployed on Streamlit Community Cloud
- **Orchestration:** GitHub Actions (daily scheduled pipeline + PR-triggered CI)
- **Viz:** Plotly (for the Sankey diagram specifically)

**Explicitly excluded — do not introduce without discussing first:** pandas, dbt Cloud,
SQLAlchemy, incremental dbt logic. This is a deliberate minimalism choice, not an
oversight. Every tooling addition needs justification.

## Architecture

- ELT pattern with a **full daily rebuild**, not incremental accumulation. Chosen
  deliberately for simplicity/reliability at this data scale — don't propose
  incremental models.
- Raw XML → near-1:1 raw tables in DuckDB → dbt staging → dbt intermediate (stage
  taxonomy mapping, cosponsor/committee rollups) → dbt marts (`dim_bills`,
  `fct_bill_actions` — star schema).
- DuckDB file is stored as a GitHub Release asset (overwritten each run); Streamlit
  Community Cloud redeploys via a trigger commit.
- Single responsibility, separated concerns: split dbt models by rollup type (don't
  merge cosponsor and committee logic into one model), split app code (`queries.py`
  vs `streamlit_app.py` — keep query logic out of the UI file).

## Known data quirks (don't rediscover these)

- `policyArea` is available directly in BILLSTATUS XML — no BILLSUM integration needed.
- Committees are nested **per-action**, not at the bill level.
- `action_code` is genuinely optional — handle its absence, don't assume it's always set.
- GovInfo XML actions are ordered **newest-first**.
- Watch for KPIs that silently divide/aggregate over `IntroReferral` actions and
  produce misleading 0.0s — this has bitten us before.

## Working conventions

- **Run dbt from `dbt_project/`, not the repo root.** This is a recurring mistake —
  always confirm the working directory before running `dbt` commands or querying
  DuckDB directly.
- **Explicit failure over silent defaults.** Use sentinel values like `Unmapped`
  instead of `NULL` for unmapped categories. Use `assert` over silently returning
  `None`. Make problems visible immediately, not downstream.
- **Don't add what isn't needed.** Push back if you're about to introduce a library,
  abstraction, or pattern the ticket doesn't call for — flag it and ask first rather
  than just doing it.
- **Document decisions, don't silently resolve ambiguity.** If a design decision or
  known issue comes up mid-task, flag it explicitly in your output so it can go into
  the Notion Decisions Log — don't just pick an approach and move on quietly.
- Real data has repeatedly forced design changes here. If something in the XML or
  data doesn't match the assumed shape, say so and propose an adaptation — don't
  paper over it with a workaround.

## Testing

- dbt schema tests (`not_null`, `unique`, `accepted_values`, `relationships`) plus
  custom singular tests for business logic (taxonomy mapping, bounds checks,
  cross-table consistency).
- pytest, fixture-based, for the Python extraction layer — cover edge cases (zero
  cosponsors, multiple committees, a bill that became law, missing optional fields).
- Run relevant tests after any change to extraction or dbt models before considering
  a task done.

## Communication style

- Under time pressure: give direct solutions with clear explanations, not Socratic
  back-and-forth.
- Flag assumptions and open questions rather than guessing silently.
- Point out real bugs or bad assumptions even if they're outside the current task's
  scope — don't stay narrowly on-task if something looks broken.