#!/usr/bin/env python3
"""Measure trajectory at EXACT displayed-frame times (every 10th frame)."""
import subprocess, sys, numpy as np, cv2
sys.path.insert(0, ".")
import roll_sift as R

video, out = sys.argv[1], sys.argv[2]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 10
FPS = 30000 / 1001

nframes = int(round(float(subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "csv=p=0", video],
    capture_output=True, text=True, check=True).stdout) * 30000 / 1001))

ref = R.grab(video, 15 * step / FPS)   # a displayed frame as reference
rk, rd = R.feats(ref)

rows = []
ns = list(range(0, nframes, step))
for n in ns:
    t = n * 1001.0 / 30000.0
    try:
        img = R.grab(video, t)
        if img.size == 0:
            rows.append((t, np.nan, np.nan, np.nan, 0)); continue
        k, d = R.feats(img)
        r = R.register(rk, rd, k, d)
        if r is None:
            rows.append((t, np.nan, np.nan, np.nan, 0)); continue
        ang, scale, (tx, ty), n_in, n_good = r
        rows.append((t, ang, tx, ty, n_in))
    except Exception:
        rows.append((t, np.nan, np.nan, np.nan, 0))
    if n % 500 == 0:
        print(f"  frame {n}/{ns[-1]}", flush=True)

arr = np.array(rows)
np.savetxt(out, arr, fmt="%.4f %.5f %.2f %.2f %d")
g = arr[~np.isnan(arr[:, 1])]
print(f"# {len(arr)} displayed samples, {np.isnan(arr[:,1]).sum()} failed")
print(f"# roll: {g[:,1].min():+.3f} to {g[:,1].max():+.3f} | inliers med {np.median(g[:,4]):.0f}")
