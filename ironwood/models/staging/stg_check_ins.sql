select
    check_in_id,
    member_id,
    location_id,
    cast(check_in_at as timestamp) as check_in_at
from {{ source('raw', 'check_ins') }}
