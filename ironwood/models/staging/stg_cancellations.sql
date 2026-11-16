select
    cancellation_id,
    member_id,
    membership_id,
    cast(cancel_date as date) as cancel_date,
    reason
from {{ source('raw', 'cancellations') }}
