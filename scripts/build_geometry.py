"""Simplify boundaries while preserving the small Christiansø polygons."""
import json
from pathlib import Path
import subprocess
import tempfile

from shapely import get_parts, orient_polygons

PROTECTED_FEATURES = {95: "Christiansø"}


def add_protected_geometry(topology, backbone):
    geometries = topology["objects"]["regions"]["geometries"]
    missing = [g for g in geometries if not g.get("arcs")]
    for g in missing:
        region_id = g["properties"]["id"]
        if PROTECTED_FEATURES.get(region_id) != backbone.at[region_id, "name"]:
            raise ValueError(f"Unexpected feature without geometry: {region_id}")
    if not missing:
        return []

    # Refine the integer grid without changing the coordinates of existing arcs.
    refine = 8
    arcs = topology["arcs"]
    scale = topology["transform"]["scale"]
    origin = topology["transform"]["translate"]
    scale[:] = [step / refine for step in scale]
    for arc in arcs:
        for point in arc:
            point[:] = [v * refine for v in point]

    for g in missing:
        region_id = g["properties"]["id"]
        raw = orient_polygons(backbone.at[region_id, "geometry"], exterior_cw=True)
        polygons = []
        for polygon in get_parts(raw):
            rings = []
            for ring in (polygon.exterior, *polygon.interiors):
                points = [tuple(round((v - zero) / step) for v, zero, step in zip(point, origin, scale))
                          for point in ring.coords]
                points = [p for i, p in enumerate(points) if not i or points[i - 1] != p]
                area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:]))
                if not area:
                    if not rings:
                        break
                    continue
                rings.append([len(arcs)])
                arcs.append([points[0]] + [[x1 - x0, y1 - y0] for (x0, y0), (x1, y1)
                                          in zip(points, points[1:])])
            if rings:
                polygons.append(rings)
        if not polygons:
            raise ValueError(f"Protected feature collapsed on the refined grid: {region_id}")
        # MultiPolygon → polygons → rings → arc indices.
        g.update(type="MultiPolygon", arcs=polygons)
    return [{"id": g["properties"]["id"], "name": backbone.at[g["properties"]["id"], "name"]}
            for g in missing]


def build_geometry(backbone, mapshaper, simplify, output):
    gg = backbone[["id", "geometry"]].copy()
    gg["geometry"] = gg.geometry.make_valid()
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "regions.geojson"
        target = Path(directory) / "regions.topo.json"
        gg.to_file(source, driver="GeoJSON")
        subprocess.run(
            ["node", str(mapshaper), str(source), "-simplify", simplify, "weighted", "keep-shapes",
             "-filter-slivers", "keep-shapes", "-rename-layers", "regions", "-o",
             str(target), "format=topojson", "quantization=10000"],
            check=True,
        )
        topology = json.loads(target.read_text())
    restored = add_protected_geometry(topology, backbone)
    geometries = topology["objects"]["regions"]["geometries"]
    mapped = {g["properties"]["id"] for g in geometries if g.get("arcs")}
    if len(geometries) != len(backbone) or mapped != set(backbone.id):
        raise ValueError(f"Features without geometry: {sorted(set(backbone.id) - mapped)}")
    output.write_text(json.dumps(topology, sort_keys=True, separators=(",", ":")))
    return restored
