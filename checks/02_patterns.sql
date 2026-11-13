-- 4. Summer dip: visits per 30 member-days by calendar month (expect Jun-Aug about 20 percent lower)
with months as (
  select distinct cast(date_trunc('month', check_in_at) as date) as month_start
  from raw.check_ins
),
member_days as (
  select mo.month_start,
         sum(date_diff('day',
                       greatest(m.start_date, mo.month_start),
                       least(coalesce(m.end_date, date '2025-12-31'), last_day(mo.month_start))
             ) + 1) as member_days
  from months mo
  join raw.memberships m
    on m.start_date <= last_day(mo.month_start)
   and coalesce(m.end_date, date '2025-12-31') >= mo.month_start
  group by 1
),
visits as (
  select cast(date_trunc('month', check_in_at) as date) as month_start,
         count(*) as visits
  from raw.check_ins
  group by 1
)
select month(v.month_start) as month_num,
       round(sum(v.visits) * 30.0 / sum(d.member_days), 2) as visits_per_30_member_days
from visits v
join member_days d using (month_start)
group by 1
order by 1;

-- 5. Monthly churn rate by plan (expect Premium lowest, Basic highest)
select p.plan_name,
       sum(case when m.status = 'cancelled' then 1 else 0 end) as cancellations,
       round(sum(date_diff('day', m.start_date, coalesce(m.end_date, date '2025-12-31')) + 1) / 30.0) as member_months,
       round(100.0 * sum(case when m.status = 'cancelled' then 1 else 0 end)
             / (sum(date_diff('day', m.start_date, coalesce(m.end_date, date '2025-12-31')) + 1) / 30.0), 1) as monthly_churn_pct
from raw.memberships m
join raw.plans p using (plan_id)
group by 1
order by monthly_churn_pct desc;

-- 6. Joins per open month and monthly churn by gym (expect Ocala about 0.6x joins, 1.5x churn)
with joins as (
  select home_location_id as location_id, count(*) as joins
  from raw.members
  group by 1
),
churn as (
  select mb.home_location_id as location_id,
         sum(case when m.status = 'cancelled' then 1 else 0 end) as cancellations,
         sum(date_diff('day', m.start_date, coalesce(m.end_date, date '2025-12-31')) + 1) / 30.0 as member_months
  from raw.memberships m
  join raw.members mb using (member_id)
  group by 1
)
select l.location_name,
       date_diff('month', greatest(l.opened_date, date '2023-01-01'), date '2025-12-31') + 1 as open_months,
       round(j.joins * 1.0 / (date_diff('month', greatest(l.opened_date, date '2023-01-01'), date '2025-12-31') + 1), 1) as joins_per_open_month,
       round(100.0 * c.cancellations / c.member_months, 1) as monthly_churn_pct
from raw.locations l
join joins j using (location_id)
join churn c using (location_id)
order by joins_per_open_month;

-- 7. Churn in the first 90 days vs. after (expect first 90 days about 2x)
with per_member as (
  select mb.member_id,
         date_diff('day', mb.join_date, max(coalesce(m.end_date, date '2025-12-31'))) + 1 as total_days,
         max(case when m.status = 'cancelled' then date_diff('day', mb.join_date, m.end_date) end) as cancel_tenure_days
  from raw.members mb
  join raw.memberships m using (member_id)
  group by mb.member_id, mb.join_date
)
select
  round(100.0 * count(*) filter (where cancel_tenure_days < 90)
        / (sum(least(total_days, 90)) / 30.0), 1) as first_90_days_churn_pct,
  round(100.0 * count(*) filter (where cancel_tenure_days >= 90)
        / (sum(greatest(total_days - 90, 0)) / 30.0), 1) as after_90_days_churn_pct
from per_member;