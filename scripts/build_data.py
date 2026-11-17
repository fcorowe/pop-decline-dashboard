#!/usr/bin/env python3
"""Build the lightweight data bundle for the population-decline dashboard.

Inputs (the raw files from the two papers, kept one level above this project):
  Map.gpkg                              boundaries for 2,042 sub-national areas
  Paper 1 - Clusters.csv                7 decline trajectories + annual states (696 areas)
  Paper 1 - PopChangeStates.csv         numeric annual states (-2..2)
  Paper 2 - Mergesheet for maps.csv     area → country, code, depopulation signature
  Paper 2 - Demographic Rates.csv       crude birth, death, net-migration, change rates
  Paper 2 - Cluster Components.csv      signature-level contributions to change

Outputs (site/data/):
  regions.topo.json   simplified TopoJSON, one object "regions", property id
  regions.json        attributes keyed by id
  signatures.json     signature-level component contributions by year
  regions.csv         flat download for users
  build_report.json   join diagnostics

Usage: python3 scripts/build_data.py [--raw ../] [--out site/data]
Requires: pandas, geopandas, and Node with mapshaper (npm i) for simplification.
"""
import argparse
import difflib
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from build_geometry import build_geometry
from coast_distance import LAND_VERSION, coast_distances
from place_attributes import merge_attributes

ROOT = Path(__file__).resolve().parents[1]
ENC = "cp1252"  # the CSVs were exported from Excel on Windows

YEARS_STATE = list(range(2001, 2019))  # 00/01 … 17/18 → labelled by end year
YEARS_RATE = list(range(2000, 2019))

STATE_TEXT = {"Decline": -2, "Moderate Decline": -1, "Stable": 0,
              "Moderate Growth": 1, "Growth": 2}

TRAJ = ["Persistent Decline", "Accelerating Decline", "Diminishing Decline",
        "Persistent Moderate Decline", "Accelerating Moderate Decline",
        "Diminished Decline", "Temporary Decline"]
SIG = {1: "Migration & Fertility Reversal", 2: "Natural Reversal",
       3: "Volatile Dual Deficit", 4: "Steady Dual Deficit",
       5: "Migration Resurgence"}
COUNTRY = {"AL": "Albania", "AN": "Andorra", "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria",
           "BR": "Belarus", "CH": "Switzerland", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany",
           "DK": "Denmark", "EE": "Estonia", "EL": "Greece", "ES": "Spain", "FI": "Finland",
           "FR": "France", "HR": "Croatia", "HU": "Hungary", "IE": "Ireland", "IS": "Iceland",
           "IT": "Italy", "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia",
           "ME": "Montenegro", "MK": "North Macedonia", "ML": "Moldova", "MT": "Malta",
           "NL": "Netherlands", "NO": "Norway", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
           "RS": "Serbia", "RU": "Russia", "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia",
           "SM": "San Marino", "TR": "Türkiye", "UK": "United Kingdom", "UN": "Ukraine"}
NUTS = re.compile(r"^[A-Z]{2}[0-9A-Z]{1,3}$")


def norm(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()
    x = re.sub(r"\(nuts \d{4}\)", "", x)
    return re.sub(r"[^a-z0-9]", "", x)


STOP = r"\b(region|oblast|krai|kray|republic|respublika|apskritis|kreisfreie stadt|landkreis|miasto|city of|mun\.?|okrug|autonomous)\b"


def fuzzy_key(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "replace").decode().lower()
    x = re.sub(r"\(.*?\)", "", x)
    x = re.sub(STOP, "", x)
    x = re.sub(r"[^a-z?]", "", x).replace("kh", "h").replace("y", "i")
    return re.sub(r"(ska|ski|ka|ki|a|i|e)$", "", x)


def clean_geo(v):
    v = str(v).strip()
    return v if NUTS.match(v) else None


def num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def r1(v, d=1):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), d)


def country_code(value):
    value = value.strip()
    names = {name.casefold(): code for code, name in COUNTRY.items()}
    aliases = {"GB": "UK", "GR": "EL", "BY": "BR", "MD": "ML", "UA": "UN", "AD": "AN"}
    return names.get(value.casefold(), aliases.get(value.upper(), value.upper()))


def make_locator(backbone, crosswalk, review):
    by_geo = {v: i for i, v in zip(backbone.id, backbone.geo) if isinstance(v, str)}
    by_cn = {(c, k): i for i, c, k in zip(backbone.id, backbone.country, backbone.k)}
    name_counts = backbone.k.value_counts()
    by_name = {k: i for i, k in zip(backbone.id, backbone.k) if name_counts[k] == 1}
    by_country = {}
    for row in backbone.itertuples():
        by_country.setdefault(row.country, []).append((row.name, fuzzy_key(row.name)))
    approved = {}
    for row in crosswalk.itertuples():
        key = (row.country, norm(row.source_name))
        match = (norm(row.map_name), row.method)
        if row.method not in {"manual", "fuzzy-reviewed"} or approved.get(key, match) != match:
            raise ValueError(f"Invalid or conflicting crosswalk entry: {row.country} {row.source_name}")
        approved[key] = match

    def locate(geo, country, name):
        code = clean_geo(geo)
        if code in by_geo:
            return by_geo[code], "code"
        if not isinstance(name, str) or not name.strip():
            return None, None
        key = norm(name)
        if (country, key) in approved:
            target, method = approved[(country, key)]
            if (country, target) not in by_cn:
                raise ValueError(f"Crosswalk points to an unknown area: {country} {name} -> {target}")
            region_id = by_cn[(country, target)]
            if method == "fuzzy-reviewed":
                map_name = backbone.at[region_id, "name"]
                review.add((name, map_name, country, round(difflib.SequenceMatcher(
                    None, fuzzy_key(name), fuzzy_key(map_name)).ratio(), 6)))
            return region_id, method
        if (country, key) in by_cn:
            return by_cn[(country, key)], "name+country"
        if key in by_name and (not isinstance(country, str) or
                backbone.at[by_name[key], "country"] == country or
                pd.isna(backbone.at[by_name[key], "country"])):
            return by_name[key], "name"
        fuzzy = fuzzy_key(name)
        scored = sorted(((difflib.SequenceMatcher(None, fuzzy, candidate).ratio(), label)
                         for label, candidate in by_country.get(country, [])), reverse=True)
        if scored and scored[0][0] >= 0.8 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.08):
            score, target = scored[0]
            raise ValueError(f"Unreviewed fuzzy match: {country} {name} -> {target} ({score:.3f})")
        return None, None

    return locate


def require_complete(dataset, missing, duplicates):
    if missing or duplicates:
        raise ValueError(f"{dataset}: unmatched {missing}; duplicate targets {duplicates}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT.parent))
    ap.add_argument("--out", default=str(ROOT / "site" / "data"))
    ap.add_argument("--simplify", default="1.5%")
    ap.add_argument("--land", type=Path, default=ROOT / ".cache" / "ne_10m_land.zip")
    ap.add_argument("--review-out", type=Path)
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out)
    review_out = a.review_out or out.parent / "data_review"
    if a.review_out is None and out.resolve() == ROOT / "site" / "data":
        review_out = ROOT / "data_review"
    report = {}
    review = set()

    # ---- backbone: geometry + mergesheet ---------------------------------
    g = gpd.read_file(raw / "Map.gpkg", fid_as_index=True).sort_index().reset_index(drop=True)
    g["id"] = g.index.astype(int)
    g["k"] = g["name"].map(norm)

    m = pd.read_csv(raw / "Paper 2 - Mergesheet for maps.csv", encoding=ENC)
    m.columns = ["area", "country_name", "country", "geo", "signature", "sig_label"]
    m["k"] = m["area"].map(norm)
    m["geo"] = m["geo"].map(clean_geo)
    m = m.drop_duplicates("k")
    b = g.merge(m[["k", "country_name", "country", "geo", "signature"]], on="k", how="left")
    b["geo"] = b["geo"].fillna(b["nuts_id"].map(clean_geo))
    report["backbone_areas"] = len(b)
    report["backbone_without_country"] = b.loc[b.country.isna(), "name"].tolist()

    overrides = pd.read_csv(ROOT / "scripts" / "geometry_overrides.csv")
    for override in overrides.itertuples():
        if b.at[override.id, "name"] != override.original_name:
            raise ValueError(f"Geometry override no longer matches feature {override.id}")
        b.loc[override.id, ["name", "k"]] = [override.map_name, norm(override.map_name)]
    report["geometry_overrides"] = overrides.to_dict("records")
    locate = make_locator(b, pd.read_csv(ROOT / "scripts" / "name_crosswalk.csv"), review)

    rec = {int(i): {"id": int(i), "name": n, "country": c if isinstance(c, str) else None,
                    "countryName": COUNTRY.get(c) if isinstance(c, str) else None,
                    "code": geo if isinstance(geo, str) else None, "coast": int(co) if not pd.isna(co) else None,
                    "signature": int(s) if not pd.isna(s) and int(s) > 0 else None,
                    "trajectory": None, "states": None, "change": None,
                    "rates": None}
           for i, n, c, cn, geo, co, s in zip(b.id, b.name, b.country, b.country_name,
                                              b.geo, b.Coast, b.signature)}

    # ---- Paper 1: trajectories + annual states ---------------------------
    c = pd.read_csv(raw / "Paper 1 - Clusters.csv", encoding=ENC)
    state_cols = [col for col in c.columns if re.match(r"^\d\d/\d\d$", col)]
    assert len(state_cols) == 18, state_cols
    miss, how, dup = [], {}, []
    for _, r in c.iterrows():
        i, h = locate(r["GEO"], r["Country"], r["Name"])
        if i is None:
            miss.append(f'{r["Country"]} {r["Name"]} ({r["GEO"]})'); continue
        how[h] = how.get(h, 0) + 1
        if rec[i]["trajectory"] is not None:
            dup.append(f'{r["Name"]} -> {rec[i]["name"]}')
        rec[i]["trajectory"] = TRAJ.index(r["cl1.4fac_"])
        rec[i]["states"] = [STATE_TEXT.get(r[col]) if isinstance(r[col], str) else None
                            for col in state_cols]
        rec[i]["change"] = num(r["Diff"])
    require_complete("Paper 1 trajectories", miss, dup)
    report["paper1_trajectories"] = {"rows": len(c), "matched": len(c) - len(miss),
                                     "match_method": how, "unmatched": miss,
                                     "duplicate_targets": dup}

    s = pd.read_csv(raw / "Paper 1 - PopChangeStates.csv", encoding=ENC)
    s = s[s["Name"].notna()]
    add = 0
    for _, r in s.iterrows():
        i, _h = locate(r["GEO"], r["Country"], r["Name"])
        if i is None or rec[i]["states"] is not None:
            continue
        rec[i]["states"] = [None if num(r[col]) is None else int(num(r[col])) for col in state_cols]
        rec[i]["change"] = num(r["Diff"])
        add += 1
    report["paper1_states_extra"] = add

    # ---- Paper 2: demographic rates --------------------------------------
    d = pd.read_csv(raw / "Paper 2 - Demographic Rates.csv", encoding=ENC)
    miss, how, sigdiff, dup = [], {}, [], []
    for _, r in d.iterrows():
        i, h = locate(None, r["Country"], r["Name.x"])
        if i is None:
            miss.append(f'{r["Country"]} {r["Name.x"]}'); continue
        how[h] = how.get(h, 0) + 1
        if rec[i]["rates"] is not None:
            dup.append(f'{r["Name.x"]} -> {rec[i]["name"]}')
        rec[i]["rates"] = {
            "birth": [r1(num(r[f"B{y}"])) for y in YEARS_RATE],
            "death": [r1(num(r[f"D{y}"])) for y in YEARS_RATE],
            "mig": [r1(num(r[f"NM{y}"])) for y in YEARS_RATE],
            "change": [r1(num(r[f"R.imp{y}"])) for y in YEARS_RATE],
        }
        rate_cluster = int(r["cluster"])
        if rec[i]["signature"] != rate_cluster:
            sigdiff.append({"id": i, "name": rec[i]["name"], "country": r["Country"],
                            "mergesheet": rec[i]["signature"], "rates": rate_cluster})
        rec[i]["signature"] = rate_cluster
    require_complete("Paper 2 demographic rates", miss, dup)
    mergesheet_only = []
    for region in rec.values():
        if region["signature"] is not None and region["rates"] is None:
            mergesheet_only.append({"id": region["id"], "name": region["name"],
                                    "signature": region["signature"]})
            region["signature"] = None
    report["paper2_rates"] = {
        "rows": len(d), "matched": len(d), "match_method": how, "unmatched": miss,
        "duplicate_targets": dup, "signature_disagreements": sorted(sigdiff, key=lambda row: row["id"]),
        "signature_overridden_from_rates_file": len(sigdiff), "mergesheet_only": mergesheet_only,
    }
    report["place_attributes"] = merge_attributes(
        raw / "Paper 2 - Place attributes.csv", locate, rec, country_code
    )

    # Distance to Natural Earth land exteriors, independent of the gpkg flag.
    for region, distance in zip(rec.values(), coast_distances(b.geometry, a.land), strict=True):
        region["coast_km"] = distance
    report["coast"] = {"source": "Natural Earth 1:10m land", "version": LAND_VERSION,
                       "method": "Minimum polygon-to-exterior shoreline distance in local AEQD (km)"}
    report["fuzzy_review_pairs"] = len(review)

    out.mkdir(parents=True, exist_ok=True)
    report["geometry_restored_after_simplification"] = build_geometry(
        b, ROOT / "node_modules" / "mapshaper" / "bin" / "mapshaper",
        a.simplify, out / "regions.topo.json"
    )
    review_out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sorted(review, key=lambda r: (r[2], r[0].casefold(), r[0], r[1])),
                 columns=["source_name", "map_name", "country", "similarity_score"]).to_csv(
        review_out / "matches_for_review.csv", index=False, lineterminator="\n"
    )
    pd.DataFrame([{key: row[key] for key in ("id", "name", "country", "coast", "coast_km")}
                  for row in rec.values()]).rename(columns={"coast": "gpkg_coast"}).to_csv(
        review_out / "coast_comparison.csv", index=False, lineterminator="\n"
    )

    # ---- Paper 2: signature-level components -----------------------------
    k = pd.read_csv(raw / "Paper 2 - Cluster Components.csv")
    sig = {}
    for cl, grp in k.groupby("cluster"):
        grp = grp.sort_values("year")
        sig[int(cl)] = {
            "label": SIG[int(cl)], "years": grp.year.astype(int).tolist(),
            # Gupta decomposition of the year-on-year change in the rate of population
            # change (per 1,000), 3-yr moving average; positive = pushes towards growth
            "fertility": [r1(v, 3) for v in grp["birth.3ya"]],
            "mortality": [r1(v, 3) for v in grp["death.3ya"]],
            "migration": [r1(v, 3) for v in grp["mig.3ya"]],
            "total": [r1(v, 3) for v in grp["rate.3ya"]],
        }
    (out / "signatures.json").write_text(json.dumps(sig, sort_keys=True, separators=(",", ":"), allow_nan=False))

    # ---- write attributes --------------------------------------------------
    (out / "regions.json").write_text(json.dumps(
        {"years": {"states": YEARS_STATE, "rates": YEARS_RATE},
         "trajectories": TRAJ, "signatures": SIG,
         "regions": [{k: v for k, v in r.items() if v is not None} for r in rec.values()]}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))

    flat = []
    for _, v in sorted(rec.items()):
        row = {key: v[key] for key in ("id", "name", "country", "code", "coast", "coast_km", "change")}
        row["trajectory"] = TRAJ[v["trajectory"]] if v["trajectory"] is not None else ""
        row["signature"] = SIG[v["signature"]] if v["signature"] else ""
        for y, st in zip(YEARS_STATE, v["states"] or [None] * 18):
            row[f"state_{y}"] = st
        flat.append(row)
    pd.DataFrame(flat).to_csv(out / "regions.csv", index=False, lineterminator="\n")

    report["sizes_kb"] = {
        filename: round((out / filename).stat().st_size / 1024)
        for filename in ("regions.json", "regions.topo.json", "signatures.json")
    }
    (out / "build_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, sort_keys=True))
    print(json.dumps({k2: (v2 if not isinstance(v2, dict) else {x: (y if not isinstance(y, list) else len(y)) for x, y in v2.items()})
                      for k2, v2 in report.items() if k2 != "backbone_without_country"}, indent=1))
    print("backbone without country:", len(report["backbone_without_country"]))


if __name__ == "__main__":
    sys.exit(main())
