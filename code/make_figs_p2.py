"""Figures for Problem 2."""
import numpy as np, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

OUT = "../figures"

pts = np.load('p2_final_pts.npy')
d = json.load(open('../results/problem2.json'))
ty = d['design']['ty']

fig, ax = plt.subplots(figsize=(6.6, 6.6))
ax.scatter(pts[:, 0], pts[:, 1], s=2, c='#1f77b4', alpha=0.7,
           label=f"Heliostats (N={d['design']['n']})")
ax.add_patch(Circle((0, 0), 350, fill=False, ec='k', ls='--',
                    label='Field R=350 m'))
ax.add_patch(Circle((0, ty), 100, fill=False, ec='r', ls='--',
                    label='Exclusion R=100 m (around tower)'))
ax.plot(0, ty, marker='^', ms=12, color='orange',
        label=f'Tower (0, {ty})')
ax.set_aspect('equal'); ax.set_xlim(-360, 360); ax.set_ylim(-360, 360)
ax.set_xlabel('x (East, m)'); ax.set_ylabel('y (North, m)')
ax.set_title(f"Problem 2 layout: {d['design']['W']}×{d['design']['H']} m mirrors, "
             f"dr={d['design']['dr']} m, z={d['design']['z']} m")
ax.grid(True, alpha=0.3); ax.legend(loc='upper right', fontsize=8)
fig.tight_layout()
fig.savefig(f"{OUT}/p2_layout.png", dpi=150)
plt.close(fig)
print('wrote p2_layout.png')

# monthly bars
months = sorted(int(m) for m in d['monthly'])
power = [d['monthly'][str(m)]['power'] / 1000.0 for m in months]
eta = [d['monthly'][str(m)]['eta'] for m in months]
ppa = [d['monthly'][str(m)]['ppa'] for m in months]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.3))
a1.bar(months, power, color='#ff7f0e', ec='k')
a1.set_xlabel('Month'); a1.set_ylabel('Monthly mean thermal power (MW)')
a1.set_title('Problem 2: monthly mean output')
a1.axhline(60, color='r', ls='--', label='Rated 60 MW')
a1.set_xticks(months); a1.grid(True, axis='y', alpha=0.3); a1.legend()

a2.plot(months, eta, '-o', label=r'$\eta$')
a2.plot(months, ppa, '-s', label=r'$\eta\,\mathrm{DNI}$ per area (kW/m$^2$)')
a2.set_xlabel('Month'); a2.set_xticks(months); a2.grid(True, alpha=0.3); a2.legend()
a2.set_title('Problem 2: monthly mean efficiency & per-area power')
fig.tight_layout()
fig.savefig(f"{OUT}/p2_monthly.png", dpi=150)
plt.close(fig)
print('wrote p2_monthly.png')
