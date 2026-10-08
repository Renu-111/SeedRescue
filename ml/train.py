"""Train the SeedRescue baseline/proposed Random Forest predictor."""
import os,joblib,pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score,mean_absolute_error
from ml.model import FEATURES,TARGETS,DISASTERS,PATH

df=pd.read_csv("data/processed/scenario_dataset.csv")
df["disaster_code"]=df["disaster"].map(DISASTERS).fillna(0)
# Derived features keep training aligned with online inference.
p=df["population"].clip(lower=1)
df["population_pressure"]=(p/30000).clip(0,1)
df["water_per_person"]=df["water"]/p
df["food_per_person"]=df["food"]/p
df["medical_per_1000"]=df["medical"]/p*1000
df["shelter_per_person"]=df["shelter_capacity"]/p
df["road_blockage"]=(df["blocked_count"]/15).clip(0,1)
X,y=df[FEATURES],df[TARGETS]
Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,random_state=1)
rf=RandomForestRegressor(n_estimators=300,max_depth=16,min_samples_leaf=2,random_state=1,n_jobs=-1).fit(Xtr,ytr)
pred=rf.predict(Xte)
metrics={"samples":len(df),"data":"synthetic","model":"RandomForestRegressor","targets":{}}
for i,t in enumerate(TARGETS):metrics["targets"][t]={"r2":round(r2_score(yte[t],pred[:,i]),3),"mae":round(mean_absolute_error(yte[t],pred[:,i]),2)}
metrics["feature_importance"]={f:round(float(v),4) for f,v in sorted(zip(FEATURES,rf.feature_importances_),key=lambda x:-x[1])}
os.makedirs(os.path.dirname(PATH),exist_ok=True); joblib.dump({"model":rf,"metrics":metrics},PATH); print(metrics)