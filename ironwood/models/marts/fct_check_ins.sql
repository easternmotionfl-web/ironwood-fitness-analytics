with check_ins as (
    select * from {{ ref('stg_check_ins') }}
),
memberships as (
    select * from {{ ref('fct_memberships') }}
)

select
    ci.check_in_id,
    ci.member_id,
    ci.location_id,
    ci.check_in_at,
    cast(ci.check_in_at as date) as check_in_date,
    hour(ci.check_in_at) as check_in_hour,
    m.membership_id,
    m.plan_id,
    m.plan_name
from check_ins ci
left join memberships m
  on m.member_id = ci.member_id
 and cast(ci.check_in_at as date) between m.start_date and m.effective_end_date
