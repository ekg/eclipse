#!/usr/bin/env python3
"""Round-trip calibration: inject known rotation+translation into clip10s,
build corrections from SIFT, apply, verify residual motion is ~zero."""
import subprocess, numpy as np, runpy

SRC = "clip10s.mp4"
WARP = "clip_warped.mp4"
LOCK = "clip_locked.mp4"

# 1) inject: rotate a=0.02*sin(0.5*t) rad, then translate x=35*sin(t), y=20*sin(1.3*t) px
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", SRC,
                "-vf",
                "rotate=a='0.02*sin(0.5*t)':ow=4050:oh=2500:c=black,"
                "scale=3840:2160:flags=bicubic,"
                "format=yuv420p",  # rotate stage normalized first
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15", "-an",
                "clip_rot_tmp.mp4"], check=True)
subprocess.run(["ffmpeg", "-y", "-v", "error",
                "-f", "lavfi", "-i", "color=c=black:s=3840x2160:r=30000/1001:d=10",
                "-i", "clip_rot_tmp.mp4",
                "-filter_complex",
                "[0:v][1:v]overlay=x='35*sin(t)':y='20*sin(1.3*t)'",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15", "-an",
                WARP], check=True)
print("warp injected: rot=1.15*sin(0.5t) deg, tx=35sin(t) ty=20sin(1.3t) px")

# 2) measure with SIFT
subprocess.run(["python3", "roll_sift.py", WARP, "sift_warp.txt", "4", "1.0"], check=True)

# 3) build corrections (small smoothing; translation path 45s ~ keeps sin)
runpy.run_path("build_lock.py", run_name="__main__") if False else None
import sys
sys.argv = ["build_lock.py", "sift_warp.txt", "0.8", "45"]
runpy.run_path("build_lock.py", run_name="__main__")

geom = open("geometry.txt").read().split()
wbb, hbb, cw, ch = map(int, geom[:4])
a = open("corr_a.txt").read(); x = open("corr_x.txt").read(); y = open("corr_y.txt").read()

# 4) apply: rotate, then crop with dynamic x/y, then scale back to 4K
cx = (wbb - cw) // 2; cy = (hbb - ch) // 2
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", WARP,
                "-vf",
                f"rotate=a='{a}':ow={wbb}:oh={hbb}:c=black,"
                f"crop=w={cw}:h={ch}:x='({x})+{cx}':y='({y})+{cy}',"
                f"scale=3840:2160:flags=bicubic",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15", "-an",
                LOCK], check=True)
print("lock applied")

# 5) verify: SIFT-register locked clip to its own ref -> residual should be ~0
subprocess.run(["python3", "roll_sift.py", LOCK, "sift_locked.txt", "4", "1.0"], check=True)
before = np.loadtxt("sift_warp.txt"); after = np.loadtxt("sift_locked.txt")
gb = before[~np.isnan(before[:, 1])]; ga = after[~np.isnan(after[:, 1])]
print(f"INJECTED motion : roll span {gb[:,1].max()-gb[:,1].min():.3f}deg  "
      f"tx span {gb[:,2].max()-gb[:,2].min():.2f}px  ty span {gb[:,3].max()-gb[:,3].min():.2f}px (960w)")
print(f"AFTER LOCK      : roll span {ga[:,1].max()-ga[:,1].min():.3f}deg  "
      f"tx span {ga[:,2].max()-ga[:,2].min():.2f}px  ty span {ga[:,3].max()-ga[:,3].min():.2f}px")
