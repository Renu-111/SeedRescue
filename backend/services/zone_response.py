"""
SeedRescue Zone Response Engine
"""

from typing import Dict, Any


VALID_ZONES = {
    "RED",
    "ORANGE",
    "YELLOW",
}


def normalize_zone(zone: Any) -> str:
    """
    Accept either:
        "ORANGE"

    or a classifier dictionary such as:
        {"zone": "ORANGE", ...}

    or older dictionaries such as:
        {"ZONE": "ORANGE", ...}

    Always return the normalized zone string.
    """

    # Already a string
    if isinstance(zone, str):
        value = zone.strip().upper()

    # Dictionary returned by a classifier
    elif isinstance(zone, dict):
        value = (
            zone.get("zone")
            or zone.get("ZONE")
            or zone.get("hazard_zone")
            or zone.get("HAZARD_ZONE")
            or ""
        )

        value = str(value).strip().upper()

    else:
        value = str(zone).strip().upper()

    if value not in VALID_ZONES:
        raise ValueError(
            f"Invalid hazard zone: {value}. "
            f"Expected RED, ORANGE, or YELLOW."
        )

    return value


def get_zone_response(zone: Any) -> Dict:
    """
    Return operational response rules for a hazard zone.

    Accepts both a zone string and the dictionary returned
    by classify_zone().
    """

    zone = normalize_zone(zone)

    # --------------------------------------------------------
    # RED ZONE
    # --------------------------------------------------------
    if zone == "RED":
        return {
            "evacuation": {
                "priority": "IMMEDIATE",
                "required": True
            },

            "resources": {
                "priority": "MAXIMUM",
                "water": "CRITICAL",
                "food": "HIGH",
                "medical": "CRITICAL"
            },

            "shelter": {
                "priority": "IMMEDIATE",
                "required": True
            },

            "routing": {
                "priority": "SAFEST",
                "avoid_high_risk_roads": True
            },

            "monitoring": {
                "level": "CONTINUOUS"
            }
        }

    # --------------------------------------------------------
    # ORANGE ZONE
    # --------------------------------------------------------
    elif zone == "ORANGE":
        return {
            "evacuation": {
                "priority": "HIGH",
                "required": True
            },

            "resources": {
                "priority": "HIGH",
                "water": "HIGH",
                "food": "HIGH",
                "medical": "HIGH"
            },

            "shelter": {
                "priority": "HIGH",
                "required": True
            },

            "routing": {
                "priority": "SAFE",
                "avoid_high_risk_roads": True
            },

            "monitoring": {
                "level": "FREQUENT"
            }
        }

    # --------------------------------------------------------
    # YELLOW ZONE
    # --------------------------------------------------------
    elif zone == "YELLOW":
        return {
            "evacuation": {
                "priority": "MONITOR",
                "required": False
            },

            "resources": {
                "priority": "PREPARE",
                "water": "NORMAL",
                "food": "NORMAL",
                "medical": "NORMAL"
            },

            "shelter": {
                "priority": "MONITOR",
                "required": False
            },

            "routing": {
                "priority": "NORMAL",
                "avoid_high_risk_roads": False
            },

            "monitoring": {
                "level": "NORMAL"
            }
        }

    # This should never be reached because normalize_zone()
    # validates the zone.
    raise ValueError(
        f"Invalid hazard zone: {zone}. "
        f"Expected RED, ORANGE, or YELLOW."
    )


def apply_zone_response(plan: Dict, zone: Any) -> Dict:
    """
    Attach zone response to the recovery plan.

    `zone` may be:
        "ORANGE"
    or:
        {"zone": "ORANGE", ...}
    """

    normalized_zone = normalize_zone(zone)

    response = get_zone_response(normalized_zone)

    plan["zone_response"] = response

    return plan