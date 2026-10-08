"""STEP 1 of the real-data upgrade. Needs internet. Run once per region:
    python -m data_pipeline.fetch_real_data "Belagavi, Karnataka, India"
Downloads ONLY real data:
  - road network + hospitals/shelters/fire stations   (OpenStreetMap)
  - earthquake catalogue for Karnataka region          (USGS)
  - daily rainfall history 1990-today for the region   (Open-Meteo / ERA5 reanalysis)
"""
import os, re, sys, datetime
import requests, pandas as pd
import osmnx as ox

PLACE = sys.argv[1] if len(sys.argv) > 1 else "Belagavi, Karnataka, India"
slug = re.sub(r"[^a-z0-9]+", "_", PLACE.lower()).strip("_")
OUT = f"data/raw/{slug}"
os.makedirs(OUT, exist_ok=True)
print(f"== Region: {PLACE}  ->  {OUT}")

# 1. Road network (drivable) --------------------------------------------------
G = ox.graph_from_place(PLACE, network_type="drive")
ox.save_graphml(G, f"{OUT}/roads.graphml")
print(f"roads: {len(G.nodes):,} junctions, {len(G.edges):,} road segments")

# 2. Facilities: hospitals, shelters (schools, halls, stadiums), depots -------
TAGS = {"amenity": ["hospital", "clinic", "school", "community_centre", "fire_station", "townhall"],
        "leisure": ["stadium", "sports_centre"]}
gdf = ox.features_from_place(PLACE, TAGS)
pts = gdf.geometry.representative_point()
KIND = {"hospital": "hospital", "clinic": "hospital", "school": "shelter", "community_centre": "shelter",
        "stadium": "shelter", "sports_centre": "shelter", "townhall": "shelter", "fire_station": "depot"}
rows = []
for (_, _), r, p in zip(gdf.index, gdf.to_dict("records"), pts):
    key = r.get("amenity") if isinstance(r.get("amenity"), str) else r.get("leisure")
    if key in KIND:
        rows.append({"name": r.get("name") if isinstance(r.get("name"), str) else f"Unnamed {key}",
                     "osm_tag": key, "kind": KIND[key], "lat": p.y, "lon": p.x})
fac = pd.DataFrame(rows)
fac.to_csv(f"{OUT}/facilities.csv", index=False)
print("facilities:", fac["kind"].value_counts().to_dict())

# 3. Earthquakes (USGS), bounding box around Karnataka ------------------------
q = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", timeout=120, params=dict(
    format="csv", starttime="1970-01-01", minlatitude=11.5, maxlatitude=18.5,
    minlongitude=74.0, maxlongitude=78.6, minmagnitude=2.5, orderby="time"))
q.raise_for_status()
open(f"{OUT}/usgs_earthquakes_karnataka.csv", "w", encoding="utf-8").write(q.text)
print("earthquakes:", max(0, q.text.count("\n") - 1), "events")

# 4. Rainfall history at the region centre (Open-Meteo archive) ---------------
lat, lon = ox.geocode(PLACE)
r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=180, params=dict(
    latitude=lat, longitude=lon, start_date="1990-01-01",
    end_date=(datetime.date.today() - datetime.timedelta(days=7)).isoformat(),
    daily="precipitation_sum", timezone="Asia/Kolkata"))
r.raise_for_status()
d = r.json()["daily"]
rain = pd.DataFrame({"date": d["time"], "rain_mm": d["precipitation_sum"]})
rain.to_csv(f"{OUT}/rainfall_daily.csv", index=False)
print(f"rainfall: {len(rain):,} days, max single day {rain.rain_mm.max()} mm")
print("\nDONE. Send me these printed lines and I will wire the real data into the engine.")
