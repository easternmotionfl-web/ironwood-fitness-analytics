"""Answer a plain-English question about the gym franchise using the semantic layer.

Step 1: turn the question into a metric choice and check it against the catalog.

Run from the repo root:  python llm/ask.py "Which plan has the highest churn?"
"""
import json
import sys

import ollama

from catalog import build_catalog

MODEL = "qwen2.5-coder:7b"

SYSTEM_PROMPT = """You turn questions about a gym franchise into a metric query.

Rules:
- Choose metrics and dimensions ONLY from the catalog below. Never invent names.
- Put anything the question splits by (plan, gym, gender, year, month) in group_by.
- For "highest", "most" or "top", set order to the metric name with a minus sign in front, for example "-monthly_churn_rate". For "lowest" or "least", use the metric name without the minus. Otherwise leave order empty.
- For a question about a single date, such as active members at the end of a year, group by metric_time__day and set start_time and end_time to that date as YYYY-MM-DD. Otherwise leave both empty.
- When comparing groups, use rates, not raw counts: prefer monthly_churn_rate, visits_per_member_month and failed_payment_rate over cancellations, visits and failed_charges.

Catalog:
{catalog}

Examples:
Question: Which plan has the highest churn?
Answer: {{"metrics": ["monthly_churn_rate"], "group_by": ["membership__plan_name"], "order": "-monthly_churn_rate", "start_time": "", "end_time": ""}}

Question: How many active members were there at the end of 2024?
Answer: {{"metrics": ["active_members"], "group_by": ["metric_time__day"], "order": "", "start_time": "2024-12-31", "end_time": "2024-12-31"}}
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
    return json.loads(response["message"]["content"])


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

    return problems


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit('Usage: python llm/ask.py "your question"')
    question = sys.argv[1]

    catalog = build_catalog()
    choice = choose(question, catalog)
    print(json.dumps(choice, indent=2))

    problems = validate(choice, catalog)
    if problems:
        print("Problems:")
        for problem in problems:
            print(" -", problem)
    else:
        print("Choice is valid.")


if __name__ == "__main__":
    main()