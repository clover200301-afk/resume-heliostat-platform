"""Smoke-test for the vectorised shadow/block efficiency."""
import numpy as np, time
import engine as E

pts = np.load('positions.npy')
fld = E.Field(pts, 6.0, 6.0, 4.0, tower=(0.0, 0.0))
s, alt = E.sun_vector(E.day_number(3), 12.0)
cosv, n = fld.cosine_eff(s)
t = time.time()
sb = fld.shadow_block_eff(s, n, n_samp=3)
print('vectorised shadow_block time', time.time() - t,
      'mean sb', sb.mean(), 'min', sb.min())
