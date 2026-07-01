"""Test whether 60 MW is reachable with σ_opt = 1.5 mrad (high-quality
heliostats, e.g. SolarReserve Crescent Dunes class)."""
import numpy as np
import engine as E
import solve_p2_grid as G

E.SIGMA_OPT = 1.5e-3
E.SIGMA_TOT = np.sqrt(E.SIGMA_SUN ** 2 + E.SIGMA_OPT ** 2)

cases = [
    (5, 2.5, 10.0, -50),
    (5, 2.5, 10.0, -100),
    (6, 3.0, 11.0, -50),
    (6, 3.0, 11.0, 0),
    (6, 4.0, 11.0, 0),
    (7, 3.5, 12.0, 0),
    (7, 6.0, 12.0, 0),
    (8, 4.0, 13.0, 0),
]
for size, z, dr, ty in cases:
    pts = G.staggered_rings_in_field(size, dr, tower=(0, ty))
    fld = E.Field(pts, size, size, z, tower=(0, ty))
    rows = fld.evaluate(do_shadow=True, n_samp=3)
    _, ann = E.monthly_annual(rows, fld.area.sum())
    print(f"sz={size} z={z} dr={dr} ty={ty:+.0f}: N={fld.N:4d} area={fld.area.sum():.0f}"
          f"  P={ann['power']:.2f} MW  ppa={ann['ppa']:.4f}  eta={ann['eta']:.4f}")
