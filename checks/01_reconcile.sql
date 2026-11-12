-- 1. Cancelled memberships with no cancellation row (expect 0)
select count(*) as missing
from raw.memberships m
left join raw.cancellations c
  on c.membership_id = m.membership_id
where m.status = 'cancelled'
  and c.membership_id is null;

  -- 2. Check-ins outside every membership row for that member (expect 0)
select count(*) as outside
from raw.check_ins ci
where not exists (
  select 1
  from raw.memberships m
  where m.member_id = ci.member_id
    and cast(ci.check_in_at as date) >= m.start_date
    and cast(ci.check_in_at as date) <= coalesce(m.end_date, date '2025-12-31')
);