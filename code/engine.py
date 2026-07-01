"""
Optical-efficiency engine for the tower-type solar power heliostat field.
CUMCM 2023 Problem A.

Coordinate frame (field frame): x = East, y = North, z = Up.
Origin at the centre of the circular field. Tower base at tower (tx,ty).
Receiver: external cylindrical receiver, height 8 m, diameter 7 m,
centre at (tx, ty, 80).

All angles in radians internally.
"""

import numpy as np
from scipy.spatial import cKDTree

# ----------------------------------------------------------------------------
# Physical constants and site parameters
# ----------------------------------------------------------------------------
PHI = np.deg2rad(39.4)        # latitude (north positive)
H_ALT = 3.0                    # altitude, km
G0 = 1.366                     # solar constant, kW/m^2
ETA_REF = 0.92                 # mirror reflectivity
REC_Z = 80.0                   # receiver centre height, m
REC_H = 8.0                    # receiver height, m
REC_D = 7.0                    # receiver diameter, m
REC_R = REC_D / 2.0            # receiver radius, m

# DNI coefficients (depend only on altitude H)
_A = 0.4237 - 0.00821 * (6 - H_ALT) ** 2
_B = 0.5055 + 0.00595 * (6.5 - H_ALT) ** 2
_C = 0.2711 + 0.01858 * (2.5 - H_ALT) ** 2

# Beam-error budget for the truncation (HFLCAL-style) model, radians.
# 2.0 mrad is a representative combined slope + tracking + specular error
# for modern stamped-glass heliostats (e.g. Pfahl 2017, Ho 2008).
SIGMA_SUN = 2.51e-3            # Gaussian-equivalent sunshape
SIGMA_OPT = 2.0e-3
SIGMA_TOT = np.sqrt(SIGMA_SUN ** 2 + SIGMA_OPT ** 2)

# The five standard time points (local/solar time, hours)
TIMES = [9.0, 10.5, 12.0, 13.5, 15.0]
MONTHS = list(range(1, 13))

# Day number D measured from spring equinox (Mar 21 -> D = 0).
# Using a non-leap year; the 21st of each month.
import datetime
_REF = datetime.date(2023, 3, 21)
def day_number(month):
    d = datetime.date(2023, month, 21)
    return (d - _REF).days

# ----------------------------------------------------------------------------
# Solar geometry
# ----------------------------------------------------------------------------
def declination(D):
    """Solar declination angle (rad). D days from spring equinox."""
    s = np.sin(2 * np.pi * D / 365.0) * np.sin(np.deg2rad(23.45))
    return np.arcsin(s)

def sun_vector(D, ST):
    """Unit vector pointing from the field toward the sun, ENU frame.
    Returns (vec3, altitude). vec = (East, North, Up)."""
    delta = declination(D)
    omega = np.pi / 12.0 * (ST - 12.0)          # hour angle
    sin_alt = (np.sin(PHI) * np.sin(delta)
               + np.cos(PHI) * np.cos(delta) * np.cos(omega))
    sin_alt = np.clip(sin_alt, -1, 1)
    alt = np.arcsin(sin_alt)
    sE = -np.cos(delta) * np.sin(omega)
    sN = np.cos(PHI) * np.sin(delta) - np.sin(PHI) * np.cos(delta) * np.cos(omega)
    sU = sin_alt
    v = np.array([sE, sN, sU])
    v = v / np.linalg.norm(v)
    return v, alt

def dni(alt):
    """Direct normal irradiance, kW/m^2, from solar altitude (rad)."""
    sa = np.sin(alt)
    if sa <= 0:
        return 0.0
    return G0 * (_A + _B * np.exp(-_C / sa))

# ----------------------------------------------------------------------------
# Mirror geometry helpers
# ----------------------------------------------------------------------------
def mirror_frame(normal):
    """Given a mirror normal (unit), return (w_hat, h_hat) the in-plane axes.
    w_hat is horizontal (top/bottom edges parallel to ground); h_hat = n x w."""
    z = np.array([0.0, 0.0, 1.0])
    w = np.cross(normal, z)
    nw = np.linalg.norm(w)
    if nw < 1e-9:                    # normal vertical -> degenerate
        w = np.array([1.0, 0.0, 0.0])
    else:
        w = w / nw
    h = np.cross(normal, w)
    h = h / np.linalg.norm(h)
    if h[2] < 0:                     # make h point upward
        h = -h
        w = -w
    return w, h


class Field:
    """A heliostat field: positions, sizes, install heights, tower position."""

    def __init__(self, pos_xy, width, height, z_install, tower=(0.0, 0.0)):
        pos_xy = np.asarray(pos_xy, float)
        self.N = len(pos_xy)
        self.width = np.full(self.N, width, float) if np.isscalar(width) else np.asarray(width, float)
        self.height = np.full(self.N, height, float) if np.isscalar(height) else np.asarray(height, float)
        self.z = np.full(self.N, z_install, float) if np.isscalar(z_install) else np.asarray(z_install, float)
        self.pos = np.column_stack([pos_xy[:, 0], pos_xy[:, 1], self.z])
        self.tower = np.array([tower[0], tower[1], REC_Z])
        self.area = self.width * self.height
        # KD-tree on horizontal positions for neighbour queries
        self.tree = cKDTree(pos_xy)
        self.pos_xy = pos_xy

    # --- per-mirror static quantities (independent of sun) ---
    def aim_vectors(self):
        """Unit vector from each mirror centre to receiver centre, and distance."""
        d = self.tower[None, :] - self.pos      # (N,3)
        dist = np.linalg.norm(d, axis=1)
        t = d / dist[:, None]
        return t, dist

    def atmospheric_eff(self):
        _, dhr = self.aim_vectors()
        d = np.clip(dhr, 0, 1000)
        return 0.99321 - 0.0001176 * d + 1.97e-8 * d ** 2

    # --- sun-dependent ---
    def normals(self, s):
        """Mirror normals for sun vector s (broadcast over mirrors)."""
        t, _ = self.aim_vectors()
        n = s[None, :] + t
        n = n / np.linalg.norm(n, axis=1)[:, None]
        return n

    def cosine_eff(self, s):
        n = self.normals(s)
        c = n @ s
        return np.clip(c, 0, 1), n

    def truncation_eff(self, s, n):
        """HFLCAL-style: convolve projected mirror image with beam-error
        Gaussian; integrate over the receiver rectangular aperture (7 x 8 m)."""
        from scipy.special import erf
        t, dhr = self.aim_vectors()
        # incidence cosine (for image foreshortening along incidence)
        cos_i = np.clip((n * s[None, :]).sum(1), 1e-3, 1)
        # geometric image half-sizes (m): flat-mirror image ~ mirror size,
        # the dimension along the incidence plane is foreshortened by cos_i.
        # Represent the (uniform) mirror image as a Gaussian with sigma=size/sqrt(12).
        sig_img_w = self.width / np.sqrt(12.0)
        sig_img_h = self.height * cos_i / np.sqrt(12.0)
        # beam spreading at the receiver (m): angular error x slant distance
        sig_beam = dhr * SIGMA_TOT / np.sqrt(np.maximum(cos_i, 1e-3))
        sig_x = np.sqrt(sig_img_w ** 2 + sig_beam ** 2)
        sig_y = np.sqrt(sig_img_h ** 2 + sig_beam ** 2)
        # fraction of 2-D Gaussian within receiver aperture (half-w 3.5, half-h 4)
        fx = erf(REC_R / (np.sqrt(2) * sig_x))
        fy = erf((REC_H / 2) / (np.sqrt(2) * sig_y))
        return np.clip(fx * fy, 0, 1)

    # ------------------------------------------------------------------
    # Shadow & blocking efficiency by surface sampling
    # ------------------------------------------------------------------
    def shadow_block_eff(self, s, n, n_samp=5, neigh_radius=None, max_neigh=40):
        """Fraction of mirror surface that is neither shadowed (incoming sun
        blocked by a neighbour) nor blocking (outgoing ray to receiver blocked).
        Sampled on an n_samp x n_samp grid per mirror.  Vectorised over the
        neighbour set of each mirror."""
        N = self.N
        eff = np.ones(N)
        g = (np.arange(n_samp) + 0.5) / n_samp - 0.5
        gu, gv = np.meshgrid(g, g)
        gu = gu.ravel(); gv = gv.ravel()           # (S,)
        S = gu.size
        t_all, _ = self.aim_vectors()
        if neigh_radius is None:
            neigh_radius = float(np.max(self.width) * 3 + 25)
        # in-plane axes for all mirrors at once
        z = np.array([0.0, 0.0, 1.0])
        w_all = np.cross(n, z)
        nw = np.linalg.norm(w_all, axis=1)
        bad = nw < 1e-9
        w_all[bad] = np.array([1.0, 0.0, 0.0])
        nw[bad] = 1.0
        w_all = w_all / nw[:, None]
        h_all = np.cross(n, w_all)
        h_all = h_all / np.linalg.norm(h_all, axis=1)[:, None]
        flip = h_all[:, 2] < 0
        h_all[flip] = -h_all[flip]
        w_all[flip] = -w_all[flip]

        for i in range(N):
            ni = n[i]; wi = w_all[i]; hi = h_all[i]
            Wi, Hi = self.width[i], self.height[i]
            centre = self.pos[i]
            P = (centre[None, :]
                 + np.outer(gu * Wi, wi)
                 + np.outer(gv * Hi, hi))             # (S,3)
            idx = self.tree.query_ball_point(self.pos_xy[i], neigh_radius)
            idx = [j for j in idx if j != i]
            if not idx:
                continue
            if len(idx) > max_neigh:
                d2 = np.sum((self.pos_xy[idx] - self.pos_xy[i]) ** 2, axis=1)
                idx = list(np.array(idx)[np.argsort(d2)[:max_neigh]])
            idx = np.asarray(idx)
            nj = n[idx]                                # (M,3)
            wj = w_all[idx]                            # (M,3)
            hj = h_all[idx]                            # (M,3)
            cj = self.pos[idx]                         # (M,3)
            Wj = self.width[idx]; Hj = self.height[idx]
            ti = t_all[i]
            # both rays at once
            blocked_sun = self._block_mask(P, s, nj, wj, hj, cj, Wj, Hj)
            blocked_rec = self._block_mask(P, ti, nj, wj, hj, cj, Wj, Hj)
            good = ~(blocked_sun | blocked_rec)
            eff[i] = good.mean()
        return eff

    @staticmethod
    def _block_mask(P, dvec, nj, wj, hj, cj, Wj, Hj):
        """For sample points P (S,3) and ray direction dvec (3,), check whether
        each ray P + a*dvec hits any of the neighbour mirrors (M of them).
        Returns boolean (S,) — True if blocked by ANY neighbour."""
        S = P.shape[0]
        # denom (M,) = nj . dvec
        denom = nj @ dvec
        eps = 1e-6
        ok_plane = np.abs(denom) > eps
        if not np.any(ok_plane):
            return np.zeros(S, bool)
        # a (S,M) = ((cj - P) . nj) / denom
        # (cj - P) . nj : compute via einsum
        diff = cj[None, :, :] - P[:, None, :]          # (S,M,3)
        a = np.einsum('smc,mc->sm', diff, nj) / denom[None, :]
        hit = P[:, None, :] + a[:, :, None] * dvec[None, None, :]   # (S,M,3)
        rel = hit - cj[None, :, :]                                   # (S,M,3)
        u = np.einsum('smc,mc->sm', rel, wj)
        v = np.einsum('smc,mc->sm', rel, hj)
        inside = ((a > 1e-3)
                  & (np.abs(u) <= Wj[None, :] / 2)
                  & (np.abs(v) <= Hj[None, :] / 2)
                  & ok_plane[None, :])
        return inside.any(axis=1)

    # ------------------------------------------------------------------
    def evaluate(self, months=MONTHS, times=TIMES, do_shadow=True,
                 n_samp=5, verbose=False):
        """Compute per-time and aggregated efficiencies + power.
        Returns dict of arrays indexed by (month,time)."""
        at = self.atmospheric_eff()                  # (N,) static
        rec = {}
        rows = []
        for m in months:
            D = day_number(m)
            for ST in times:
                s, alt = sun_vector(D, ST)
                if alt <= 0:
                    continue
                I = dni(alt)
                cosv, n = self.cosine_eff(s)
                trunc = self.truncation_eff(s, n)
                if do_shadow:
                    sb = self.shadow_block_eff(s, n, n_samp=n_samp)
                else:
                    sb = np.ones(self.N)
                eta = sb * cosv * at * trunc * ETA_REF
                # field thermal power (kW): DNI * sum(A_i * eta_i)
                power = I * np.sum(self.area * eta)    # kW
                rows.append(dict(month=m, time=ST, alt=alt, dni=I,
                                 eta=np.average(eta, weights=self.area),
                                 cos=np.average(cosv, weights=self.area),
                                 sb=np.average(sb, weights=self.area),
                                 trunc=np.average(trunc, weights=self.area),
                                 at=np.average(at, weights=self.area),
                                 power=power))
                if verbose:
                    print(f"m{m:02d} t{ST:4.1f} alt={np.rad2deg(alt):5.1f} "
                          f"DNI={I:.3f} eta={rows[-1]['eta']:.4f} P={power/1000:.3f}MW")
        return rows


def monthly_annual(rows, total_area):
    """Aggregate per-time rows into monthly means and annual means."""
    import collections
    bym = collections.defaultdict(list)
    for r in rows:
        bym[r['month']].append(r)
    monthly = {}
    for m, rs in bym.items():
        k = len(rs)
        monthly[m] = dict(
            eta=np.mean([r['eta'] for r in rs]),
            cos=np.mean([r['cos'] for r in rs]),
            sb=np.mean([r['sb'] for r in rs]),
            trunc=np.mean([r['trunc'] for r in rs]),
            at=np.mean([r['at'] for r in rs]),
            power=np.mean([r['power'] for r in rs]),               # kW
            ppa=np.mean([r['power'] for r in rs]) / total_area,    # kW/m^2
        )
    annual = dict(
        eta=np.mean([monthly[m]['eta'] for m in monthly]),
        cos=np.mean([monthly[m]['cos'] for m in monthly]),
        sb=np.mean([monthly[m]['sb'] for m in monthly]),
        trunc=np.mean([monthly[m]['trunc'] for m in monthly]),
        at=np.mean([monthly[m]['at'] for m in monthly]),
        power=np.mean([monthly[m]['power'] for m in monthly]) / 1000.0,  # MW
        ppa=np.mean([monthly[m]['ppa'] for m in monthly]),               # kW/m^2
    )
    return monthly, annual
