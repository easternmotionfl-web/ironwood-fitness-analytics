with members as (
    select * from {{ ref('stg_members') }}
),
locations as (
    select * from {{ ref('dim_locations') }}
),
latest_membership as (
    select
        *,
        row_number() over (partition by member_id order by start_date desc) as row_num
    from {{ ref('fct_memberships') }}
)

select
    mb.member_id,
    mb.join_date,
    mb.home_location_id as location_id,
    l.location_name,
    mb.age_band,
    mb.gender,
    lm.plan_name as current_plan,
    case when lm.status = 'cancelled' then 'churned' else 'active' end as current_status,
    case when lm.status = 'cancelled' then lm.end_date end as churn_date,
    date_diff('day', mb.join_date, lm.effective_end_date) + 1 as tenure_days
from members mb
join latest_membership lm
  on lm.member_id = mb.member_id
 and lm.row_num = 1
join locations l on l.location_id = mb.home_location_id
