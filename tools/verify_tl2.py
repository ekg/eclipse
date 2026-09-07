#!/usr/bin/env python3
"""Fast timelapse jitter verification: piped decode, pairwise ECC deltas.
Usage: verify_tl2.py <timelapse.mp4>"""
import subprocess, sys, numpy as np, cv2

video = sys.argv[1]
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
while True:
    buf = p.stdout.read(FS)
    if not buf or len(buf) < FS:
        break
    frames.append(np.frombuffer(buf, dtype=np.uint8))
p.wait()
mask = np.zeros((H, W), dtype=np.uint8); mask[int(0.42 * H):, :] = 255
crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 40, 1e-5)
res = []
prev = frames[0].reshape(H, W).astype(np.float32) / 255.0
for k in range(1, len(frames)):
    cur = frames[k].reshape(H, W).astype(np.float32) / 255.0
    try:
        cc, M = cv2.findTransformECC(prev, cur, np.eye(2, 3, dtype=np.float32),
                                     cv2.MOTION_EUCLIDEAN, crit, mask, 5)
        res.append((np.degrees(np.arctan2(M[1, 0], M[0, 0])), M[0, 2] * 3, M[1, 2] * 3))
    except cv2.error:
        pass
    prev = cur
a = np.array(res)
d = a
print(f"pairs measured: {len(a)} / {len(frames)-1}")
print(f"dx @4K: med {np.median(np.abs(d[:,1])):.1f}  p95 {np.percentile(np.abs(d[:,1]),95):.1f}  max {np.abs(d[:,1]).max():.1f} px")
print(f"dy @4K: med {np.median(np.abs(d[:,2])):.1f}  p95 {np.percentile(np.abs(d[:,2]),95):.1f}  max {np.abs(d[:,2]).max():.1f} px")
print(f"droll: med {np.median(np.abs(d[:,0]))*1000:.0f}  p95 {np.percentile(np.abs(d[:,0]),95)*1000:.0f} millideg")
worst = np.argsort(-np.hypot(d[:, 1], d[:, 2]))[:6]
print("worst pairs (t_display, dx, dy @4K):")
for i in worst:
    print(f"  t={(i+1)/29.97:6.2f}s  dx={d[i,1]:+6.1f} dy={d[i,2]:+6.1f}")
