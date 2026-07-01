"""Thin web-facing wrapper around the CUMCM 2023A physics engine.

This module:
- exposes site-parameterised versions of DNI / solar geometry
  (latitude, altitude, atmospheric clearness all configurable per request),
- caches a single representative heliostat field (Problem-2 optimum scaled
  down to ~500 mirrors so 3D rendering stays smooth and per-request
  evaluation stays sub-second),
- exposes `instant_metrics()` and `annual_curve()` for the FastAPI layer.
"""
from __future__ import annotations
import os, sys, datetime
import numpy as np
from functools import lru_cache

# allow importing engine.py from the existing code/ directory
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..', 'code'))
import engine as E   # noqa: E402

G0 = 1.366
ETA_REF = E.ETA_REF
SIGMA_TOT = E.SIGMA_TOT


# ---------------------------------------------------------------------------
# Parameterised DNI + sun geometry (lat / altitude / clearness configurable)
# ---------------------------------------------------------------------------
def dni_param(alt_rad: float, h_km: float, clearness: float = 1.0) -> float:
    """Direct-normal irradiance (kW/m^2) as a function of solar altitude,
    site altitude and atmospheric clearness (0.5 hazy .. 1.0 pristine)."""
    sa = np.sin(alt_rad)
    if sa <= 0:
        return 0.0
    a = 0.4237 - 0.00821 * (6 - h_km) ** 2
    b = 0.5055 + 0.00595 * (6.5 - h_km) ** 2
    c = 0.2711 + 0.01858 * (2.5 - h_km) ** 2
    return float(clearness * G0 * (a + b * np.exp(-c / sa)))


def sun_vector_at(lat_deg: float, D: int, ST: float):
    """ENU unit sun vector + altitude (rad) for given latitude (deg),
    day-from-spring-equinox D, solar-time ST hours."""
    phi = np.deg2rad(lat_deg)
    s = np.sin(2 * np.pi * D / 365.0) * np.sin(np.deg2rad(23.45))
    delta = np.arcsin(np.clip(s, -1, 1))
    omega = np.pi / 12.0 * (ST - 12.0)
    sin_alt = (np.sin(phi) * np.sin(delta)
               + np.cos(phi) * np.cos(delta) * np.cos(omega))
    sin_alt = float(np.clip(sin_alt, -1, 1))
    alt = float(np.arcsin(sin_alt))
    sE = -np.cos(delta) * np.sin(omega)
    sN = np.cos(phi) * np.sin(delta) - np.sin(phi) * np.cos(delta) * np.cos(omega)
    sU = sin_alt
    v = np.array([sE, sN, sU], float)
    nv = float(np.linalg.norm(v))
    if nv < 1e-12:
        return np.array([0.0, 0.0, 1.0]), 0.0
    v = v / nv
    # azimuth measured east-of-north
    az = (np.degrees(np.arctan2(sE, sN)) + 360.0) % 360.0
    return v, alt, float(az)


def day_number_from_date(date_str: str) -> int:
    """Days from spring equinox (Mar 21). Accepts 'YYYY-MM-DD' or 'MM-DD'."""
    parts = date_str.split('-')
    if len(parts) == 2:
        m, d = int(parts[0]), int(parts[1])
        y = 2023
    else:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    target = datetime.date(y, m, d)
    ref = datetime.date(y, 3, 21)
    return (target - ref).days


# ---------------------------------------------------------------------------
# Default heliostat field: Problem-2 optimum, downsampled to ~500 mirrors
# ---------------------------------------------------------------------------
def _field_params_for_n(n_target: int):
    """(Legacy) map a target mirror count to (W, dr).  Kept for API back-compat
    but no longer used by the new "dense-rings + east-west corridor" builder,
    which takes W directly."""
    n_target = max(500, min(12000, int(n_target)))
    table = [
        (1000,  8.0, 22.0),
        (2000,  6.0, 14.0),
        (3000,  5.0, 11.0),
        (4000,  4.5,  9.0),
        (5000,  3.5,  7.5),
        (6000,  3.0,  6.5),
        (7000,  2.5,  6.0),
        (8000,  2.0,  5.5),
        (9000,  2.0,  5.0),
        (12000, 2.0,  4.5),
    ]
    for cap, W, dr in table:
        if n_target <= cap:
            return W, dr
    return 2.0, 4.5


# Half-width of the east-west maintenance corridor (m).  Mirrors whose centre
# falls within |y| < CORRIDOR_HALF are dropped so a service road runs along
# the x-axis through the whole field.
CORRIDOR_HALF = 4.0


def _build_default_field(mirror_size: float = 5.0):
    """A DENSE concentric-ring heliostat field with a single east-west
    maintenance corridor.

    Design rules (per user spec):
      * Every ring is packed at the minimum-allowed spacing:
          - radial pitch  dr = mirror_size + 5  (CUMCM constraint)
          - azimuth pitch W + 5
      * Per-ring count is NOT clamped or subsampled — it grows naturally
        with radius so outer rings have more mirrors than inner rings.
      * A thin east-west corridor (|y| < CORRIDOR_HALF) is left empty for
        service vehicles.
    """
    W = H = float(mirror_size)
    dr = W + 5.0
    GAP = 5.0
    z = float(max(2.0, min(6.0, W / 2.0 + 0.5)))
    tower = (0.0, 0.0)
    R_FIELD = 350.0
    R_EXCL = 100.0

    pts = []
    r = R_EXCL + dr * 0.5
    ring_idx = 0
    while r <= R_FIELD - 1e-6:
        n = max(1, int(np.floor(2 * np.pi * r / (W + GAP))))
        dphi = 2 * np.pi / n
        # alternating stagger so radial neighbours are also spaced correctly
        offset = (ring_idx % 2) * dphi * 0.5
        for k in range(n):
            phi = offset + k * dphi
            x = tower[0] + r * np.cos(phi)
            y = tower[1] + r * np.sin(phi)
            if np.hypot(x, y) > R_FIELD - 1e-6:
                continue
            # skip mirrors in the east-west maintenance corridor
            if abs(y) < CORRIDOR_HALF:
                continue
            pts.append((x, y))
        r += dr
        ring_idx += 1

    return np.array(pts) if pts else np.zeros((0, 2)), dict(
        W=W, H=H, z=z, tower=tower)


# Keyed by mirror-size (rounded to the nearest 0.5 m).  The slider snaps to
# 0.5 m steps so the same cache entry gets reused across identical selections.
_FIELD_CACHE: dict = {}


def get_field_state(mirror_size: float = 5.0) -> dict:
    key = round(float(mirror_size) * 2) / 2
    key = max(2.0, min(8.0, key))
    if key not in _FIELD_CACHE:
        pts, meta = _build_default_field(key)
        _FIELD_CACHE[key] = dict(
            pts_render=pts,
            mirror_size=key,
            W=meta['W'], H=meta['H'], z=meta['z'],
            tower=meta['tower'],
        )
    return _FIELD_CACHE[key]


# ---------------------------------------------------------------------------
# Site-parameterised efficiency evaluation
# ---------------------------------------------------------------------------
def _evaluate_one(field: E.Field, s_vec: np.ndarray, dni_value: float,
                  do_shadow: bool, n_samp: int):
    """Compute area-weighted efficiencies + total power for one time-point.
    Returns dict (cos, sb, at, trunc, total, power_mw, ppa_kw_m2)."""
    at = field.atmospheric_eff()
    cosv, n = field.cosine_eff(s_vec)
    trunc = field.truncation_eff(s_vec, n)
    if do_shadow:
        sb = field.shadow_block_eff(s_vec, n, n_samp=n_samp)
    else:
        sb = np.ones(field.N)
    eta = sb * cosv * at * trunc * ETA_REF
    area = field.area
    A_tot = area.sum()
    power_kw = dni_value * float(np.sum(area * eta))
    return dict(
        cos=float(np.average(cosv, weights=area)),
        sb=float(np.average(sb, weights=area)),
        at=float(np.average(at, weights=area)),
        trunc=float(np.average(trunc, weights=area)),
        eta=float(np.average(eta, weights=area)),
        power_mw=power_kw / 1000.0,
        ppa_kw_m2=power_kw / A_tot,
        per_mirror_eta=eta.tolist() if field.N <= 8000 else None,
    )


def instant_metrics(lat: float, lng: float, altitude_km: float,
                    clearness: float, date_str: str, time_hours: float,
                    mirror_size: float = 5.0):
    """Single-timepoint evaluation on the current dense ring field.
    Mirror size (2–8 m) is the density knob — everything else (dr,
    per-ring count, corridor) is derived deterministically."""
    fs = get_field_state(mirror_size)
    D = day_number_from_date(date_str)
    s_vec, alt, az = sun_vector_at(lat, D, time_hours)
    dni = dni_param(alt, altitude_km, clearness)

    field_r = E.Field(fs['pts_render'], fs['W'], fs['H'], fs['z'],
                      tower=fs['tower'])
    if alt <= 0 or dni <= 0:
        m = dict(cos=0.0, sb=0.0, at=float(field_r.atmospheric_eff().mean()),
                 trunc=0.0, eta=0.0, power_mw=0.0, ppa_kw_m2=0.0,
                 per_mirror_eta=[0.0] * field_r.N)
    else:
        m = _evaluate_one(field_r, s_vec, dni, do_shadow=True, n_samp=2)

    return dict(
        sun=dict(alt_deg=float(np.degrees(alt)),
                 az_deg=float(az),
                 vec_enu=s_vec.tolist()),
        dni=dni,
        efficiencies=dict(cos=m['cos'], sb=m['sb'], at=m['at'],
                          trunc=m['trunc'], total=m['eta']),
        power_render_mw=m['power_mw'],
        power_full_mw=m['power_mw'],
        ppa_kw_m2=m['ppa_kw_m2'],
        n_render=int(field_r.N),
        n_full=int(field_r.N),
        area_render_m2=float(field_r.area.sum()),
        area_full_m2=float(field_r.area.sum()),
        per_mirror_eta=m['per_mirror_eta'],
    )


def get_field_pts(mirror_size: float = 5.0):
    """Render-sized mirror positions for the 3D scene."""
    fs = get_field_state(mirror_size)
    pts = fs['pts_render']
    return dict(
        positions=[(float(x), float(y)) for x, y in pts],
        width=fs['W'], height=fs['H'],
        install_height=fs['z'],
        tower=[float(fs['tower'][0]), float(fs['tower'][1])],
        n=len(pts),
        mirror_size=fs['mirror_size'],
    )


# ---------------------------------------------------------------------------
# Annual evaluation (12 months x 5 times) — cached
# ---------------------------------------------------------------------------
_TIMES = (9.0, 10.5, 12.0, 13.5, 15.0)
_MONTHS = tuple(range(1, 13))


def _annual_inner(lat: float, altitude_km: float, clearness: float):
    """Run 60-timepoint annual eval on the FULL field (3520 mirrors) without
    shadow/blocking (which is independent of latitude — same layout, same
    geometry — and would slow things to ~6 s per request).  Shadow loss is
    rolled in via a single climate-independent multiplier estimated from
    Problem 1/2 evaluations (~0.86)."""
    fs = get_field_state()
    pts_full = fs['pts_full']
    field_f = E.Field(pts_full, fs['W'], fs['H'], fs['z'], tower=fs['tower'])
    at = field_f.atmospheric_eff()
    SHADOW = 0.86  # representative annual mean from Problem-2 full eval
    monthly = []
    for m in _MONTHS:
        D = day_number_from_date(f"2023-{m:02d}-21")
        bym = []
        for ST in _TIMES:
            s_vec, alt, _ = sun_vector_at(lat, D, ST)
            if alt <= 0:
                continue
            dni = dni_param(alt, altitude_km, clearness)
            cosv, n = field_f.cosine_eff(s_vec)
            trunc = field_f.truncation_eff(s_vec, n)
            eta = cosv * at * trunc * ETA_REF * SHADOW
            power = dni * float(np.sum(field_f.area * eta))
            bym.append(dict(
                eta=float(np.average(eta, weights=field_f.area)),
                power_mw=power / 1000.0,
                dni=dni,
            ))
        if not bym:
            monthly.append(dict(month=m, eta=0.0, power_mw=0.0, dni=0.0))
        else:
            monthly.append(dict(
                month=m,
                eta=float(np.mean([r['eta'] for r in bym])),
                power_mw=float(np.mean([r['power_mw'] for r in bym])),
                dni=float(np.mean([r['dni'] for r in bym])),
            ))
    A_tot = float(field_f.area.sum())
    annual = dict(
        eta=float(np.mean([r['eta'] for r in monthly])),
        power_mw=float(np.mean([r['power_mw'] for r in monthly])),
        ppa_kw_m2=float(np.mean([r['power_mw'] for r in monthly])) * 1000.0 / A_tot,
        dni=float(np.mean([r['dni'] for r in monthly])),
    )
    return dict(monthly=monthly, annual=annual, total_area_m2=A_tot,
                n_mirrors=int(field_f.N))


@lru_cache(maxsize=128)
def _annual_cached(lat_r: float, alt_r: float, clear_r: float):
    return _annual_inner(lat_r, alt_r, clear_r)


def annual_curve(lat: float, altitude_km: float, clearness: float):
    """Snap to a coarse grid for caching."""
    lat_r = round(lat * 2) / 2          # 0.5° grid
    alt_r = round(altitude_km * 2) / 2  # 0.5 km grid
    clear_r = round(clearness * 20) / 20  # 0.05 grid
    return _annual_cached(lat_r, alt_r, clear_r)
