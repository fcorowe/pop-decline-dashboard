"""Validate and merge the optional 2011 characteristics supplied by the authors."""
import math

import pandas as pd

NUMERIC = (
    "aged_65_pct", "foreign_born_pct", "unemployment_pct",
    "distance_city_1m_km", "distance_coast_km", "mean_altitude_m",
)
SETTLEMENT = "settlement_type"


def merge_attributes(path, locate, records, normalise_country):
    if not path.is_file():
        print(f"Place characteristics skipped: {path.name} is absent.")
        return {"status": "absent", "matched": 0}

    source = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    source.columns = source.columns.str.strip().str.lower()
    required = set(NUMERIC + (SETTLEMENT,))
    missing = required - set(source.columns)
    if missing or ("code" not in source and not {"name", "country"} <= set(source.columns)):
        raise ValueError(f"{path.name} needs code or name and country, plus {', '.join(sorted(required))}")
    seen = set()
    matched = 0
    for row_no, row in enumerate(source.to_dict("records"), 2):
        code = row.get("code", "").strip()
        country = normalise_country(row.get("country", ""))
        name = row.get("name", "").strip()
        if not code and not (country and name):
            raise ValueError(f"{path.name}:{row_no}: supply a code or a name and country")
        region_id, _ = locate(code, country, name)
        if region_id is None or region_id in seen:
            raise ValueError(f"{path.name}:{row_no}: unmatched or duplicate area ({code or name})")
        region = records[region_id]
        if region["signature"] is None:
            raise ValueError(f"{path.name}:{row_no}: area has no Paper 2 signature ({code or name})")
        seen.add(region_id)

        values = {}
        for key in NUMERIC:
            cell = row[key].strip()
            if not cell:
                continue
            value = float(cell)
            if (not math.isfinite(value) or (key.endswith("_pct") and not 0 <= value <= 100)
                    or (key.endswith("_km") and value < 0)):
                raise ValueError(f"{path.name}:{row_no}: invalid {key}: {cell}")
            values[key] = value
        settlement = row[SETTLEMENT].strip().lower()
        if settlement:
            if settlement not in {"urban", "intermediate", "rural"}:
                raise ValueError(f"{path.name}:{row_no}: unknown settlement type {settlement}")
            values[SETTLEMENT] = settlement
        if values:
            region["place"] = values
            matched += 1
    return {"status": "supplied", "rows": len(source), "matched": matched}
