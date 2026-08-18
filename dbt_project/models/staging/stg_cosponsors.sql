

with source as (

    select * from {{source('govinfo', 'raw_cosponsors')}}
),

renamed as (
    select bill_id,
    bioguide_id,
    full_name as cosponsor_full_name,
    party as cosponsor_party
    from source
    )

select * from renamed
    