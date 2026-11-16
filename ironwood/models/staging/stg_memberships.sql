select
    membership_id,
    member_id,
    plan_id,
    cast(start_date as date) as start_date,
    cast(end_date as date) as end_date,
    status
from {{ source('raw', 'memberships') }}
