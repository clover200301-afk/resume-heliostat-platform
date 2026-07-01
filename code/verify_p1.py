"""Re-run Problem 1 with the new vectorised engine to verify results."""
import numpy as np, json, time
import engine as E

pts = np.load('positions.npy')
fld = E.Field(pts, 6.0, 6.0, 4.0, tower=(0.0, 0.0))
print('N=', fld.N, 'area=', fld.area.sum())

t = time.time()
rows = fld.evaluate(do_shadow=True, n_samp=5)
print('elapsed', time.time() - t)

monthly, annual = E.monthly_annual(rows, fld.area.sum())
print(json.dumps(annual, indent=2, default=float))
