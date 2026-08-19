
with actions as (
    select * from {{ref('stg_actions')}}
),

staged as (
    SELECT
        action_id,
        bill_id,
        action_date,
        text,
        action_type,
        action_code,
        source_system,
        CASE 
            WHEN action_type = 'IntroReferral' THEN 'Committee'
            WHEN action_type = 'Committee' THEN 'Committee'
            WHEN action_type = 'Calendars' THEN 'Committee'
            WHEN action_type = 'Discharge' THEN 'Floor'
            WHEN action_type = 'Floor' THEN 'Floor'
            WHEN action_type = 'President' THEN 'Passed Chamber'
            WHEN action_type = 'BecameLaw' THEN 'Became Law'
            ELSE  'Unmapped'
        END AS canonical_stage,
        CASE
            WHEN action_type = 'IntroReferral' THEN 2
            WHEN action_type = 'Committee' THEN 2
            WHEN action_type = 'Calendars' THEN 2
            WHEN action_type = 'Discharge' THEN 3
            WHEN action_type = 'Floor' THEN 3
            WHEN action_type = 'President' THEN 4
            WHEN action_type = 'BecameLaw' THEN 5
            ELSE  null
        END AS stage_order
        FROM actions
)
select * from staged