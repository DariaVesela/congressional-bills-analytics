select
    a.bill_id,
    a.action_id,
    a.action_date,
    b.introduced_date
from {{ ref('fct_bill_actions') }} a
join {{ ref('dim_bills') }} b on a.bill_id = b.bill_id
where a.action_date < b.introduced_date
