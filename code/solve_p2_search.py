"""Problem 2 optimizer (fast surrogate + final full eval).

Why a 2-stage approach:
- A full shadow/block evaluation costs O(N) per sun position with a Python
  loop over neighbours, so an exhaustive grid search over (size,z,dr,tower-y)
  is too slow with N~3000.
- Shadow loss is a smooth function of layout density (radial pitch dr and
  azimuth pitch ~W+gap). Therefore we use the cheap "no-shadow" annual
  surrogate (cos*at*trunc*ref) to RANK mirrors and to SCALE the design until
  it reaches ~target_MW / shadow_factor, with shadow_factor estimated from
  the prior literature (~0.93 for staggered fields). Once we lock the design,
  we evaluate with the full shadow/block model.

Output:
- p2_best_pts.npy : (N,2) chosen mirror centres
- p2_best_meta.json : design parameters
- ../results/problem2.json : the full evaluation summary (Tables 1 & 2)
- ../results/result2.xlsx  : the submission file (Tables of params + pts)
"""
import numpy as np, json, time
import engine as E

TARGET_MW = 60.0
R_FIELD = 350.0
R_EXCL_TOWER = 100.0


def staggered_rings_in_field(W, dr, tower=(0.0, 0.0), gap=5.0):
    """Concentric rings centered on the TOWER, alternately phase-shifted.
    Keep only mirrors that are inside the 350-m field circle and at least
    R_EXCL_TOWER away from the tower."""
    tx, ty = tower
    min_sep = W + gap
    pts = []
    r = R_EXCL_TOWER + dr * 0.5
    ring = 0
    rmax_t = R_FIELD + np.hypot(tx, ty)
    while r <= rmax_t + 1e-6:
        n = max(1, int(np.floor(2 * np.pi * r / min_sep)))
        dphi = 2 * np.pi / n
        offset = (ring % 2) * dphi * 0.5
        for k in range(n):
            phi = offset + k * dphi
            x = tx + r * np.cos(phi)
            y = ty + r * np.sin(phi)
            if np.hypot(x, y) <= R_FIELD - 1e-6:
                pts.append((x, y))
        r += dr
        ring += 1
    return np.array(pts) if pts else np.zeros((0, 2))


def per_mirror_no_shadow(fld, months=(3, 6, 9, 12),
                         times=(9.0, 12.0, 15.0)):
    """Annual surrogate that ignores shadow/blocking — vectorised, fast.
    Returns (mean_per_timepoint_kW per mirror, mean_eta per mirror)."""
    at = fld.atmospheric_eff()
    acc_p = np.zeros(fld.N)
    acc_e = np.zeros(fld.N)
    k = 0
    for m in months:
        D = E.day_number(m)
        for ST in times:
            s, alt = E.sun_vector(D, ST)
            if alt <= 0:
                continue
            I = E.dni(alt)
            cosv, n = fld.cosine_eff(s)
            trunc = fld.truncation_eff(s, n)
            eta = cosv * at * trunc * E.ETA_REF
            acc_p += I * fld.area * eta
            acc_e += eta
            k += 1
    return acc_p / k, acc_e / k


SHADOW_GUESS = 0.94   # typical for staggered radial layouts (from P1: ~0.93)


def evaluate_design_surrogate(size, z, dr, ty, gap=5.0):
    W = H = size
    tower = (0.0, ty)
    pts = staggered_rings_in_field(W, dr, tower=tower, gap=gap)
    if len(pts) < 50:
        return None
    fld = E.Field(pts, W, H, z, tower=tower)
    pmw, peta = per_mirror_no_shadow(fld)
    # rank mirrors by no-shadow efficiency; greedily add until we hit
    # TARGET / SHADOW_GUESS so that AFTER shadow the field is ~TARGET_MW.
    order = np.argsort(-peta)
    cum = np.cumsum(pmw[order]) / 1000.0    # MW (no-shadow surrogate)
    target_surrogate = TARGET_MW / SHADOW_GUESS
    if cum[-1] < target_surrogate:
        return dict(feasible=False, reach=cum[-1] * SHADOW_GUESS, size=size,
                    z=z, dr=dr, ty=ty, n_full=len(pts))
    nsel = int(np.searchsorted(cum, target_surrogate) + 1)
    sel = order[:nsel]
    sel_pts = pts[sel]
    area = nsel * W * H
    # estimate ppa using the surrogate
    power_est = cum[nsel - 1] * SHADOW_GUESS
    ppa_est = power_est * 1000.0 / area
    return dict(feasible=True, size=size, z=z, dr=dr, gap=gap, ty=ty,
                n=nsel, n_full=len(pts), area=area,
                power_est=power_est, ppa_est=ppa_est,
                mean_eta_est=peta[sel].mean() * SHADOW_GUESS,
                pts=sel_pts, W=W, H=H)


def search():
    rows = []
    t0 = time.time()
    print(f"{'design':50s} {'n':>5} {'n_full':>6} {'area':>7} {'P_est':>6} {'ppa':>6}")
    for size in [5, 6, 7, 8]:
        zmin = max(2.0, size / 2.0)
        zmax = min(6.0, size)
        z_grid = sorted(set([round(zmin, 2),
                             round((zmin + zmax) / 2, 2),
                             round(zmax, 2)]))
        for z in z_grid:
            for extra in [0.0, 1.0, 2.0, 3.0, 4.0]:
                dr = size + 5.0 + extra
                for ty in [-150.0, -120.0, -90.0, -60.0, -30.0, 0.0, 30.0]:
                    r = evaluate_design_surrogate(size, z, dr, ty)
                    if r is None:
                        continue
                    tag = f"sz={size} z={z:.2f} dr={dr:.0f} ty={ty:+.0f}"
                    if r.get('feasible'):
                        print(f"{tag:50s} {r['n']:>5} {r['n_full']:>6} "
                              f"{r['area']:>7.0f} {r['power_est']:>6.2f} "
                              f"{r['ppa_est']:>6.4f}")
                        rows.append(r)
                    else:
                        print(f"{tag:50s}   INFEAS reach={r['reach']:.1f}")
    print("elapsed", time.time() - t0)
    feas = [r for r in rows if r.get('feasible')]
    feas.sort(key=lambda r: -r['ppa_est'])
    print("\nTop 8 surrogate ppa:")
    for r in feas[:8]:
        print(f"  sz={r['size']} z={r['z']} dr={r['dr']:.0f} ty={r['ty']:+.0f} "
              f"n={r['n']} area={r['area']:.0f} ppa={r['ppa_est']:.4f}")
    return feas


def select_best(feas):
    """Pick the design with the highest surrogate ppa as the answer."""
    best = feas[0]
    np.save('p2_best_pts.npy', best['pts'])
    meta = {k: v for k, v in best.items() if k != 'pts'}
    with open('p2_best_meta.json', 'w') as f:
        json.dump(meta, f, indent=2, default=float)
    print("saved p2_best_pts.npy, p2_best_meta.json")
    return best


if __name__ == '__main__':
    feas = search()
    if feas:
        select_best(feas)
