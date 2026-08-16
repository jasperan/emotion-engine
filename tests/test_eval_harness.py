"""Step 8: offline eval harness tests.

Covers:
- scenario registry lists the built-in scenarios
- a single (scenario, seed) run produces cooperation + emergence + fingerprint
- run_matrix executes scenario × seeds headlessly
- determinism fingerprints match for identical (scenario, seed) repeats
- check_determinism flags divergences
"""

from __future__ import annotations

import pytest

from emotionsim.eval import harness
from emotionsim.eval.metrics import compute_run_metrics, run_fingerprint


@pytest.mark.asyncio
async def test_list_scenarios():
    names = harness.list_scenarios()
    assert "Rising Flood" in names
    assert len(names) >= 2


@pytest.mark.asyncio
async def test_run_matrix_produces_metrics():
    results = await harness.run_matrix(
        scenario_names=["Rising Flood"],
        seeds=[1, 2],
        max_steps=2,
    )
    assert len(results) == 2
    for r in results:
        assert r["scenario"] == "Rising Flood"
        assert 0.0 <= r["cooperation_score"] <= 1.0
        assert "emergence" in r
        assert r["emergence"]["steps"] == 2
        assert r["emergence"]["total_actions"] >= 1
        assert len(r["fingerprint"]) == 64  # sha256 hex


@pytest.mark.asyncio
async def test_determinism_matches_for_same_seed():
    a = await harness.run_matrix(["Rising Flood"], [42], max_steps=2)
    b = await harness.run_matrix(["Rising Flood"], [42], max_steps=2)
    assert a[0]["fingerprint"] == b[0]["fingerprint"]
    assert a[0]["cooperation_score"] == b[0]["cooperation_score"]


def test_check_determinism_detects_violations():
    results = [
        {"scenario": "S", "seed": 1, "fingerprint": "aa"},
        {"scenario": "S", "seed": 1, "fingerprint": "bb"},  # divergence
        {"scenario": "S", "seed": 2, "fingerprint": "cc"},
        {"scenario": "S", "seed": 2, "fingerprint": "cc"},
    ]
    violations = harness.check_determinism(results)
    assert len(violations) == 1
    assert violations[0]["scenario"] == "S"
    assert violations[0]["seed"] == 1


def test_check_determinism_clean():
    results = [
        {"scenario": "S", "seed": 1, "fingerprint": "aa"},
        {"scenario": "S", "seed": 1, "fingerprint": "aa"},
    ]
    assert harness.check_determinism(results) == []


@pytest.mark.asyncio
async def test_prompt_variants_change_fingerprint(db_session):
    """Different prompt variants produce different (but self-consistent) runs."""
    results = await harness.run_matrix(
        scenario_names=["Rising Flood"],
        seeds=[7],
        max_steps=2,
        prompt_variants=["default", "altruistic"],
    )
    assert len(results) == 2
    assert {r["prompt_variant"] for r in results} == {"default", "altruistic"}
    assert results[0]["fingerprint"] != results[1]["fingerprint"]
    # Same variant + same seed → same fingerprint
    again = await harness.run_matrix(
        ["Rising Flood"], [7], max_steps=2, prompt_variants=["altruistic"],
    )
    assert again[0]["fingerprint"] == results[1]["fingerprint"]


@pytest.mark.asyncio
async def test_run_eval_summary():
    summary = await harness.run_eval(
        scenario_names=["Rising Flood"],
        seeds=2,
        max_steps=2,
        repeat=2,
    )
    assert summary["run_count"] == 4  # 1 scenario × 2 seeds × 2 repeats
    assert summary["deterministic"] is True
    assert summary["determinism_violations"] == []
    assert "Rising Flood" in summary["per_scenario"]
    assert "cooperation_avg" in summary["per_scenario"]["Rising Flood"]
    assert len(summary["results"]) == 4


def test_run_fingerprint_normalizes_agent_ids():
    payload_a = {
        "step": 1,
        "world_state": {
            "hazard_level": 4,
            "agents": {"uuid-1": {"name": "Ada", "location": "Town Square"}},
        },
        "actions": [{"agent_name": "Ada", "action_type": "move", "target": "Hill"}],
        "messages": [],
    }
    payload_b = {
        "step": 1,
        "world_state": {
            "hazard_level": 4,
            "agents": {"uuid-999": {"name": "Ada", "location": "Town Square"}},
        },
        "actions": [{"agent_name": "Ada", "action_type": "move", "target": "Hill"}],
        "messages": [],
    }
    assert run_fingerprint([payload_a]) == run_fingerprint([payload_b])
