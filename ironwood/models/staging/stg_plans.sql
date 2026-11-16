select
    plan_id,
    plan_name,
    cast(monthly_price as decimal(10, 2)) as monthly_price
from {{ source('raw', 'plans') }}
