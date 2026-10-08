"""
SeedRescue recovery engine using the real Bengaluru dataset.

Public interface preserved for the existing Flask app:
    generate_plan
    graph_info
    find_critical_bottlenecks
    detect_road_status_from_location
    apply_automatic_road_detection
    NODES
    EDGES

Routing uses:
    data/raw/bengaluru/roads.graphml

Population exposure uses:
    data/raw/bengaluru/population_cells.geojson

Shelter candidates come from:
    1. shelters.geojson
    2. suitable records from schools.geojson

The old fictional Z1-Z4 / S1-S3 / H1 / D1 demo geography is not used.
"""

from __future__ import annotations

import math
from functools import lru_cache

import networkx as nx

from backend.routing.adaptive_router import edge_cost
from backend.allocation.fair_allocator import allocate as fair_allocate
from backend.services.zone_classifier import classify_zone
from backend.services.zone_response import apply_zone_response
from real_data_loader import load_dataset, dataset_summary


# ============================================================
# CONFIGURATION
# ============================================================

SEVERITY = {
    "flood": 1.0,
    "earthquake": 1.25,
    "cyclone": 0.9,
    "landslide": 1.1,
}

EARTH_RADIUS_KM = 6371.0

# Facilities from schools.geojson that are reasonable
# candidates for temporary emergency use.
TEMP_SHELTER_AMENITIES = {
    "school",
    "college",
    "university",
}


# ============================================================
# DATASET
# ============================================================

def _dataset():
    return load_dataset()


# ============================================================
# REAL ROAD COMPATIBILITY VIEWS
# ============================================================

@lru_cache(maxsize=1)
def _road_nodes():
    g = _dataset()["graph"]

    return {
        str(n): (
            str(n),
            "road",
            float(attrs["y"]),
            float(attrs["x"]),
        )
        for n, attrs in g.nodes(data=True)
    }


# app.py imports these.
# They now refer to the real Bengaluru road network.
NODES = _road_nodes()


@lru_cache(maxsize=1)
def _road_edges():
    return [
        (
            e["id"],
            e["u"],
            e["v"],
        )
        for e in _dataset()["road_edges"]
    ]


EDGES = _road_edges()


# ============================================================
# GEOMETRY
# ============================================================

def _haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(dlon / 2) ** 2
    )

    return (
        2
        *
        EARTH_RADIUS_KM
        *
        math.asin(math.sqrt(a))
    )


# ============================================================
# NEAREST ROAD NODE
# ============================================================

@lru_cache(maxsize=1)
def _road_spatial_index():
    graph = _dataset()["graph"]

    items = list(
        graph.nodes(data=True)
    )

    ids = [
        str(n)
        for n, _ in items
    ]

    coords = [
        (
            float(attrs["x"]),
            float(attrs["y"]),
        )
        for _, attrs in items
    ]

    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(coords)

        return (
            "scipy",
            tree,
            ids,
            coords,
        )

    except Exception:
        return (
            "python",
            None,
            ids,
            coords,
        )


def _nearest_road_node(
    lat,
    lon,
):
    mode, tree, ids, coords = _road_spatial_index()

    if not ids:
        raise ValueError(
            "Real road graph contains no nodes."
        )

    if mode == "scipy":
        _, index = tree.query(
            [
                float(lon),
                float(lat),
            ]
        )

        return ids[int(index)]

    best_id = ids[0]
    best = float("inf")

    cosine = math.cos(
        math.radians(float(lat))
    )

    for node_id, (
        x,
        y,
    ) in zip(
        ids,
        coords,
    ):
        distance = (
            (
                float(lon) - x
            )
            *
            cosine
        ) ** 2 + (
            float(lat) - y
        ) ** 2

        if distance < best:
            best = distance
            best_id = node_id

    return best_id


# ============================================================
# FACILITY HELPERS
# ============================================================

def _facility_node_id(
    prefix,
    record_id,
):
    return f"{prefix}:{record_id}"


def _safe_number(
    value,
    default=0.0,
):
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return float(default)


def _estimated_capacity(
    properties,
    amenity=None,
):
    """
    Use a real dataset capacity when one exists.

    Otherwise estimate capacity transparently.
    """

    properties = properties or {}

    for key in (
        "capacity",
        "beds",
        "emergency_capacity",
    ):
        value = _safe_number(
            properties.get(key),
            0,
        )

        if value > 0:
            return (
                int(round(value)),
                "dataset",
            )

    amenity = str(
        amenity
        or properties.get("amenity")
        or ""
    ).lower()

    defaults = {
        "school": 200,
        "college": 300,
        "university": 400,
        "community_centre": 250,
        "community_center": 250,
        "townhall": 300,
        "stadium": 1000,
    }

    return (
        defaults.get(
            amenity,
            200,
        ),
        "estimated",
    )


# ============================================================
# REAL TEMPORARY SHELTER POOL
# ============================================================

@lru_cache(maxsize=1)
def _temporary_shelters():
    """
    Build the real emergency-stay candidate pool.

    Source 1:
        shelters.geojson

    Source 2:
        schools.geojson

    No fictional shelters are created.
    """

    dataset = _dataset()

    result = []

    # --------------------------------------------------------
    # 1. Facilities explicitly listed in shelters.geojson
    # --------------------------------------------------------

    for record in dataset.get(
        "shelters",
        [],
    ):
        properties = record.get(
            "properties",
            {},
        )

        amenity = str(
            properties.get("amenity")
            or ""
        ).lower()

        capacity, capacity_source = (
            _estimated_capacity(
                properties,
                amenity,
            )
        )

        result.append(
            {
                **record,

                "facility_id":
                    _facility_node_id(
                        "shelter",
                        record["id"],
                    ),

                "facility_type":
                    amenity
                    or
                    "shelter_facility",

                "shelter_status":
                    "listed shelter facility",

                "capacity":
                    capacity,

                "capacity_source":
                    capacity_source,

                "source_dataset":
                    "shelters.geojson",
            }
        )

    # --------------------------------------------------------
    # 2. Schools / colleges / universities
    # --------------------------------------------------------

    for record in dataset.get(
        "schools",
        [],
    ):
        properties = record.get(
            "properties",
            {},
        )

        amenity = str(
            properties.get("amenity")
            or "school"
        ).lower()

        if (
            amenity
            not in
            TEMP_SHELTER_AMENITIES
        ):
            continue

        capacity, capacity_source = (
            _estimated_capacity(
                properties,
                amenity,
            )
        )

        emergency_flag = str(
            properties.get("emergency")
            or
            properties.get("shelter")
            or
            ""
        ).lower()

        if emergency_flag in {
            "yes",
            "true",
            "1",
            "designated",
        }:
            shelter_status = (
                "emergency-flagged "
                "potential temporary shelter"
            )
        else:
            shelter_status = (
                "potential temporary "
                "shelter - emergency "
                "suitability not verified"
            )

        result.append(
            {
                **record,

                "facility_id":
                    _facility_node_id(
                        "temporary",
                        record["id"],
                    ),

                "facility_type":
                    amenity,

                "shelter_status":
                    shelter_status,

                "capacity":
                    capacity,

                "capacity_source":
                    capacity_source,

                "source_dataset":
                    "schools.geojson",
            }
        )

    # Official/listed facilities first,
    # potential temporary facilities second.
    result.sort(
        key=lambda item: (
            0
            if item[
                "source_dataset"
            ]
            ==
            "shelters.geojson"
            else 1,

            str(
                item.get("name")
                or ""
            ).lower(),
        )
    )

    return result


def _all_shelters():
    return list(
        _temporary_shelters()
    )


def _all_hospitals():
    return _dataset().get(
        "hospitals",
        [],
    )


# ============================================================
# REAL POPULATION CELLS
# ============================================================

def _affected_cells(seed):
    """
    Return only real population cells inside the selected hazard radius.

    IMPORTANT:
    - A geographic allocation is only meaningful when an incident
      latitude/longitude is supplied.
    - We therefore never fall back to arbitrary high-population cells.
    """

    cells = _dataset().get(
        "population_cells",
        [],
    )

    latitude = seed.get("latitude")
    longitude = seed.get("longitude")

    if (
        latitude is None
        or longitude is None
        or not cells
    ):
        return []

    radius = max(
        0.1,
        float(
            seed.get(
                "hazard_radius_km",
                2.2,
            )
        ),
    )

    nearby = [
        cell
        for cell in cells
        if _haversine_km(
            cell["lat"],
            cell["lng"],
            float(latitude),
            float(longitude),
        ) <= radius
    ]

    # If no cell centroid is inside the radius, use the single nearest
    # real population cell so the selected location still produces a
    # geographically grounded result.
    if not nearby:
        nearest = min(
            cells,
            key=lambda cell:
                _haversine_km(
                    cell["lat"],
                    cell["lng"],
                    float(latitude),
                    float(longitude),
                ),
        )
        nearby = [nearest]

    nearby.sort(
        key=lambda cell: (
            _haversine_km(
                cell["lat"],
                cell["lng"],
                float(latitude),
                float(longitude),
            ),
            -int(
                cell.get(
                    "population",
                    0,
                )
            ),
        )
    )

    max_cells = max(
        1,
        int(
            seed.get(
                "max_population_cells",
                20,
            )
        ),
    )

    return nearby[:max_cells]


def _cell_displaced(
    cell,
    damage,
    severity,
):
    population = max(
        0,
        int(
            cell.get(
                "population",
                0,
            )
        ),
    )

    ratio = (
        0.15
        +
        0.85
        *
        float(damage)
        /
        100.0
    ) * float(severity)

    return max(
        0,
        int(
            min(
                population,
                population * ratio,
            )
        ),
    )


# ============================================================
# REAL ROUTING GRAPH
# ============================================================

@lru_cache(maxsize=1)
def _base_routing_graph():
    """
    Build one cached real road graph.

    Attaches:
        - real temporary shelters
        - real hospitals
    """

    source = _dataset()["graph"]

    graph = nx.DiGraph()

    # --------------------------------------------------------
    # Road nodes
    # --------------------------------------------------------

    for node_id, attrs in source.nodes(
        data=True
    ):
        graph.add_node(
            str(node_id),

            kind="road",

            lat=float(
                attrs["y"]
            ),

            lng=float(
                attrs["x"]
            ),
        )

    # --------------------------------------------------------
    # Real road edges
    # --------------------------------------------------------

    for edge in _dataset()[
        "road_edges"
    ]:
        length_km = max(
            0.001,
            float(
                edge["length_m"]
            )
            /
            1000.0,
        )

        graph.add_edge(
            str(edge["u"]),
            str(edge["v"]),

            id=str(
                edge["id"]
            ),

            distance=
                length_km,

            length_m=
                float(
                    edge["length_m"]
                ),

            highway=
                edge.get(
                    "highway"
                ),

            name=
                edge.get(
                    "name"
                ),
        )

    # --------------------------------------------------------
    # Temporary shelter facilities
    # --------------------------------------------------------

    for record in _all_shelters():
        facility_id = record[
            "facility_id"
        ]

        nearest = _nearest_road_node(
            record["lat"],
            record["lng"],
        )

        nearest_record = NODES[
            nearest
        ]

        access_km = max(
            0.001,
            _haversine_km(
                record["lat"],
                record["lng"],
                nearest_record[2],
                nearest_record[3],
            ),
        )

        graph.add_node(
            facility_id,

            kind=
                record[
                    "facility_type"
                ],

            lat=
                float(
                    record["lat"]
                ),

            lng=
                float(
                    record["lng"]
                ),

            name=
                record["name"],
        )

        graph.add_edge(
            nearest,
            facility_id,

            id=
                f"access:{facility_id}",

            distance=
                access_km,

            length_m=
                access_km * 1000.0,

            access=True,
        )

        graph.add_edge(
            facility_id,
            nearest,

            id=
                f"access:{facility_id}:reverse",

            distance=
                access_km,

            length_m=
                access_km * 1000.0,

            access=True,
        )

    # --------------------------------------------------------
    # Hospitals
    # --------------------------------------------------------

    for record in _all_hospitals():
        hospital_id = _facility_node_id(
            "hospital",
            record["id"],
        )

        nearest = _nearest_road_node(
            record["lat"],
            record["lng"],
        )

        nearest_record = NODES[
            nearest
        ]

        access_km = max(
            0.001,
            _haversine_km(
                record["lat"],
                record["lng"],
                nearest_record[2],
                nearest_record[3],
            ),
        )

        graph.add_node(
            hospital_id,

            kind="hospital",

            lat=
                float(
                    record["lat"]
                ),

            lng=
                float(
                    record["lng"]
                ),

            name=
                record["name"],
        )

        graph.add_edge(
            nearest,
            hospital_id,

            id=
                f"access:{hospital_id}",

            distance=
                access_km,

            length_m=
                access_km * 1000.0,

            access=True,
        )

        graph.add_edge(
            hospital_id,
            nearest,

            id=
                f"access:{hospital_id}:reverse",

            distance=
                access_km,

            length_m=
                access_km * 1000.0,

            access=True,
        )

    return graph


def _weight_function(
    blocked,
    disaster,
    damage,
):
    blocked = set(
        blocked or []
    )

    damage_fraction = (
        float(damage)
        /
        100.0
    )

    def weight(
        u,
        v,
        attrs,
    ):
        road_id = attrs.get(
            "id"
        )

        if road_id in blocked:
            return None

        distance_km = max(
            0.001,
            float(
                attrs.get(
                    "distance",
                    0.001,
                )
            ),
        )

        # Facility access links are not blocked roads.
        if attrs.get(
            "access"
        ):
            return distance_km

        return edge_cost(
            distance_km,
            min(
                1.0,
                damage_fraction,
            ),
            damage_fraction,
            0,
            str(
                disaster
            ).lower(),
        )

    return weight


def _path(
    graph,
    start,
    end,
    blocked,
    disaster,
    damage,
):
    if (
        start not in graph
        or end not in graph
    ):
        return (
            None,
            None,
        )

    try:
        weight = _weight_function(
            blocked,
            disaster,
            damage,
        )

        path = nx.dijkstra_path(
            graph,
            start,
            end,
            weight=weight,
        )

        distance = (
            nx.dijkstra_path_length(
                graph,
                start,
                end,
                weight=weight,
            )
        )

        return (
            path,
            distance,
        )

    except (
        nx.NetworkXNoPath,
        nx.NodeNotFound,
    ):
        return (
            None,
            None,
        )


# ============================================================
# AUTOMATIC ROAD DETECTION
# ============================================================

def _point_to_segment_distance_km(
    point_lat,
    point_lon,
    a_lat,
    a_lon,
    b_lat,
    b_lon,
):
    lat_scale = 111.32

    lon_scale = (
        111.32
        *
        math.cos(
            math.radians(
                (
                    a_lat
                    +
                    b_lat
                    +
                    point_lat
                )
                /
                3.0
            )
        )
    )

    px = point_lon * lon_scale
    py = point_lat * lat_scale

    ax = a_lon * lon_scale
    ay = a_lat * lat_scale

    bx = b_lon * lon_scale
    by = b_lat * lat_scale

    dx = bx - ax
    dy = by - ay

    denominator = (
        dx * dx
        +
        dy * dy
    )

    if denominator == 0:
        return _haversine_km(
            point_lat,
            point_lon,
            a_lat,
            a_lon,
        )

    t = max(
        0.0,
        min(
            1.0,
            (
                (
                    px - ax
                )
                *
                dx
                +
                (
                    py - ay
                )
                *
                dy
            )
            /
            denominator,
        ),
    )

    cx = ax + t * dx
    cy = ay + t * dy

    return math.sqrt(
        (
            px - cx
        ) ** 2
        +
        (
            py - cy
        ) ** 2
    )


def detect_road_status_from_location(
    latitude,
    longitude,
    blocked_radius_km=0.35,
    orange_radius_km=0.75,
    yellow_radius_km=1.25,
):
    latitude = float(latitude)
    longitude = float(longitude)

    blocked_radius = max(
        0.0,
        float(
            blocked_radius_km
        ),
    )

    orange_radius = max(
        blocked_radius,
        float(
            orange_radius_km
        ),
    )

    yellow_radius = max(
        orange_radius,
        float(
            yellow_radius_km
        ),
    )

    latitude_delta = (
        yellow_radius
        /
        111.32
    )

    longitude_delta = (
        yellow_radius
        /
        max(
            1e-6,
            111.32
            *
            math.cos(
                math.radians(
                    latitude
                )
            ),
        )
    )

    road_graph = _dataset()[
        "graph"
    ]

    candidates = []

    for edge in _dataset()[
        "road_edges"
    ]:
        start = road_graph.nodes.get(
            edge["u"],
            {},
        )

        end = road_graph.nodes.get(
            edge["v"],
            {},
        )

        if not start or not end:
            continue

        if (
            max(
                float(start["y"]),
                float(end["y"]),
            )
            <
            latitude
            -
            latitude_delta
        ):
            continue

        if (
            min(
                float(start["y"]),
                float(end["y"]),
            )
            >
            latitude
            +
            latitude_delta
        ):
            continue

        if (
            max(
                float(start["x"]),
                float(end["x"]),
            )
            <
            longitude
            -
            longitude_delta
        ):
            continue

        if (
            min(
                float(start["x"]),
                float(end["x"]),
            )
            >
            longitude
            +
            longitude_delta
        ):
            continue

        distance_km = (
            _point_to_segment_distance_km(
                latitude,
                longitude,
                float(start["y"]),
                float(start["x"]),
                float(end["y"]),
                float(end["x"]),
            )
        )

        if (
            distance_km
            <=
            yellow_radius
        ):
            candidates.append(
                (
                    edge,
                    distance_km,
                )
            )

    blocked = []
    orange = []
    yellow = []

    details = []

    for edge, distance_km in candidates:

        if (
            distance_km
            <=
            blocked_radius
        ):
            status = "blocked"
            target = blocked

        elif (
            distance_km
            <=
            orange_radius
        ):
            status = "orange"
            target = orange

        else:
            status = "yellow"
            target = yellow

        target.append(
            edge["id"]
        )

        details.append(
            {
                "id":
                    edge["id"],

                "from":
                    edge["u"],

                "to":
                    edge["v"],

                "distance_km":
                    round(
                        distance_km,
                        4,
                    ),

                "status":
                    status,

                "name":
                    edge.get(
                        "name"
                    ),
            }
        )

    details.sort(
        key=lambda item:
            item["distance_km"]
    )

    return {
        "enabled": True,

        "source":
            "real_bengaluru_roads",

        "latitude":
            latitude,

        "longitude":
            longitude,

        "blocked_radius_km":
            blocked_radius,

        "orange_radius_km":
            orange_radius,

        "yellow_radius_km":
            yellow_radius,

        "blocked":
            sorted(
                set(blocked)
            ),

        "orange":
            sorted(
                set(orange)
            ),

        "yellow":
            sorted(
                set(yellow)
            ),

        "safe":
            [],

        "road_details":
            details,

        "blocked_count":
            len(set(blocked)),

        "orange_count":
            len(set(orange)),

        "yellow_count":
            len(set(yellow)),

        "safe_count":
            0,
    }


def apply_automatic_road_detection(seed):
    """
    Combine manual blocked roads with automatically detected road hazards
    around the selected incident location.

    No coordinates means no automatic geographic detection.
    """
    seed = dict(seed or {})

    manual_blocked = set(
        seed.get("blocked", []) or []
    )

    # No incident location -> keep manual road selections only.
    if (
        seed.get("latitude") is None
        or seed.get("longitude") is None
    ):
        seed["blocked"] = sorted(
            manual_blocked
        )

        seed["orange_roads"] = sorted(
            set(
                seed.get(
                    "orange_roads",
                    [],
                )
            )
        )

        seed["yellow_roads"] = sorted(
            set(
                seed.get(
                    "yellow_roads",
                    [],
                )
            )
        )

        seed["road_detection"] = {
            "enabled": False,
            "source": "manual_fallback",
            "blocked": sorted(
                manual_blocked
            ),
            "orange": seed[
                "orange_roads"
            ],
            "yellow": seed[
                "yellow_roads"
            ],
            "safe": [],
            "road_details": [],
        }

        return seed

    detection = detect_road_status_from_location(
        seed["latitude"],
        seed["longitude"],
        float(
            seed.get(
                "blocked_radius_km",
                0.35,
            )
        ),
        float(
            seed.get(
                "orange_radius_km",
                0.75,
            )
        ),
        float(
            seed.get(
                "yellow_radius_km",
                1.25,
            )
        ),
    )

    automatic_blocked = set(
        detection.get(
            "blocked",
            [],
        )
    )

    combined_blocked = (
        manual_blocked
        |
        automatic_blocked
    )

    seed["blocked"] = sorted(
        combined_blocked
    )

    seed["orange_roads"] = sorted(
        set(
            detection.get(
                "orange",
                [],
            )
        )
    )

    seed["yellow_roads"] = sorted(
        set(
            detection.get(
                "yellow",
                [],
            )
        )
    )

    detection["manual_blocked"] = sorted(
        manual_blocked
    )

    detection["blocked"] = sorted(
        combined_blocked
    )

    detection["blocked_count"] = len(
        combined_blocked
    )

    seed["road_detection"] = detection

    return seed


def graph_info(
    limit=5000
):
    """
    Return a browser-sized view of the real Bengaluru network.

    Includes:
        - sampled real road nodes/edges
        - real population-cell nodes
        - real shelter facilities
        - potential temporary school facilities
        - real hospitals
    """

    dataset = _dataset()

    limit = max(
        100,
        min(
            int(
                limit
                or
                5000
            ),
            10000,
        ),
    )

    road_edges = dataset[
        "road_edges"
    ]

    if (
        len(road_edges)
        >
        limit
    ):
        step = max(
            1,
            len(road_edges)
            //
            limit,
        )

        sampled_edges = (
            road_edges[
                ::step
            ][:limit]
        )

    else:
        sampled_edges = (
            road_edges
        )

    nodes = {}
    edges = []

    road_graph = dataset[
        "graph"
    ]

    # --------------------------------------------------------
    # Real sampled roads
    # --------------------------------------------------------

    for edge in sampled_edges:

        start_id = str(
            edge["u"]
        )

        end_id = str(
            edge["v"]
        )

        edges.append(
            {
                "id":
                    str(
                        edge["id"]
                    ),

                "a":
                    start_id,

                "b":
                    end_id,

                "name":
                    edge.get(
                        "name"
                    ),

                "highway":
                    edge.get(
                        "highway"
                    ),
            }
        )

        for node_id in (
            start_id,
            end_id,
        ):
            if node_id in nodes:
                continue

            attrs = (
                road_graph.nodes.get(
                    node_id,
                    {},
                )
            )

            if attrs:
                nodes[node_id] = {
                    "name":
                        node_id,

                    "type":
                        "road",

                    "lat":
                        float(
                            attrs["y"]
                        ),

                    "lng":
                        float(
                            attrs["x"]
                        ),
                }

    # --------------------------------------------------------
    # Real population cells
    # --------------------------------------------------------

    for cell in dataset.get(
        "population_cells",
        [],
    ):
        cell_id = cell[
            "id"
        ]

        nodes[cell_id] = {
            "name":
                (
                    cell.get(
                        "name"
                    )
                    or
                    (
                        "Population Cell "
                        +
                        str(
                            cell_id
                        ).split(
                            "_"
                        )[-1]
                    )
                ),

            "type":
                "population_cell",

            "lat":
                float(
                    cell["lat"]
                ),

            "lng":
                float(
                    cell["lng"]
                ),

            "population":
                int(
                    cell.get(
                        "population",
                        0,
                    )
                ),
        }

    facilities = []

    # --------------------------------------------------------
    # Real shelter + temporary shelter facilities
    # --------------------------------------------------------

    for record in _all_shelters():

        if (
            record[
                "source_dataset"
            ]
            ==
            "shelters.geojson"
        ):
            display_type = (
                "shelter"
            )
        else:
            display_type = (
                "temporary_shelter"
            )

        facility = {
            "id":
                record[
                    "facility_id"
                ],

            "name":
                record[
                    "name"
                ],

            "type":
                display_type,

            "facility_type":
                record[
                    "facility_type"
                ],

            "shelter_status":
                record[
                    "shelter_status"
                ],

            "lat":
                float(
                    record[
                        "lat"
                    ]
                ),

            "lng":
                float(
                    record[
                        "lng"
                    ]
                ),

            "capacity":
                int(
                    record[
                        "capacity"
                    ]
                ),

            "capacity_source":
                record[
                    "capacity_source"
                ],

            "source_dataset":
                record[
                    "source_dataset"
                ],
        }

        facilities.append(
            facility
        )

        nodes[
            record[
                "facility_id"
            ]
        ] = {
            "name":
                record[
                    "name"
                ],

            "type":
                display_type,

            "facility_type":
                record[
                    "facility_type"
                ],

            "shelter_status":
                record[
                    "shelter_status"
                ],

            "lat":
                float(
                    record[
                        "lat"
                    ]
                ),

            "lng":
                float(
                    record[
                        "lng"
                    ]
                ),

            "capacity":
                int(
                    record[
                        "capacity"
                    ]
                ),

            "capacity_source":
                record[
                    "capacity_source"
                ],
        }

    # --------------------------------------------------------
    # Real hospitals
    # --------------------------------------------------------

    for hospital in _all_hospitals():

        hospital_id = (
            _facility_node_id(
                "hospital",
                hospital["id"],
            )
        )

        facilities.append(
            {
                "id":
                    hospital_id,

                "name":
                    hospital["name"],

                "type":
                    "hospital",

                "lat":
                    float(
                        hospital["lat"]
                    ),

                "lng":
                    float(
                        hospital["lng"]
                    ),
            }
        )

        nodes[hospital_id] = {
            "name":
                hospital["name"],

            "type":
                "hospital",

            "lat":
                float(
                    hospital["lat"]
                ),

            "lng":
                float(
                    hospital["lng"]
                ),
        }

    return {
        "data_source":
            "data/raw/bengaluru",

        "road_nodes":
            road_graph.number_of_nodes(),

        "road_edges":
            road_graph.number_of_edges(),

        "nodes":
            nodes,

        "edges":
            edges,

        "facilities":
            facilities,

        "population_cells":
            len(
                dataset.get(
                    "population_cells",
                    [],
                )
            ),

        "temporary_shelters":
            len(
                _all_shelters()
            ),

        "sampled_edges":
            len(edges),

        "note":
            (
                "Road routing uses the complete real GraphML network. "
                "Shelter allocation uses real facilities from shelters.geojson "
                "plus suitable school/college/university records from schools.geojson."
            ),
    }


# ============================================================
# RISK HELPERS
# ============================================================

def _local_risk(
    overall_risk,
    damage,
    population,
    blocked_count,
    total_roads,
):
    population_factor = (
        min(
            1.0,
            population / 20000.0,
        )
        *
        100.0
    )

    blockage_ratio = (
        blocked_count
        /
        max(
            1,
            total_roads,
        )
    )

    value = (
        0.60
        *
        float(
            overall_risk
        )
        +
        0.20
        *
        float(
            damage
        )
        +
        0.10
        *
        population_factor
        +
        0.10
        *
        blockage_ratio
        *
        100.0
    )

    return max(
        0.0,
        min(
            100.0,
            round(
                value,
                2,
            ),
        ),
    )


def _nearest_hospitals_for_zone(
    zone,
    limit=3,
):
    hospitals = (
        _all_hospitals()
    )

    ranked = sorted(
        hospitals,
        key=lambda hospital:
            _haversine_km(
                zone["lat"],
                zone["lng"],
                hospital["lat"],
                hospital["lng"],
            ),
    )

    return ranked[:limit]


def _shelter_capacity_data():
    """
    Build capacity data directly from the loader's real facility records.

    IMPORTANT:
    The facility_id generated by real_data_loader.py is the canonical ID.
    We do not reconstruct IDs here, which keeps shelter and school/
    temporary-shelter routing IDs consistent.
    """
    data = {}

    for record in _all_shelters():

        facility_id = record[
            "facility_id"
        ]

        data[
            facility_id
        ] = {
            "capacity":
                int(
                    record[
                        "capacity"
                    ]
                ),

            "capacity_source":
                record[
                    "capacity_source"
                ],

            "name":
                record[
                    "name"
                ],

            "lat":
                float(
                    record[
                        "lat"
                    ]
                ),

            "lng":
                float(
                    record[
                        "lng"
                    ]
                ),

            "facility_type":
                record[
                    "facility_type"
                ],

            "shelter_status":
                record[
                    "shelter_status"
                ],

            "source_dataset":
                record[
                    "source_dataset"
                ],
        }

    return data


def _zone_string(value):
    """
    Normalize the classifier output.

    Handles:
        "ORANGE"

    and:
        {"zone": "ORANGE", ...}

    and older:
        {"ZONE": "ORANGE", ...}
    """

    if isinstance(
        value,
        str,
    ):
        zone = (
            value
            .strip()
            .upper()
        )

    elif isinstance(
        value,
        dict,
    ):
        zone = str(
            value.get(
                "zone"
            )
            or
            value.get(
                "ZONE"
            )
            or
            value.get(
                "hazard_zone"
            )
            or
            value.get(
                "HAZARD_ZONE"
            )
            or
            ""
        ).strip().upper()

    else:
        zone = str(
            value
        ).strip().upper()

    # The existing zone_response.py supports RED / ORANGE / YELLOW.
    if zone == "GREEN":
        return "YELLOW"

    if zone not in {
        "RED",
        "ORANGE",
        "YELLOW",
    }:
        raise ValueError(
            f"Invalid hazard zone: {zone}"
        )

    return zone


def _enrich_assignments(
    assignments,
    shelter_data,
    zone_meta,
):
    """
    Add actual names and metadata to fair-allocation records.
    """

    for assignment in assignments:

        shelter_id = assignment.get(
            "shelter"
        )

        zone_id = assignment.get(
            "zone"
        )

        facility = shelter_data.get(
            shelter_id
        )

        if facility:

            assignment[
                "shelter_name"
            ] = facility[
                "name"
            ]

            assignment[
                "facility_type"
            ] = facility[
                "facility_type"
            ]

            assignment[
                "shelter_status"
            ] = facility[
                "shelter_status"
            ]

            assignment[
                "capacity"
            ] = int(
                facility[
                    "capacity"
                ]
            )

            assignment[
                "capacity_source"
            ] = facility[
                "capacity_source"
            ]

            assignment[
                "source_dataset"
            ] = facility[
                "source_dataset"
            ]

            assignment[
                "latitude"
            ] = facility[
                "lat"
            ]

            assignment[
                "longitude"
            ] = facility[
                "lng"
            ]

        if (
            zone_id
            in
            zone_meta
        ):
            assignment[
                "zone_name"
            ] = zone_meta[
                zone_id
            ][
                "name"
            ]

    return assignments

def calculate_zone_priority(zones):
    """
    Calculate adaptive recovery priority for each real
    population zone.

    Priority is based on:

    1. Local risk
    2. Humanitarian demand / need
    3. Unsheltered population
    4. Road accessibility
    5. Hospital accessibility

    This does not replace the existing risk engine.
    It is a decision-support layer built on top of
    the existing V4 outputs.
    """

    if not zones:
        return []

    max_risk = max(
        [float(zone.get("risk", 0)) for zone in zones],
        default=1.0,
    )

    max_need = max(
        [float(zone.get("need", 0)) for zone in zones],
        default=1.0,
    )

    max_unsheltered = max(
        [float(zone.get("unsheltered", 0)) for zone in zones],
        default=1.0,
    )

    results = []

    for zone in zones:
        risk = float(zone.get("risk", 0))
        need = float(zone.get("need", 0))
        unsheltered = float(zone.get("unsheltered", 0))
        reachable = bool(zone.get("reachable", True))
        hospital_access = bool(zone.get("hospital_access", True))

        risk_score = risk / max(1.0, max_risk)
        demand_score = need / max(1.0, max_need)
        unsheltered_score = unsheltered / max(1.0, max_unsheltered)

        road_problem = 1.0 if not reachable else 0.0
        hospital_problem = 1.0 if not hospital_access else 0.0

        priority_score = (
            0.30 * risk_score
            + 0.30 * demand_score
            + 0.20 * unsheltered_score
            + 0.10 * road_problem
            + 0.10 * hospital_problem
        )

        priority_score = round(priority_score * 100.0, 1)

        if priority_score >= 75:
            priority_level = "CRITICAL"
        elif priority_score >= 50:
            priority_level = "HIGH"
        elif priority_score >= 25:
            priority_level = "MEDIUM"
        else:
            priority_level = "LOW"

        reasons = []

        if risk_score >= 0.75:
            reasons.append("High local disaster risk")

        if demand_score >= 0.75:
            reasons.append("High population support requirement")

        if unsheltered_score >= 0.75:
            reasons.append("High number of unsheltered people")

        if not reachable:
            reasons.append("Limited road accessibility")

        if not hospital_access:
            reasons.append("Limited hospital access")

        if not reasons:
            reasons.append("Relatively lower recovery pressure")

        results.append(
            {
                "zone_id": zone.get("id"),
                "zone_name": zone.get("name"),
                "latitude": zone.get("latitude"),
                "longitude": zone.get("longitude"),
                "priority_score": priority_score,
                "priority_level": priority_level,
                "risk": round(risk, 1),
                "need": int(need),
                "unsheltered": int(unsheltered),
                "sheltered": int(zone.get("sheltered", 0)),
                "reachable": reachable,
                "hospital_access": hospital_access,
                "hazard_zone": zone.get("hazard_zone"),
                "reasons": reasons,
            }
        )

    results.sort(
        key=lambda item: item["priority_score"],
        reverse=True,
    )

    for index, item in enumerate(results, start=1):
        item["rank"] = index

    return results


# ============================================================
# MAIN PLAN
# ============================================================


def generate_plan(
    seed,
    ml_prediction=None,
):
    """
    Generate a recovery plan from the current disaster seed.

    Location-aware behavior:
        - Without latitude/longitude:
          calculate scenario-level risk/resource/ML metrics only.
          No geographic shelter allocation is invented.

        - With latitude/longitude:
          use real population cells inside the hazard radius,
          constrain exposure to the user's population input,
          find nearby real facilities,
          route through the real Bengaluru road graph,
          and run the fairness-aware shelter allocator.
    """

    seed = apply_automatic_road_detection(
        seed
    )

    population_input = max(
        1,
        int(
            float(
                seed.get(
                    "population",
                    1,
                )
            )
        ),
    )

    damage = min(
        100.0,
        max(
            0.0,
            float(
                seed.get(
                    "damage",
                    0,
                )
            ),
        ),
    )

    disaster = str(
        seed.get(
            "disaster",
            "flood",
        )
    ).lower()

    severity = SEVERITY.get(
        disaster,
        1.0,
    )

    blocked = set(
        seed.get(
            "blocked",
            [],
        )
        or []
    )

    dataset = _dataset()
    graph = _base_routing_graph()

    has_location = (
        seed.get("latitude") is not None
        and
        seed.get("longitude") is not None
    )

    # --------------------------------------------------------
    # Real geographic exposure
    # --------------------------------------------------------

    cells = _affected_cells(seed)

    exposed_by_cell = {}
    displaced_by_cell = {}

    if has_location and cells:

        total_real_population = sum(
            max(
                0,
                int(
                    cell.get(
                        "population",
                        0,
                    )
                ),
            )
            for cell in cells
        )

        # Never let geographic exposure silently exceed the
        # scenario population entered by the user.
        target_exposed = min(
            population_input,
            total_real_population,
        )

        if total_real_population > 0:
            for cell in cells:
                cell_population = max(
                    0,
                    int(
                        cell.get(
                            "population",
                            0,
                        )
                    ),
                )

                share = (
                    cell_population
                    /
                    total_real_population
                )

                exposed_by_cell[
                    cell["id"]
                ] = int(
                    round(
                        target_exposed
                        * share
                    )
                )

        # Correct rounding so the total is exactly the
        # user-requested population, as long as the real
        # cells contain enough population.
        rounding_difference = (
            target_exposed
            -
            sum(
                exposed_by_cell.values()
            )
        )

        if rounding_difference != 0:

            ordered_cells = sorted(
                cells,
                key=lambda cell:
                    _haversine_km(
                        cell["lat"],
                        cell["lng"],
                        float(
                            seed["latitude"]
                        ),
                        float(
                            seed["longitude"]
                        ),
                    ),
            )

            for cell in ordered_cells:

                cid = cell["id"]

                cell_population = max(
                    0,
                    int(
                        cell.get(
                            "population",
                            0,
                        )
                    ),
                )

                current = exposed_by_cell.get(
                    cid,
                    0,
                )

                if rounding_difference > 0:

                    room = max(
                        0,
                        cell_population
                        -
                        current,
                    )

                    if room > 0:

                        add = min(
                            room,
                            rounding_difference,
                        )

                        exposed_by_cell[
                            cid
                        ] = (
                            current
                            +
                            add
                        )

                        rounding_difference -= add

                else:

                    removable = min(
                        current,
                        -rounding_difference,
                    )

                    if removable > 0:

                        exposed_by_cell[
                            cid
                        ] = (
                            current
                            -
                            removable
                        )

                        rounding_difference += removable

                if rounding_difference == 0:
                    break

        damage_ratio = (
            0.15
            +
            0.85
            *
            damage
            /
            100.0
        )

        for cell in cells:

            cid = cell["id"]

            exposed = int(
                exposed_by_cell.get(
                    cid,
                    0,
                )
            )

            displaced_by_cell[
                cid
            ] = max(
                0,
                min(
                    exposed,
                    int(
                        round(
                            exposed
                            *
                            damage_ratio
                            *
                            severity
                        )
                    ),
                ),
            )

        displaced = min(
            population_input,
            sum(
                displaced_by_cell.values()
            ),
        )

    else:

        # Scenario-only mode.
        # We can still calculate ML/risk/resource metrics,
        # but we DO NOT invent affected geographic cells.
        displaced = int(
            min(
                population_input,
                population_input
                *
                (
                    0.15
                    +
                    0.85
                    *
                    damage
                    /
                    100.0
                )
                *
                severity,
            )
        )

    # --------------------------------------------------------
    # ML prediction integration
    # --------------------------------------------------------

    if ml_prediction:

        displaced = int(
            round(
                0.55
                * displaced
                +
                0.45
                *
                float(
                    ml_prediction.get(
                        "displaced",
                        displaced,
                    )
                )
            )
        )

        # The ML output cannot create more affected people
        # than the population supplied by the user.
        displaced = max(
            0,
            min(
                population_input,
                displaced,
            ),
        )

    # --------------------------------------------------------
    # Resource demand
    # --------------------------------------------------------

    demand = {
        "water":
            int(
                displaced * 15
            ),

        "food":
            int(
                round(
                    displaced * 0.5
                )
            ),

        "medical":
            max(
                1,
                int(
                    round(
                        population_input
                        *
                        damage
                        /
                        100.0
                        *
                        0.04
                        *
                        severity
                    )
                ),
            ),
    }

    if ml_prediction:

        demand["medical"] = max(
            1,
            int(
                round(
                    0.55
                    *
                    demand["medical"]
                    +
                    0.45
                    *
                    float(
                        ml_prediction.get(
                            "medical_demand",
                            demand[
                                "medical"
                            ],
                        )
                    )
                )
            ),
        )

    supply = {
        resource:
            float(
                seed.get(
                    resource,
                    0,
                )
            )
        for resource in (
            "water",
            "food",
            "medical",
        )
    }

    cover = {
        resource:
            min(
                1.0,
                supply[resource]
                /
                max(
                    1,
                    demand[resource],
                ),
            )
        for resource in demand
    }

    shortage = {
        resource:
            max(
                0,
                demand[resource]
                -
                supply[resource],
            )
        for resource in demand
    }

    # --------------------------------------------------------
    # Risk
    # --------------------------------------------------------

    risk_breakdown = {
        "Population exposed":
            min(
                25.0,
                population_input
                /
                20000.0
                *
                25.0,
            ),

        "Infrastructure damage":
            damage
            /
            100.0
            *
            35.0,

        "Blocked roads":
            min(
                20.0,
                len(
                    blocked
                )
                /
                max(
                    1,
                    len(
                        EDGES
                    ),
                )
                *
                40.0,
            ),

        "Resource shortage":
            20.0
            *
            (
                1.0
                -
                sum(
                    cover.values()
                )
                /
                3.0
            ),
    }

    risk_breakdown = {
        key:
            round(
                value
                *
                (
                    0.8
                    +
                    0.2
                    *
                    severity
                ),
                1,
            )
        for key, value
        in
        risk_breakdown.items()
    }

    risk = min(
        100.0,
        round(
            sum(
                risk_breakdown.values()
            ),
            1,
        ),
    )

    if ml_prediction:

        risk = round(
            0.65 * risk
            +
            0.35
            *
            float(
                ml_prediction.get(
                    "risk",
                    risk,
                )
            ),
            1,
        )

        risk = max(
            0.0,
            min(
                100.0,
                risk,
            ),
        )

    # --------------------------------------------------------
    # Hazard zone
    # --------------------------------------------------------

    hazard = classify_zone(
        risk
    )

    overall_zone = _zone_string(
        hazard
    )

    risk_level = (
        "CRITICAL"
        if risk >= 75
        else
        "HIGH"
        if risk >= 55
        else
        "MEDIUM"
        if risk >= 35
        else
        "LOW"
    )

    # --------------------------------------------------------
    # Real population-cell zones
    # --------------------------------------------------------

    zone_need = {}
    zone_meta = {}

    if has_location:

        for cell in cells:

            zone_id = cell["id"]

            need = int(
                displaced_by_cell.get(
                    zone_id,
                    0,
                )
            )

            zone_need[
                zone_id
            ] = need

            zone_meta[
                zone_id
            ] = {
                "id":
                    zone_id,

                "name":
                    (
                        cell.get(
                            "name"
                        )
                        or
                        (
                            "Population Cell "
                            +
                            str(
                                zone_id
                            ).split(
                                "_"
                            )[-1]
                        )
                    ),

                "lat":
                    float(
                        cell["lat"]
                    ),

                "lng":
                    float(
                        cell["lng"]
                    ),

                "population":
                    int(
                        exposed_by_cell.get(
                            zone_id,
                            0,
                        )
                    ),
            }

    # --------------------------------------------------------
    # Real shelter pool
    # --------------------------------------------------------

    shelter_data = (
        _shelter_capacity_data()
    )

    shelter_ids = list(
        shelter_data
    )

    max_shelter_candidates = max(
        1,
        int(
            seed.get(
                "shelter_candidates",
                6,
            )
        ),
    )

    candidate_cache = {}

    def candidates(zone_id):

        if zone_id in candidate_cache:
            return candidate_cache[
                zone_id
            ]

        if zone_id not in zone_meta:
            return []

        zone = zone_meta[
            zone_id
        ]

        ranked_shelters = sorted(
            shelter_ids,
            key=lambda shelter_id:
                _haversine_km(
                    zone["lat"],
                    zone["lng"],
                    shelter_data[
                        shelter_id
                    ]["lat"],
                    shelter_data[
                        shelter_id
                    ]["lng"],
                ),
        )[
            :max_shelter_candidates
        ]

        zone_node = _nearest_road_node(
            zone["lat"],
            zone["lng"],
        )

        output = []

        for shelter_id in ranked_shelters:

            shelter = shelter_data[
                shelter_id
            ]

            path, distance = _path(
                graph,
                zone_node,
                shelter_id,
                blocked,
                disaster,
                damage,
            )

            if path is None:
                continue

            medical_access = False

            for hospital in _nearest_hospitals_for_zone(
                zone,
                limit=2,
            ):

                hospital_id = (
                    _facility_node_id(
                        "hospital",
                        hospital["id"],
                    )
                )

                hospital_path, _ = _path(
                    graph,
                    shelter_id,
                    hospital_id,
                    blocked,
                    disaster,
                    damage,
                )

                if hospital_path is not None:
                    medical_access = True
                    break

            output.append(
                {
                    "zone":
                        zone_id,

                    "zone_name":
                        zone["name"],

                    "shelter":
                        shelter_id,

                    "shelter_name":
                        shelter["name"],

                    "facility_type":
                        shelter[
                            "facility_type"
                        ],

                    "shelter_status":
                        shelter[
                            "shelter_status"
                        ],

                    "capacity":
                        int(
                            shelter[
                                "capacity"
                            ]
                        ),

                    "capacity_source":
                        shelter[
                            "capacity_source"
                        ],

                    "source_dataset":
                        shelter[
                            "source_dataset"
                        ],

                    "km":
                        round(
                            float(
                                distance
                            ),
                            2,
                        ),

                    "path":
                        path,

                    "need_score":
                        min(
                            1.0,
                            zone_need[
                                zone_id
                            ]
                            /
                            max(
                                1,
                                displaced
                                /
                                max(
                                    1,
                                    len(
                                        zone_need
                                    ),
                                ),
                            ),
                        ),

                    "safety":
                        max(
                            0.0,
                            1.0
                            -
                            damage
                            /
                            100.0,
                        ),

                    "medical_access":
                        (
                            1.0
                            if
                            medical_access
                            else
                            0.25
                        ),
                }
            )

        output.sort(
            key=lambda item:
                item["km"]
        )

        candidate_cache[
            zone_id
        ] = output

        return output

    # --------------------------------------------------------
    # Fair shelter allocation
    # --------------------------------------------------------

    if (
        has_location
        and
        zone_need
        and
        shelter_data
    ):
        assignments, remaining = (
            fair_allocate(
                zone_need,
                shelter_data,
                candidates,
            )
        )
    else:
        assignments = []

        remaining = {
            zone_id:
                int(
                    need
                )
            for zone_id, need
            in zone_need.items()
        }

    assignments = _enrich_assignments(
        assignments,
        shelter_data,
        zone_meta,
    )

    # --------------------------------------------------------
    # Relevant facilities around the selected incident
    # --------------------------------------------------------

    relevant_facilities = []

    if has_location:

        facility_radius = max(
            0.1,
            float(
                seed.get(
                    "facility_display_radius_km",
                    3.0,
                )
            ),
        )

        facility_limit = max(
            1,
            int(
                seed.get(
                    "facility_display_limit",
                    30,
                )
            ),
        )

        incident_lat = float(
            seed["latitude"]
        )

        incident_lng = float(
            seed["longitude"]
        )

        for record in _all_shelters():

            distance = _haversine_km(
                incident_lat,
                incident_lng,
                record["lat"],
                record["lng"],
            )

            if (
                distance
                <=
                facility_radius
            ):

                relevant_facilities.append(
                    {
                        "id":
                            record[
                                "facility_id"
                            ],

                        "name":
                            record[
                                "name"
                            ],

                        "type":
                            (
                                "shelter"
                                if
                                record[
                                    "source_dataset"
                                ]
                                ==
                                "shelters.geojson"
                                else
                                "temporary_shelter"
                            ),

                        "facility_type":
                            record[
                                "facility_type"
                            ],

                        "shelter_status":
                            record[
                                "shelter_status"
                            ],

                        "capacity":
                            int(
                                record[
                                    "capacity"
                                ]
                            ),

                        "capacity_source":
                            record[
                                "capacity_source"
                            ],

                        "source_dataset":
                            record[
                                "source_dataset"
                            ],

                        "lat":
                            float(
                                record[
                                    "lat"
                                ]
                            ),

                        "lng":
                            float(
                                record[
                                    "lng"
                                ]
                            ),

                        "distance_from_hazard_km":
                            round(
                                distance,
                                3,
                            ),
                    }
                )

        for hospital in _all_hospitals():

            distance = _haversine_km(
                incident_lat,
                incident_lng,
                hospital["lat"],
                hospital["lng"],
            )

            if (
                distance
                <=
                facility_radius
            ):

                relevant_facilities.append(
                    {
                        "id":
                            _facility_node_id(
                                "hospital",
                                hospital["id"],
                            ),

                        "name":
                            hospital[
                                "name"
                            ],

                        "type":
                            "hospital",

                        "facility_type":
                            "hospital",

                        "lat":
                            float(
                                hospital[
                                    "lat"
                                ]
                            ),

                        "lng":
                            float(
                                hospital[
                                    "lng"
                                ]
                            ),

                        "distance_from_hazard_km":
                            round(
                                distance,
                                3,
                            ),
                    }
                )

        relevant_facilities.sort(
            key=lambda item:
                item[
                    "distance_from_hazard_km"
                ]
        )

        relevant_facilities = (
            relevant_facilities[
                :facility_limit
            ]
        )

    # --------------------------------------------------------
    # Zone details and routes
    # --------------------------------------------------------

    zones = []
    supply_routes = []
    hospital_access = {}

    source_node = None

    if has_location:

        source_node = _nearest_road_node(
            float(
                seed["latitude"]
            ),
            float(
                seed["longitude"]
            ),
        )

    for zone_id in sorted(
        zone_need,
        key=lambda item:
            -zone_need[item],
    ):

        zone = zone_meta[
            zone_id
        ]

        zone_node = _nearest_road_node(
            zone["lat"],
            zone["lng"],
        )

        allocated = sum(
            int(
                assignment.get(
                    "people",
                    0,
                )
            )
            for assignment
            in assignments
            if assignment.get(
                "zone"
            )
            ==
            zone_id
        )

        unsheltered = max(
            0,
            int(
                zone_need[
                    zone_id
                ]
            )
            -
            allocated,
        )

        local_risk = _local_risk(
            risk,
            damage,
            zone["population"],
            len(
                blocked
            ),
            len(
                EDGES
            ),
        )

        local_classification = (
            classify_zone(
                local_risk
            )
        )

        local_zone = _zone_string(
            local_classification
        )

        # ----------------------------------------------------
        # Hospital access
        # ----------------------------------------------------

        hospital_ok = False

        for hospital in _nearest_hospitals_for_zone(
            zone,
            limit=3,
        ):

            hospital_id = (
                _facility_node_id(
                    "hospital",
                    hospital["id"],
                )
            )

            hospital_path, _ = _path(
                graph,
                zone_node,
                hospital_id,
                blocked,
                disaster,
                damage,
            )

            if hospital_path is not None:
                hospital_ok = True
                break

        hospital_access[
            zone_id
        ] = hospital_ok

        # ----------------------------------------------------
        # Supply route
        # ----------------------------------------------------

        if source_node is not None:

            supply_path, supply_km = _path(
                graph,
                source_node,
                zone_node,
                blocked,
                disaster,
                damage,
            )

            if supply_path:

                supply_routes.append(
                    {
                        "zone":
                            zone_id,

                        "zone_name":
                            zone["name"],

                        "path":
                            supply_path,

                        "km":
                            round(
                                float(
                                    supply_km
                                ),
                                2,
                            ),

                        "source":
                            "hazard_location_staging_point",
                    }
                )

        zones.append(
            {
                "id":
                    zone_id,

                "name":
                    zone["name"],

                "latitude":
                    zone["lat"],

                "longitude":
                    zone["lng"],

                "population":
                    zone["population"],

                "need":
                    zone_need[
                        zone_id
                    ],

                "sheltered":
                    allocated,

                "unsheltered":
                    unsheltered,

                "reachable":
                    bool(
                        candidates(
                            zone_id
                        )
                    ),

                "hospital_access":
                    hospital_ok,

                "risk":
                    local_risk,

                "hazard_zone":
                    local_zone,

                "severity":
                    local_classification.get(
                        "severity"
                    ),

                "zone_priority":
                    local_classification.get(
                        "priority"
                    ),

                "zone_color":
                    local_classification.get(
                        "color"
                    ),

                "evacuation":
                    local_classification.get(
                        "evacuation"
                    ),

                "resource_priority":
                    local_classification.get(
                        "resource_priority"
                    ),

                "medical_priority":
                    local_classification.get(
                        "medical_priority"
                    ),

                "route_priority":
                    local_classification.get(
                        "route_priority"
                    ),

                "recommended_action":
                    local_classification.get(
                        "recommended_action"
                    ),
            }
        )

    # --------------------------------------------------------
    # Zone Priority Engine
    # --------------------------------------------------------

    zone_priorities = calculate_zone_priority(
        zones
    )

    # --------------------------------------------------------
    # Recovery metrics
    # --------------------------------------------------------

    sheltered = sum(
        int(
            assignment.get(
                "people",
                0,
            )
        )
        for assignment
        in assignments
    )

    total_unsheltered = sum(
        int(
            zone["unsheltered"]
        )
        for zone
        in zones
    )

    shelter_coverage = (
        sheltered
        /
        max(
            1,
            displaced,
        )
    )

    # If no location has been selected there are deliberately
    # no geographic zones to assess.
    if not has_location:
        accessibility = 0.0
    else:
        accessibility = (
            sum(
                bool(
                    zone["reachable"]
                )
                for zone
                in zones
            )
            /
            max(
                1,
                len(
                    zones
                ),
            )
        )

    resource_coverage = (
        sum(
            cover.values()
        )
        /
        3.0
    )

    allocation_values = [
        int(
            assignment.get(
                "people",
                0,
            )
        )
        for assignment
        in
        assignments
        if int(
            assignment.get(
                "people",
                0,
            )
        )
        > 0
    ]

    if (
        allocation_values
        and
        sheltered > 0
    ):

        fairness = (
            1.0
            -
            (
                max(
                    allocation_values
                )
                -
                min(
                    allocation_values
                )
            )
            /
            max(
                1,
                sheltered,
            )
        )

    else:
        fairness = 0.0

    fairness = max(
        0.0,
        min(
            1.0,
            fairness,
        ),
    )

    recovery_score = round(
        100.0
        *
        (
            0.30
            *
            shelter_coverage
            +
            0.20
            *
            accessibility
            +
            0.25
            *
            resource_coverage
            +
            0.10
            *
            fairness
            +
            0.15
            *
            (
                1.0
                -
                risk
                /
                100.0
            )
        )
    )

    # --------------------------------------------------------
    # Recovery priorities
    # --------------------------------------------------------

    gaps = {
        "Medical support":
            1.0
            -
            cover[
                "medical"
            ],

        "Shelter allocation":
            (
                1.0
                if not has_location
                else
                1.0
                -
                shelter_coverage
            ),

        "Water distribution":
            1.0
            -
            cover[
                "water"
            ],

        "Food distribution":
            1.0
            -
            cover[
                "food"
            ],

        "Route restoration":
            max(
                0.0,
                1.0
                -
                accessibility
                +
                len(
                    blocked
                )
                *
                0.03,
            ),
    }

    priorities = [
        {
            "name":
                name,

            "gap":
                round(
                    gap
                    *
                    100
                ),
        }
        for name, gap
        in sorted(
            gaps.items(),
            key=lambda item:
                -item[1],
        )
    ]

    # --------------------------------------------------------
    # Final plan
    # --------------------------------------------------------

    location = {
        "selected":
            bool(
                has_location
            ),

        "latitude":
            (
                float(
                    seed[
                        "latitude"
                    ]
                )
                if has_location
                else None
            ),

        "longitude":
            (
                float(
                    seed[
                        "longitude"
                    ]
                )
                if has_location
                else None
            ),

        "hazard_radius_km":
            (
                float(
                    seed.get(
                        "hazard_radius_km",
                        2.2,
                    )
                )
                if has_location
                else None
            ),
    }

    plan = {
        "risk":
            risk,

        "risk_level":
            risk_level,

        "risk_breakdown":
            risk_breakdown,

        "hazard_zone":
            overall_zone,

        "zone":
            overall_zone,

        "zone_color":
            hazard.get(
                "color",
                "#808080",
            ),

        "zone_severity":
            hazard.get(
                "severity",
                "UNKNOWN",
            ),

        "zone_priority":
            hazard.get(
                "priority",
                "UNKNOWN",
            ),

        "displaced":
            displaced,

        "demand":
            demand,

        "supply":
            supply,

        "shortage":
            shortage,

        "location":
            location,

        "geographic_plan_ready":
            bool(
                has_location
                and
                bool(
                    zones
                )
            ),

        "message":
            (
                "Select an incident location on the map to "
                "calculate geographically relevant population "
                "exposure, shelters, hospitals, and routes."
                if not has_location
                else
                "Recovery plan calculated for the selected "
                "incident location using real Bengaluru data."
            ),

        "zones":
            zones,

        "zone_priorities":
            zone_priorities,

        "assignments":
            assignments,

        "remaining":
            remaining,

        "supply_routes":
            supply_routes,

        "accessible_roads":
            max(
                0,
                len(
                    EDGES
                )
                -
                len(
                    blocked
                ),
            ),

        "blocked_roads":
            sorted(
                blocked
            ),

        "sheltered":
            sheltered,

        "unsheltered":
            total_unsheltered,

        "priorities":
            priorities,

        "recovery_score":
            recovery_score,

        "fairness_score":
            round(
                fairness
                *
                100.0,
                1,
            ),

        "access":
            {
                "accessibility_score":
                    round(
                        accessibility,
                        4,
                    ),

                "hospital_access":
                    hospital_access,
            },

        "routing_mode":
            (
                "risk-aware adaptive "
                "Dijkstra on real "
                "Bengaluru road graph"
            ),

        "road_detection":
            seed.get(
                "road_detection",
                {},
            ),

        "orange_roads":
            sorted(
                seed.get(
                    "orange_roads",
                    [],
                )
            ),

        "yellow_roads":
            sorted(
                seed.get(
                    "yellow_roads",
                    [],
                )
            ),

        "dataset":
            dataset_summary(),

        "real_data":
            {
                "population_cells_used":
                    len(
                        cells
                    ),

                "shelters_considered":
                    (
                        len(
                            shelter_data
                        )
                        if has_location
                        else 0
                    ),

                "official_shelters":
                    sum(
                        record[
                            "source_dataset"
                        ]
                        ==
                        "shelters.geojson"
                        for record
                        in
                        _all_shelters()
                    ),

                "temporary_shelters":
                    sum(
                        record[
                            "source_dataset"
                        ]
                        ==
                        "schools.geojson"
                        for record
                        in
                        _all_shelters()
                    ),

                "capacity_rule":
                    (
                        "Dataset capacity when "
                        "capacity/beds/emergency_capacity "
                        "exists; otherwise explicitly "
                        "labelled estimated emergency capacity."
                    ),
            },

        "relevant_facilities":
            relevant_facilities,

        "shelter_capacity_note":
            (
                "Shelter allocation uses real facilities "
                "from shelters.geojson and suitable "
                "school/college/university records from "
                "schools.geojson. Geographic allocation "
                "is only generated after an incident location "
                "is supplied. The user-entered shelter_capacity "
                "value is not split into fake S1/S2/S3 capacities."
            ),
    }

    # --------------------------------------------------------
    # Zone response
    # --------------------------------------------------------

    return apply_zone_response(
        plan,
        overall_zone,
    )


# ============================================================
# BOTTLENECKS# ============================================================
# BOTTLENECKS
# ============================================================

def find_critical_bottlenecks(
    seed
):
    """
    Return a bounded list of real roads with the greatest
    impact on the current recovery plan.
    """

    seed = dict(
        seed or {}
    )

    base_plan = generate_plan(
        seed
    )

    current_blocked = set(
        seed.get(
            "blocked",
            [],
        )
        or []
    )

    detection = (
        base_plan.get(
            "road_detection"
        )
        or {}
    )

    if detection.get(
        "road_details"
    ):
        candidate_ids = [
            item["id"]
            for item
            in detection[
                "road_details"
            ]
            if item["id"]
            not in
            current_blocked
        ][:20]

    else:
        candidate_ids = [
            road_id
            for road_id, _, _
            in EDGES
            if road_id
            not in
            current_blocked
        ][:20]

    results = []

    for road_id in candidate_ids:

        test_seed = dict(
            seed
        )

        test_seed[
            "blocked"
        ] = sorted(
            current_blocked
            |
            {
                road_id
            }
        )

        test_seed.pop(
            "road_detection",
            None,
        )

        test_plan = (
            generate_plan(
                test_seed
            )
        )

        results.append(
            {
                "road_id":
                    road_id,

                "risk_increase":
                    round(
                        float(
                            test_plan[
                                "risk"
                            ]
                        )
                        -
                        float(
                            base_plan[
                                "risk"
                            ]
                        ),
                        2,
                    ),

                "sheltered_loss":
                    max(
                        0,
                        int(
                            base_plan[
                                "sheltered"
                            ]
                        )
                        -
                        int(
                            test_plan[
                                "sheltered"
                            ]
                        ),
                    ),

                "recovery_score_loss":
                    max(
                        0,
                        int(
                            base_plan[
                                "recovery_score"
                            ]
                        )
                        -
                        int(
                            test_plan[
                                "recovery_score"
                            ]
                        ),
                    ),
            }
        )

    results.sort(
        key=lambda item: (
            item[
                "risk_increase"
            ],

            item[
                "sheltered_loss"
            ],

            item[
                "recovery_score_loss"
            ],
        ),

        reverse=True,
    )

    return results[:10]