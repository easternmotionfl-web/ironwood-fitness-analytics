select
    member_id,
    home_location_id,
    cast(join_date as date) as join_date,
    age_band,
    gender
from {{ source('raw', 'members') }}
