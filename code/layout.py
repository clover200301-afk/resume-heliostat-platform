"""Layout generation + fast surrogate evaluation for optimization (P2/P3)."""
import numpy as np
import engine as E

R_FIELD = 350.0
R_EXCL = 100.0      # no mirrors within 100 m of tower base

def staggered_rings(W, dr, tower=(0.0, 0.0), r0=None, gap=5.0):
    """Concentric staggered-ring layout.
    W   : mirror width (used for azimuth spacing: centre dist >= W+gap)
    dr  : radial pitch between rings
    Returns array of (x,y) within the annulus [R_EXCL, R_FIELD] around tower.
    Rings are azimuthally offset by half a slot (staggered) alternately."""
    tx, ty = tower
    if r0 is None:
        r0 = R_EXCL + dr * 0.5
    pts = []
    r = r0
    ring = 0
    min_sep = W + gap
    while r <= R_FIELD - 1e-6:
        circ = 2 * np.pi * r
        n = int(np.floor(circ / min_sep))
        if n < 1:
            n = 1
        dphi = 2 * np.pi / n
        offset = (ring % 2) * dphi * 0.5
        for k in range(n):
            phi = offset + k * dphi
            x = tx + r * np.cos(phi)
            y = ty + r * np.sin(phi)
            # keep inside the circular field (centred at origin, radius 350)
            if np.hypot(x, y) <= R_FIELD + 1e-6:
                pts.append((x, y))
        r += dr
        ring += 1
    return np.array(pts)


def surrogate_eval(fld, months=(3, 6, 9, 12), times=(9.0, 12.0, 15.0), n_samp=3):
    """Fast annual estimate: subset of timepoints, coarse shadow sampling.
    Returns (annual_power_MW, per_area_kW_m2, mean_eta)."""
    at = fld.atmospheric_eff()
    powers = []
    etas = []
    total_area = fld.area.sum()
    for m in months:
        D = E.day_number(m)
        for ST in times:
            s, alt = E.sun_vector(D, ST)
            if alt <= 0:
                continue
            I = E.dni(alt)
            cosv, n = fld.cosine_eff(s)
            trunc = fld.truncation_eff(s, n)
            sb = fld.shadow_block_eff(s, n, n_samp=n_samp)
            eta = sb * cosv * at * trunc * E.ETA_REF
            powers.append(I * np.sum(fld.area * eta))
            etas.append(np.average(eta, weights=fld.area))
    P = np.mean(powers) / 1000.0       # MW (approx annual)
    return P, np.mean(powers) / total_area, np.mean(etas)
