import os, mmap, rasterio, geopandas as gpd
from rasterio.windows import from_bounds

PATH = "data/raw/ind_ppp_2020.tif"
OUT = "data/raw/bengaluru/population.tif"
boundary = gpd.read_file("data/raw/bengaluru/boundary.geojson")

# find places where a TIFF file header starts (after the junk at the front)
cands = []
with open(PATH, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
    for magic in (b"II*\x00", b"II+\x00"):
        pos = 900_000_000
        while len(cands) < 30:
            pos = m.find(magic, pos)
            if pos == -1:
                break
            cands.append(pos)
            pos += 4
cands = sorted(set(cands))
print("possible start points:", cands)

for off in cands:
    try:
        with rasterio.open(f"/vsisubfile/{off}_-1,{PATH}") as src:
            minx, miny, maxx, maxy = boundary.to_crs(src.crs).total_bounds
            win = from_bounds(minx, miny, maxx, maxy, src.transform)
            arr = src.read(1, window=win)
            meta = src.meta.copy()
            meta.update(height=arr.shape[0], width=arr.shape[1],
                        transform=src.window_transform(win), count=1)
        with rasterio.open(OUT, "w", **meta) as dst:
            dst.write(arr, 1)
        print("SUCCESS from offset", off)
        print("saved", OUT, arr.shape, "total people:", int(arr[arr > 0].sum()))
        break
    except Exception as e:
        print("not this one:", off, str(e)[:80])
else:
    print("No good copy found. Use the GHSL tile option instead.")