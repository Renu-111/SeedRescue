"""Adaptive, fairness-aware shelter allocation.

Keeps a greedy baseline but scores candidate shelters using need, safety,
distance, medical access and current utilization.
"""
def allocate(zone_needs, shelters, candidate_fn, alpha=0.35, beta=0.20, gamma=0.15, delta=0.15, equity=0.15):
    caps={k:float(v["capacity"]) for k,v in shelters.items()}
    assignments=[]
    allocated_by_zone={z:0 for z in zone_needs}
    total_need=max(1,sum(zone_needs.values()))
    for z,need in sorted(zone_needs.items(), key=lambda x:-x[1]):
        left=float(need)
        candidates=candidate_fn(z)
        for c in candidates:
            s=c["shelter"]
            if caps.get(s,0)<=0: continue
            # Higher score is better; equity rewards zones with lower current coverage.
            current_cov=allocated_by_zone[z]/max(1,zone_needs[z])
            score=(alpha*c.get("need_score",1.0)+beta*c.get("safety",1.0)
                   +gamma*c.get("medical_access",1.0)+delta*(1-min(1,c.get("km",0)/10))
                   +equity*(1-current_cov))
            take=min(left,caps[s])
            if take<=0: continue
            caps[s]-=take; left-=take; allocated_by_zone[z]+=take
            assignments.append({**c,"people":int(take),"allocation_score":round(score,4)})
            if left<=0: break
    return assignments, {k:round(v,2) for k,v in caps.items()}
