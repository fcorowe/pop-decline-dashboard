# Project log — "Shrinking places" population-decline dashboard

This log is for any agent (Codex) or person picking up the project. Read it before `CODEX_PROMPT.md`.

## 1. Original brief (Francisco Rowe, 17 Nov 2026)

Francisco Rowe (Professor of Population Data Science, GDSL, University of Liverpool) has published two papers with Niall Newsham on population decline across Europe:

- **Paper 1** — Newsham & Rowe (2022), *Understanding trajectories of population decline across rural and urban Europe: a sequence analysis*. Population, Space and Place. https://doi.org/10.1002/psp.2630. Classifies areas by their trajectory: persistent decline, declines that accelerate or slow down, transitions such as decline followed by growth, and so on.
- **Paper 2** — Newsham & Rowe (2025), *The demographic causes of European sub-national population declines*. European Journal of Population 41:10. https://doi.org/10.1007/s10680-025-09730-0. Looks at the drivers of decline (fertility, mortality and migration) and at the characteristics of the places on each trajectory.

What he asked for, in his own terms:

- an engaging, good-looking, **minimalist and professional** dashboard that lets the public interact with the data;
- users can explore the trajectories, see where they are and how they changed over time, and get a sense of **what sort of places** they are and **what drives** the decline;
- **colour-blind-safe** palettes with engaging colours;
- **lightweight**, so people can interact quickly, and functional and practical;
- a font that is easy to read on a **website and on a phone**, so the dashboard must work on phones;
- **tests**, including for the phone version;
- he had no fixed idea of the design and asked Claude to propose one.

Later requests (same day):

- hand the remaining work to Codex: preserve the aesthetics, fix the known issues, publish on GitHub Pages and link the dashboard as a **Resource** on franciscorowe.com (see `CODEX_PROMPT.md`);
- Francisco will supply the **place characteristics used in Paper 2's model** later.

Writing conventions: British English; academic, precise tone; say plainly when evidence is insufficient; never fabricate data or results.

## 2. Inputs (read-only, in the parent folder `../`)

| File | Content | Notes |
|---|---|---|
| `Map.gpkg` | 2,042 sub-national polygons (layer `for_francisco`, EPSG:4326). Fields `name`, `nuts_id` (1,269 non-null), `Sig.Lab`, `Coast`, `mergeshe_4` | 133 MB. Covers the whole of Russia, including Asia; Chukotka crosses 180° |
| `Paper 1 - Clusters.csv` | 696 declining areas: annual state labels for 00/01…17/18 (18 periods), `Diff` (population change), `cl1.4fac_` (trajectory) | cp1252 encoding. The `GEO` codes are mangled by Excel (`Dec-01`, `68000000000`) |
| `Paper 1 - PopChangeStates.csv` | Numeric states (−2…2) for about 723 areas; many blank rows | contains `#VALUE!` cells |
| `Paper 2 - Mergesheet for maps.csv` | Area, Country, GEO, Signature (0 = growth, 1–5), label, for every map polygon | Name-matches the gpkg 99.95%; source of the country codes (`BR` = Belarus, `ML` = Moldova, `UN` = Ukraine, `AN` = Andorra) |
| `Paper 2 - Demographic Rates.csv` | 732 areas: crude birth (B), death (D), net migration (NM), change (R, R.imp) per 1,000, 2000–2018, plus `cluster` (signature) | No GEO code, so joined by name + country. Polish and Czech diacritics are lost (`?`) |
| `Paper 2 - Cluster Components.csv` | Per signature × year (2001–2018): Gupta 3-factor decomposition of the year-on-year change in the growth rate; `*.3ya` = 3-year moving average | Positive = pushes towards growth. Verified: `birth.3ya + death.3ya + mig.3ya = rate.3ya`; the `.invert` columns flip the sign and are **not** used |
| `refs/*.pdf` | Both papers | Descriptions in the UI are paraphrased from them |

Key definitions taken from the papers:

- **Annual states** (Paper 1, Table 1; thresholds = median 0.303 and SD 0.990 of annual % change): Decline ≤ −0.99; Moderate decline −0.99 to −0.3; Stable −0.3 to 0.3; Moderate growth 0.3 to 0.99; Growth ≥ 0.99.
- **Trajectories** (Paper 1, Table 4 counts / loss 2000–18): Persistent Decline 69 / 23.75%; Accelerating Decline 46 / 14.96%; Diminishing Decline 57 / 15.04%; Persistent Moderate Decline 180 / 9.30%; Accelerating Moderate Decline 107 / 5.84%; Diminished Decline 106 / 3.68%; Temporary Decline 131 / 4.03%.
- **Signatures** (Paper 2, Table 1): Steady Dual Deficit 215; Volatile Dual Deficit 151; Natural Reversal 90 (82% of losses from natural change); Migration & Fertility Reversal 116; Migration Resurgence 160.
- **Paper 2 place covariates** (multinomial logit, 2011, not yet supplied): % aged 65+, % foreign-born, unemployment, proximity to a city over 1 million, proximity to the coast, altitude, urban/intermediate/rural type.

## 3. What Claude built (17 Nov 2026)

### Architecture decisions and why

- **Static site with no framework** (HTML + CSS + vanilla JS + D3 v7 + topojson-client, all vendored, no CDN). Reason: the dashboard must be lightweight, publicly hostable anywhere and easy to maintain. About 0.5 MB gzipped in total; data ready in about 0.5 s locally.
- **SVG choropleth with d3-zoom**, Azimuthal Equal-Area projection centred on 15°E 52°N (equivalent to Europe's LAEA), framed on Europe. Russia beyond the Urals is reachable by panning.
- **Font: Atkinson Hyperlegible Next** (Braille Institute, OFL), self-hosted 400/700 weights, Latin + Latin Extended subsets. Chosen for legibility on screens; it has a slashed zero.
- **Colour by computation, not taste.** Every palette was checked with a CVD validator (OKLab ΔE under simulated protan/deutan/tritan vision, all pairs for the map). Seven trajectories cannot be separated by hue alone, so the map uses **4 hues for the dynamic** (persistent / accelerating / slowing / temporary) **× texture for the pace** (solid = fast, striped = moderate). Signatures use 5 hues validated across all pairs. Annual states use a red ↔ blue diverging palette with a grey midpoint. Lighter hues are always paired with text labels or tables.
- **Three tabs**: Trajectories (Paper 1), Year by year (annual states with slider and play), Drivers (Paper 2 signatures). Area detail opens on click, tap or search. Legend chips isolate a single category. The URL hash holds the state (`#v=year&y=2011&r=7`).
- **Responsive**: at 900 px and wider, a fixed-viewport app with the map on the left and a 400 px panel on the right; below that, a single column, sticky tabs, the map at 58dvh and a "details ↓" pill after a tap. Touch targets ≥ 44 px.

### Files

```
scripts/build_data.py        raw → site/data (joins, encoding fixes, mapshaper simplification 1.5%, quantisation 1e4)
scripts/name_crosswalk.csv   30 manual name matches (transliteration, characters lost in export, Moldovan Calarasi)
site/index.html, css/style.css, js/app.js
site/data/regions.topo.json  (1.09 MB raw / 0.23 MB gzip)
site/data/regions.json       (0.5 MB / 0.12 MB gzip) — id, name, country, countryName, code, coast, trajectory, signature, states[18], change, rates{birth,death,mig,change}[19]
site/data/signatures.json    component contributions per signature
site/data/regions.csv        public download
site/data/build_report.json  join diagnostics
tests/test_data.py           7 data-integrity tests (counts vs the papers' tables, balancing identity, payload budget)
tests/ui.spec.js             13 Playwright tests × 5 profiles (desktop 1366, laptop 1024, iPhone 13, Pixel 7, iPhone SE) = 65
playwright.config.js, package.json, README.md, CODEX_PROMPT.md
```

### Join logic (build_data.py)

The backbone is the gpkg, with the country taken from the mergesheet by name. Each source row is placed by these rules, in order:

1. a valid NUTS code;
2. the manual crosswalk;
3. an exact normalised name match within the same country;
4. a unique exact name;
5. a fuzzy match within the same country (difflib ≥ 0.8 with a margin ≥ 0.08 over the runner-up).

Results:

| Source | Matched | By code | By name + country | Fuzzy |
|---|---|---|---|---|
| Paper 1 | 695 / 696 | 461 | 150 | 70 |
| Paper 2 rates | 731 / 732 | — | — | 106 |

Claude inspected every fuzzy match and judged all of them correct. No two sources map to the same target.

### Test status at hand-over

`pytest`: 7/7 pass. Playwright: 65/65 pass. Screenshots were reviewed at 1366, 1024, iPhone 13 and iPhone SE widths.

### Content choices worth knowing

- Area panel chart: stacked diverging bars of births minus deaths (violet) and net migration (orange) per 1,000, with total change shown as a line with dots. The table view sits under "Show as table".
- Year-by-year commentary is **derived from the data**: 55–70% of declining areas lose population in a typical year; fast decline jumps to 34% in 2011; 21% grow in 2016, mostly in Germany. The suggestion that the 2011 jump partly reflects census re-estimation is labelled in the UI as a possibility, not a finding.
- Growing areas are drawn in pale grey ("grew overall, 2000–18") and are not part of either analysis.

## 4. Open issues (handed to Codex — see CODEX_PROMPT.md, Part 2)

1. **Srednjobanatska (RS)** is unmatched. The gpkg has both `Severnobanatska` and `Severno-Banatski`, so one is probably mislabelled. Resolve it with a centroid check (Zrenjanin 45.38 N, 20.39 E).
2. **Fuzzy matches** must become an explicit reviewed crosswalk, and the build should fail on new unreviewed matches.
3. **5 signature disagreements** between the mergesheet and the rates file (the rates file is used because it reproduces Table 1).
4. **1 polygon is dropped** by mapshaper (2,041 of 2,042 retained).
5. **Antimeridian** handling for Chukotka needs checking.
6. **The gpkg `Coast` flag is unreliable** (landlocked North Ossetia is flagged coastal). It is hidden in the UI (`app.js`, `renderPlace`) until Francisco confirms the definition used in Paper 2.
7. **Place characteristics** (Paper 2 covariates) are pending from Francisco. Build the optional merge and the UI now and test them with a synthetic fixture; never invent values.
8. Accessibility (axe), a performance test with CPU throttling, a custom D3 bundle, About & cite, a social card and a favicon.

## 5. Deployment targets

- Dashboard: new public repository `fcorowe/pop-decline-dashboard`, deployed to GitHub Pages via Actions (`site/` as the artefact) at https://fcorowe.github.io/pop-decline-dashboard/. Do **not** commit `../Map.gpkg` (over the 100 MB limit) or other raw files.
- Personal website: `fcorowe/franciscorowe` (Quarto; Netlify serves the committed `_site/`; follow its `AGENTS.md`). Add a card at the top of `resources.qmd` → "Interactive tools and data stories", copying the markup pattern of the EXHALE UK Data Explorer card. Do not loosen the CSP in `netlify.toml`.

## 6. Decisions pending from Francisco

- Francisco confirmed CC BY 4.0 for the derived data and Niall Newsham’s agreement to public release on 2026-11-17.
- Which coastal definition Paper 2 used.
- A visual check of `data_review/matches_for_review.csv` once Codex produces it.
- Delivery of the place-characteristics file (`../Paper 2 - Place attributes.csv`).
- Optional: dark mode; whether areas beyond the Urals should stay in the default view.

## 7. Log

| Date | Who | Entry |
|---|---|---|
| 2026-11-17 | Claude | Read both papers and the raw data; designed and built the dashboard, the data pipeline and the tests; 72/72 tests pass; wrote CODEX_PROMPT.md and this log. |
| 2026-11-17 | Codex | Part 1. Committed ten approved macOS screenshots before changing the application, pinned dependencies, verified byte-identical data rebuilds, and reduced the D3 bundle from 281 KB to 113 KB. All ten screenshots passed against the original baselines. The original UI suite intermittently lost its local server connection, so browser tests now bind explicitly to IPv4. |
| 2026-11-17 | Codex | Part 2. Matched 696 trajectories and 732 signatures, recovered Christiansø, verified the Chukotka projection and recorded 116 fuzzy pairs and the independent coastline comparison. The supplied signature sources agree for all 732 joins. Added keyboard and motion support, axe and Android performance tests, optional place profiles, an About & cite dialog, a social image and a favicon. Updated screenshots for the corrected counts and boundary, larger controls, darker secondary text and footer link. |
| 2026-11-17 | Codex | Part 3. Francisco confirmed CC BY 4.0 and co-author consent. Created the public repository, enabled GitHub Actions for Pages, compared the original and hardened Linux snapshots, and added the CI and deployed-path smoke checks. The Resources card rendered at desktop and mobile widths with the existing dark styling and passed Netlify preflight. The full local run passed 14 data tests and 94 browser checks. |
