"""Seed -> state -> consequence propagation engine.

This is the project-specific contribution layer. It turns a change in the
compact seed into interpretable downstream changes before the final plan is
manifested.
"""
from typing import Dict, Any
from backend.state.state_builder import build_state

RESOURCE_KEYS = ["water", "food", "medical"]


def _delta(a,b):
    return round(float(b)-float(a),4)


def propagate(old_seed: Dict[str,Any], new_seed: Dict[str,Any], old_plan=None, new_plan=None):
    old_state=build_state(old_seed, old_plan)
    new_state=build_state(new_seed, new_plan)
    state_delta={k:_delta(old_state[k],new_state[k]) for k in old_state}

    pop_old=max(1,int(old_seed.get("population",1)))
    pop_new=max(1,int(new_seed.get("population",1)))
    dmg_old=float(old_seed.get("damage",0)); dmg_new=float(new_seed.get("damage",0))
    blocked_old=len(old_seed.get("blocked",[])); blocked_new=len(new_seed.get("blocked",[]))
    consequences=[]
    drivers=[]
    if pop_new!=pop_old:
        drivers.append({"factor":"population","before":pop_old,"after":pop_new,"delta":pop_new-pop_old})
        consequences += ["Affected-population pressure changed", "Water, food, medical and shelter demand were recalculated"]
    if dmg_new!=dmg_old:
        drivers.append({"factor":"damage","before":dmg_old,"after":dmg_new,"delta":round(dmg_new-dmg_old,2)})
        consequences += ["Infrastructure risk changed", "Displacement and recovery priority were recalculated"]
    if blocked_new!=blocked_old:
        drivers.append({"factor":"blocked_roads","before":blocked_old,"after":blocked_new,"delta":blocked_new-blocked_old})
        consequences += ["Road accessibility changed", "Route costs and reachable shelters were recalculated"]
    for k in RESOURCE_KEYS:
        if float(new_seed.get(k,0)) != float(old_seed.get(k,0)):
            drivers.append({"factor":k+"_supply","before":old_seed.get(k,0),"after":new_seed.get(k,0),"delta":_delta(old_seed.get(k,0),new_seed.get(k,0))})
            consequences.append(f"{k.title()} shortage/coverage was recalculated")
    if int(new_seed.get("shelter_capacity",0)) != int(old_seed.get("shelter_capacity",0)):
        drivers.append({"factor":"shelter_capacity","before":old_seed.get("shelter_capacity",0),"after":new_seed.get("shelter_capacity",0),"delta":int(new_seed.get("shelter_capacity",0))-int(old_seed.get("shelter_capacity",0))})
        consequences.append("Shelter allocation was recalculated")

    # Compact causal propagation scores: positive means more pressure.
    pressure_delta=round(sum(max(0,v) for k,v in state_delta.items() if k.endswith("stress") or k in ("population_pressure","road_blockage","infrastructure_risk")),4)
    return {
        "seed_change": {k:{"before":old_seed.get(k),"after":new_seed.get(k)} for k in set(old_seed)|set(new_seed) if old_seed.get(k)!=new_seed.get(k)},
        "state_before": old_state,
        "state_after": new_state,
        "state_delta": state_delta,
        "drivers": drivers,
        "pressure_delta": pressure_delta,
        "consequences": list(dict.fromkeys(consequences)),
    }
