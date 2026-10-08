"""
SeedRescue Hazard Zone Classifier

RED    : 70 - 100
ORANGE : 40 - 69.99
YELLOW : 0 - 39.99
"""

from typing import Dict

RED_THRESHOLD = 70.0
ORANGE_THRESHOLD = 40.0


def classify_zone(risk_score: float) -> Dict:
    try:
        risk = float(risk_score)
    except (TypeError, ValueError):
        risk = 0.0

    # Keep risk between 0 and 100
    risk = max(0.0, min(100.0, risk))

    # RED
    if risk >= RED_THRESHOLD:
        return {
            "zone": "RED",
            "color": "#FF0000",
            "severity": "CRITICAL",
            "risk_score": round(risk, 2),
            "priority": "IMMEDIATE",
            "evacuation": "IMMEDIATE",
            "resource_priority": "MAXIMUM",
            "medical_priority": "CRITICAL",
            "route_priority": "SAFEST",
            "recommended_action":
                "Immediate emergency response and evacuation recommended."
        }

    # ORANGE
    elif risk >= ORANGE_THRESHOLD:
        return {
            "zone": "ORANGE",
            "color": "#FFA500",
            "severity": "HIGH",
            "risk_score": round(risk, 2),
            "priority": "HIGH",
            "evacuation": "PREPARE",
            "resource_priority": "HIGH",
            "medical_priority": "HIGH",
            "route_priority": "SAFE",
            "recommended_action":
                "Prepare evacuation and deploy emergency resources."
        }

    # YELLOW
    else:
        return {
            "zone": "YELLOW",
            "color": "#FFD700",
            "severity": "MODERATE",
            "risk_score": round(risk, 2),
            "priority": "MONITOR",
            "evacuation": "MONITOR",
            "resource_priority": "PREPARE",
            "medical_priority": "NORMAL",
            "route_priority": "NORMAL",
            "recommended_action":
                "Monitor the situation and keep emergency resources prepared."
        }


def get_zone_color(zone: str) -> str:
    colors = {
        "RED": "#FF0000",
        "ORANGE": "#FFA500",
        "YELLOW": "#FFD700"
    }

    return colors.get(str(zone).upper(), "#808080")

def get_zone_description(zone: str) -> str:
    descriptions = {
        "RED": "Very high risk. Immediate emergency action required.",
        "ORANGE": "High risk. Prepare and deploy emergency resources.",
        "YELLOW": "Moderate risk. Monitor and prepare resources."
    }

    return descriptions.get(
        str(zone).upper(),
        "Unknown hazard zone."
    )