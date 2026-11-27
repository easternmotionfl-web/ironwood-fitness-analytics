"""Answer a plain-English question about the gym franchise using the semantic layer.

1. Choose: the model turns the question into a metric choice.
2. Check: the choice is checked against the catalog and business rules.
3. Run: MetricFlow runs the query and returns the numbers and the SQL.
4. Answer: the model writes a short answer using only those numbers.
5. Log: everything is saved to llm/logs/answers.jsonl.

Run from the repo root:  python llm/ask.py "Which plan has the highest churn?"
"""
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import ollama

from catalog import build_catalog

MODEL = "qwen2.5-coder:7b"

ROOT = Path(__file__).resolve().parents[1]
DBT_DIR = ROOT / "ironwood"
LOG_DIR = ROOT / "llm" / "logs"
RESULT_FILE = LOG_DIR / "last_result.csv"
LOG_FILE = LOG_DIR / "answers.jsonl"
MF = Path(sys.executable).parent / "mf"  # the mf command inside .venv

SYSTEM_PROMPT = """You turn questions about a gym franchise into a metric query.

Rules:
- Choose metrics and dimensions ONLY from the catalog below. Never invent names.
- Put anything the question splits by (plan, gym, gender, year, month) in group_by.
- For "highest", "most" or "top", set order to the metric name with a minus sign in front, for example "-monthly_churn_rate". For "lowest" or "least", use the metric name without the minus. Otherwise leave order empty.
- For a question about a single date, such as active members at the end of a year, group by metric_time__day and set start_time and end_time to that date as YYYY-MM-DD. Otherwise leave both empty.
- When comparing groups, use rates, not raw counts: prefer monthly_churn_rate, visits_per_member_month and failed_payment_rate over cancellations, visits and failed_charges.
- The data runs to 2025-12-31. Questions about now, currently, or "how many members do we have" mean that date: use active_members grouped by metric_time__day with start_time and end_time set to 2025-12-31.

Catalog:
{catalog}

Examples:
Question: Which plan has the highest churn?
Answer: {{"metrics": ["monthly_churn_rate"], "group_by": ["membership__plan_name"], "order": "-monthly_churn_rate", "start_time": "", "end_time": ""}}

Question: How many active members were there at the end of 2024?
Answer: {{"metrics": ["active_members"], "group_by": ["metric_time__day"], "order": "", "start_time": "2024-12-31", "end_time": "2024-12-31"}}
"""

ANSWER_PROMPT = """Answer the question in one or two sentences, using ONLY the numbers in the result below.
- Rates are fractions: show them as percentages with one decimal place (0.0791 is 7.9%).
- Show money with a dollar sign and commas.
- Do not add any fact, cause or number that is not in the result.
- If the question compares groups, give the number for each group it mentions.

Examples (made-up numbers, showing the style only):

Question: Which gym has the lowest failed payment rate?
Result:
[{{"location__location_name": "Orange Park", "failed_payment_rate": "2.1%"}}, {{"location__location_name": "Ocala", "failed_payment_rate": "4.0%"}}]
Answer: Orange Park has the lowest failed payment rate at 2.1%, compared with 4.0% at Ocala.

Question: How many visits were there by year?
Result:
[{{"metric_time__year": "2023", "visits": "98,000"}}, {{"metric_time__year": "2024", "visits": "150,000"}}]
Answer: There were 98,000 visits in 2023 and 150,000 in 2024.

Now answer the real question using only the real result.

Question: {question}

Result:
{rows}

"""


def make_schema(catalog: dict) -> dict:
    """The exact JSON shape the model must return. The enum lists limit it to real names."""
    metric_names = [m["name"] for m in catalog["metrics"]]
    dimension_names = [d["name"] for d in catalog["dimensions"]]
    return {
        "type": "object",
        "properties": {
            "metrics": {"type": "array", "items": {"type": "string", "enum": metric_names}},
            "group_by": {"type": "array", "items": {"type": "string", "enum": dimension_names}},
            "order": {"type": "string"},
            "start_time": {"type": "string"},
            "end_time": {"type": "string"},
        },
        "required": ["metrics", "group_by", "order", "start_time", "end_time"],
    }


def choose(question: str, catalog: dict) -> dict:
    """Ask the model which metrics and dimensions answer the question."""
    prompt = SYSTEM_PROMPT.format(catalog=json.dumps(catalog, indent=2))
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ],
        format=make_schema(catalog),
        options={"temperature": 0},
    )
    choice = json.loads(response["message"]["content"])
    # Small models sometimes repeat a name: keep each one once, in order
    choice["metrics"] = list(dict.fromkeys(choice["metrics"]))
    choice["group_by"] = list(dict.fromkeys(choice["group_by"]))
    return choice

def validate(choice: dict, catalog: dict) -> list:
    """Return a list of problems with the choice. An empty list means it's valid."""
    metric_names = {m["name"] for m in catalog["metrics"]}
    dimension_names = {d["name"] for d in catalog["dimensions"]}
    problems = []

    if not choice["metrics"]:
        problems.append("No metric chosen.")
    for name in choice["metrics"]:
        if name not in metric_names:
            problems.append(f"Unknown metric: {name}")
    for name in choice["group_by"]:
        if name not in dimension_names:
            problems.append(f"Unknown dimension: {name}")

    allowed_order = {""}
    for name in choice["metrics"] + choice["group_by"]:
        allowed_order.add(name)
        allowed_order.add("-" + name)
    if choice["order"] not in allowed_order:
        problems.append(f"Order must use a chosen metric or dimension: {choice['order']}")

    # Business rules that must always hold, whatever the model chose
    if "active_members" in choice["metrics"] and not choice["start_time"]:
        problems.append("active_members needs a single date: set start_time and end_time.")
    time_groups = [g for g in choice["group_by"] if g.startswith("metric_time")]
    if "monthly_churn_rate" in choice["metrics"] and time_groups:
        problems.append("monthly_churn_rate can't be grouped by time: use churn_rate_over_time.")

    return problems


def build_command(choice: dict) -> list:
    """Turn the checked choice into an mf query command, as a list of words."""
    command = [str(MF), "query", "--metrics", ",".join(choice["metrics"])]
    if choice["group_by"]:
        command += ["--group-by", ",".join(choice["group_by"])]
    time_groups = [g for g in choice["group_by"] if g.startswith("metric_time")]
    if choice["order"]:
        command += ["--order", choice["order"]]
    elif time_groups:
        command += ["--order", time_groups[0]]  # time results always in date order
    if choice["start_time"]:
        command += ["--start-time", choice["start_time"]]
    if choice["end_time"]:
        command += ["--end-time", choice["end_time"]]
    return command


def tidy_rows(rows: list) -> list:
    """Make results easier to read: short dates and rounded numbers."""
    tidy = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            if key.endswith("__year"):
                value = value[:4]            # 2024-01-01 00:00:00 -> 2024
            elif key.endswith("__month"):
                value = value[:7]            # -> 2024-01
            elif key.endswith("__day"):
                value = value[:10]           # -> 2024-01-31
            else:
                try:
                    number = round(float(value), 4)
                    value = int(number) if number.is_integer() else number
                except ValueError:
                    pass                     # not a number, e.g. a plan name
            new_row[key] = value
        tidy.append(new_row)
    return tidy


def format_value(key: str, value):
    """Show a number the way a person would read it."""
    if not isinstance(value, (int, float)):
        return value                      # text or a date: leave it
    if key == "revenue":
        return f"${value:,.0f}"           # 1366745 -> $1,366,745
    if "_rate" in key:
        return f"{value:.1%}"             # 0.0791 -> 7.9%
    if isinstance(value, float):
        return f"{value:,.2f}"            # 3.7389 -> 3.74
    return f"{value:,}"                   # 3917 -> 3,917


def format_rows(rows: list) -> list:
    """Format every value in the result for people to read."""
    return [{key: format_value(key, value) for key, value in row.items()} for row in rows]


def run_query(choice: dict) -> tuple:
    """Run the query through MetricFlow. Return the result rows and the SQL it used."""
    LOG_DIR.mkdir(exist_ok=True)
    command = build_command(choice)

    # 1. Run the query and save the result as a CSV file
    run = subprocess.run(command + ["--csv", str(RESULT_FILE)], cwd=DBT_DIR, capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"MetricFlow failed:\n{run.stdout}\n{run.stderr}")
    with open(RESULT_FILE, newline="") as f:
        rows = tidy_rows(list(csv.DictReader(f)))

    # 2. Run it again with --explain to get the SQL, without running it
    explain = subprocess.run(command + ["--explain"], cwd=DBT_DIR, capture_output=True, text=True)


    # Keep only the SQL: drop mf's progress messages before it
    lines = explain.stdout.splitlines()
    first = next((i for i, line in enumerate(lines) if line.startswith(("WITH", "SELECT"))), 0)
    sql = "\n".join(lines[first:])
    return rows, sql


def write_answer(question: str, rows: list) -> str:
    """Ask the model for a short answer, using only the result rows."""
    prompt = ANSWER_PROMPT.format(question=question, rows=json.dumps(rows, indent=2))
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0},
    )
    return response["message"]["content"].strip()


def log_answer(record: dict) -> None:
    """Add one line to the log file: one JSON record per question."""
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit('Usage: python llm/ask.py "your question"')
    question = sys.argv[1]

    catalog = build_catalog()
    choice = choose(question, catalog)
    print(json.dumps(choice, indent=2))

    problems = validate(choice, catalog)
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "question": question,
        "choice": choice,
        "problems": problems,
    }
    if problems:
        print("Problems:")
        for problem in problems:
            print(" -", problem)
        log_answer(record)
        return

    try:
        rows, sql = run_query(choice)
    except RuntimeError as error:
        print(error)
        record["error"] = str(error)
        log_answer(record)
        return
    shown = format_rows(rows)
    answer = write_answer(question, shown)

    print("\nResult:")
    for row in shown:
        print("  " + " | ".join(str(value) for value in row.values()))
    print("\nAnswer:", answer)
    print("\nSQL used:\n" + sql)

    record.update({"rows": rows, "shown": shown, "answer": answer, "sql": sql})
    log_answer(record)


if __name__ == "__main__":
    main()