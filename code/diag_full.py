"""Test the annual MW ceiling for the densest valid 6x6 layout."""
import numpy as np, time
import engine as E
import solve_p2_grid as G

# Tight 6m mirrors, dr=11 (W+5), tower at origin.
size, z, dr, ty = 6, 4.0, 11.0, 0.0
W = H = size
tower = (0.0, ty)
pts = G.staggered_rings_in_field(W, dr, tower=tower)
fld = E.Field(pts, W, H, z, tower=tower)
print('N=', fld.N, 'area=', fld.area.sum(), 'm^2')

t = time.time()
rows = fld.evaluate(do_shadow=True, n_samp=5)
print('full eval elapsed', time.time() - t)

monthly, annual = E.monthly_annual(rows, fld.area.sum())
print('annual:')
for k in ['power','ppa','eta','cos','sb','trunc','at']:
    print(f'  {k} = {annual[k]:.4f}')
