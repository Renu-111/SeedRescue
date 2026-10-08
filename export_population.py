"""
Exports the Bengaluru population raster as a GeoJSON of ~1 km cells,
so you can open it like the other files.   python export_population.py
Output: data/raw/bengaluru/population_cells.geojson
"""
import json, os
import numpy as np, rasterio

RAW = os.path.join("data", "raw", "bengaluru")
BLOCK = 11                                   # 11 pixels of ~92 m  =  about 1 km
with rasterio.open(os.path.join(RAW, "population.tif")) as src:
    pop = np.nan_to_num(src.read(1)).astype(float)
    T = src.transform
pop[pop < 0] = 0

feats = []
for r in range(0, pop.shape[0], BLOCK):
    for c in range(0, pop.shape[1], BLOCK):
        tot = pop[r:r + BLOCK, c:c + BLOCK].sum()
        if tot < 1:
            continue
        x0, y0 = T * (c, r)
        x1, y1 = T * (min(c + BLOCK, pop.shape[1]), min(r + BLOCK, pop.shape[0]))
        feats.append({"type": "Feature",
                      "properties": {"population": int(tot)},
                      "geometry": {"type": "Polygon",
                                   "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}})

out = os.path.join(RAW, "population_cells.geojson")
with open(out, "w") as f:
    json.dump({"type": "FeatureCollection", "features": feats}, f)
print(f"saved {out}: {len(feats)} cells, total people {sum(f['properties']['population'] for f in feats):,}")