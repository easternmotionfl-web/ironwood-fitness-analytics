# Ironwood Fitness: metric definitions

These are the business metrics the semantic layer will define and the LLM will answer questions with. Every metric reads from a mart model, never from staging or raw.

**Conventions**
- Data window: Jan 1, 2023 to Dec 31, 2025 (`window_start_date` and `as_of_date` in `dbt_project.yml`).
- A **member-month** is 30 member-days. Rates use member-months, not head counts, so members who joined or left partway through a period are counted for the days they were actually members.
- Dimensions are the labels a metric can be split by. The common ones are month, location, plan, age band and gender.

## Membership

### Active members
- **Definition:** members with a membership row covering a given date. A membership's end date is the member's last day, so a member who cancels on a date still counts as active on that date.
- **Formula:** `count(distinct member_id)` from `fct_memberships` where `start_date <= date <= effective_end_date`.
- **Dimensions:** location, plan (held on that date), age band, gender.
- **Check:** 3,917 on Dec 31, 2025 (one member cancelled that day and is counted as active).
- **Example question:** How many active members did Ocala have at the end of 2025?
- **Watch out:** a point-in-time count. "Active members in March" needs a specific day, normally the last day of the month.
- **Not the same as current status:** `current_status` in `dim_members` shows 3,916 active. It excludes every member whose membership has ended, including the one who cancelled on Dec 31, 2025. Use active members for "as of a date" questions and current status for "who is still a member".

### New members
- **Definition:** members whose first membership started in a period.
- **Formula:** `count(*)` from `dim_members`, grouped by `join_date`.
- **Dimensions:** month, location, age band, gender.
- **Example question:** Which months had the most new members?

### Joins per open month (by location)
- **Definition:** new members at a gym divided by the months it was open in the data window.
- **Formula:** new members / `months_open_in_window` from `dim_locations`.
- **Dimensions:** location.
- **Example question:** Which gym attracts the fewest new members?
- **Watch out:** use this, not total joins, to compare gyms. Ocala and Daytona Beach opened during the window.

## Churn

### Cancellations
- **Definition:** membership rows that ended with status cancelled.
- **Formula:** `count(*)` from `fct_memberships` where `is_cancelled`, grouped by `end_date`.
- **Dimensions:** month, location, plan, cancel reason.
- **Check:** 6,084 in total.
- **Example question:** What are the most common cancellation reasons?
- **Watch out:** a plan change is not a cancellation.

### Monthly churn rate
- **Definition:** cancellations per member-month.
- **Formula:** `sum(is_cancelled) / (sum(member_days) / 30)` from `fct_memberships`.
- **Dimensions:** location, plan, age band, gender.
- **Check:** Basic 7.9%, Standard 6.5%, Premium 3.7%.
- **Example question:** Which plan has the highest churn?
- **Watch out:** for a single month, count only the member-days inside that month. The formula above covers the whole window.

### First-90-day churn rate
- **Definition:** cancellations within 90 days of joining, per member-month spent in the first 90 days.
- **Formula:** as in check 7 in `checks/02_patterns.sql`, using `is_cancelled_first_90_days` from `fct_memberships`.
- **Check:** 10.8% a month, against 4.9% after 90 days.
- **Example question:** Are new members more likely to cancel?

## Revenue

### Revenue
- **Definition:** money collected from paid charges.
- **Formula:** `sum(revenue)` from `fct_payments`, grouped by `charge_date`.
- **Dimensions:** month, location, plan.
- **Check:** $3,768,210.00 in total.
- **Example question:** What was total revenue by location in 2025?
- **Watch out:** `amount` includes failed charges; always use `revenue`.

### Revenue per member-month
- **Definition:** revenue divided by member-months in the same period and group.
- **Formula:** `sum(revenue)` from `fct_payments` / (`sum(member_days)` from `fct_memberships` / 30).
- **Dimensions:** location, plan.
- **Example question:** Which gym earns the most per member?
- **Watch out:** combines two fact tables, so both must be filtered to the same period and group.

### Failed payment rate
- **Definition:** share of charge attempts that failed.
- **Formula:** `count(*) where not is_paid / count(*)` from `fct_payments`.
- **Check:** 3.0%.
- **Example question:** How much revenue did failed payments cost us?

## Engagement

### Visits per 30 member-days
- **Definition:** gym visits per member-month.
- **Formula:** `count(*)` from `fct_check_ins` / (`sum(member_days)` from `fct_memberships` / 30), for the same period and group.
- **Dimensions:** month, location, plan (held on the visit date).
- **Check:** about 4.1 in June to August against about 5.2 in other months.
- **Example question:** Do Premium members visit more than Basic members?
- **Watch out:** never compare raw visit counts across plans. Plans have very different numbers of members, so the totals look similar even though Premium members visit about twice as often.

### Busiest hours
- **Definition:** visits by hour of day.
- **Formula:** `count(*)` from `fct_check_ins`, grouped by `check_in_hour`.
- **Dimensions:** hour, location.
- **Example question:** When is the gym busiest?

## Open questions for the semantic layer
- Monthly trends for churn rate, revenue per member-month and visits need member-days split by month. Decide whether to add a month-by-member model or compute the split in the semantic layer.
- Active members needs a date. Decide on a default (the as-of date) when a question doesn't give one.
