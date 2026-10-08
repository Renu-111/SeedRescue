"""Risk-aware routing helpers used by the graph engine."""

def disaster_weights(disaster):
    return {
        "flood": {"risk":0.45,"damage":0.25,"distance":0.20,"blocked":0.10},
        "earthquake": {"risk":0.30,"damage":0.40,"distance":0.20,"blocked":0.10},
        "cyclone": {"risk":0.40,"damage":0.25,"distance":0.20,"blocked":0.15},
        "landslide": {"risk":0.45,"damage":0.30,"distance":0.15,"blocked":0.10},
    }.get(disaster,{"risk":0.35,"damage":0.30,"distance":0.25,"blocked":0.10})

def edge_cost(length_km, risk=0.0, damage=0.0, blocked_penalty=0.0, disaster="flood"):
    w=disaster_weights(disaster)
    return (w["distance"]*length_km + w["risk"]*risk*max(length_km,1.0)
            + w["damage"]*damage*max(length_km,1.0) + w["blocked"]*blocked_penalty)
