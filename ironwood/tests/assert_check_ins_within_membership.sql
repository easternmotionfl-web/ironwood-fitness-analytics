-- Fails if any check-in falls outside every membership row for that member.
select ci.*
from {{ ref('stg_check_ins') }} ci
where not exists (
    select 1
    from {{ ref('stg_memberships') }} m
    where m.member_id = ci.member_id
      and cast(ci.check_in_at as date) >= m.start_date
      and cast(ci.check_in_at as date) <= coalesce(m.end_date, date '{{ var("as_of_date") }}')
)
