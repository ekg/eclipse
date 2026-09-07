#!/usr/bin/env python3
"""Remove auto-exposure gain wobble using the terrain band as a constant
reference. Y-plane-only correction, chroma untouched.

G(k) = trend(terr_luma(k)) / terr_luma(k), clamped; multiplies luma.
Usage: luma_fix.py <in.mp4> <out.mp4> [crf] [preset] [trend_sigma_frames]
"""
import subprocess, sys, numpy as np
from scipy.ndimage import gaussian_filter1d, maximum_filter1d

inp, out = sys.argv[1], sys.argv[2]
crf = sys.argv[3] if len(sys.argv) > 3 else "16"
preset = sys.argv[4] if len(sys.argv) > 4 else "medium"
sigma_f = float(sys.argv[5]) if len(sys.argv) > 5 else 120.0  # displayed frames

W, H = 3840, 2160

# probe
probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
                        "-of", "csv=p=0", inp], capture_output=True, text=True, check=True)
n = int(proof if False else subprocess.run(
    ["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0",
     "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", inp],
    capture_output=True, text=True, check=True).stdout)

# 1) measure terrain luma per frame (fast pass, downscaled)
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", inp, "-vf",
                      "scale=192:108,format=gray", "-f", "rawvideo",
                      "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
small = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 108, 192).astype(np.float32)
terr = small[:, 70:, :].mean(axis=(1, 2))
# band-stop (1.2-8s display) gated by sustained slope: AE wobble oscillates
# (low sustained slope) -> corrected; eclipse transitions are sustained
# monotone ramps -> gate disables correction there, preserving the drama
band = (gaussian_filter1d(terr, 1.2 * 30, mode="reflect")
        - gaussian_filter1d(terr, 8.0 * 30, mode="reflect"))
slope = np.abs(np.gradient(gaussian_filter1d(terr, 4.0 * 30, mode="reflect")) * 30.0)  # luma per display-second
w = 1.0 / (1.0 + (slope / 1.5) ** 2)          # 1 = flat, 0 = steep ramp
w = 1.0 - maximum_filter1d(1.0 - w, 16 * 30)  # dilate: band memory is +/-8s
gain = np.clip((terr - w * band) / np.maximum(terr, 1e-6), 0.78, 1.28)
print(f"frames {n}, terrain luma med {np.median(terr):.1f}, "
      f"gain range {gain.min():.3f}..{gain.max():.3f} (std {gain.std():.4f})")

# 2) re-encode with per-frame Y gain
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", inp, "-f", "rawvideo",
                        "-pix_fmt", "yuv420p", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-y", "-v", "warning", "-stats",
                        "-f", "rawvideo", "-pix_fmt", "yuv420p",
                        "-s", f"{W}x{H}", "-r", "30000/1001", "-i", "-",
                        "-c:v", "libx264", "-preset", preset, "-crf", crf,
                        "-movflags", "+faststart", "-an", out],
                       stdin=subprocess.PIPE)
YS = W * H
k = 0
while True:
    yuv = dec.stdout.read(YS * 3 // 2)
    if not yuv or len(yuv) < YS * 3 // 2:
        break
    a = np.frombuffer(yuv, dtype=np.uint8).copy()
    y = a[:YS].astype(np.float32) * gain[min(k, n - 1)]
    a[:YS] = np.clip(y, 0, 255).astype(np.uint8)
    enc.stdin.write(a.tobytes())
    k += 1
dec.stdout.close(); enc.stdin.close()
dec.wait(); enc.wait()
print(f"done: {k} frames -> {out}")
