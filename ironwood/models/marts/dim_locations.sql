select
    location_id,
    location_name,
    city,
    opened_date,
    date_diff('month',
              greatest(opened_date, date '{{ var("window_start_date") }}'),
              date '{{ var("as_of_date") }}') + 1 as months_open_in_window
from {{ ref('stg_locations') }}
