"""Generate synthetic Ironwood Fitness data into data/ironwood.duckdb (schema: raw).

Run from the repo root, with the virtual environment active:
    python generator/generate.py

Same SEED = same data, every run. Never use today's date anywhere: everything
is relative to START and AS_OF.
"""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Settings: the rule sheet in code. Change values here, not inside functions.
# ---------------------------------------------------------------------------
SEED = 42
START = pd.Timestamp("2023-01-01")
AS_OF = pd.Timestamp("2025-12-31")
N_MEMBERS = 10_000
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ironwood.duckdb"

PLAN_MIX = {"Basic": 0.50, "Standard": 0.35, "Premium": 0.15}
MONTHLY_CHURN = {"Basic": 0.06, "Standard": 0.05, "Premium": 0.03}
FIRST_90_DAY_CHURN_MULTIPLIER = 2.0          # pattern 2
VISITS_PER_MONTH = {"Basic": 4, "Standard": 5, "Premium": 8}  # pattern 4
SUMMER_MONTHS = {6, 7, 8}                    # pattern 5
SUMMER_VISIT_FACTOR = 0.8
PEAK_JOIN_MONTHS = {1, 9}                    # pattern 1
PEAK_JOIN_FACTOR = 2.0
WEAK_LOCATION_ID = 10                        # pattern 3 (Ocala)
WEAK_JOIN_FACTOR = 0.6
WEAK_CHURN_FACTOR = 1.5
PLAN_CHANGE_CANDIDATES = 1_900           # about 1,000 actually change (others churn first)
FAILED_PAYMENT_RATE = 0.03
AGE_BANDS = {"18-24": 0.20, "25-34": 0.30, "35-44": 0.22, "45-54": 0.15, "55+": 0.13}
GENDER_MIX = {"Female": 0.48, "Male": 0.49, "Not given": 0.03}
# Check-in hour weights for 5am to 10pm: busiest early morning and after work
HOUR_WEIGHTS = [4, 8, 9, 7, 5, 4, 4, 5, 5, 4, 4, 6, 9, 10, 8, 6, 3, 1]
# Cancellation reason: (weight for later leavers, weight for first-90-day leavers)
CANCEL_REASONS = {
    "Cost": (0.30, 0.25),
    "Not using it": (0.25, 0.45),
    "Switched gyms": (0.20, 0.15),
    "Moving": (0.15, 0.10),
    "Injury or health": (0.10, 0.05),
}


# ---------------------------------------------------------------------------
# Finished tables
# ---------------------------------------------------------------------------
def make_locations() -> pd.DataFrame:
    """10 gyms. Two open during the data window, so joins must respect open dates."""
    rows = [
        (1, "Jacksonville - Southside", "2019-03-01"),
        (2, "Jacksonville - Riverside", "2020-06-15"),
        (3, "St. Augustine", "2021-01-10"),
        (4, "Orlando - Winter Park", "2018-09-01"),
        (5, "Orlando - Lake Nona", "2022-02-01"),
        (6, "Tampa - Westshore", "2019-11-01"),
        (7, "Gainesville", "2021-08-01"),
        (8, "Tallahassee", "2020-01-15"),
        (9, "Daytona Beach", "2023-07-01"),
        (10, "Ocala", "2024-04-01"),
    ]
    df = pd.DataFrame(rows, columns=["location_id", "location_name", "opened_date"])
    df["opened_date"] = pd.to_datetime(df["opened_date"])
    return df


def make_plans() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "plan_id": [1, 2, 3],
            "plan_name": ["Basic", "Standard", "Premium"],
            "monthly_price": [25.00, 40.00, 70.00],
        }
    )


# ---------------------------------------------------------------------------
# Wednesday
# ---------------------------------------------------------------------------
def make_members(rng: np.random.Generator, locations: pd.DataFrame) -> pd.DataFrame:
    """One row per person who ever joined."""
    # 1. Every month in the window, with a join weight (2x in Jan and Sep)
    months = pd.date_range(START, AS_OF, freq="MS")
    weights = np.array([PEAK_JOIN_FACTOR if m.month in PEAK_JOIN_MONTHS else 1.0 for m in months])
    weights = weights / weights.sum()

    # 2. A join month for every member, then a random day in that month
    join_months = pd.DatetimeIndex(rng.choice(months, size=N_MEMBERS, p=weights))
    days = rng.integers(1, join_months.days_in_month + 1)
    join_dates = join_months + pd.to_timedelta(days - 1, unit="D")

    # 3. A home location, only among gyms open on the join date, Ocala weighted down
    loc_ids = locations["location_id"].to_numpy()
    opened = locations["opened_date"].to_numpy()
    base_weight = np.where(loc_ids == WEAK_LOCATION_ID, WEAK_JOIN_FACTOR, 1.0)
    home = []
    for d in join_dates:
        w = np.where(opened <= d.to_datetime64(), base_weight, 0.0)
        home.append(rng.choice(loc_ids, p=w / w.sum()))

    # 4. Age band and gender
    age_band = rng.choice(list(AGE_BANDS), size=N_MEMBERS, p=list(AGE_BANDS.values()))
    gender = rng.choice(list(GENDER_MIX), size=N_MEMBERS, p=list(GENDER_MIX.values()))

    # 5. Put it together, oldest first, and number the members
    df = pd.DataFrame({"home_location_id": home, "join_date": join_dates,
                       "age_band": age_band, "gender": gender})
    df = df.sort_values("join_date", kind="stable").reset_index(drop=True)
    df.insert(0, "member_id", np.arange(1, len(df) + 1))
    return df


def make_memberships(rng: np.random.Generator, members: pd.DataFrame) -> pd.DataFrame:
    """One row per plan period. Churn and plan changes are decided here."""
    plan_names = list(PLAN_MIX)
    plan_ids = {"Basic": 1, "Standard": 2, "Premium": 3}

    # 1. Each member's starting plan, and which members will try a plan change
    start_plans = rng.choice(plan_names, size=len(members), p=list(PLAN_MIX.values()))
    changers = set(rng.choice(members["member_id"], size=PLAN_CHANGE_CANDIDATES, replace=False))

    rows = []
    for m, plan in zip(members.itertuples(), start_plans):
        joined = m.join_date
        row_start = joined
        change_month = int(rng.integers(2, 13)) if m.member_id in changers else None
        k = 1
        while True:
            month_start = joined + pd.DateOffset(months=k - 1)
            month_end = joined + pd.DateOffset(months=k) - pd.Timedelta(days=1)

            # 2. Plan change at the start of this month: end the old row, start a new one
            if k == change_month and month_start <= AS_OF:
                rows.append((m.member_id, plan_ids[plan], row_start, month_start - pd.Timedelta(days=1), "changed"))
                plan = rng.choice([p for p in plan_names if p != plan])
                row_start = month_start

            # 3. Still running at the as-of date: the row stays open
            if month_end > AS_OF:
                rows.append((m.member_id, plan_ids[plan], row_start, pd.NaT, "active"))
                break

            # 4. Churn chance for this month of membership
            chance = MONTHLY_CHURN[plan]
            if (month_start - joined).days < 90:
                chance *= FIRST_90_DAY_CHURN_MULTIPLIER
            if m.home_location_id == WEAK_LOCATION_ID:
                chance *= WEAK_CHURN_FACTOR
            if rng.random() < chance:
                cancel_date = month_end - pd.Timedelta(days=int(rng.integers(0, 28)))
                cancel_date = max(cancel_date, row_start)
                rows.append((m.member_id, plan_ids[plan], row_start, cancel_date, "cancelled"))
                break
            k += 1

    # 5. Put it together and number the rows
    df = pd.DataFrame(rows, columns=["member_id", "plan_id", "start_date", "end_date", "status"])
    df = df.sort_values(["member_id", "start_date"], kind="stable").reset_index(drop=True)
    df.insert(0, "membership_id", np.arange(1, len(df) + 1))
    return df


# ---------------------------------------------------------------------------
# Thursday
# ---------------------------------------------------------------------------
def make_check_ins(rng: np.random.Generator, memberships: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    """One row per visit, at the member's home gym, only while a membership row is running."""
    home = members.set_index("member_id")["home_location_id"]
    plan_names = {1: "Basic", 2: "Standard", 3: "Premium"}
    hour_probs = np.array(HOUR_WEIGHTS) / sum(HOUR_WEIGHTS)

    member_ids, days = [], []
    for row in memberships.itertuples():
        start = row.start_date
        end = row.end_date if pd.notna(row.end_date) else AS_OF
        visits = VISITS_PER_MONTH[plan_names[row.plan_id]]

        # 1. Walk each calendar month the row covers
        for month in pd.date_range(start.replace(day=1), end, freq="MS"):
            seg_start = max(start, month)
            seg_end = min(end, month + pd.offsets.MonthEnd(0))
            n_days = (seg_end - seg_start).days + 1

            # 2. Expected visits scale with the share of the month covered, lower in summer
            expected = visits * n_days / month.days_in_month
            if month.month in SUMMER_MONTHS:
                expected *= SUMMER_VISIT_FACTOR
            n = rng.poisson(expected)

            # 3. A random day in the covered part of the month for each visit
            offsets = rng.integers(0, n_days, size=n)
            days.append(seg_start.to_datetime64() + offsets.astype("timedelta64[D]"))
            member_ids.append(np.full(n, row.member_id))

    member_ids = np.concatenate(member_ids)
    days = np.concatenate(days)

    # 4. A time of day: busiest early morning and after work
    hours = rng.choice(np.arange(5, 23), size=len(days), p=hour_probs)
    minutes = rng.integers(0, 60, size=len(days))
    check_in_at = (pd.to_datetime(days) + pd.to_timedelta(hours, unit="h")
                   + pd.to_timedelta(minutes, unit="m"))

    df = pd.DataFrame({"member_id": member_ids,
                       "location_id": home.loc[member_ids].to_numpy(),
                       "check_in_at": check_in_at})
    df = df.sort_values(["check_in_at", "member_id"], kind="stable").reset_index(drop=True)
    df.insert(0, "check_in_id", np.arange(1, len(df) + 1))
    return df


def make_payments(rng: np.random.Generator, memberships: pd.DataFrame, plans: pd.DataFrame) -> pd.DataFrame:
    """One row per monthly charge attempt, on the member's billing day."""
    price = plans.set_index("plan_id")["monthly_price"]
    # The member's first row starts on their join date, which sets the billing day
    join_date = memberships.groupby("member_id")["start_date"].min()

    rows = []
    for row in memberships.itertuples():
        start = row.start_date
        end = row.end_date if pd.notna(row.end_date) else AS_OF
        joined = join_date[row.member_id]
        bill_day = min(joined.day, 28)

        # 1. One charge a month on the billing day, while the row is running
        for month in pd.date_range(start.replace(day=1), end, freq="MS"):
            charge = month.replace(day=bill_day)
            if start <= charge <= end:
                rows.append((row.member_id, row.membership_id, charge, price[row.plan_id]))

        # 2. Members who join on the 29th to 31st pay on their join date first
        if start == joined and joined.day > 28:
            rows.append((row.member_id, row.membership_id, joined, price[row.plan_id]))

    df = pd.DataFrame(rows, columns=["member_id", "membership_id", "charge_date", "amount"])

    # 3. A small share of charges fail: no retry, and they never cause churn
    df["status"] = np.where(rng.random(len(df)) < FAILED_PAYMENT_RATE, "failed", "paid")
    df = df.sort_values(["charge_date", "member_id"], kind="stable").reset_index(drop=True)
    df.insert(0, "payment_id", np.arange(1, len(df) + 1))
    return df


def make_cancellations(rng: np.random.Generator, memberships: pd.DataFrame) -> pd.DataFrame:
    """Derived, not generated: one row per cancelled membership, plus a reason."""
    join_date = memberships.groupby("member_id")["start_date"].min()
    cancelled = memberships[memberships["status"] == "cancelled"].copy()

    # 1. Early leavers (first 90 days) are more likely to say "Not using it"
    tenure = (cancelled["end_date"] - cancelled["member_id"].map(join_date)).dt.days
    early = (tenure < 90).to_numpy()
    reasons = list(CANCEL_REASONS)
    p_late = np.array([w for w, _ in CANCEL_REASONS.values()])
    p_early = np.array([w for _, w in CANCEL_REASONS.values()])
    cancelled["reason"] = [rng.choice(reasons, p=p_early if e else p_late) for e in early]

    df = cancelled.rename(columns={"end_date": "cancel_date"})[
        ["member_id", "membership_id", "cancel_date", "reason"]]
    df = df.sort_values(["cancel_date", "member_id"], kind="stable").reset_index(drop=True)
    df.insert(0, "cancellation_id", np.arange(1, len(df) + 1))
    return df


# ---------------------------------------------------------------------------
# Output and checks (finished)
# ---------------------------------------------------------------------------
def fingerprint(tables: dict[str, pd.DataFrame]) -> None:
    """Row count and a content checksum per table. Run twice and compare."""
    for name, df in tables.items():
        checksum = int(pd.util.hash_pandas_object(df, index=False).sum()) if len(df) else 0
        print(f"{name:<15} {len(df):>9,} rows   checksum {checksum}")


def write_tables(tables: dict[str, pd.DataFrame]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DB_PATH)) as con:
        con.execute("create schema if not exists raw")
        for name, df in tables.items():
            con.register("incoming", df)
            con.execute(f"create or replace table raw.{name} as select * from incoming")
            con.unregister("incoming")
    print(f"Wrote {len(tables)} tables to {DB_PATH}")


def main() -> None:
    rng = np.random.default_rng(SEED)
    locations = make_locations()
    plans = make_plans()
    members = make_members(rng, locations)
    memberships = make_memberships(rng, members)
    check_ins = make_check_ins(rng, memberships, members)
    payments = make_payments(rng, memberships, plans)
    cancellations = make_cancellations(rng, memberships)

    tables = {
        "locations": locations,
        "plans": plans,
        "members": members,
        "memberships": memberships,
        "check_ins": check_ins,
        "payments": payments,
        "cancellations": cancellations,
    }
    fingerprint(tables)
    write_tables(tables)


if __name__ == "__main__":
    main()
