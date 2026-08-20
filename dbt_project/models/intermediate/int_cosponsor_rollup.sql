with cosponsors_with_sponsor_party as (

    select
        c.bill_id,
        c.bioguide_id,
        c.cosponsor_party,
        b.sponsor_party
    from {{ ref('stg_cosponsors') }} c
    join {{ ref('stg_bills') }} b
        on c.bill_id = b.bill_id

),

cosponsor_counts as (

    select
        bill_id,
        count(*) as cosponsor_count,
        count(*) filter (where cosponsor_party != sponsor_party) as bipartisan_cosponsor_count
    from cosponsors_with_sponsor_party
    group by bill_id

)

select
    bills.bill_id,
    coalesce(cc.cosponsor_count, 0) as cosponsor_count,
    coalesce(cc.bipartisan_cosponsor_count, 0) as bipartisan_cosponsor_count,
    case
        when coalesce(cc.cosponsor_count, 0) = 0 then null
        else cc.bipartisan_cosponsor_count::float / cc.cosponsor_count
    end as bipartisan_cosponsor_ratio
from {{ ref('stg_bills') }} bills
left join cosponsor_counts cc
    on bills.bill_id = cc.bill_id