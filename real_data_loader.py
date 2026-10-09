"""Real Bengaluru dataset loader for SeedRescue.

Loads the local data/raw/bengaluru dataset without hard-coding the old
Z1-Z4/S1-S3/H1/D1 demonstration network.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from functools import lru_cache

import networkx as nx


DATA_DIR = Path(__file__).resolve().parent / "data" / "raw" / "bengaluru"


def _load_geojson(name: str):
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _point(feature):
    geom = feature.get("geometry") or {}
    if geom.get("type") != "Point":
        return None
    coords = geom.get("coordinates") or []
    if len(coords) < 2:
        return None
    return float(coords[1]), float(coords[0])  # lat, lon


def _to_number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _estimated_capacity(properties):
    """Transparent fallback because OSM-derived shelter records may lack capacity."""
    for key in ("capacity", "beds", "emergency_capacity"):
        n = _to_number(properties.get(key))
        if n is not None and n > 0:
            return int(n), "dataset"

    amenity = str(properties.get("amenity") or "").lower()
    # These are explicitly estimates, not claimed real capacities.
    defaults = {
        "school": 200,
        "college": 300,
        "community_centre": 250,
        "townhall": 300,
        "stadium": 1000,
    }
    return defaults.get(amenity, 200), "estimated"


def _feature_records(filename):
    data = _load_geojson(filename)
    records = []
    for i, feature in enumerate(data.get("features", [])):
        p = feature.get("properties") or {}
        pt = _point(feature)
        if pt is None:
            continue
        lat, lon = pt
        records.append({
            "id": f"{Path(filename).stem}_{i}",
            "name": p.get("name") or f"{Path(filename).stem.title()} {i + 1}",
            "lat": lat,
            "lng": lon,
            "properties": p,
        })
    return records


@lru_cache(maxsize=1)
def load_dataset():
    """Load and cache the real Bengaluru road/facility/population dataset."""
    graph = nx.read_graphml(DATA_DIR / "roads.graphml.gz")
    # Keep node IDs as strings and numeric coordinates as floats.
    for node, attrs in graph.nodes(data=True):
        attrs["x"] = float(attrs.get("x"))
        attrs["y"] = float(attrs.get("y"))
        attrs["street_count"] = _to_number(attrs.get("street_count"))

    # GraphML may be MultiDiGraph, DiGraph or Graph depending on export.
    # SeedRescue treats each directed GraphML edge as a routable edge.
    road_edges = []
    for u, v, attrs in graph.edges(data=True):
        length_m = _to_number(attrs.get("length"))
        if length_m is None:
            length_m = _haversine_km(
                graph.nodes[u]["y"], graph.nodes[u]["x"],
                graph.nodes[v]["y"], graph.nodes[v]["x"],
            ) * 1000.0
        road_edges.append({
            "id": f"road_{u}_{v}_{len(road_edges)}",
            "u": str(u),
            "v": str(v),
            "length_m": float(length_m),
            "highway": attrs.get("highway"),
            "name": attrs.get("name"),
            "oneway": attrs.get("oneway"),
            "geometry": attrs.get("geometry"),
        })

    shelters = _feature_records("shelters.geojson")
    hospitals = _feature_records("hospitals.geojson")
    schools = _feature_records("schools.geojson")
    water = _load_geojson("water.geojson")

    # Build one pool of potential temporary emergency shelters.
    # Official/explicit shelter records are included, and schools/colleges are
    # added as potential temporary shelters. Missing capacity is estimated and
    # labelled rather than presented as verified capacity.
    temporary_shelters = []

    for rec in shelters:
        capacity, source = _estimated_capacity(rec["properties"])
        rec["capacity"] = capacity
        rec["capacity_source"] = source
        rec["facility_type"] = rec["properties"].get("amenity") or "temporary shelter"
        rec["shelter_status"] = "listed shelter facility"
        rec["source_dataset"] = "shelters.geojson"
        temporary_shelters.append(rec)

    for rec in schools:
        amenity = str(rec["properties"].get("amenity") or "school").lower()
        if amenity not in {"school", "college", "university"}:
            continue
        capacity, source = _estimated_capacity(rec["properties"])
        rec["capacity"] = capacity
        rec["capacity_source"] = source
        rec["facility_type"] = amenity
        emergency = rec["properties"].get("emergency")
        rec["shelter_status"] = (
            "emergency-flagged potential temporary shelter"
            if str(emergency).lower() in {"true", "yes", "1"}
            else "potential temporary shelter - emergency suitability not verified"
        )
        rec["source_dataset"] = "schools.geojson"
        temporary_shelters.append(rec)

    population = _load_geojson("population_cells.geojson")
    population_cells = []
    for i, feature in enumerate(population.get("features", [])):
        props = feature.get("properties") or {}
        geom = feature.get("geometry") or {}
        if geom.get("type") != "Polygon":
            continue
        rings = geom.get("coordinates") or []
        if not rings or not rings[0]:
            continue
        ring = rings[0]
        lon = sum(float(p[0]) for p in ring) / len(ring)
        lat = sum(float(p[1]) for p in ring) / len(ring)
        pop = _to_number(props.get("population")) or 0
        population_cells.append({
            "id": f"cell_{i}",
            "lat": lat,
            "lng": lon,
            "population": max(0, int(round(pop))),
            "geometry": geom,
        })

    return {
        "graph": graph,
        "road_edges": road_edges,
        "shelters": shelters,
        "temporary_shelters": temporary_shelters,
        "hospitals": hospitals,
        "schools": schools,
        "water": water,
        "population_cells": population_cells,
        "boundary": _load_geojson("boundary.geojson"),
    }


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def dataset_summary():
    d = load_dataset()
    return {
        "data_source": "data/raw/bengaluru",
        "road_nodes": d["graph"].number_of_nodes(),
        "road_edges": d["graph"].number_of_edges(),
        "shelters": len(d.get("temporary_shelters", d["shelters"])),
        "official_shelters": len(d["shelters"]),
        "hospitals": len(d["hospitals"]),
        "schools": len(d["schools"]),
        "population_cells": len(d["population_cells"]),
    }
