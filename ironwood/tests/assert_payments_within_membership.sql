-- Fails if any payment is dated outside its own membership row.
select p.*
from {{ ref('stg_payments') }} p
join {{ ref('stg_memberships') }} m
  on m.membership_id = p.membership_id
where p.charge_date < m.start_date
   or p.charge_date > coalesce(m.end_date, date '{{ var("as_of_date") }}')
