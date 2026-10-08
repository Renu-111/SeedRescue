"""Human-readable explanation layer for SeedRescue decisions."""

def explain_plan(seed, plan):
    reasons=[]
    rb=plan.get("risk_breakdown",{})
    for name,value in sorted(rb.items(), key=lambda x:-x[1])[:3]:
        reasons.append({"factor":name,"contribution":value,"message":f"{name} contributes {value} risk points."})
    shortages=plan.get("shortage",{})
    for k,v in shortages.items():
        if v>0: reasons.append({"factor":f"{k}_shortage","contribution":round(float(v),2),"message":f"{k.title()} has a shortage of {round(float(v),2)} units."})
    if plan.get("unsheltered",0)>0:
        reasons.append({"factor":"shelter_gap","contribution":plan["unsheltered"],"message":f"{plan['unsheltered']} affected people remain without assigned shelter."})
    return reasons[:8]
