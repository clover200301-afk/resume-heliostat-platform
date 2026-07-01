"""Diagnose max annual MW for the densest possible 7x7 staggered layout."""
import numpy as np, time
import engine as E
import solve_p2_grid as G

cases = [
    (5, 3.5, 10.0,  0),
    (5, 3.5, 10.0, -100),
    (5, 5.0, 10.0,  0),
    (6, 4.0, 11.0,  0),
    (7, 4.0, 12.0,  0),
]
for size, z, dr, ty in cases:
    pts = G.staggered_rings_in_field(size, dr, tower=(0, ty))
    fld = E.Field(pts, size, size, z, tower=(0, ty))
    rows = fld.evaluate(do_shadow=True, n_samp=3)
    _, ann = E.monthly_annual(rows, fld.area.sum())
    print(f"sz={size} z={z} dr={dr} ty={ty:+.0f}: N={fld.N:4d} area={fld.area.sum():.0f}"
          f"  P={ann['power']:.2f} MW  ppa={ann['ppa']:.4f}  eta={ann['eta']:.4f}")
