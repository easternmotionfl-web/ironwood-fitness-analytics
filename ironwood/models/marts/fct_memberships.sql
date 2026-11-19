with memberships as (
    select * from {{ ref('stg_memberships') }}
),
plans as (
    select * from {{ ref('stg_plans') }}
),
members as (
    select * from {{ ref('stg_members') }}
),
cancellations as (
    select * from {{ ref('stg_cancellations') }}
)

select
    m.membership_id,
    m.member_id,
    mb.home_location_id as location_id,
    m.plan_id,
    p.plan_name,
    p.monthly_price,
    m.start_date,
    m.end_date,
    coalesce(m.end_date, date '{{ var("as_of_date") }}') as effective_end_date,
    m.status,
    date_diff('day', m.start_date,
              coalesce(m.end_date, date '{{ var("as_of_date") }}')) + 1 as member_days,
    m.status = 'cancelled' as is_cancelled,
    m.status = 'cancelled'
        and date_diff('day', mb.join_date, m.end_date) < 90 as is_cancelled_first_90_days,
    c.reason as cancel_reason
from memberships m
join plans p on p.plan_id = m.plan_id
join members mb on mb.member_id = m.member_id
left join cancellations c on c.membership_id = m.membership_id
