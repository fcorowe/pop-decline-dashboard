"""Tests that rebuild with the research inputs kept outside the repository."""
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not (ROOT.parent / "Map.gpkg").is_file(), reason="Raw study inputs are unavailable")
def test_build_is_byte_identical_on_repeat(tmp_path):
    output = tmp_path / "data"
    command = [sys.executable, str(ROOT / "scripts" / "build_data.py"), "--out", str(output)]

    def build_and_hash():
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        return {p.relative_to(tmp_path): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in (output, tmp_path / "data_review") for p in folder.iterdir()}

    assert build_and_hash() == build_and_hash()


@pytest.fixture
def builder(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("build_data")


@pytest.fixture
def matching_inputs(builder):
    bundle = json.loads((ROOT / "site/data/regions.json").read_text())
    records = {r["id"]: r for r in bundle["regions"]}
    frame = builder.pd.DataFrame([{"id": r["id"], "name": r["name"], "k": builder.norm(r["name"]),
                                   "country": r.get("country"), "geo": r.get("code")}
                                  for r in records.values()])
    return records, frame, builder.pd.read_csv(ROOT / "scripts/name_crosswalk.csv")


def test_unreviewed_fuzzy_candidate_fails(builder, matching_inputs):
    _, frame, crosswalk = matching_inputs
    candidate = (crosswalk["country"] == "BG") & (crosswalk["source_name"] == "Montana")
    with pytest.raises(ValueError, match="Unreviewed fuzzy match: BG Montana -> Monta"):
        builder.make_locator(frame, crosswalk[~candidate], set())(None, "BG", "Montana")


def test_place_attributes_merge_code_and_names_without_inventing_values(builder, matching_inputs, tmp_path):
    records, frame, crosswalk = matching_inputs
    locate = builder.make_locator(frame, crosswalk, set())
    missing = builder.merge_attributes(tmp_path / "missing.csv", locate, records, builder.country_code)
    assert missing == {"status": "absent", "matched": 0}
    fixture = ROOT / "tests/fixtures/place-attributes.csv"
    assert builder.merge_attributes(fixture, locate, records, builder.country_code) == {
        "status": "supplied", "rows": 3, "matched": 3,
    }
    assert records[7]["place"]["aged_65_pct"] == 20
    assert records[531]["place"]["settlement_type"] == "rural"
    assert records[10]["place"]["distance_city_1m_km"] == 0
    assert sum("place" in r for r in records.values()) == 3
