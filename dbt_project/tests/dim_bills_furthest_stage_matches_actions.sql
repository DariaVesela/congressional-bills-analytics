with dim_max as (
    select bill_id, furthest_stage_order
    from {{ ref('dim_bills') }}
),

fct_max as (
    select bill_id, max(stage_order) as max_stage_order
    from {{ ref('fct_bill_actions') }}
    group by bill_id
)

select
    dim_max.bill_id,
    dim_max.furthest_stage_order as dim_value,
    fct_max.max_stage_order as fct_value
from dim_max
join fct_max on dim_max.bill_id = fct_max.bill_id
where dim_max.furthest_stage_order != fct_max.max_stage_order
