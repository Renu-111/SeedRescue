"""
SeedRescue Adaptive Recovery Engine

Seed -> Unfolding -> Manifestation

Combined recovery engine containing:

- Disaster risk estimation
- Population displacement estimation
- Humanitarian demand estimation
- ML prediction blending
- Risk-aware adaptive routing
- Fair shelter allocation
- Hospital accessibility
- Supply routing
- Resource shortage detection
- Recovery scoring
- Fairness scoring
- Incident Commander briefing
- Critical road bottleneck analysis
- Automatic coordinate-based road hazard detection
- Hazard zone classification
- Zone-specific response recommendations
- What-if scenario compatibility
- Frontend graph information
"""

import math
import networkx as nx

from backend.routing.adaptive_router import edge_cost
from backend.allocation.fair_allocator import allocate as fair_allocate

from backend.services.zone_classifier import classify_zone
from backend.services.zone_response import apply_zone_response


# ============================================================
# 1. DEMO REGION — BENGALURU
# ============================================================

NODES = {

    "Z1": (
        "Riverside Colony",
        "zone",
        12.9716,
        77.5946
    ),

    "Z2": (
        "Lakeview Nagar",
        "zone",
        12.9900,
        77.6200
    ),

    "Z3": (
        "Old Market",
        "zone",
        12.9500,
        77.5700
    ),

    "Z4": (
        "East Basti",
        "zone",
        12.9600,
        77.6500
    ),

    "S1": (
        "Govt School Shelter",
        "shelter",
        12.9800,
        77.5800
    ),

    "S2": (
        "Community Hall",
        "shelter",
        12.9650,
        77.6150
    ),

    "S3": (
        "Stadium Shelter",
        "shelter",
        12.9400,
        77.6000
    ),

    "H1": (
        "District Hospital",
        "hospital",
        12.9750,
        77.6050
    ),

    "D1": (
        "Relief Depot",
        "depot",
        12.9550,
        77.5900
    )
}


# ============================================================
# 2. ROAD NETWORK
# ============================================================

EDGES = [

    ("R1", "Z1", "S1"),
    ("R2", "Z1", "H1"),
    ("R3", "Z1", "D1"),

    ("R4", "Z2", "S1"),
    ("R5", "Z2", "H1"),
    ("R6", "Z2", "S2"),

    ("R7", "Z3", "D1"),
    ("R8", "Z3", "S3"),
    ("R9", "Z3", "Z1"),

    ("R10", "Z4", "S2"),
    ("R11", "Z4", "H1"),
    ("R12", "Z4", "S3"),

    ("R13", "D1", "S3"),
    ("R14", "D1", "H1"),

    ("R15", "S1", "H1")
]


# ============================================================
# 3. ZONE PARAMETERS
# ============================================================

ZONE_SHARE = {
    "Z1": 0.30,
    "Z2": 0.25,
    "Z3": 0.25,
    "Z4": 0.20
}


ZONE_DAMAGE = {
    "Z1": 1.3,
    "Z2": 1.0,
    "Z3": 0.8,
    "Z4": 1.0
}


SEVERITY = {
    "flood": 1.0,
    "earthquake": 1.25,
    "cyclone": 0.9,
    "landslide": 1.1
}


# ============================================================
# 4. DISTANCE CALCULATION
# ============================================================

def _km(a, b):
    """
    Calculate approximate distance between two network nodes
    using the Haversine formula.
    """

    lat1 = NODES[a][2]
    lon1 = NODES[a][3]

    lat2 = NODES[b][2]
    lon2 = NODES[b][3]

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        (lat1, lon1, lat2, lon2)
    )

    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin((lon2 - lon1) / 2) ** 2
    )

    return 12742 * math.asin(math.sqrt(h))


# ============================================================
# 5. GRAPH INFORMATION FOR FRONTEND
# ============================================================

def graph_info():
    """
    Return network information required by Leaflet frontend.
    """

    return {
        "nodes": {
            node_id: {
                "name": values[0],
                "type": values[1],
                "lat": values[2],
                "lng": values[3]
            }
            for node_id, values in NODES.items()
        },

        "edges": [
            {
                "id": road_id,
                "a": a,
                "b": b
            }
            for road_id, a, b in EDGES
        ]
    }


# ============================================================
# 6. BUILD ADAPTIVE GRAPH
# ============================================================

def build_graph(
    blocked,
    disaster="flood",
    damage=0
):
    """
    Build the active disaster-aware road network.

    Blocked roads are removed.

    Open roads receive risk-aware adaptive costs.
    """

    G = nx.Graph()

    G.add_nodes_from(NODES)

    blocked = set(blocked or [])

    damage_ratio = min(
        1.0,
        max(
            0.0,
            float(damage) / 100.0
        )
    )

    for road_id, a, b in EDGES:

        distance = _km(a, b)

        road_risk = min(
            1.0,
            damage_ratio
            +
            (
                0.25
                if road_id in blocked
                else 0
            )
        )

        blocked_penalty = (
            1
            if road_id in blocked
            else 0
        )

        # Blocked roads are excluded.
        if road_id in blocked:
            continue

        adaptive_weight = edge_cost(
            distance,
            road_risk,
            damage_ratio,
            blocked_penalty,
            disaster
        )

        G.add_edge(
            a,
            b,
            id=road_id,
            weight=adaptive_weight,
            distance=distance,
            risk=road_risk
        )

    return G


# ============================================================
# 7. RISK-AWARE DIJKSTRA PATH
# ============================================================

def _path(G, a, b):
    """
    Find shortest risk-aware path.

    Returns:
        (path, distance)

    If no route exists:
        (None, None)
    """

    try:

        path = nx.dijkstra_path(
            G,
            a,
            b,
            weight="weight"
        )

        distance = nx.dijkstra_path_length(
            G,
            a,
            b,
            weight="weight"
        )

        return path, distance

    except (
        nx.NetworkXNoPath,
        nx.NodeNotFound
    ):

        return None, None


# ============================================================
# 8. LOCAL ZONE RISK
# ============================================================

def _calculate_local_zone_risk(
    overall_risk,
    damage,
    population,
    blocked_count,
    zone_id
):
    """
    Calculate local risk for an individual zone.

    Factors:
    - overall disaster risk
    - infrastructure damage
    - zone damage multiplier
    - population exposure
    - blocked roads
    """

    zone_damage_multiplier = ZONE_DAMAGE.get(
        zone_id,
        1.0
    )

    total_roads = max(
        1,
        len(EDGES)
    )

    blockage_ratio = (
        blocked_count / total_roads
    )

    population_factor = (
        min(
            1.0,
            population / 20000
        )
        * 100
    )

    local_risk = (
        0.60 * float(overall_risk)
        +
        0.20 * (
            float(damage)
            * zone_damage_multiplier
        )
        +
        0.10 * population_factor
        +
        0.10 * (
            blockage_ratio * 100
        )
    )

    return max(
        0.0,
        min(
            100.0,
            round(local_risk, 2)
        )
    )


# ============================================================
# 9. POINT TO ROAD DISTANCE
# ============================================================

def _point_to_road_distance_km(
    point_lat,
    point_lon,
    start_lat,
    start_lon,
    end_lat,
    end_lon
):
    """
    Approximate shortest distance from a point
    to a road segment in kilometres.
    """

    mean_lat = math.radians(
        (
            float(start_lat)
            +
            float(end_lat)
        ) / 2.0
    )

    lat_scale = 111.32

    lon_scale = (
        111.32
        *
        math.cos(mean_lat)
    )

    px = float(point_lon) * lon_scale
    py = float(point_lat) * lat_scale

    ax = float(start_lon) * lon_scale
    ay = float(start_lat) * lat_scale

    bx = float(end_lon) * lon_scale
    by = float(end_lat) * lat_scale

    dx = bx - ax
    dy = by - ay

    length_sq = (
        dx * dx
        +
        dy * dy
    )

    if length_sq == 0:

        return math.sqrt(
            (px - ax) ** 2
            +
            (py - ay) ** 2
        )

    ratio = (
        (
            (px - ax) * dx
            +
            (py - ay) * dy
        )
        /
        length_sq
    )

    ratio = max(
        0.0,
        min(
            1.0,
            ratio
        )
    )

    closest_x = ax + ratio * dx
    closest_y = ay + ratio * dy

    return math.sqrt(
        (px - closest_x) ** 2
        +
        (py - closest_y) ** 2
    )


# ============================================================
# 10. AUTOMATIC ROAD HAZARD DETECTION
# ============================================================

def detect_road_status_from_location(
    latitude,
    longitude,
    blocked_radius_km=0.35,
    orange_radius_km=0.75,
    yellow_radius_km=1.25
):
    """
    Classify roads around a disaster location as:

        blocked
        orange
        yellow
        safe
    """

    latitude = float(latitude)
    longitude = float(longitude)

    blocked = []
    orange = []
    yellow = []
    safe = []

    road_details = []

    for road_id, node_a, node_b in EDGES:

        distance_km = _point_to_road_distance_km(
            latitude,
            longitude,
            NODES[node_a][2],
            NODES[node_a][3],
            NODES[node_b][2],
            NODES[node_b][3]
        )

        if distance_km <= blocked_radius_km:

            status = "blocked"
            blocked.append(road_id)

        elif distance_km <= orange_radius_km:

            status = "orange"
            orange.append(road_id)

        elif distance_km <= yellow_radius_km:

            status = "yellow"
            yellow.append(road_id)

        else:

            status = "safe"
            safe.append(road_id)

        road_details.append({
            "id": road_id,
            "from": node_a,
            "to": node_b,
            "distance_km": round(
                distance_km,
                3
            ),
            "status": status
        })

    return {
        "enabled": True,
        "source": "coordinate_based_hazard_detection",

        "latitude": latitude,
        "longitude": longitude,

        "blocked_radius_km":
            blocked_radius_km,

        "orange_radius_km":
            orange_radius_km,

        "yellow_radius_km":
            yellow_radius_km,

        "blocked":
            sorted(blocked),

        "orange":
            sorted(orange),

        "yellow":
            sorted(yellow),

        "safe":
            sorted(safe),

        "road_details":
            road_details,

        "blocked_count":
            len(blocked),

        "orange_count":
            len(orange),

        "yellow_count":
            len(yellow),

        "safe_count":
            len(safe)
    }


# ============================================================
# 11. APPLY AUTOMATIC ROAD DETECTION
# ============================================================

def apply_automatic_road_detection(seed):
    """
    Automatically derive road status from disaster coordinates.

    If coordinates are unavailable, manually supplied
    road information is preserved.
    """

    seed = dict(seed or {})

    latitude = seed.get("latitude")
    longitude = seed.get("longitude")

    manual_blocked = set(
        seed.get("blocked", []) or []
    )

    manual_orange = set(
        seed.get("orange_roads", []) or []
    )

    manual_yellow = set(
        seed.get("yellow_roads", []) or []
    )

    # --------------------------------------------------------
    # No coordinates -> manual fallback
    # --------------------------------------------------------

    if latitude is None or longitude is None:

        seed["blocked"] = sorted(
            manual_blocked
        )

        seed["orange_roads"] = sorted(
            manual_orange
        )

        seed["yellow_roads"] = sorted(
            manual_yellow
        )

        seed["road_detection"] = {
            "enabled": False,
            "source": "manual_fallback",
            "blocked": sorted(manual_blocked),
            "orange": sorted(manual_orange),
            "yellow": sorted(manual_yellow),
            "safe": [],
            "road_details": []
        }

        return seed

    # --------------------------------------------------------
    # Coordinate-based detection
    # --------------------------------------------------------

    try:

        detection = detect_road_status_from_location(
            latitude,
            longitude
        )

    except (
        TypeError,
        ValueError
    ):

        seed["blocked"] = sorted(
            manual_blocked
        )

        seed["orange_roads"] = sorted(
            manual_orange
        )

        seed["yellow_roads"] = sorted(
            manual_yellow
        )

        seed["road_detection"] = {
            "enabled": False,
            "source":
                "invalid_coordinates_manual_fallback",
            "blocked":
                sorted(manual_blocked),
            "orange":
                sorted(manual_orange),
            "yellow":
                sorted(manual_yellow),
            "safe": [],
            "road_details": []
        }

        return seed

    # --------------------------------------------------------
    # Combine automatic + manually blocked roads
    # --------------------------------------------------------

    detected_blocked = set(
        detection["blocked"]
    )

    detected_orange = set(
        detection["orange"]
    )

    detected_yellow = set(
        detection["yellow"]
    )

    combined_blocked = (
        manual_blocked
        |
        detected_blocked
    )

    combined_orange = (
        manual_orange
        |
        detected_orange
    )

    combined_yellow = (
        manual_yellow
        |
        detected_yellow
    )

    # A blocked road should not remain orange/yellow.
    combined_orange -= combined_blocked
    combined_yellow -= combined_blocked

    seed["blocked"] = sorted(
        combined_blocked
    )

    seed["orange_roads"] = sorted(
        combined_orange
    )

    seed["yellow_roads"] = sorted(
        combined_yellow
    )

    detection["blocked"] = sorted(
        combined_blocked
    )

    detection["orange"] = sorted(
        combined_orange
    )

    detection["yellow"] = sorted(
        combined_yellow
    )

    detection["blocked_count"] = len(
        combined_blocked
    )

    detection["orange_count"] = len(
        combined_orange
    )

    detection["yellow_count"] = len(
        combined_yellow
    )

    seed["road_detection"] = detection

    return seed


# ============================================================
# 12. INCIDENT COMMANDER BRIEFING
# ============================================================

def generate_commander_briefing(plan):
    """
    Generate concise operational directives
    for the disaster-response commander.
    """

    directives = []

    # --------------------------------------------------------
    # Medical isolation
    # --------------------------------------------------------

    isolated = [
        zone["name"]
        for zone in plan.get("zones", [])
        if not zone.get(
            "hospital_access",
            False
        )
    ]

    if isolated:

        directives.append(
            "MEDICAL ISOLATION: "
            f"Civilians in {', '.join(isolated)} "
            "are cut off from District Hospital H1. "
            "Dispatch emergency road-clearing teams."
        )

    # --------------------------------------------------------
    # Shelter shortage
    # --------------------------------------------------------

    stranded = [
        zone
        for zone in plan.get("zones", [])
        if zone.get(
            "unsheltered",
            0
        ) > 0
    ]

    if stranded:

        stranded_names = [
            f"{zone['name']} "
            f"({zone['unsheltered']:,} stranded)"
            for zone in stranded
        ]

        total_stranded = sum(
            zone["unsheltered"]
            for zone in stranded
        )

        directives.append(
            "SHELTER DEFICIT: "
            f"{total_stranded:,} people "
            "without shelter in "
            f"{', '.join(stranded_names)}. "
            "Establish secondary shelter or tent camps."
        )

    # --------------------------------------------------------
    # Resource shortage
    # --------------------------------------------------------

    shortages = [
        f"{key.upper()} "
        f"(short {value:,.0f})"
        for key, value
        in plan.get(
            "shortage",
            {}
        ).items()
        if value > 0
    ]

    if shortages:

        directives.append(
            "AID DISPATCH: "
            "Acute deficit in "
            f"{', '.join(shortages)}. "
            "Dispatch convoys from Relief Depot D1."
        )

    else:

        directives.append(
            "AID STATUS: "
            "Food, water, and medical resources "
            "meet active humanitarian demand."
        )

    # --------------------------------------------------------
    # Road accessibility
    # --------------------------------------------------------

    blocked_count = len(
        plan.get(
            "blocked_roads",
            []
        )
    )

    if blocked_count > 0:

        directives.append(
            "ROUTE ALERT: "
            f"{blocked_count} road segment(s) "
            "are blocked. "
            "Use adaptive routing and prioritize "
            "critical access corridors."
        )

    # --------------------------------------------------------
    # High risk
    # --------------------------------------------------------

    risk = float(
        plan.get(
            "risk",
            0
        )
    )

    if risk >= 75:

        directives.append(
            "CRITICAL RISK: "
            "Immediate multi-agency intervention "
            "is recommended."
        )

    elif risk >= 55:

        directives.append(
            "HIGH RISK: "
            "Prioritize evacuation, sheltering, "
            "medical access and resource delivery."
        )

    else:

        directives.append(
            "RISK STATUS: "
            "Continue monitoring and adapt the plan "
            "as the disaster seed changes."
        )

    return directives


# ============================================================
# 13. MAIN RECOVERY PLAN
# ============================================================

def generate_plan(
    seed,
    ml_prediction=None
):
    """
    Convert disaster seed into a complete adaptive
    recovery plan.
    """

    # --------------------------------------------------------
    # Automatic road hazard detection
    # --------------------------------------------------------

    seed = apply_automatic_road_detection(
        seed
    )

    # --------------------------------------------------------
    # Input values
    # --------------------------------------------------------

    pop = max(
        1,
        int(
            seed.get(
                "population",
                10000
            )
        )
    )

    damage = min(
        100,
        max(
            0,
            float(
                seed.get(
                    "damage",
                    40
                )
            )
        )
    )

    disaster = seed.get(
        "disaster",
        "flood"
    )

    blocked = set(
        seed.get(
            "blocked",
            []
        )
    )

    severity = SEVERITY.get(
        disaster,
        1.0
    )

    # --------------------------------------------------------
    # Build adaptive network
    # --------------------------------------------------------

    G = build_graph(
        blocked,
        disaster,
        damage
    )

    # --------------------------------------------------------
    # Population displacement
    # --------------------------------------------------------

    displaced = int(
        min(
            pop,
            pop
            *
            (
                0.15
                +
                0.85
                *
                damage
                / 100
            )
            *
            severity
        )
    )

    # --------------------------------------------------------
    # Humanitarian demand
    # --------------------------------------------------------

    demand = {

        "water":
            displaced * 15,

        "food":
            round(
                displaced * 0.5
            ),

        "medical":
            max(
                1,
                round(
                    pop
                    *
                    damage
                    / 100
                    *
                    0.04
                    *
                    severity
                )
            )
    }

    # --------------------------------------------------------
    # ML prediction blending
    # --------------------------------------------------------

    if ml_prediction:

        predicted_displaced = float(
            ml_prediction.get(
                "displaced",
                displaced
            )
        )

        predicted_medical = float(
            ml_prediction.get(
                "medical_demand",
                demand["medical"]
            )
        )

        displaced = round(
            0.55 * displaced
            +
            0.45 * predicted_displaced
        )

        displaced = min(
            displaced,
            pop
        )

        demand["water"] = (
            displaced * 15
        )

        demand["food"] = round(
            displaced * 0.5
        )

        demand["medical"] = round(
            0.55 * demand["medical"]
            +
            0.45 * predicted_medical
        )

    # --------------------------------------------------------
    # Available resources
    # --------------------------------------------------------

    supply = {

        "water": float(
            seed.get(
                "water",
                0
            )
        ),

        "food": float(
            seed.get(
                "food",
                0
            )
        ),

        "medical": float(
            seed.get(
                "medical",
                0
            )
        )
    }

    # --------------------------------------------------------
    # Resource coverage
    # --------------------------------------------------------

    cover = {

        key: min(
            1.0,
            supply[key]
            /
            max(
                1,
                demand[key]
            )
        )

        for key in demand
    }

    # --------------------------------------------------------
    # Resource shortage
    # --------------------------------------------------------

    shortage = {

        key: max(
            0,
            demand[key]
            -
            supply[key]
        )

        for key in demand
    }

    # --------------------------------------------------------
    # Overall risk breakdown
    # --------------------------------------------------------

    parts = {

        "Population exposed":
            min(
                25,
                pop / 20000 * 25
            ),

        "Infrastructure damage":
            damage / 100 * 35,

        "Blocked roads":
            min(
                20,
                len(blocked)
                /
                max(
                    1,
                    len(EDGES)
                )
                *
                40
            ),

        "Resource shortage":
            20
            *
            (
                1
                -
                sum(
                    cover.values()
                )
                / 3
            )
    }

    parts = {

        key: round(
            value
            *
            (
                0.8
                +
                0.2 * severity
            ),
            1
        )

        for key, value in parts.items()
    }

    # --------------------------------------------------------
    # Overall risk
    # --------------------------------------------------------

    risk = min(
        100,
        round(
            sum(
                parts.values()
            )
        )
    )

    # --------------------------------------------------------
    # Blend ML risk
    # --------------------------------------------------------

    if ml_prediction:

        predicted_risk = float(
            ml_prediction.get(
                "risk",
                risk
            )
        )

        risk = round(
            0.65 * risk
            +
            0.35 * predicted_risk,
            1
        )

    # --------------------------------------------------------
    # Overall hazard zone
    # --------------------------------------------------------

    hazard_zone = classify_zone(
        risk
    )

    overall_zone = hazard_zone[
        "zone"
    ]

    overall_zone_color = hazard_zone[
        "color"
    ]

    overall_zone_severity = hazard_zone[
        "severity"
    ]

    overall_zone_priority = hazard_zone[
        "priority"
    ]

    # --------------------------------------------------------
    # Risk level
    # --------------------------------------------------------

    if risk >= 75:

        risk_level = "CRITICAL"

    elif risk >= 55:

        risk_level = "HIGH"

    elif risk >= 35:

        risk_level = "MEDIUM"

    else:

        risk_level = "LOW"

    # --------------------------------------------------------
    # Zone shelter demand
    # --------------------------------------------------------

    raw_need = {

        zone:
            ZONE_SHARE[zone]
            *
            ZONE_DAMAGE[zone]

        for zone in ZONE_SHARE
    }

    total_weight = sum(
        raw_need.values()
    )

    need = {

        zone:
            round(
                displaced
                *
                raw_need[zone]
                /
                max(
                    0.0001,
                    total_weight
                )
            )

        for zone in raw_need
    }

    # --------------------------------------------------------
    # Shelter capacity
    # --------------------------------------------------------

    shelter_capacity = int(
        seed.get(
            "shelter_capacity",
            4000
        )
    )

    caps = {

        "S1":
            shelter_capacity * 0.35,

        "S2":
            shelter_capacity * 0.30,

        "S3":
            shelter_capacity * 0.35
    }

    shelter_data = {

        shelter: {
            "capacity": capacity
        }

        for shelter, capacity
        in caps.items()
    }

    # --------------------------------------------------------
    # Shelter candidates
    # --------------------------------------------------------

    def candidates(zone):

        result = []

        for shelter in caps:

            path, distance = _path(
                G,
                zone,
                shelter
            )

            if not path:
                continue

            hospital_path, _ = _path(
                G,
                shelter,
                "H1"
            )

            result.append({

                "zone":
                    zone,

                "shelter":
                    shelter,

                "km":
                    round(
                        distance,
                        2
                    ),

                "path":
                    path,

                "need_score":
                    min(
                        1,
                        need[zone]
                        /
                        max(
                            1,
                            displaced
                            /
                            max(
                                1,
                                len(need)
                            )
                        )
                    ),

                "safety":
                    max(
                        0,
                        1 - damage / 100
                    ),

                "medical_access":
                    1.0
                    if hospital_path
                    else 0.25
            })

        return sorted(
            result,
            key=lambda item:
                item["km"]
        )

    # --------------------------------------------------------
    # Fair shelter allocation
    # --------------------------------------------------------

    assignments, remaining = fair_allocate(
        need,
        shelter_data,
        candidates
    )

    # --------------------------------------------------------
    # Zone analysis
    # --------------------------------------------------------

    zones = []

    supply_routes = []

    hospital_access = {}

    for zone in sorted(
        need,
        key=lambda z:
            -need[z]
    ):

        # ----------------------------------------------------
        # Depot -> Zone
        # ----------------------------------------------------

        supply_path, supply_distance = _path(
            G,
            "D1",
            zone
        )

        # ----------------------------------------------------
        # Zone -> Hospital
        # ----------------------------------------------------

        hospital_path, _ = _path(
            G,
            zone,
            "H1"
        )

        hospital_reachable = (
            hospital_path is not None
        )

        hospital_access[zone] = (
            hospital_reachable
        )

        # ----------------------------------------------------
        # Allocated population
        # ----------------------------------------------------

        allocated = sum(
            assignment["people"]
            for assignment in assignments
            if assignment["zone"] == zone
        )

        unsheltered = max(
            0,
            need[zone]
            -
            allocated
        )

        # ----------------------------------------------------
        # Local risk
        # ----------------------------------------------------

        local_risk = _calculate_local_zone_risk(
            overall_risk=risk,
            damage=damage,
            population=pop,
            blocked_count=len(blocked),
            zone_id=zone
        )

        # ----------------------------------------------------
        # Local hazard classification
        # ----------------------------------------------------

        local_zone = classify_zone(
            local_risk
        )

        # ----------------------------------------------------
        # Supply route
        # ----------------------------------------------------

        if supply_path:

            supply_routes.append({

                "zone":
                    zone,

                "path":
                    supply_path,

                "km":
                    round(
                        supply_distance,
                        2
                    )
            })

        # ----------------------------------------------------
        # Complete zone object
        # ----------------------------------------------------

        zones.append({

            "id":
                zone,

            "name":
                NODES[zone][0],

            "latitude":
                NODES[zone][2],

            "longitude":
                NODES[zone][3],

            # Population / shelter
            "need":
                need[zone],

            "sheltered":
                allocated,

            "unsheltered":
                unsheltered,

            # Connectivity
            "reachable":
                bool(
                    candidates(zone)
                ),

            "hospital_access":
                hospital_reachable,

            # Local hazard information
            "risk":
                local_risk,

            "hazard_zone":
                local_zone["zone"],

            "severity":
                local_zone["severity"],

            "zone_priority":
                local_zone["priority"],

            "zone_color":
                local_zone["color"],

            # Zone response
            "evacuation":
                local_zone["evacuation"],

            "resource_priority":
                local_zone[
                    "resource_priority"
                ],

            "medical_priority":
                local_zone[
                    "medical_priority"
                ],

            "route_priority":
                local_zone[
                    "route_priority"
                ],

            "recommended_action":
                local_zone[
                    "recommended_action"
                ]
        })

    # ========================================================
    # RECOVERY METRICS
    # ========================================================

    sheltered = sum(
        assignment["people"]
        for assignment in assignments
    )

    total_unsheltered = sum(
        zone["unsheltered"]
        for zone in zones
    )

    shelter_coverage = (
        sheltered
        /
        max(
            1,
            displaced
        )
    )

    shelter_coverage = min(
        1.0,
        shelter_coverage
    )

    access_score = (
        sum(
            1
            for zone in zones
            if zone["reachable"]
        )
        /
        max(
            1,
            len(zones)
        )
    )

    resource_coverage = (
        sum(
            cover.values()
        )
        /
        3
    )

    # ========================================================
    # FAIRNESS
    # ========================================================

    allocated_values = [
        assignment["people"]
        for assignment in assignments
    ]

    if allocated_values:

        fairness = (
            1
            -
            (
                max(allocated_values)
                -
                min(allocated_values)
            )
            /
            max(
                1,
                sheltered
            )
        )

    else:

        fairness = 1.0

    fairness = max(
        0.0,
        min(
            1.0,
            fairness
        )
    )

    # ========================================================
    # RECOVERY SCORE
    # ========================================================

    recovery_score = round(
        100
        *
        (
            0.30 * shelter_coverage
            +
            0.20 * access_score
            +
            0.25 * resource_coverage
            +
            0.10 * fairness
            +
            0.15 *
            (
                1
                -
                risk / 100
            )
        )
    )

    # ========================================================
    # RECOVERY PRIORITIES
    # ========================================================

    gaps = {

        "Medical support":
            1 - cover["medical"],

        "Shelter allocation":
            1 - shelter_coverage,

        "Water distribution":
            1 - cover["water"],

        "Food distribution":
            1 - cover["food"],

        "Route restoration":
            (
                1
                -
                access_score
                +
                len(blocked) * 0.03
            )
    }

    priorities = [

        {
            "name":
                key,

            "gap":
                round(
                    value * 100
                )
        }

        for key, value
        in sorted(
            gaps.items(),
            key=lambda item:
                -item[1]
        )
    ]

    # ========================================================
    # ACCESSIBILITY
    # ========================================================

    accessibility = round(
        access_score,
        4
    )

    # ========================================================
    # FINAL PLAN
    # ========================================================

    plan = {

        # ----------------------------------------------------
        # Risk
        # ----------------------------------------------------

        "risk":
            risk,

        "risk_level":
            risk_level,

        "risk_breakdown":
            parts,

        # ----------------------------------------------------
        # Overall hazard zone
        # ----------------------------------------------------

        "hazard_zone":
            overall_zone,

        "zone":
            overall_zone,

        "zone_color":
            overall_zone_color,

        "zone_severity":
            overall_zone_severity,

        "zone_priority":
            overall_zone_priority,

        # ----------------------------------------------------
        # Population
        # ----------------------------------------------------

        "displaced":
            displaced,

        # ----------------------------------------------------
        # Humanitarian resources
        # ----------------------------------------------------

        "demand":
            demand,

        "supply":
            supply,

        "shortage":
            shortage,

        # ----------------------------------------------------
        # Zone analysis
        # ----------------------------------------------------

        "zones":
            zones,

        # ----------------------------------------------------
        # Shelter allocation
        # ----------------------------------------------------

        "assignments":
            assignments,

        "remaining":
            remaining,

        # ----------------------------------------------------
        # Supply routing
        # ----------------------------------------------------

        "supply_routes":
            supply_routes,

        # ----------------------------------------------------
        # Road information
        # ----------------------------------------------------

        "accessible_roads":
            len(EDGES)
            -
            len(blocked),

        "blocked_roads":
            sorted(blocked),

        "orange_roads":
            sorted(
                seed.get(
                    "orange_roads",
                    []
                )
            ),

        "yellow_roads":
            sorted(
                seed.get(
                    "yellow_roads",
                    []
                )
            ),

        # ----------------------------------------------------
        # Shelter metrics
        # ----------------------------------------------------

        "sheltered":
            sheltered,

        "unsheltered":
            total_unsheltered,

        # ----------------------------------------------------
        # Priorities
        # ----------------------------------------------------

        "priorities":
            priorities,

        # ----------------------------------------------------
        # Recovery
        # ----------------------------------------------------

        "recovery_score":
            recovery_score,

        "fairness_score":
            round(
                fairness * 100,
                1
            ),

        # ----------------------------------------------------
        # Access
        # ----------------------------------------------------

        "access": {

            "accessibility_score":
                accessibility,

            "hospital_access":
                hospital_access
        },

        # ----------------------------------------------------
        # Routing
        # ----------------------------------------------------

        "routing_mode":
            "risk-aware adaptive Dijkstra"
    }

    # ========================================================
    # ROAD DETECTION INFORMATION
    # ========================================================

    plan["road_detection"] = seed.get(
        "road_detection",
        {
            "enabled": False,
            "source":
                "manual_fallback",

            "blocked":
                sorted(blocked),

            "orange": [],

            "yellow": [],

            "safe": [],

            "road_details": []
        }
    )

    # ========================================================
    # HAZARD-ZONE RESPONSE
    # ========================================================

    plan = apply_zone_response(
        plan,
        overall_zone
    )

    # ========================================================
    # INCIDENT COMMANDER BRIEFING
    # ========================================================

    plan["briefing"] = (
        generate_commander_briefing(
            plan
        )
    )

    # ========================================================
    # ML INFORMATION
    # ========================================================

    if ml_prediction:

        predicted_risk_value = float(
            ml_prediction.get(
                "risk",
                risk
            )
        )

        if predicted_risk_value >= 75:

            predicted_risk_level = (
                "CRITICAL"
            )

        elif predicted_risk_value >= 55:

            predicted_risk_level = (
                "HIGH"
            )

        elif predicted_risk_value >= 35:

            predicted_risk_level = (
                "MEDIUM"
            )

        else:

            predicted_risk_level = (
                "LOW"
            )

        plan["ml"] = {

            "risk":
                round(
                    predicted_risk_value,
                    1
                ),

            "risk_level":
                predicted_risk_level,

            "displaced":
                round(
                    float(
                        ml_prediction.get(
                            "displaced",
                            displaced
                        )
                    )
                ),

            "medical_demand":
                round(
                    float(
                        ml_prediction.get(
                            "medical_demand",
                            demand["medical"]
                        )
                    )
                )
        }

    return plan


# ============================================================
# 14. CRITICAL ROAD BOTTLENECK ANALYSIS
# ============================================================

def find_critical_bottlenecks(seed):
    """
    Determine which currently open roads are most critical.

    Each road is temporarily blocked and the recovery plan
    is recalculated.

    Roads are ranked according to:

        - Risk increase
        - Loss of sheltered population

    Returns:
        Top 3 vulnerable roads.
    """

    base_plan = generate_plan(
        seed
    )

    current_blocked = set(
        seed.get(
            "blocked",
            []
        )
    )

    available_roads = [

        road_id

        for road_id, _, _
        in EDGES

        if road_id
        not in current_blocked
    ]

    bottlenecks = []

    for road_id in available_roads:

        simulated_seed = dict(
            seed
        )

        simulated_seed["blocked"] = list(
            current_blocked
            |
            {road_id}
        )

        simulated_plan = generate_plan(
            simulated_seed
        )

        # ----------------------------------------------------
        # Risk increase
        # ----------------------------------------------------

        risk_spike = (
            simulated_plan["risk"]
            -
            base_plan["risk"]
        )

        # ----------------------------------------------------
        # Shelter loss
        # ----------------------------------------------------

        sheltered_loss = (
            base_plan["sheltered"]
            -
            simulated_plan["sheltered"]
        )

        # ----------------------------------------------------
        # Road endpoints
        # ----------------------------------------------------

        edge = next(
            edge
            for edge in EDGES
            if edge[0] == road_id
        )

        from_name = NODES[
            edge[1]
        ][0]

        to_name = NODES[
            edge[2]
        ][0]

        # ----------------------------------------------------
        # Vulnerability score
        # ----------------------------------------------------

        vulnerability_score = (
            risk_spike * 2
            +
            (
                sheltered_loss
                /
                max(
                    1,
                    base_plan["displaced"]
                )
                *
                100
            )
        )

        bottlenecks.append({

            "road_id":
                road_id,

            "name":
                f"{from_name} ↔ {to_name}",

            "risk_spike":
                round(
                    risk_spike,
                    1
                ),

            "sheltered_loss":
                sheltered_loss,

            "vulnerability_score":
                round(
                    vulnerability_score,
                    1
                )
        })

    # Highest vulnerability first

    bottlenecks.sort(
        key=lambda item:
            -item["vulnerability_score"]
    )

    return bottlenecks[:3]