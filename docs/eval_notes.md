# Eval notes

Questions tested by hand before the eval set exists.

| # | Question | Correct choice | First result | Fix | After fix |
|---|---|---|---|---|---|
| 1 | Which plan has the highest churn? | monthly_churn_rate by membership__plan_name, -order | Correct | — | Correct |
| 2 | Which gym has the highest churn? | monthly_churn_rate by location__location_name, -order | Correct | — | Correct |
| 3 | What was total revenue by year? | revenue by metric_time__year | Correct | — | Correct |
| 4 | Do Premium members visit more than Basic members? | visits_per_member_month by membership__plan_name | Correct | — | Correct |
| 5 | How many members do we have? | active_members, metric_time__day, 2025-12-31 | Wrong: no date (would count everyone ever) | Prompt rule for "now" + code check | Correct |
| 6 | What is our churn by year? | churn_rate_over_time by metric_time__year | Wrong: monthly_churn_rate | Description + code check | Correct (added an unrequested sort) |
| 7 | How many active members did we have at the end of 2025? | active_members, metric_time__day, 2025-12-31 | Correct | — | Correct |

Notes:
- Questions 1 and 7 closely match the prompt's examples, so they're easy passes.
- The model sometimes adds an order the question didn't ask for (question 6).
- Visits: it rounded 7.48 to 7.5 and 3.74 to 3.7, despite "copy each number exactly". It's harmless here, but it's a rule break. Your Week 5 scoring needs to decide whether that counts as wrong.
- "We have 3,917 active members" leaves out "as of Dec 31, 2025." A real user could take that as today's number. One way to fix it later: show the date in the answer whenever start_time is set.