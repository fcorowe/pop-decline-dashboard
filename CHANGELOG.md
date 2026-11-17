# Changelog

## 2026-11-17

- Made the build reproducible with pinned dependencies, deterministic outputs, and a D3 bundle reduced from 281 KB to about 113 KB. Captured the approved desktop and iPhone views before changing the application.
- Matched all 696 trajectory areas and 732 signature areas. Category counts reproduce Table 4 in the trajectory paper and Table 1 in the signatures paper. Corrected the Central and Northern Banat assignments using boundary centroids and district seats. The supplied releases agree on all 732 signature assignments.
- Retained all 2,042 map geometries by restoring Christiansø on a finer grid and verified that Chukotka stays compact in the map projection when zooming out and panning. Mapshaper still reports pre-existing unresolved intersections in the generalised boundaries.
- Recorded 116 previously reviewed fuzzy name pairs with similarity scores. The build now stops on a new eligible fuzzy match. Computed independently sourced shoreline distances for all areas and kept both coastal measures out of the interface.
- Added keyboard tab navigation, focus handling, reduced-motion support, 44 px controls, axe checks, and a 4× CPU-throttled Android pinch test. Screenshot changes reflect the corrected counts and boundary, larger controls, stronger secondary text contrast, and the About & cite link.
- Added an optional 2011 characteristics section and a compact signature comparison, tested with synthetic inputs. Added the citation dialog, favicon, and a 1,200 × 630 preview image.
- Configured the GitHub Pages workflow and added smoke tests for the deployed project path. Francisco confirmed CC BY 4.0 for derived data and Niall Newsham’s agreement to public release. The dashboard code is MIT-licensed.
- Open items for Francisco are to check the [fuzzy matches](data_review/matches_for_review.csv), confirm how the original study measured coastal proximity, and provide the 2011 place-attributes file.
