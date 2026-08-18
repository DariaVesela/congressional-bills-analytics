
with source as (

    select * from {{source('govinfo', 'raw_action_committees')}}
),

renamed as (
    select 
    action_id,
    bill_id,
    system_code,
    name as committee_name
    from source
    )

select * from renamed
    