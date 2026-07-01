"""Check per-component efficiency for a candidate dense P2 layout."""
import numpy as np
import engine as E
import solve_p2_grid as G

size, z, dr, ty = 6, 4.0, 11.0, 0.0
W = H = size
tower = (0.0, ty)
pts = G.staggered_rings_in_field(W, dr, tower=tower)
fld = E.Field(pts, W, H, z, tower=tower)
print('N=', fld.N, 'area=', fld.area.sum())

t_, dhr = fld.aim_vectors()
print('aim distance: min', dhr.min(), 'max', dhr.max(), 'mean', dhr.mean())

at = fld.atmospheric_eff()
print('atmospheric: mean', at.mean(), 'min', at.min())

# evaluate at noon March 21
s, alt = E.sun_vector(E.day_number(3), 12.0)
cosv, n = fld.cosine_eff(s)
trunc = fld.truncation_eff(s, n)
sb = fld.shadow_block_eff(s, n, n_samp=3)
print(f'\nMarch 21 noon (alt={np.rad2deg(alt):.1f}deg):')
print(f'  cos  mean={cosv.mean():.4f} min={cosv.min():.4f}')
print(f'  sb   mean={sb.mean():.4f}  min={sb.min():.4f}')
print(f'  trunc mean={trunc.mean():.4f} min={trunc.min():.4f}')
print(f'  at   mean={at.mean():.4f}')
eta = sb*cosv*at*trunc*E.ETA_REF
print(f'  eta  mean={eta.mean():.4f}')
I = E.dni(alt)
print(f'  DNI={I:.3f}, instantaneous P = {I*np.sum(fld.area*eta)/1000:.2f} MW')
