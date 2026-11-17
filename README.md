# Shrinking places — population decline across Europe, 2000–2018

A lightweight, public-facing interactive dashboard of the two GDSL papers:

- Newsham & Rowe (2022) *Understanding trajectories of population decline across rural and urban Europe: a sequence analysis*. Population, Space and Place. https://doi.org/10.1002/psp.2630
- Newsham & Rowe (2025) *The demographic causes of European sub-national population declines*. European Journal of Population 41:10. https://doi.org/10.1007/s10680-025-09730-0

## What it does

| View | Map shows | Side panel shows |
|---|---|---|
| **Trajectories** | 7 decline pathways (Paper 1). Hue = dynamic (persistent / accelerating / slowing / temporary); solid = fast (>1%/yr), striped = moderate | Counts, combined losses and plain-language descriptions; tap to isolate |
| **Year by year** | Annual state of change, 2001–2018, with slider + play | Share of declining areas in each state per year |
| **Drivers** | 5 depopulation signatures (Paper 2) | Small multiples of fertility, mortality and migration contributions |
| **Any area** (tap/search) | Highlighted outline | Population change, 18-year sequence barcode, births − deaths vs net migration per 1,000, trajectory and signature descriptions |

State is kept in the URL (`#v=year&y=2011&r=7`), so any view can be shared as a link.

## Design choices

- **No framework, no build step.** Static HTML + D3 v7 + TopoJSON, all vendored (no CDN calls). ~0.5 MB gzipped in total.
- **Font:** Atkinson Hyperlegible Next (Braille Institute, OFL), self-hosted, Latin + Latin Extended for place names.
- **Colour:** every categorical palette checked with a CVD validator (protan/deutan/tritan simulation, all-pairs for maps). Seven trajectories cannot be separated safely by hue alone, so the map uses 4 hues × texture (solid/striped). Lighter hues are always paired with text labels, and every chart has a legend or a table view.
- **Mobile first:** 44 px touch targets, sticky tabs, map at 58% of the viewport, details below with a "details ↓" pill; tested on iPhone SE / 13 and Pixel 7 profiles.

## Layout

```
site/                 ← deploy this folder as-is (GitHub Pages, Netlify, university web space)
  index.html, css/, js/app.js, vendor/, fonts/
  data/regions.topo.json   simplified boundaries
  data/regions.json        attributes per area
  data/signatures.json     signature-level component contributions
  data/regions.csv         public download
  data/build_report.json   join diagnostics (do not need to deploy)
scripts/build_data.py      rebuilds site/data from the raw files one folder up
scripts/name_crosswalk.csv manual name matches (transliteration, encoding losses)
tests/test_data.py         data integrity (counts reproduce the papers' tables)
tests/ui.spec.js           end-to-end tests on 2 desktop + 3 phone profiles
```

## Commands

```bash
npm install                 # mapshaper, Playwright, D3 sources
npx playwright install chromium
npm run build:data          # = python3 scripts/build_data.py  (needs pandas, geopandas)
npm run serve               # http://localhost:8000
npm test                    # data tests + 65 UI tests
```

## Known data issues (see data/build_report.json)

- **Srednjobanatska (Serbia)** cannot be placed: the boundary file contains two "Severnobanatska/Severno-Banatski" polygons and no Srednjobanatska, so one is probably mislabelled. 1 trajectory area and 1 signature area are therefore missing from the map.
- 70 (Paper 1) and 106 (Paper 2) areas were matched by fuzzy name within country (Serbian, Russian, Lithuanian, Polish and Czech names, many with characters lost in the CSV export). All are listed in the build report for checking; 30 more are fixed by hand in `scripts/name_crosswalk.csv`.
- The `Coast` flag in `Map.gpkg` marks some landlocked areas (e.g. North Ossetia) as coastal, so it is kept in the data but not shown in the interface.
- The place attributes in Paper 2's regression (share aged 65+, foreign-born, unemployment, distance to a large city and to the coast, altitude, urban–rural type) are not in the raw folder yet; adding them would let the dashboard show "what sort of place" each area is.
