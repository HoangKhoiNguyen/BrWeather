"""Reference evaluator for rules/recommendation_rules.json (T6.2-1, T6.2-4).

The production rule engine lives in the backend (T6.2-2, Java). This small evaluator defines the expected
behaviour so the shared case table rules/recommendation_cases.json can be checked automatically here,
and the backend can run the very same table in its own tests.

    evaluate({"pm25_now": 62.5, "rain_prob_max_6h": 70, ...}) ->
    {"recommendations": [{"id", "topic", "message", "evidence", "sources"}, ...],
     "missing_inputs": [...], "missing_topics": [...], "disclaimer": "..."}

Semantics:
  * An input that is missing or null is never treated as 0: rules using it are skipped and reported.
  * Within a group, only the rule with the highest severity that matches is returned.
  * Output order follows the rule order in the JSON file.
"""
import json
import operator
from functools import lru_cache
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parents[3] / "rules" / "recommendation_rules.json"
OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq}


@lru_cache(maxsize=4)
def load_rules(path: str | None = None) -> dict:
    with open(path or RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "có" if value else "không"
    r = round(float(value), 1)
    return str(int(r)) if r == int(r) else f"{r:.1f}".replace(".", ",")


def evaluate(inputs: dict, rules: dict | None = None) -> dict:
    rules = rules or load_rules()
    best: dict[str, dict] = {}
    missing_inputs: set[str] = set()
    topic_inputs: dict[str, set[str]] = {}

    for rule in rules["rules"]:
        name = rule["when"]["input"]
        topic_inputs.setdefault(rule["topic"], set()).add(name)
        value = inputs.get(name)
        if value is None:
            missing_inputs.add(name)
            continue
        if not OPS[rule["when"]["op"]](value, rule["when"]["value"]):
            continue
        current = best.get(rule["group"])
        if current is None or rule["severity"] > current["severity"]:
            best[rule["group"]] = {**rule, "_value": value}

    order = {r["id"]: i for i, r in enumerate(rules["rules"])}
    recs = [{
        "id": r["id"], "topic": r["topic"], "message": r["message"],
        "evidence": r["evidence"].format(value=_fmt(r["_value"])), "sources": r["sources"],
    } for r in sorted(best.values(), key=lambda r: order[r["id"]])]
    missing_topics = sorted(t for t, names in topic_inputs.items() if names <= missing_inputs)
    return {
        "recommendations": recs,
        "missing_inputs": sorted(missing_inputs),
        "missing_topics": missing_topics,
        "disclaimer": rules["disclaimer"],
    }
