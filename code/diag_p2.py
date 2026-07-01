"""Diagnostic: compute the *maximum-feasible* annual MW for a given mirror
size and install height by trying very dense layouts and ranking mirrors."""
import numpy as np, time, json
import engine as E
import solve_p2_grid as G

# size, z, dr, ty
DESIGNS = [
    (6, 4.0, 11.0, -150),     # tightest dr for 6m mirrors
    (6, 4.0, 11.0, -100),
    (6, 4.0, 11.0,  -50),
    (6, 4.0, 11.0,   0),
    (7, 5.0, 12.0, -150),
    (7, 5.0, 12.0,    0),
    (8, 5.0, 13.0, -150),
    (8, 5.0, 13.0,    0),
]

for d in DESIGNS:
    size, z, dr, ty = d
    W = H = size
    tower = (0.0, ty)
    pts = G.staggered_rings_in_field(W, dr, tower=tower)
    print(f"size={size} z={z} dr={dr} ty={ty:+.0f} n_full={len(pts)} area={len(pts)*W*H} m^2")
    if not len(pts):
        continue
    fld = E.Field(pts, W, H, z, tower=tower)
    t0 = time.time()
    pmw, peta = G.per_mirror_with_shadow(fld)
    print(f"   per-mirror surrogate done in {time.time()-t0:.1f}s, "
          f"max kW/mirror={pmw.max()*60/60/1000:.3f}, "
          f"sum kW={pmw.sum()/1000:.2f} MW")
    order = np.argsort(-peta)
    cum = np.cumsum(pmw[order]) / 1000.0
    if cum[-1] >= 60.0:
        nsel = int(np.searchsorted(cum, 60.0) + 1)
        print(f"   FEASIBLE: nsel={nsel}, area={nsel*W*H}, ppa={60000.0/(nsel*W*H):.4f}")
    else:
        print(f"   max MW reachable={cum[-1]:.2f}")
