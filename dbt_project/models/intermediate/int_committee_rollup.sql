with committees_with_dates as (

    select
        c.bill_id,
        c.system_code,
        c.committee_name,
        c.committee_order,
        a.action_date
    from {{ ref('stg_action_committees') }} c
    join {{ ref('stg_actions') }} a
        on c.action_id = a.action_id

),

ranked as (

    select
        *,
        row_number() over (
            partition by bill_id
            order by action_date, committee_order
        ) as rn
    from committees_with_dates

),

primary_committee as (

    select
        bill_id,
        system_code as primary_committee_code,
        committee_name as primary_committee_name
    from ranked
    where rn = 1

),

committee_counts as (

    select
        bill_id,
        count(distinct system_code) as num_committees_referred
    from committees_with_dates
    group by bill_id

)

select
    bills.bill_id,
    pc.primary_committee_code,
    pc.primary_committee_name,
    coalesce(cc.num_committees_referred, 0) as num_committees_referred
from {{ ref('stg_bills') }} bills
left join primary_committee pc
    on bills.bill_id = pc.bill_id
left join committee_counts cc
    on bills.bill_id = cc.bill_id