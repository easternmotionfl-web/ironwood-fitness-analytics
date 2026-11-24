-- Fails if the daily table doesn't have exactly one row per member-day in fct_memberships.
select *
from (select count(*) as day_rows from {{ ref('fct_member_days') }}) as actual
cross join (select sum(member_days) as expected from {{ ref('fct_memberships') }}) as target
where actual.day_rows != target.expected