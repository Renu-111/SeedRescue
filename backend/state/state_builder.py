"""Build a normalized disaster state from a compact SeedRescue seed."""
from typing import Dict, Any, Optional


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(x)))


def build_state(seed: Dict[str, Any], plan: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    pop=max(1,int(seed.get("population",1)))
    damage=clamp(float(seed.get("damage",0))/100)
    blocked=int(len(seed.get("blocked",[])))
    edge_count=max(1,int(seed.get("edge_count",15)))
    water=max(0,float(seed.get("water",0)))
    food=max(0,float(seed.get("food",0)))
    medical=max(0,float(seed.get("medical",0)))
    shelter=max(0,float(seed.get("shelter_capacity",0)))
    # Per-person capacities are normalized to practical planning scales.
    water_stress=clamp(1-water/(pop*15))
    food_stress=clamp(1-food/(pop*0.5))
    medical_stress=clamp(1-medical/max(1,pop*0.04))
    shelter_stress=clamp(1-shelter/max(1,pop*(0.15+0.85*damage)))
    road_blockage=clamp(blocked/edge_count)
    population_pressure=clamp(pop/30000)
    infrastructure_risk=damage
    if plan:
        access=plan.get("access",{})
        accessibility=clamp(float(access.get("accessibility_score",1)))
    else:
        accessibility=1-road_blockage
    return {
        "population_pressure": round(population_pressure,4),
        "infrastructure_risk": round(infrastructure_risk,4),
        "water_stress": round(water_stress,4),
        "food_stress": round(food_stress,4),
        "medical_stress": round(medical_stress,4),
        "shelter_stress": round(shelter_stress,4),
        "road_blockage": round(road_blockage,4),
        "accessibility": round(accessibility,4),
    }
