# Ironwood Fitness: data model and rules

## dbt terms in my own words
- Model: A file containing a select statement that transforms raw data in a data warehouse or lakehouse into clean, analytics ready data sets.
- Source: A raw table or view residing in the data warehouse or lakehouse that is loaded by an external process (ELT) rather than managed in dbt.
- ref(): a Jinja function that points one model at another. dbt uses these references to build models in dependency order (the DAG) and fills in the correct database and schema for the environment.

## Window
- Data from: 2023-01-01   As-of date: 2025-12-31   (never use today's date)

## Tables
| Table | One row per | Key | Columns | Links to |
|---|---|---|---|---|
| locations | gym | location_id | location_id, location_name, city, opened_date | — |
| plans | plan tier | plan_id | plan_id, plan_name, monthly_price | — |
| members | person who ever joined | member_id | member_id, home_location_id, join_date, age_band, gender | locations |
| memberships | period on one plan | membership_id | membership_id, member_id, plan_id, start_date, end_date (empty if still active), status (active / changed / cancelled) | members, plans |
| check_ins | visit | check_in_id | check_in_id, member_id, location_id, checked_in_at (date and time) | members, locations |
| payments | monthly charge attempt | payment_id | payment_id, member_id, membership_id, charge_date, amount, status (paid / failed) | members, memberships |
| cancellations | cancelled membership | cancellation_id | cancellation_id, membership_id, member_id, cancel_date, reason | memberships, members |

## Business rules
- Plan prices: Basic $25, Standard $40, Premium $70 a month. Mix of new members: 50% / 35% / 15%.
- Age bands: 18-24 20%, 25-34 30%, 35-44 22%, 45-54 15%, 55+ 13%.
- Gender: Female 48%, Male 49%, Not given 3%. Has no effect on visits or churn.
- Billing day: the member's join day each month, capped at the 28th. Amount = price of the plan held that day.
- Plan changes: about 1,000 members change plan once. Old row ends with status "changed", a new row starts the next day. Not a cancellation.
- Failed payments: 3% of charges fail. No retry, no revenue, never causes churn.
- Active member on a date: has a membership row whose start_date is on or before that date and whose end_date is empty or after it.
- Churned member: their latest membership row has status "cancelled".
- Underperforming location: location 10 (Ocala) gets 40% fewer joins and 1.5x the churn chance.
- No joins at a location before its opened_date. No check-ins or payments after a membership ends.
- Check-ins happen at the member's home location only (visits at other locations: optional, add later).

## Planted patterns: the setting, and how I'll test it as a rate
| Pattern | Setting in the generator | Test (rate, not count) |
|---|---|---|
| Jan and Sep join spikes | Join weight 2x in Jan and Sep | Joins per month: Jan and Sep about 2x the average of other months |
| Higher churn in first 90 days | Monthly churn chance doubled in first 90 days | Cancellations per member at risk: first 90 days about 2x later months |
| One weak location | Location 10 (Ocala): 0.6x joins, 1.5x churn | Joins per open month and churn rate at Ocala vs. the others |
| Premium visits more, churns less | Visits a month: Basic 4, Standard 5, Premium 8. Churn: 6% / 5% / 3% | Visits per active member per month, and monthly churn rate, by plan |
| Summer check-in dip | Visits x 0.8 in Jun to Aug | Check-ins per active member per month: Jun to Aug about 20% below other months |

## Deliberate data problems (optional, add after the clean version works)
- 

## Changes from the starting rules (and why)
- 
