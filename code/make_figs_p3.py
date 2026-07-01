"""Figures for Problem 3 (zonal design)."""
import numpy as np, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

OUT = "../figures"

pts = np.load('p3_final_pts.npy')
sizes = np.load('p3_final_sizes.npy')
zs = np.load('p3_final_zs.npy')
d = json.load(open('../results/problem3.json'))
tower = d['design']['tower']

# layout coloured by mirror size
fig, ax = plt.subplots(figsize=(6.6, 6.6))
unique_sizes = sorted(set(sizes))
colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(unique_sizes)))
for sz, col in zip(unique_sizes, colors):
    m = sizes == sz
    ax.scatter(pts[m, 0], pts[m, 1], s=4, color=col,
               label=f'{int(sz)}×{int(sz)} m (N={m.sum()})', alpha=0.8)
ax.add_patch(Circle((0, 0), 350, fill=False, ec='k', ls='--',
                    label='Field R=350 m'))
ax.add_patch(Circle(tower, 100, fill=False, ec='r', ls='--',
                    label='Exclusion R=100 m'))
ax.plot(tower[0], tower[1], marker='^', ms=12, color='orange',
        label=f'Tower {tower}')
ax.set_aspect('equal'); ax.set_xlim(-360, 360); ax.set_ylim(-360, 360)
ax.set_xlabel('x (East, m)'); ax.set_ylabel('y (North, m)')
ax.set_title(f"Problem 3 zonal layout: inner 5×5 m, outer 6×6 m  "
             f"(N={d['design']['n']}, A={d['design']['area']:.0f} m²)")
ax.grid(True, alpha=0.3); ax.legend(loc='upper right', fontsize=8)
fig.tight_layout()
fig.savefig(f"{OUT}/p3_layout.png", dpi=150)
plt.close(fig)
print('wrote p3_layout.png')

# monthly bars
months = sorted(int(m) for m in d['monthly'])
power = [d['monthly'][str(m)]['power'] / 1000.0 for m in months]
eta = [d['monthly'][str(m)]['eta'] for m in months]
ppa = [d['monthly'][str(m)]['ppa'] for m in months]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.3))
a1.bar(months, power, color='#2ca02c', ec='k')
a1.axhline(60, color='r', ls='--', label='Rated 60 MW')
a1.set_xlabel('Month'); a1.set_ylabel('Monthly mean thermal power (MW)')
a1.set_title('Problem 3: monthly mean output (two-zone design)')
a1.set_xticks(months); a1.grid(True, axis='y', alpha=0.3); a1.legend()

a2.plot(months, eta, '-o', label=r'$\eta$')
a2.plot(months, ppa, '-s', label=r'ppa (kW/m$^2$)')
a2.set_xlabel('Month'); a2.set_xticks(months); a2.grid(True, alpha=0.3); a2.legend()
a2.set_title('Problem 3: monthly mean efficiency & per-area power')
fig.tight_layout()
fig.savefig(f"{OUT}/p3_monthly.png", dpi=150)
plt.close(fig)
print('wrote p3_monthly.png')
