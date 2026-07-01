"""Full-fidelity grid search for Problem 2.
Uses the vectorised shadow/block engine and evaluates 4-month x 3-time
windows for ranking, then full 12x5 for the top picks.
"""
import numpy as np, json, time
import engine as E

TARGET_MW = 60.0
R_FIELD = 350.0
R_EXCL_TOWER = 100.0


def staggered_rings_in_field(W, dr, tower=(0.0, 0.0), gap=5.0):
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


def per_mirror_with_shadow(fld, months=(3, 6, 9, 12),
                           times=(9.0, 12.0, 15.0), n_samp=3):
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
            sb = fld.shadow_block_eff(s, n, n_samp=n_samp)
            eta = sb * cosv * at * trunc * E.ETA_REF
            acc_p += I * fld.area * eta
            acc_e += eta
            k += 1
    return acc_p / k, acc_e / k


def evaluate_design(size, z, dr, ty, gap=5.0):
    W = H = size
    tower = (0.0, ty)
    pts = staggered_rings_in_field(W, dr, tower=tower, gap=gap)
    if len(pts) < 50:
        return None
    fld = E.Field(pts, W, H, z, tower=tower)
    pmw, peta = per_mirror_with_shadow(fld)
    order = np.argsort(-peta)
    cum = np.cumsum(pmw[order]) / 1000.0
    reach = cum[-1]
    if reach < TARGET_MW:
        return dict(feasible=False, reach=reach, size=size, z=z, dr=dr, ty=ty,
                    n_full=len(pts))
    nsel = int(np.searchsorted(cum, TARGET_MW) + 1)
    sel = order[:nsel]
    sel_pts = pts[sel]
    area = nsel * W * H
    power = cum[nsel - 1]
    ppa = power * 1000.0 / area
    return dict(feasible=True, size=size, z=z, dr=dr, gap=gap, ty=ty,
                n=nsel, n_full=len(pts), area=area, power=power, ppa=ppa,
                pts=sel_pts, W=W, H=H, mean_eta=peta[sel].mean())


def search(grid):
    rows = []
    t0 = time.time()
    print(f"{'design':50s} {'n':>5} {'nfull':>6} {'area':>7} {'reach':>6} {'sel.P':>6} {'ppa':>7} {'eta':>6}")
    for size, z, dr, ty in grid:
        r = evaluate_design(size, z, dr, ty)
        tag = f"sz={size} z={z:.2f} dr={dr:.0f} ty={ty:+.0f}"
        if r is None:
            print(f"{tag:50s}  -- no layout"); continue
        if r['feasible']:
            print(f"{tag:50s} {r['n']:>5} {r['n_full']:>6} "
                  f"{r['area']:>7.0f} {r['n_full']*r['W']*r['H']/1e3:>6.1f} "
                  f"{r['power']:>6.2f} {r['ppa']:>7.4f} {r['mean_eta']:>6.4f}")
            rows.append(r)
        else:
            print(f"{tag:50s}    INFEAS reach={r['reach']:.2f}")
    print("elapsed", time.time() - t0, "s")
    feas = [r for r in rows if r.get('feasible')]
    feas.sort(key=lambda r: -r['ppa'])
    print("\nTop 8 by per-area thermal (surrogate w/ shadow):")
    for r in feas[:8]:
        print(f"  sz={r['size']} z={r['z']:.2f} dr={r['dr']:.0f} ty={r['ty']:+.0f} "
              f"n={r['n']} area={r['area']:.0f} P={r['power']:.2f} ppa={r['ppa']:.4f}")
    return feas


# Coarse grid: vary size, z, dr (relative to size+5), ty
def build_grid():
    grid = []
    for size in [5, 6, 7, 8]:
        zmin = max(2.0, size / 2.0)
        zmax = min(6.0, size)
        for z in sorted(set([round(zmin, 2), round(zmax, 2)])):
            for extra in [0.0, 2.0, 4.0, 6.0, 8.0]:
                dr = size + 5.0 + extra
                for ty in [-150.0, -100.0, -50.0, 0.0]:
                    grid.append((size, z, dr, ty))
    return grid


if __name__ == '__main__':
    feas = search(build_grid())
    # save top
    best = feas[0]
    np.save('p2_best_pts.npy', best['pts'])
    meta = {k: v for k, v in best.items() if k != 'pts'}
    with open('p2_best_meta.json', 'w') as f:
        json.dump(meta, f, indent=2, default=float)
    # also save 2nd 3rd for verification
    with open('p2_top5.json', 'w') as f:
        json.dump([{k: v for k, v in r.items() if k != 'pts'}
                   for r in feas[:8]], f, indent=2, default=float)
    print("saved p2_best_pts.npy / p2_best_meta.json / p2_top5.json")
