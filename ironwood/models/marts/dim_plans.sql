select
    plan_id,
    plan_name,
    monthly_price
from {{ ref('stg_plans') }}
