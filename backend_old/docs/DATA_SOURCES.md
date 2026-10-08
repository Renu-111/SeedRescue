# SeedRescue – Real data sources (check each licence before redistributing)

| Need | Source | How | Auto? |
|---|---|---|---|
| Roads, hospitals, schools, halls, stadiums, fire stations | OpenStreetMap | `data_pipeline/fetch_real_data.py` (osmnx) | yes |
| Earthquake history | USGS Earthquake Catalog API | same script | yes |
| Rainfall history (flood trigger) | Open-Meteo archive (ERA5 reanalysis) | same script | yes |
| Population per area | Census of India 2011 district/ward tables (e.g. DataMeet maps repo) and/or WorldPop India 1 km grid | download -> `data/raw/population/` | manual |
| Past disaster impacts (affected, deaths, damage) | EM-DAT (free academic registration) | download CSV, filter India | manual |
| Landslide events | NASA Global Landslide Catalog | download CSV, filter India | manual |
| Flood extent / damage maps | Copernicus EMS Rapid Mapping; Bhuvan (ISRO) | per-event downloads | manual |
| Building damage (optional) | xBD / xView2 | large; optional | manual |
| Karnataka rainfall / disaster alerts | KSNDMC | portal / request | manual |
| Humanitarian planning standards | Sphere Handbook (water 15 L/person/day, 3.5 m2 shelter space/person, 2,100 kcal/day) | constants in engine | n/a |

Honest limit: no public dataset contains "the optimal recovery plan". Real data feeds hazard, exposure,
infrastructure and history; the plan itself is produced by transparent algorithms and Sphere standards.
