# Shrinking places — population decline across Europe, 2000–2018

A lightweight, public-facing interactive dashboard of the two GDSL papers:

- Newsham & Rowe (2023, first published online in 2022) *Understanding trajectories of population decline across rural and urban Europe: a sequence analysis*. Population, Space and Place 29(3), e2630. https://doi.org/10.1002/psp.2630
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
scripts/name_crosswalk.csv explicit manual and reviewed fuzzy matches
scripts/geometry_overrides.csv documented boundary-label corrections
data_review/               fuzzy match scores and coastal comparison
tests/test_data.py         data integrity (counts reproduce the papers' tables)
tests/ui.spec.js           end-to-end tests on 2 desktop + 3 phone profiles
```

## Commands

```bash
python3 -m pip install -r requirements.txt
npm ci                      # exact dependencies from package-lock.json
npx playwright install chromium
npm run data                # rebuild from the raw inputs one folder up
npm run build:vendor        # rebuild the checked-in D3 subset when dependencies change
npm run serve               # http://localhost:8000
npm test                    # data, determinism, UI and visual tests
npm run snapshots           # update expected images after reviewing intentional changes
```

## Data joins and caveats

- All 696 trajectory areas and 732 signature areas match the published counts. Boundary centroids place the polygon labelled `Severnobanatska` closest to Zrenjanin, so the build relabels it as `Srednjobanatska` (Central Banat). The distinct `Severno-Banatski` polygon represents Northern Banat, and `Juznobanatska` represents Southern Banat. The original GeoPackage is unchanged.
- Fuzzy matches from the handover are explicit in `scripts/name_crosswalk.csv`. The build rejects any new acceptable fuzzy candidate until its match is recorded. The review CSV lists each accepted source–boundary pair and the name similarity score. A score measures spelling similarity and does not establish geographic equivalence.
- The Paper 2 demographic rates file determines the signature. The current build finds zero disagreements with the map mergesheet among the 732 joined areas. The build report records the two values and area name for any disagreement.
- The simplified map keeps all 2,042 boundaries. Christiansø is restored from its original geometry because its rings collapse during simplification. The restoration refines the TopoJSON grid without shifting other boundaries. Chukotka's source rings are already split at the antimeridian.
- The boundary file flags some landlocked areas as coastal, including North Ossetia. The separate `coast_km` estimate measures minimum polygon-to-shoreline distance, rounded to 0.1 km, from exterior rings of dissolved [Natural Earth 1:10m land polygons, v5.1.1](https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/). It excludes interior lakes and the artificial antimeridian seam. Distances use an azimuthal equidistant projection centred on each area's largest polygon. Boundaries that touch or cross the shoreline have distance zero. Differences in shoreline resolution can affect small islands and coastal margins. Both measures are withheld from the interface pending confirmation of the definition in Paper 2.
- Rebuilding requires the original research files in the parent directory. The first rebuild downloads and verifies the pinned Natural Earth archive in `.cache/`. For offline rebuilding, supply that archive with `python3 scripts/build_data.py --land /path/to/ne_10m_land.zip`.

## Optional 2011 place characteristics

The build skips the characteristics when `../Paper 2 - Place attributes.csv` is absent. Supply a UTF-8 CSV with `code` or `name` and `country` for each area, plus these columns:

| Field | Unit or values |
|---|---|
| `aged_65_pct`, `foreign_born_pct`, `unemployment_pct` | Percentages on a 0–100 scale |
| `distance_city_1m_km`, `distance_coast_km` | Kilometres |
| `mean_altitude_m` | Metres |
| `settlement_type` | `urban`, `intermediate` or `rural` |

Blank values remain missing. Numeric percentiles use the midrank among declining areas with an observed value. The Drivers table compares within-signature medians and the most common settlement type. The supplied 2011 coast variable is distinct from the Natural Earth comparison.

To regenerate the 1,200 × 630 social image, start `npm run serve` and run `npm run social-card` in another terminal.

## Deployment and licence

GitHub Actions runs the data and Chromium suites before deploying `site/` to [GitHub Pages](https://fcorowe.github.io/pop-decline-dashboard/). The CI job tests the committed derived bundle. The local determinism test requires the raw files.

Run smoke tests against the published project path:

```bash
BASE_URL=https://fcorowe.github.io/pop-decline-dashboard/ npx playwright test --grep @smoke
```

The [MIT licence](LICENSE) covers the dashboard code. The [derived data licence](DATA-LICENSE.md) is CC BY 4.0 and provides the study citations. The font and JavaScript dependencies retain their own licences in `site/fonts/` and `site/vendor/`.
