"""
Download REAL Bengaluru data for SeedRescue.

Run from the folder that contains app.py:
    pip install osmnx geopandas rasterio requests
    python download_bengaluru.py

Output goes to data/raw/bengaluru/
  boundary.geojson      city boundary
  roads.graphml         drivable road network (for Dijkstra routing)
  roads_edges.geojson   same roads as lines (for the map)
  hospitals.geojson     hospitals + clinics
  schools.geojson       schools + colleges (candidate shelters)
  shelters.geojson      community halls, town halls, stadiums
  water.geojson         lakes, rivers, streams, drains (flood context)
  population.tif        WorldPop 100 m population, clipped to Bengaluru
"""
import os
import requests
import osmnx as ox
import geopandas as gpd

PLACE = "Bengaluru, Karnataka, India"
OUT = os.path.join("data", "raw", "bengaluru")
os.makedirs(OUT, exist_ok=True)

# WorldPop India 100 m, UN-adjusted 2020. Check the URL on worldpop.org if it 404s.
WORLDPOP_URL = ("https://data.worldpop.org/GIS/Population/"
                "Global_2000_2020/2020/IND/ind_ppp_2020.tif")

def save(gdf, name):
    keep = [c for c in ("name", "amenity", "building", "healthcare", "beds",
                        "capacity", "emergency", "natural", "waterway",
                        "leisure", "geometry") if c in gdf.columns]
    gdf[keep].to_file(os.path.join(OUT, name), driver="GeoJSON")
    print(f"  saved {name}: {len(gdf)} features")


def features(tags, name):
    try:
        gdf = ox.features_from_place(PLACE, tags)
        save(gdf.reset_index(drop=True), name)
    except Exception as e:
        print(f"  FAILED {name}: {e}")


print("1/6 boundary")
boundary = ox.geocode_to_gdf(PLACE)
boundary.to_file(os.path.join(OUT, "boundary.geojson"), driver="GeoJSON")

print("2/6 road network (takes a few minutes)")
G = ox.graph_from_place(PLACE, network_type="drive")
ox.save_graphml(G, os.path.join(OUT, "roads.graphml"))
_, edges = ox.graph_to_gdfs(G)
edges[["name", "highway", "length", "geometry"]].astype({"name": str, "highway": str}) \
    .to_file(os.path.join(OUT, "roads_edges.geojson"), driver="GeoJSON")
print(f"  roads: {len(G.nodes)} nodes, {len(G.edges)} edges")

print("3/6 hospitals")
features({"amenity": ["hospital", "clinic"], "healthcare": ["hospital"]}, "hospitals.geojson")

print("4/6 schools")
features({"amenity": ["school", "college"]}, "schools.geojson")

print("5/6 shelters and water")
features({"amenity": ["community_centre", "townhall"], "leisure": ["stadium"]}, "shelters.geojson")
features({"natural": ["water"], "waterway": ["river", "stream", "canal", "drain"]}, "water.geojson")

print("6/6 population raster (large download, ~ hundreds of MB)")
try:
    import rasterio
    from rasterio.mask import mask
    tif = os.path.join("data", "raw", "ind_ppp_2020.tif")
    if not os.path.exists(tif):
        with requests.get(WORLDPOP_URL, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(tif, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    with rasterio.open(tif) as src:
        geom = boundary.to_crs(src.crs).geometry
        arr, transform = mask(src, geom, crop=True)
        meta = src.meta.copy()
        meta.update(height=arr.shape[1], width=arr.shape[2], transform=transform)
    with rasterio.open(os.path.join(OUT, "population.tif"), "w", **meta) as dst:
        dst.write(arr)
    print("  saved population.tif")
except Exception as e:
    print(f"  population FAILED: {e}\n  Download manually from worldpop.org and put it in data/raw/")

print("\nDone. Files are in", OUT)