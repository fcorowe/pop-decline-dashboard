"""Data-integrity tests for the built bundle.  Run: python3 -m pytest tests/ -q"""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "site" / "data"
R = json.loads((D / "regions.json").read_text())
REG = R["regions"]
TOPO = json.loads((D / "regions.topo.json").read_text())


def test_ids_unique_and_geometry_matches():
    ids = [r["id"] for r in REG]
    assert len(ids) == len(set(ids)) == 2042
    geometry = TOPO["objects"]["regions"]["geometries"]
    assert len(geometry) == len(ids)
    assert {g["properties"]["id"] for g in geometry if g.get("arcs")} == set(ids)
    island = next(g for g in geometry if g["properties"]["id"] == 95)
    assert island["type"] in {"Polygon", "MultiPolygon"}


def test_trajectory_counts_match_paper_1():
    # Newsham & Rowe (2022) Table 4
    paper = [69, 46, 57, 180, 107, 106, 131]
    got = Counter(r["trajectory"] for r in REG if "trajectory" in r)
    assert got == Counter(dict(enumerate(paper)))


def test_signature_counts_match_paper_2():
    # Newsham & Rowe (2025) Table 1
    paper = {"4": 215, "3": 151, "2": 90, "1": 116, "5": 160}
    got = Counter(str(r["signature"]) for r in REG if "signature" in r)
    assert got == Counter(paper)
    assert sum("rates" in r for r in REG) == sum(paper.values())


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


def test_banat_districts_use_the_verified_boundaries():
    areas = {r["name"]: r for r in REG if r.get("country") == "RS"}
    assert (areas["Srednjobanatska"]["id"], areas["Srednjobanatska"]["trajectory"]) == (356, 2)
    assert (areas["Severno-Banatski"]["id"], areas["Severno-Banatski"]["trajectory"]) == (355, 0)
    assert (areas["Juznobanatska"]["id"], areas["Juznobanatska"]["trajectory"]) == (343, 3)
    assert all("rates" in areas[name] for name in ("Srednjobanatska", "Severno-Banatski", "Juznobanatska"))


def test_rates_and_mergesheet_comparison_is_auditable():
    report = json.loads((D / "build_report.json").read_text())
    assert report["paper1_trajectories"]["rows"] == report["paper1_trajectories"]["matched"] == 696
    rates = report["paper2_rates"]
    assert rates["rows"] == rates["matched"] == 732
    disagreements = rates["signature_disagreements"]
    assert rates["signature_overridden_from_rates_file"] == len(disagreements)
    assert disagreements == []  # The supplied inputs agree across the complete joined sample.


def test_fuzzy_match_review_covers_the_explicit_crosswalk():
    report = json.loads((D / "build_report.json").read_text())
    with (ROOT / "data_review" / "matches_for_review.csv").open() as f:
        review = list(csv.DictReader(f))
    with (ROOT / "scripts" / "name_crosswalk.csv").open() as f:
        approved = {(r["country"], r["source_name"], r["map_name"]) for r in csv.DictReader(f)
                    if r["method"] == "fuzzy-reviewed"}
    assert len(review) == report["fuzzy_review_pairs"]
    assert {(r["country"], r["source_name"], r["map_name"]) for r in review} == approved
    assert all(0.8 <= float(r["similarity_score"]) <= 1 for r in review)


def test_coast_comparison_has_every_area_and_detects_north_ossetia():
    with (ROOT / "data_review" / "coast_comparison.csv").open() as f:
        review = {int(r["id"]): r for r in csv.DictReader(f)}
    assert len(review) == len(REG)
    for region in REG:
        assert float(review[region["id"]]["coast_km"]) == region["coast_km"] >= 0
    ossetia = next(r for r in REG if r["name"] == "North Ossetia")
    assert float(review[ossetia["id"]]["gpkg_coast"]) == 1
    assert 100 < ossetia["coast_km"] < 250
