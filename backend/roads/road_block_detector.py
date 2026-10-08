"""
SeedRescue Automatic Road Block Detector

The detector takes a disaster/hazard latitude and longitude and
automatically determines which SeedRescue road segments are:

    RED    -> BLOCKED
    ORANGE -> AT RISK
    YELLOW -> WARNING / NEARBY

The current SeedRescue prototype contains a predefined road graph
with coordinates for every node. This module uses those coordinates
to automatically derive blocked roads.

Later this module can be extended to use:
    - OpenStreetMap road geometry
    - live traffic APIs
    - government road closure feeds
    - flood/landslide feeds
    - weather APIs
"""

import math


# ------------------------------------------------------------
# Distance calculation
# ------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Calculate great-circle distance between two coordinates.
    """

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# ------------------------------------------------------------
# Distance from point to road segment
# ------------------------------------------------------------

def point_to_segment_distance_km(
    point_lat,
    point_lon,
    start_lat,
    start_lon,
    end_lat,
    end_lon
):
    """
    Approximate the minimum distance from a latitude/longitude
    point to a road segment.

    For the current SeedRescue city-scale graph, converting
    latitude/longitude into a local Cartesian coordinate system
    is sufficiently accurate.
    """

    lat_scale = 111.32

    mean_lat = math.radians(
        (float(start_lat) + float(end_lat) + float(point_lat)) / 3
    )

    lon_scale = 111.32 * math.cos(mean_lat)

    px = float(point_lon) * lon_scale
    py = float(point_lat) * lat_scale

    ax = float(start_lon) * lon_scale
    ay = float(start_lat) * lat_scale

    bx = float(end_lon) * lon_scale
    by = float(end_lat) * lat_scale

    dx = bx - ax
    dy = by - ay

    length_sq = dx * dx + dy * dy

    if length_sq == 0:
        return haversine_km(
            point_lat,
            point_lon,
            start_lat,
            start_lon
        )

    t = ((px - ax) * dx + (py - ay) * dy) / length_sq

    t = max(0.0, min(1.0, t))

    closest_x = ax + t * dx
    closest_y = ay + t * dy

    distance_km = math.sqrt(
        (px - closest_x) ** 2
        + (py - closest_y) ** 2
    )

    return distance_km


# ------------------------------------------------------------
# Main automatic road detector
# ------------------------------------------------------------

def detect_blocked_roads(
    latitude,
    longitude,
    nodes,
    edges,
    blocked_radius_km=0.35,
    orange_radius_km=0.75,
    yellow_radius_km=1.25
):
    """
    Automatically detect road status from a disaster location.

    Parameters
    ----------
    latitude : float
        Disaster latitude.

    longitude : float
        Disaster longitude.

    nodes : dict
        SeedRescue graph nodes.

    edges : list
        SeedRescue graph edges.

    blocked_radius_km : float
        Roads inside this radius are BLOCKED.

    orange_radius_km : float
        Roads between blocked_radius and this radius are AT RISK.

    yellow_radius_km : float
        Roads between orange_radius and this radius are WARNING.

    Returns
    -------
    dict
        Automatic road detection result.
    """

    latitude = float(latitude)
    longitude = float(longitude)

    blocked = []
    orange = []
    yellow = []
    road_details = []

    for road_id, node_a, node_b in edges:

        if node_a not in nodes or node_b not in nodes:
            continue

        a = nodes[node_a]
        b = nodes[node_b]

        distance = point_to_segment_distance_km(
            latitude,
            longitude,
            a[2],
            a[3],
            b[2],
            b[3]
        )

        distance = round(distance, 4)

        if distance <= blocked_radius_km:
            status = "blocked"
            blocked.append(road_id)

        elif distance <= orange_radius_km:
            status = "orange"
            orange.append(road_id)

        elif distance <= yellow_radius_km:
            status = "yellow"
            yellow.append(road_id)

        else:
            status = "safe"

        road_details.append({
            "id": road_id,
            "from": node_a,
            "to": node_b,
            "distance_km": distance,
            "status": status
        })

    road_details.sort(key=lambda x: x["distance_km"])

    return {
        "latitude": latitude,
        "longitude": longitude,
        "blocked_radius_km": blocked_radius_km,
        "orange_radius_km": orange_radius_km,
        "yellow_radius_km": yellow_radius_km,
        "blocked": sorted(blocked),
        "orange": sorted(orange),
        "yellow": sorted(yellow),
        "safe": [
            r["id"]
            for r in road_details
            if r["status"] == "safe"
        ],
        "road_details": road_details,
        "blocked_count": len(blocked),
        "orange_count": len(orange),
        "yellow_count": len(yellow),
        "safe_count": len([
            r for r in road_details
            if r["status"] == "safe"
        ])
    }


# ------------------------------------------------------------
# Helper used by /api/plan
# ------------------------------------------------------------

def automatic_blocked_from_location(
    seed,
    nodes,
    edges
):
    """
    Read latitude/longitude from the scenario.

    If coordinates are present, automatically detect blocked
    roads.

    If coordinates are not present, return the manually supplied
    blocked roads as a fallback.
    """

    latitude = seed.get("latitude")
    longitude = seed.get("longitude")

    if latitude is None or longitude is None:
        return {
            "enabled": False,
            "blocked": list(seed.get("blocked", [])),
            "orange": [],
            "yellow": [],
            "road_details": []
        }

    result = detect_blocked_roads(
        latitude=latitude,
        longitude=longitude,
        nodes=nodes,
        edges=edges,
        blocked_radius_km=float(
            seed.get("blocked_radius_km", 0.35)
        ),
        orange_radius_km=float(
            seed.get("orange_radius_km", 0.75)
        ),
        yellow_radius_km=float(
            seed.get("yellow_radius_km", 1.25)
        )
    )

    return {
        "enabled": True,
        **result
    }