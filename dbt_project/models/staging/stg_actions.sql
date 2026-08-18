with source as (

    select * from {{source('govinfo', 'raw_actions')}}
),

renamed as (
    select 
    action_id,
    bill_id,
    action_date :: DATE as action_date,
    text,
    type as action_type,
    action_code,
    source_system
    from source
    )

select * from renamed
    