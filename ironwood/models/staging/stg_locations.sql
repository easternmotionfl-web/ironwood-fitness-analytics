select
    location_id,
    location_name,
    split_part(location_name, ' - ', 1) as city,
    cast(opened_date as date) as opened_date
from {{ source('raw', 'locations') }}
