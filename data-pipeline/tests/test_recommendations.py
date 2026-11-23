"""T6.2-4: run the shared case table rules/recommendation_cases.json against the rules (T6.2-1)."""
import json
import re
from pathlib import Path

import pytest

from brweather_data.recommendations import RULES_PATH, evaluate, load_rules

CASES = json.loads((RULES_PATH.parent / "recommendation_cases.json").read_text("utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["case_id"])
def test_case_table(case):
    out = evaluate(case["inputs"])
    assert [r["id"] for r in out["recommendations"]] == case["expected_ids"], case["description"]
    assert out["missing_topics"] == case["expected_missing_topics"], case["description"]


def test_every_rule_is_covered_by_a_case_and_has_a_source():
    rules = load_rules()
    covered = {i for c in CASES for i in c["expected_ids"]}
    assert {r["id"] for r in rules["rules"]} <= covered
    for r in rules["rules"]:
        assert r["sources"] and all(s in rules["sources"] for s in r["sources"]), r["id"]


def test_every_threshold_has_a_case_on_the_boundary():
    rules = load_rules()
    for r in rules["rules"]:
        name, value = r["when"]["input"], r["when"]["value"]
        if isinstance(value, bool):
            continue
        assert any(c["inputs"].get(name) == value for c in CASES), f"no boundary case for {r['id']} = {value}"


def test_evidence_quotes_the_input_value_and_disclaimer_is_present():
    out = evaluate({"pm25_now": 62.5, "rain_prob_max_6h": 70})
    texts = {r["id"]: r["evidence"] for r in out["recommendations"]}
    assert texts["PM_MASK"] == "PM2.5 hiện tại 62,5 µg/m³, trên mức 50 µg/m³."
    assert texts["RAIN_COAT"] == "Khả năng có mưa trong 6 giờ tới lên tới 70%."
    assert out["disclaimer"] == "Khuyến cáo chung, không thay thế tư vấn y tế."


def test_messages_do_not_give_medical_treatment_or_aqi():
    for r in load_rules()["rules"]:
        text = (r["message"] + " " + r["evidence"]).lower()
        for word in ("thuốc", "aqi", "chẩn đoán", "điều trị"):
            assert word not in text, (r["id"], word)


def test_rain_wording_does_not_turn_probability_into_duration():
    """US1.2: 60% chance of rain is not 'rain 60% of the time'."""
    for r in load_rules()["rules"]:
        assert not re.search(r"\d+\s*% thời gian", r["evidence"])
