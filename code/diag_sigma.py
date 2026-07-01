"""Sensitivity test: how does annual MW depend on SIGMA_OPT (beam-error)?"""
import importlib, numpy as np
import engine as E
import solve_p2_grid as G

# Use the dense 6x6 layout
size, z, dr, ty = 6, 4.0, 11.0, 0.0
W = H = size
tower = (0.0, ty)
pts = G.staggered_rings_in_field(W, dr, tower=tower)

for sigma_opt in [1.5e-3, 2.0e-3, 2.5e-3, 3.0e-3]:
    E.SIGMA_OPT = sigma_opt
    E.SIGMA_TOT = np.sqrt(E.SIGMA_SUN ** 2 + E.SIGMA_OPT ** 2)
    fld = E.Field(pts, W, H, z, tower=tower)
    rows = fld.evaluate(do_shadow=True, n_samp=3)
    _, ann = E.monthly_annual(rows, fld.area.sum())
    print(f"sigma_opt={sigma_opt*1000:.1f} mrad  trunc={ann['trunc']:.3f}  "
          f"eta={ann['eta']:.3f}  P={ann['power']:.2f} MW  ppa={ann['ppa']:.4f}")
