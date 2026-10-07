"""Metric definitions and relevance rules."""
import math

from app import evaluation as ev


def test_precision_recall_ap_definitions():
    grades = {1: 2, 2: 2, 3: 2, 4: 1}            # 3 relevant (grade 2), 1 partial
    m = ev.metrics([1, 9, 2, 8, 7, 3], grades)
    assert m["P@5"] == 2 / 5 and math.isclose(m["R@5"], 2 / 3)            # 2 relevant in the top 5 of 3 relevant overall
    assert math.isclose(m["AP@5"], (1 / 1 + 2 / 3) / min(3, 5))
    assert m["MRR"] == 1.0 and 0 < m["nDCG@10"] <= 1


def test_recall_ceiling_is_small_for_big_relevant_sets():
    grades = {i: 2 for i in range(1000)}
    assert ev.metrics(list(range(5)), grades)["R@5"] == 5 / 1000


def test_relevance_rules(engine):
    j = engine.jobs[0]
    assert ev.rule_ok(j, {"role_family": [j.role_family], "country": [j.country]})
    assert not ev.rule_ok(j, {"role_family": ["Nonexistent"]})
    assert ev.rule_ok(j, {"skills_all": [j.skills[0]]}) and not ev.rule_ok(j, {"skills_all": ["not-a-skill-xyz"]})


def test_sign_flip_test_is_symmetric_and_bounded():
    a, b = [0.9, 0.8, 0.7, 0.9], [0.1, 0.2, 0.1, 0.3]
    p = ev.sign_flip_p(a, b, trials=2000)
    assert 0 < p < 0.2 and ev.sign_flip_p(a, a) == 1.0


def test_judged_queries_are_rules_with_a_fixed_split(engine):
    import json
    spec = json.loads(ev.QUERIES_PATH.read_text())
    assert {q["split"] for q in spec["queries"]} == {"dev", "test"}
    for q in spec["queries"][:5]:
        assert sum(1 for g in ev.grades_for(engine, q).values() if g == 2) >= 5
