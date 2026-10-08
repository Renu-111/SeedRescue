SEEDRESCUE COMPLETE CODE
=========================

These are the complete replacement files for the SeedRescue application:
  engine.py
  real_data_loader.py
  app.py

They are designed to keep the existing application features while using the
real Bengaluru dataset in:
  data/raw/bengaluru/

Do NOT delete or replace the data/raw/bengaluru directory.

Required real-data files:
  boundary.geojson
  roads.graphml
  roads_edges.geojson
  hospitals.geojson
  schools.geojson
  shelters.geojson
  water.geojson
  population_cells.geojson

The old hard-coded Z1-Z4/S1-S3/H1/D1 routing graph is not used.

The code also:
  - uses real GraphML road topology for routing
  - uses real population cells for affected areas
  - uses listed shelters plus schools/colleges/universities as potential
    temporary shelters
  - uses dataset capacity when present and explicitly labels estimated capacity
    when capacity is missing
  - keeps ML prediction, fair allocation, adaptive Dijkstra, automatic road
    detection, weather, bottlenecks, APIs, and map support
  - fixes the hazard-zone dictionary/string mismatch
  - limits expensive routing work for the large real Bengaluru graph
  - preserves supply_routes using the hazard location as the route source,
    because no verified relief-depot layer is present in the supplied dataset

INSTALL / REPLACE
=================

From the existing project directory:

1. Back up the current three files if desired.
2. Copy these three files into the project root:
     engine.py
     real_data_loader.py
     app.py
3. Leave every other existing project file and the entire data/ directory as-is.
4. Stop Flask with Ctrl+C.
5. Start it again:
     python app.py

TEST
====

Health:
  Invoke-RestMethod -Uri http://127.0.0.1:5000/api/health

Graph:
  Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:5000/api/graph

Plan:
  $body = @{
      disaster = "flood"
      population = 10000
      damage = 40
      water = 60000
      food = 3000
      medical = 150
      shelter_capacity = 4000
      latitude = 12.9716
      longitude = 77.5946
      blocked = @()
  } | ConvertTo-Json

  Invoke-RestMethod `
      -Uri http://127.0.0.1:5000/api/plan `
      -Method POST `
      -ContentType "application/json" `
      -Body $body

IMPORTANT
=========

Do not mix these files with older engine.py / loader.py versions. Use all
three files from this package together.
