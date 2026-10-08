import os, joblib, pandas as pd
from backend.state.state_builder import build_state
from backend.uncertainty import tree_prediction_stats, confidence_from_std

BASE_DIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH=os.path.join(BASE_DIR,"models","seedrescue_rf.joblib")
DISASTERS={"flood":0,"earthquake":1,"cyclone":2,"landslide":3}
FEATURES=["disaster_code","population","damage","water","food","medical","shelter_capacity","blocked_count","population_pressure","water_per_person","food_per_person","medical_per_1000","shelter_per_person","road_blockage"]
TARGETS=["risk","recovery_score","displaced","medical_demand"]
_bundle=None

def to_features(s):
 pop=max(1,float(s["population"])); blocked=len(s.get("blocked",[]))
 state=build_state({**s,"edge_count":15})
 row={"disaster_code":DISASTERS.get(s.get("disaster","flood"),0),"population":pop,"damage":float(s["damage"]),"water":float(s["water"]),"food":float(s["food"]),"medical":float(s["medical"]),"shelter_capacity":float(s["shelter_capacity"]),"blocked_count":blocked,
      "population_pressure":state["population_pressure"],"water_per_person":float(s["water"])/pop,"food_per_person":float(s["food"])/pop,"medical_per_1000":float(s["medical"])/pop*1000,"shelter_per_person":float(s["shelter_capacity"])/pop,"road_blockage":state["road_blockage"]}
 return pd.DataFrame([row])[FEATURES]

def load():
 global _bundle
 if _bundle is None and os.path.exists(PATH): _bundle=joblib.load(PATH)
 return _bundle

def predict(seed):
 b=load()
 if not b:return None
 X=to_features(seed); out=b["model"].predict(X)[0]
 r=dict(zip(TARGETS,[round(float(v),1) for v in out])); stats=tree_prediction_stats(b["model"],X)
 if stats:
  _,std=stats; stds=[round(float(v),2) for v in std]; r["uncertainty"]={t:s for t,s in zip(TARGETS,stds)}; r["confidence"]=round(confidence_from_std(std),3)
 r["risk_level"]="CRITICAL" if r["risk"]>=75 else "HIGH" if r["risk"]>=55 else "MEDIUM" if r["risk"]>=35 else "LOW"
 return r

def info():
 b=load(); return b["metrics"] if b else None