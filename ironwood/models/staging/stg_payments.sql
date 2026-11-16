select
    payment_id,
    member_id,
    membership_id,
    cast(charge_date as date) as charge_date,
    cast(amount as decimal(10, 2)) as amount,
    status
from {{ source('raw', 'payments') }}
