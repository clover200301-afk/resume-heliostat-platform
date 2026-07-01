import numpy as np, json, time
import engine as E

pts = np.load('positions.npy')
fld = E.Field(pts, 6.0, 6.0, 4.0, tower=(0.0, 0.0))
total_area = fld.area.sum()
print("N=", fld.N, "total mirror area=", total_area, "m^2")

t0 = time.time()
rows = fld.evaluate(do_shadow=True, n_samp=5, verbose=True)
print("elapsed", time.time() - t0)

monthly, annual = E.monthly_annual(rows, total_area)

# save
out = dict(monthly={str(m): monthly[m] for m in monthly}, annual=annual,
           total_area=float(total_area), N=int(fld.N))
with open('../results/problem1.json', 'w') as f:
    json.dump(out, f, indent=2, default=float)

print("\n=== Table 1 (monthly) ===")
print(f"{'month':>5} {'eta':>7} {'cos':>7} {'sb':>7} {'trunc':>7} {'ppa(kW/m2)':>11}")
for m in sorted(monthly):
    d = monthly[m]
    print(f"{m:>5} {d['eta']:.4f} {d['cos']:.4f} {d['sb']:.4f} {d['trunc']:.4f} {d['ppa']:>11.4f}")
print("\n=== Table 2 (annual) ===")
print(f"eta={annual['eta']:.4f} cos={annual['cos']:.4f} sb={annual['sb']:.4f} "
      f"trunc={annual['trunc']:.4f} P={annual['power']:.4f} MW ppa={annual['ppa']:.4f} kW/m2")
