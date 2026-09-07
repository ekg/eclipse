#!/usr/bin/env python3
"""Pairwise ECC between consecutive displayed frames (single decode pass).

Decodes ALL frames at 1280w gray, keeps every step-th, ECC-aligns consecutive
displayed pairs with a terrain mask (uint8). Output: t, ang, cum_tx, cum_ty.
Usage: ecc_pairs.py <video> <out.txt> [step]
"""
import subprocess, sys, numpy as np, cv2

video, out_file = sys.argv[1], sys.argv[2]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 10
W = 1280

p2 = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-frames:v", "1",
                     "-vf", f"scale={W}:-2", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                    capture_output=True, check=True)
H = len(p2.stdout) // W
FS = W * H

p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vf",
                      f"scale={W}:-2,format=gray", "-f", "rawvideo",
                      "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
frames = []
i = 0
while True:
    buf = p.stdout.read(FS)
    if not buf or len(buf) < FS:
        break
    if i % step == 0:
        frames.append(np.frombuffer(buf, dtype=np.uint8))  # keep uint8
    i += 1
p.wait()
print(f"decoded {i} frames, kept {len(frames)} displayed ({W}x{H})", flush=True)

mask = np.zeros((H, W), dtype=np.uint8)
mask[int(0.42 * H):, :] = 255
crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-6)

rows = [(0.0, 0.0, 0.0, 0.0)]
ang_c = tx_c = ty_c = 0.0
fails = 0
prev_f = frames[0].reshape(H, W).astype(np.float32) / 255.0
for k in range(1, len(frames)):
    cur_f = frames[k].reshape(H, W).astype(np.float32) / 255.0
    try:
        cc, M = cv2.findTransformECC(prev_f, cur_f, np.eye(2, 3, dtype=np.float32),
                                     cv2.MOTION_EUCLIDEAN, crit, mask, 5)
        ang_c += np.degrees(np.arctan2(M[1, 0], M[0, 0]))
        tx_c += M[0, 2] * 0.75     # -> 960w px
        ty_c += M[1, 2] * 0.75
        prev_f = cur_f             # only advance reference on success
    except cv2.error:
        fails += 1
    rows.append((k * step * 1001 / 30000, ang_c, tx_c, ty_c))
    if k % 300 == 0:
        print(f"  pair {k}/{len(frames)-1} (fails {fails})", flush=True)

arr = np.array(rows)
np.savetxt(out_file, arr, fmt="%.4f %.5f %.3f %.3f")
print(f"# pairs {len(rows)-1}, ecc fails {fails}")
print(f"# cumulative roll {ang_c:+.3f} tx {tx_c:+.1f} ty {ty_c:+.1f} (960w px)")
