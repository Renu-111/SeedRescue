# SeedRescue v4 — Seed-Guided Adaptive Recovery

SeedRescue turns a compact disaster seed into an explainable recovery plan.

## What changed from v3
- Random Forest predictions now feed the planning engine instead of sitting beside it.
- Added derived features for population/resource pressure and road blockage.
- Added tree-ensemble uncertainty and confidence.
- Added risk-aware adaptive Dijkstra routing.
- Replaced simple shelter greedy allocation with a multi-factor, fairness-aware allocator.
- Added a Seed-Guided Propagation Engine for Seed → Unfolding → Manifestation.
- `/api/compare` now returns causal propagation information, not only numeric deltas.
- Added `/api/state` and `/api/propagate` endpoints.
- Existing `/api/plan`, `/api/compare`, `/api/graph`, `/api/model-info`, and `/api/health` remain available.

## Important research positioning
The Random Forest, Dijkstra, graph representation, fairness, uncertainty, and explainability pieces are established techniques. The project-specific contribution is the **seed-guided propagation workflow**: a change in a compact disaster seed is explicitly propagated into state pressure, demand, allocation, routing, and recovery consequences.

Do not describe the individual algorithms as newly invented.

## Run
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m ml.generate_dataset
python -m ml.train
python app.py
```
Open `http://127.0.0.1:5000/`.

## Real data
`data_pipeline/fetch_real_data.py` remains a separate ingestion step. Real OSM/USGS/Open-Meteo data should be used for validation/experiments and clearly separated from the synthetic training labels.
