-- One row per day across the data window. MetricFlow joins to it for time-based metrics.
-- generate_series includes both ends, so this runs from the window start through the as-of date.
select cast(day as date) as date_day
from generate_series(
    cast('{{ var("window_start_date") }}' as timestamp),
    cast('{{ var("as_of_date") }}' as timestamp),
    interval 1 day
) as t(day)
