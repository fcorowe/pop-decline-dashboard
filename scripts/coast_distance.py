"""Estimate minimum polygon-to-shoreline distance from Natural Earth 1:10m land."""
import hashlib
import math
from pathlib import Path
from urllib.request import urlopen

import geopandas as gpd
from pyproj import Transformer
from shapely import STRtree, box, get_parts, union_all
from shapely.geometry import LineString
from shapely.ops import transform

LAND_URL = "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip"
LAND_VERSION = "5.1.1"
LAND_SHA256 = "e547d749445eaa0964aba76738090ec88f5e63c4585122170f98c67a7ea922dc"


def land_archive(path):
    path = Path(path)
    if not path.is_file():
        with urlopen(LAND_URL, timeout=30) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != LAND_SHA256:
            raise ValueError("Natural Earth download differs from the pinned 5.1.1 archive")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    if hashlib.sha256(path.read_bytes()).hexdigest() != LAND_SHA256:
        raise ValueError(f"Unexpected Natural Earth archive checksum: {path}")
    return path.resolve()


def shoreline_chunks(land):
    # Union removes tile seams. Exterior rings exclude inland water holes.
    for polygon in get_parts(union_all(land)):
        coordinates = list(polygon.exterior.coords)
        chunk = [coordinates[0]]
        for a, b in zip(coordinates, coordinates[1:]):
            # Split at the artificial cuts on either side of the antimeridian.
            seam = abs(abs(a[0]) - 180) < 1e-8 and abs(abs(b[0]) - 180) < 1e-8
            if seam or len(chunk) == 33:
                if len(chunk) > 1:
                    yield LineString(chunk)
                chunk = [b] if seam else [a, b]
            else:
                chunk.append(b)
        if len(chunk) > 1:
            yield LineString(chunk)


def coast_distances(geometries, archive):
    land = gpd.read_file(land_archive(archive)).geometry
    tree = STRtree(list(shoreline_chunks(land)))
    return [distance_km(geometry, tree) for geometry in geometries]


def distance_km(geometry, coast):
    parts = [part for part in get_parts(geometry) if part.geom_type == "Polygon"]
    focus = max(parts, key=lambda part: part.area).representative_point()
    project = Transformer.from_crs(
        "EPSG:4326", f"+proj=aeqd +lat_0={focus.y} +lon_0={focus.x} +datum=WGS84", always_xy=True
    ).transform
    projected = transform(project, geometry)
    bounds = [part.bounds for part in parts]

    for radius in (35, 200, 800, 2500, 10000):
        latitude_margin = radius / 110
        candidates = set()
        for west, south, east, north in bounds:
            max_lat = min(89.99, max(abs(south), abs(north)) + latitude_margin)
            longitude_margin = min(180, latitude_margin / math.cos(math.radians(max_lat)))
            for offset in (-360, 0, 360):
                left = max(-180, west - longitude_margin + offset)
                right = min(180, east + longitude_margin + offset)
                if left <= right:
                    candidates.update(coast.query(box(left, south - latitude_margin, right, north + latitude_margin)))
        if candidates:
            distance = min(projected.distance(transform(project, coast.geometries[i])) for i in sorted(candidates))
            if distance <= radius * 1000:
                return round(distance / 1000, 1)
    raise ValueError(f"No Natural Earth shoreline found near {focus.wkt}")
