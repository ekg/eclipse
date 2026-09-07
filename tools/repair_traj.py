#!/usr/bin/env python3
"""Repair SIFT trajectory: replace outlier samples (low inliers / wild jumps)
by interpolation, then emit a clean trajectory file."""
import numpy as np

import sys
a = np.loadtxt(sys.argv[1] if len(sys.argv) > 1 else "sift_full.txt")
t, ang, tx, ty, inl = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4]

bad = np.zeros(len(t), bool)
bad |= inl < 25
bad |= np.abs(ang) > 3.0
bad |= np.abs(tx) > 60
bad |= np.abs(ty) > 60
bad[0] = bad[-1] = False

# rolling-median outlier pass on the survivors (window 9 samples)
good = ~bad
def rolling_med(x, ok, w=9):
    out = x.copy()
    for i in range(len(x)):
        if not ok[i]:
            continue
        lo, hi = max(0, i - w // 2), min(len(x), i + w // 2 + 1)
        out[i] = np.median(x[lo:hi][ok[lo:hi]]) if ok[lo:hi].any() else x[i]
    return out
for arr in (ang, tx, ty):
    med = rolling_med(arr, good)
    resid = np.abs(arr - med)
    thr = max(3 * np.median(resid[good]), 0.3)
    bad |= resid > thr
bad[0] = bad[-1] = False

print(f"repairing {bad.sum()} / {len(t)} samples ({bad.sum()/len(t)*100:.1f}%)")
# group contiguous bad runs for report
idx = np.where(bad)[0]
if len(idx):
    runs = np.split(idx, np.where(np.diff(idx) > 1)[0] + 1)
    for r in runs[:12]:
        print(f"  bad run t={t[r[0]]:.1f}..{t[r[-1]]:.1f}s ({len(r)} samples)")

for arr in (ang, tx, ty):
    arr[bad] = np.interp(t[bad], t[~bad], arr[~bad])
np.savetxt(sys.argv[2] if len(sys.argv) > 2 else "sift_clean.txt",
           np.column_stack([t, ang, tx, ty, inl]), fmt="%.3f %.5f %.2f %.2f %d")
g = ~bad
print(f"clean roll: {ang.min():+.3f} to {ang.max():+.3f} deg | "
      f"tx {tx.min():+.1f}..{tx.max():+.1f} ty {ty.min():+.1f}..{ty.max():+.1f} (960w)")
