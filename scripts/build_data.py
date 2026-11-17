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
import argparse, difflib, json, re, subprocess, sys, unicodedata
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

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
        return None if np.isnan(f) else f
    except (TypeError, ValueError):
        return None


def r1(v, d=1):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT.parent))
    ap.add_argument("--out", default=str(ROOT / "site" / "data"))
    ap.add_argument("--simplify", default="1.5%")
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {}

    # ---- backbone: geometry + mergesheet ---------------------------------
    g = gpd.read_file(raw / "Map.gpkg").reset_index(drop=True)
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

    # lookup helpers: GEO code first, then country+name, then name alone if unique
    by_geo = {v: i for i, v in zip(b.id, b.geo) if v}
    by_cn = {(c, k): i for i, c, k in zip(b.id, b.country, b.k)}
    name_counts = b.k.value_counts()
    by_n = {k: i for i, k in zip(b.id, b.k) if name_counts[k] == 1}

    # manual crosswalk for names that differ by language/transliteration
    xw = {}
    xw_path = ROOT / "scripts" / "name_crosswalk.csv"
    if xw_path.exists():
        for _, r in pd.read_csv(xw_path).iterrows():
            xw[(r["country"], norm(r["source_name"]))] = norm(r["map_name"])

    by_country = {}
    for i, c, n in zip(b.id, b.country, b.name):
        by_country.setdefault(c, []).append((i, fuzzy_key(n)))

    def locate(geo, country, name):
        geo = clean_geo(geo)
        if geo and geo in by_geo:
            return by_geo[geo], "code"
        k = norm(name)
        k = xw.get((country, k), k)
        if (country, k) in by_cn:
            return by_cn[(country, k)], "name+country"
        if k in by_n:
            return by_n[k], "name"
        # fuzzy, restricted to the same country; accept only a clear winner
        fk = fuzzy_key(name)
        scored = sorted(((difflib.SequenceMatcher(None, fk, ck).ratio(), i)
                         for i, ck in by_country.get(country, [])), reverse=True)
        if scored and scored[0][0] >= 0.8 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.08):
            return scored[0][1], "fuzzy"
        return None, None

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
    miss, how, fuzzy, dup = [], {}, [], []
    for _, r in c.iterrows():
        i, h = locate(r["GEO"], r["Country"], r["Name"])
        if i is None:
            miss.append(f'{r["Country"]} {r["Name"]} ({r["GEO"]})'); continue
        how[h] = how.get(h, 0) + 1
        if h == "fuzzy":
            fuzzy.append(f'{r["Country"]} {r["Name"]} -> {rec[i]["name"]}')
        if rec[i]["trajectory"] is not None:
            dup.append(f'{r["Name"]} -> {rec[i]["name"]}')
        rec[i]["trajectory"] = TRAJ.index(r["cl1.4fac_"])
        rec[i]["states"] = [STATE_TEXT.get(r[col]) if isinstance(r[col], str) else None
                            for col in state_cols]
        rec[i]["change"] = num(r["Diff"])
    report["paper1_trajectories"] = {"rows": len(c), "matched": len(c) - len(miss),
                                     "match_method": how, "unmatched": miss,
                                     "fuzzy_matches": fuzzy, "duplicate_targets": dup}

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
    miss, how, sigdiff, fuzzy, dup = [], {}, 0, [], []
    for _, r in d.iterrows():
        i, h = locate(None, r["Country"], r["Name.x"])
        if i is None:
            miss.append(f'{r["Country"]} {r["Name.x"]}'); continue
        how[h] = how.get(h, 0) + 1
        if h == "fuzzy":
            fuzzy.append(f'{r["Country"]} {r["Name.x"]} -> {rec[i]["name"]}')
        if rec[i]["rates"] is not None:
            dup.append(f'{r["Name.x"]} -> {rec[i]["name"]}')
        rec[i]["rates"] = {
            "birth": [r1(num(r[f"B{y}"])) for y in YEARS_RATE],
            "death": [r1(num(r[f"D{y}"])) for y in YEARS_RATE],
            "mig": [r1(num(r[f"NM{y}"])) for y in YEARS_RATE],
            "change": [r1(num(r[f"R.imp{y}"])) for y in YEARS_RATE],
        }
        if rec[i]["signature"] != int(r["cluster"]):
            sigdiff += 1
            rec[i]["signature"] = int(r["cluster"])
    report["paper2_rates"] = {"rows": len(d), "matched": len(d) - len(miss),
                              "match_method": how, "unmatched": miss, "fuzzy_matches": fuzzy, "duplicate_targets": dup,
                              "signature_overridden_from_rates_file": sigdiff}

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
    (out / "signatures.json").write_text(json.dumps(sig, separators=(",", ":"), allow_nan=False))

    # ---- write attributes --------------------------------------------------
    (out / "regions.json").write_text(json.dumps(
        {"years": {"states": YEARS_STATE, "rates": YEARS_RATE},
         "trajectories": TRAJ, "signatures": SIG,
         "regions": [{k: v for k, v in r.items() if v is not None} for r in rec.values()]}, separators=(",", ":"), ensure_ascii=False, allow_nan=False))

    flat = []
    for v in rec.values():
        row = {key: v[key] for key in ("id", "name", "country", "code", "coast", "change")}
        row["trajectory"] = TRAJ[v["trajectory"]] if v["trajectory"] is not None else ""
        row["signature"] = SIG[v["signature"]] if v["signature"] else ""
        for y, st in zip(YEARS_STATE, v["states"] or [None] * 18):
            row[f"state_{y}"] = st
        flat.append(row)
    pd.DataFrame(flat).to_csv(out / "regions.csv", index=False)

    # ---- geometry: simplify with mapshaper -> TopoJSON ---------------------
    tmp = out / "_tmp_regions.geojson"
    gg = b[["id", "geometry"]].copy()
    gg["geometry"] = gg.geometry.make_valid()
    gg.to_file(tmp, driver="GeoJSON")
    cmd = ["npx", "mapshaper", str(tmp), "-simplify", a.simplify, "weighted", "keep-shapes",
           "-filter-slivers", "-rename-layers", "regions",
           "-o", str(out / "regions.topo.json"), "format=topojson", "quantization=10000"]
    subprocess.run(cmd, check=True, cwd=ROOT)
    tmp.unlink()

    report["sizes_kb"] = {p.name: round(p.stat().st_size / 1024) for p in out.glob("*.json")}
    (out / "build_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({k2: (v2 if not isinstance(v2, dict) else {x: (y if not isinstance(y, list) else len(y)) for x, y in v2.items()})
                      for k2, v2 in report.items() if k2 != "backbone_without_country"}, indent=1))
    print("backbone without country:", len(report["backbone_without_country"]))


if __name__ == "__main__":
    sys.exit(main())
