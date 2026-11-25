"""Build the catalog of metrics and dimensions the LLM is allowed to choose from.

Reads the semantic layer (ironwood/target/semantic_manifest.json, written by dbt parse)
and writes llm/catalog.json.

Run from the repo root:  python llm/catalog.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ironwood" / "target" / "semantic_manifest.json"
CATALOG = ROOT / "llm" / "catalog.json"

# Time can be grouped at these grains for any metric.
TIME_DIMENSIONS = [
    {"name": "metric_time__day", "description": "The metric's date, by day. Use for a single date such as active members on Dec 31, 2025."},
    {"name": "metric_time__month", "description": "The metric's date, by month."},
    {"name": "metric_time__year", "description": "The metric's date, by year."},
]


def build_catalog() -> dict:
    """Read the semantic manifest and return the metrics and dimensions with descriptions."""
    manifest = json.loads(MANIFEST.read_text())

    # 1. Every metric, with its description
    metrics = [
        {"name": m["name"], "description": m.get("description") or ""}
        for m in manifest["metrics"]
    ]

    # 2. Every categorical dimension, named the way mf query expects: entity__dimension
    dimensions = list(TIME_DIMENSIONS)
    for model in manifest["semantic_models"]:
        primary = next(e["name"] for e in model["entities"] if e["type"] == "primary")
        for d in model.get("dimensions", []):
            if d["type"] == "time":
                continue  # time questions use metric_time instead
            dimensions.append({
                "name": f"{primary}__{d['name']}",
                "description": d.get("description") or "",
            })

    return {
        "metrics": sorted(metrics, key=lambda x: x["name"]),
        "dimensions": dimensions,
    }


def main() -> None:
    catalog = build_catalog()
    CATALOG.write_text(json.dumps(catalog, indent=2))
    print(f"Wrote {len(catalog['metrics'])} metrics and {len(catalog['dimensions'])} dimensions to {CATALOG}")


if __name__ == "__main__":
    main()