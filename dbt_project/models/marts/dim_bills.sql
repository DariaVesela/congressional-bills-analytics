

with bills as (
    select * from {{ ref('stg_bills') }}
),

cosponsors as (
    select * from {{ ref('int_cosponsor_rollup') }}
),

committees as (
    select * from {{ ref('int_committee_rollup') }}
),

stage_lookup as (
    select distinct
        stage_order,
        canonical_stage
    from {{ ref('int_action_stages') }}
    where stage_order is not null
),

furthest_stage as (
    select
        bill_id,
        max(stage_order) as furthest_stage_order
    from {{ ref('int_action_stages') }}
    group by bill_id
)

select
    bills.bill_id,
    bills.congress,
    bills.bill_type,
    bills.number,
    bills.origin_chamber,
    bills.introduced_date,
    bills.sponsor_bioguide_id,
    bills.sponsor_full_name,
    bills.sponsor_party,
    bills.primary_policy_area,
    cosponsors.cosponsor_count,
    cosponsors.bipartisan_cosponsor_count,
    cosponsors.bipartisan_cosponsor_ratio,
    committees.primary_committee_code,
    committees.primary_committee_name,
    committees.num_committees_referred,
    fs.furthest_stage_order,
    sl.canonical_stage as furthest_stage_reached
from bills
left join cosponsors
    on bills.bill_id = cosponsors.bill_id
left join committees
    on bills.bill_id = committees.bill_id
left join furthest_stage fs
    on bills.bill_id = fs.bill_id
left join stage_lookup sl
    on fs.furthest_stage_order = sl.stage_order