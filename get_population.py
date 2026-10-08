import os, time, requests, rasterio, geopandas as gpd
from rasterio.windows import from_bounds

URL = "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/IND/ind_ppp_2020.tif"
TIF = os.path.join("data", "raw", "ind_ppp_2020.tif")
OUT = os.path.join("data", "raw", "bengaluru", "population.tif")
boundary = gpd.read_file(os.path.join("data", "raw", "bengaluru", "boundary.geojson"))


def save_crop(src):
    minx, miny, maxx, maxy = boundary.to_crs(src.crs).total_bounds
    win = from_bounds(minx, miny, maxx, maxy, src.transform)
    arr = src.read(1, window=win)
    meta = src.meta.copy()
    meta.update(height=arr.shape[0], width=arr.shape[1],
                transform=src.window_transform(win), count=1)
    with rasterio.open(OUT, "w", **meta) as dst:
        dst.write(arr, 1)
    print("saved", OUT, arr.shape)


# Option 1: read only Bengaluru straight from the server
try:
    print("Trying to read only the Bengaluru area...")
    with rasterio.open(URL) as src:
        save_crop(src)
    raise SystemExit
except SystemExit:
    raise
except Exception as e:
    print("Direct read failed:", e)

# Option 2: resumable full download
part = TIF + ".part"
for attempt in range(30):
    done = os.path.getsize(part) if os.path.exists(part) else 0
    try:
        h = {"Range": f"bytes={done}-"}
        with requests.get(URL, headers=h, stream=True, timeout=60) as r:
            if r.status_code == 416:  # already complete
                break
            r.raise_for_status()
            total = done + int(r.headers.get("content-length", 0))
            with open(part, "ab") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    print(f"\r{done/1e6:.0f} / {total/1e6:.0f} MB", end="")
        break
    except Exception as e:
        print(f"\nDisconnected ({type(e).__name__}), resuming in 5s... attempt {attempt+1}")
        time.sleep(5)

os.replace(part, TIF)
with rasterio.open(TIF) as src:
    save_crop(src)