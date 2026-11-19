with payments as (
    select * from {{ ref('stg_payments') }}
),
memberships as (
    select * from {{ ref('fct_memberships') }}
)

select
    p.payment_id,
    p.member_id,
    p.membership_id,
    m.location_id,
    m.plan_id,
    m.plan_name,
    p.charge_date,
    p.amount,
    p.status,
    p.status = 'paid' as is_paid,
    case when p.status = 'paid' then p.amount else 0 end as revenue
from payments p
join memberships m on m.membership_id = p.membership_id
