"""FastAPI app — heliostat field site-selection simulator.

Endpoints:
- GET  /                — serve the single-page UI
- GET  /api/field       — get the default heliostat layout (positions + size)
- POST /api/instant     — single-timepoint metrics (debounced from UI)
- POST /api/annual      — 12-month curve for a site
- POST /api/compare     — annual curves for a list of sites (one call)

Run with:
    cd web/
    uvicorn app:app --reload --port 8000
Then open http://localhost:8000 in your browser.
"""
from __future__ import annotations
from pathlib import Path
from typing import List

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import engine_web as W

app = FastAPI(title="Heliostat Site-Selection Simulator")

STATIC_DIR = Path(__file__).resolve().parent / "static"


# ----------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------
class InstantReq(BaseModel):
    lat: float = Field(39.4, ge=-66.5, le=66.5)
    lng: float = Field(98.5, ge=-180.0, le=180.0)
    altitude_km: float = Field(3.0, ge=0.0, le=6.0)
    clearness: float = Field(1.0, ge=0.3, le=1.0)
    date: str = Field("2023-06-21")     # YYYY-MM-DD
    time_hours: float = Field(12.0, ge=0.0, le=24.0)
    mirror_size: float = Field(5.0, ge=2.0, le=8.0)


class AnnualReq(BaseModel):
    lat: float = Field(39.4, ge=-66.5, le=66.5)
    lng: float = Field(98.5, ge=-180.0, le=180.0)
    altitude_km: float = Field(3.0, ge=0.0, le=6.0)
    clearness: float = Field(1.0, ge=0.3, le=1.0)


class CompareReq(BaseModel):
    sites: List[AnnualReq]


# ----------------------------------------------------------------------
# API routes
# ----------------------------------------------------------------------
@app.get("/api/field")
def api_field(mirror_size: float = 5.0):
    """Heliostat positions, sizes, tower — used to build the 3D scene.
    Query param `mirror_size` (2–8 m, 0.5 m step) sets the density: smaller
    mirrors pack tighter so more mirrors fit in the same 350-m field."""
    return W.get_field_pts(mirror_size)


@app.post("/api/instant")
def api_instant(req: InstantReq):
    return W.instant_metrics(req.lat, req.lng, req.altitude_km,
                             req.clearness, req.date, req.time_hours,
                             req.mirror_size)


@app.post("/api/annual")
def api_annual(req: AnnualReq):
    return W.annual_curve(req.lat, req.altitude_km, req.clearness)


@app.post("/api/compare")
def api_compare(req: CompareReq):
    return dict(sites=[
        dict(lat=s.lat, lng=s.lng, altitude_km=s.altitude_km,
             clearness=s.clearness,
             result=W.annual_curve(s.lat, s.altitude_km, s.clearness))
        for s in req.sites
    ])


# ----------------------------------------------------------------------
# Static UI
# ----------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
