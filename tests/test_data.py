"""Data-integrity tests for the built bundle.  Run: python3 -m pytest tests/ -q"""
import json
from collections import Counter
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "site" / "data"
R = json.loads((D / "regions.json").read_text())
REG = R["regions"]
TOPO = json.loads((D / "regions.topo.json").read_text())


def test_ids_unique_and_geometry_matches():
    ids = [r["id"] for r in REG]
    assert len(ids) == len(set(ids)) == 2042
    geo_ids = {g["properties"]["id"] for g in TOPO["objects"]["regions"]["geometries"]}
    assert geo_ids <= set(ids)
    assert len(geo_ids) >= 2040  # mapshaper may drop one degenerate sliver


def test_trajectory_counts_match_paper_1():
    # Newsham & Rowe (2022) Table 4; one Serbian district is unmatched in the boundary file
    paper = [69, 46, 57, 180, 107, 106, 131]
    got = Counter(r["trajectory"] for r in REG if "trajectory" in r)
    assert sum(got.values()) >= 695
    for i, n in enumerate(paper):
        assert abs(got[i] - n) <= 1, (R["trajectories"][i], got[i], n)


def test_signature_counts_match_paper_2():
    # Newsham & Rowe (2025) Table 1
    paper = {"4": 215, "3": 151, "2": 90, "1": 116, "5": 160}
    got = Counter(str(r["signature"]) for r in REG if "signature" in r)
    for k, n in paper.items():
        assert got[k] == n, (k, got[k], n)


def test_states_valid():
    for r in REG:
        if "states" in r:
            assert len(r["states"]) == 18
            assert all(s is None or s in (-2, -1, 0, 1, 2) for s in r["states"])


def test_rates_balance():
    # crude change ≈ births − deaths + net migration (per 1,000) where all observed
    bad = 0
    for r in REG:
        q = r.get("rates")
        if not q:
            continue
        for b, d, m, c in zip(q["birth"], q["death"], q["mig"], q["change"]):
            if None not in (b, d, m, c) and abs((b - d + m) - c) > 0.5:
                bad += 1
    assert bad < 50, bad


def test_declining_areas_lost_population():
    lost = [r["change"] for r in REG if "trajectory" in r and "change" in r]
    assert sum(1 for x in lost if x < 0) / len(lost) > 0.97


def test_payload_budget():
    assert (D / "regions.topo.json").stat().st_size < 1.3e6
    assert (D / "regions.json").stat().st_size < 0.7e6
