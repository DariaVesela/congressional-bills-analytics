
with source as (

    select * from {{source('govinfo', 'raw_bills')}}
),

renamed as (
    select bill_id,
    congress,
    bill_type,
    number :: VARCHAR as number, 
    origin_chamber,
    introduced_date :: DATE as introduced_date,
    sponsor_bioguide_id,
    sponsor_full_name,
    sponsor_party,
    primary_policy_area
    from source
    )

select * from renamed
    