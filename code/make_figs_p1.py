"""Produce figures for Problem 1: layout, per-mirror efficiency map,
   monthly power/efficiency plots."""
import numpy as np
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import engine as E

OUT = "../figures"

pts = np.load("positions.npy")
fld = E.Field(pts, 6.0, 6.0, 4.0, tower=(0.0, 0.0))

# ----------------------------------------------------------------------
# Figure 1: field layout
# ----------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.4, 6.4))
ax.scatter(pts[:, 0], pts[:, 1], s=3, c="#1f77b4", alpha=0.7,
           label=f"Heliostats (N={fld.N})")
ax.add_patch(Circle((0, 0), 350, fill=False, ec="k", lw=1.0, ls="--",
                    label="Field boundary R=350 m"))
ax.add_patch(Circle((0, 0), 100, fill=False, ec="r", lw=1.0, ls="--",
                    label="Exclusion R=100 m"))
ax.plot(0, 0, marker="^", ms=12, color="orange",
        label="Tower (0,0)")
ax.set_aspect("equal")
ax.set_xlim(-360, 360)
ax.set_ylim(-360, 360)
ax.set_xlabel("x (East, m)")
ax.set_ylabel("y (North, m)")
ax.set_title("Problem 1: Given heliostat-field layout")
ax.legend(loc="upper right", fontsize=8)
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(f"{OUT}/p1_layout.png", dpi=150)
plt.close(fig)
print("wrote p1_layout.png")

# ----------------------------------------------------------------------
# Figure 2: per-mirror annual-mean optical efficiency (single coarse pass)
# ----------------------------------------------------------------------
print("computing per-mirror annual mean efficiency (coarse)...")
months = [3, 6, 9, 12]
times = [9.0, 12.0, 15.0]
at = fld.atmospheric_eff()
accum = np.zeros(fld.N)
k = 0
for m in months:
    D = E.day_number(m)
    for ST in times:
        s, alt = E.sun_vector(D, ST)
        if alt <= 0:
            continue
        cosv, n = fld.cosine_eff(s)
        trunc = fld.truncation_eff(s, n)
        sb = fld.shadow_block_eff(s, n, n_samp=3)
        eta = sb * cosv * at * trunc * E.ETA_REF
        accum += eta
        k += 1
per_eta = accum / k
np.save("p1_per_eta.npy", per_eta)

fig, ax = plt.subplots(figsize=(7.0, 6.4))
sc = ax.scatter(pts[:, 0], pts[:, 1], c=per_eta, s=6, cmap="viridis")
ax.add_patch(Circle((0, 0), 350, fill=False, ec="k", lw=1.0, ls="--"))
ax.add_patch(Circle((0, 0), 100, fill=False, ec="r", lw=1.0, ls="--"))
ax.plot(0, 0, marker="^", ms=12, color="orange")
ax.set_aspect("equal")
ax.set_xlim(-360, 360)
ax.set_ylim(-360, 360)
ax.set_xlabel("x (East, m)")
ax.set_ylabel("y (North, m)")
ax.set_title("Problem 1: per-mirror mean optical efficiency $\\eta$")
fig.colorbar(sc, ax=ax, label="$\\eta$")
fig.tight_layout()
fig.savefig(f"{OUT}/p1_eta_map.png", dpi=150)
plt.close(fig)
print("wrote p1_eta_map.png")

# ----------------------------------------------------------------------
# Figure 3: monthly efficiency + power bars
# ----------------------------------------------------------------------
with open("../results/problem1.json") as f:
    res = json.load(f)
m_list = sorted(int(m) for m in res["monthly"])
eta = [res["monthly"][str(m)]["eta"] for m in m_list]
cos = [res["monthly"][str(m)]["cos"] for m in m_list]
sb = [res["monthly"][str(m)]["sb"] for m in m_list]
trunc = [res["monthly"][str(m)]["trunc"] for m in m_list]
power = [res["monthly"][str(m)]["power"] / 1000.0 for m in m_list]  # MW

fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.3))
a1.plot(m_list, eta, "-o", label=r"$\eta$")
a1.plot(m_list, cos, "-s", label=r"$\eta_{\cos}$")
a1.plot(m_list, sb,  "-d", label=r"$\eta_{sb}$")
a1.plot(m_list, trunc,"-^", label=r"$\eta_{trunc}$")
a1.set_xlabel("Month")
a1.set_ylabel("Efficiency")
a1.set_title("Problem 1: monthly mean efficiencies")
a1.set_xticks(m_list)
a1.grid(True, alpha=0.3)
a1.legend(loc="lower right")

a2.bar(m_list, power, color="#ff7f0e", edgecolor="k")
a2.set_xlabel("Month")
a2.set_ylabel("Mean output thermal power (MW)")
a2.set_title("Problem 1: monthly mean output thermal power")
a2.set_xticks(m_list)
a2.grid(True, axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(f"{OUT}/p1_monthly.png", dpi=150)
plt.close(fig)
print("wrote p1_monthly.png")
print("done.")
