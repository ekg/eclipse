#!/usr/bin/env python3
"""Fuse precise-but-drifting pairwise ECC trajectory with drift-free-but-noisy
SIFT absolute trajectory:
    fused = ecc_cum + gaussian(sift - ecc_cum, sigma_s)
High-frequency micro-structure comes from ECC; the low-frequency anchor comes
from SIFT. Both inputs must be sampled on the same time grid (displayed
frames); SIFT input is interpolated onto the ECC time base.

Usage: fuse_traj.py <ecc_pairs.txt> <sift_traj.txt> <out.txt> [sigma_s=3.0]
Input formats: ecc_pairs.txt (t, ang, cum_tx, cum_ty @960w, ref=first frame)
               sift_traj.txt  (t, ang, tx, ty, inliers @960w)
Output: t, ang, tx, ty, 1
"""
import sys, numpy as np
from scipy.ndimage import gaussian_filter1d

ecc_f, sift_f, out_f = sys.argv[1], sys.argv[2], sys.argv[3]
sigma_s = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0

e = np.loadtxt(ecc_f); s = np.loadtxt(sift_f)
te = e[:, 0]
sift_ang = np.interp(te, s[:, 0], s[:, 1])
sift_tx = np.interp(te, s[:, 0], s[:, 2])
sift_ty = np.interp(te, s[:, 0], s[:, 3])

dt = float(np.median(np.diff(te)))
fused = []
for ecum, sif in [(e[:, 1], sift_ang), (e[:, 2], sift_tx), (e[:, 3], sift_ty)]:
    e0 = ecum - ecum[0]
    s0 = sif - sif[0]
    fused.append(e0 + gaussian_filter1d(s0 - e0, sigma_s / dt, mode="reflect"))

fa, fx, fy = fused
np.savetxt(out_f, np.column_stack([te, fa, fx, fy, np.ones(len(te))]),
           fmt="%.4f %.5f %.3f %.3f %d")
print(f"fused: roll {fa.min():+.3f}..{fa.max():+.3f}  "
      f"tx {fx.min():+.1f}..{fx.max():+.1f}  ty {fy.min():+.1f}..{fy.max():+.1f}")
