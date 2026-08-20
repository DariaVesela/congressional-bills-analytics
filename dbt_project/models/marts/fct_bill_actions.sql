
with actions as (
    select * from {{ref('int_action_stages')}}
),

clean as (
    SELECT 
        action_id,
        bill_id,
        action_date,
        text,
        action_type,
        action_code,
        source_system,
        canonical_stage,
        stage_order

    from actions
) 
select * from clean