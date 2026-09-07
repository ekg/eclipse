#!/usr/bin/env python3
"""Build ffmpeg correction expressions from a SIFT trajectory.

Input: trajectory file (t, ang_deg, tx_px@960w, ty_px@960w, inliers)
Target: lock angle to `target_deg` (default: robust mean), translation to its
heavily smoothed path (removes wander, keeps slow drift bounded).

Outputs:
  corr_a.txt  - rotate 'a' expression (radians)
  corr_x.txt  - crop x expression (pixels @4K)
  corr_y.txt  - crop y expression (pixels @4K)
  geometry.txt- recommended ow/oh, crop w/h (4K)
Sign conventions are calibrated by round_trip_test.py results.
"""
import sys, numpy as np

traj_file = sys.argv[1]
smooth_rot_s = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
smooth_tr_s = float(sys.argv[3]) if len(sys.argv) > 3 else 45.0
target_deg = float(sys.argv[4]) if len(sys.argv) > 4 else None

W960, W4K = 960, 3840
S = W4K / W960  # 4.0 scale factor for translations

data = np.loadtxt(traj_file)
t = data[:, 0]
ang = data[:, 1].copy(); tx = data[:, 2].copy(); ty = data[:, 3].copy()
bad = np.isnan(ang)
ang[bad] = np.interp(t[bad], t[~bad], ang[~bad])
tx[bad] = np.interp(t[bad], t[~bad], tx[~bad])
ty[bad] = np.interp(t[bad], t[~bad], ty[~bad])
dt = float(np.median(np.diff(t)))

from scipy.ndimage import gaussian_filter1d

def gsmooth(x, sigma_s):
    if sigma_s <= 0:
        return x.copy()
    return gaussian_filter1d(x, sigma_s / dt, mode="reflect")

ang_s = gsmooth(ang, smooth_rot_s)
# translation: correction uses lightly-smoothed measurements (kills SIFT noise,
# keeps real wander: slower-than-sigma wander becomes smooth motion, not jitter),
# locked against the heavily-smoothed path
tx_meas = gsmooth(tx, 1.0)
ty_meas = gsmooth(ty, 1.0)
tx_path = gsmooth(tx, smooth_tr_s)
ty_path = gsmooth(ty, smooth_tr_s)

if target_deg is None:
    target_deg = float(np.median(ang_s))

# --- corrections (calibrated signs) ---
a_corr = np.radians(target_deg - ang_s)          # rotate a=+ adds to measured ang
x_corr = (tx_meas - tx_path) * S                # content right (+tx) -> crop origin right (+)
y_corr = (ty_meas - ty_path) * S
x_corr = np.clip(x_corr, -380, 380); y_corr = np.clip(y_corr, -380, 380)

def build_expr(ts, vals, keep_every=1):
    """Flat piecewise-linear expression: v0 + sum (dv)*clip((t-t_i)/dt,0,1).
    No deep nesting -> parser/exec safe. keep_every downsamples density."""
    ts2 = np.array(ts[::keep_every]); vals2 = np.array(vals[::keep_every])
    if ts2[-1] != ts[-1]:
        ts2 = np.append(ts2, ts[-1]); vals2 = np.append(vals2, vals[-1])
    terms = [f"{vals2[0]:.4f}"]
    for i in range(1, len(ts2)):
        dtv = ts2[i] - ts2[i - 1]
        terms.append(f"({vals2[i] - vals2[i - 1]:+.4f})*clip((t-{ts2[i]:.3f})/{dtv:.3f}\\,0\\,1)")
    return "+".join(terms)

for name, vals in [("corr_a.txt", a_corr), ("corr_x.txt", x_corr), ("corr_y.txt", y_corr)]:
    with open(name, "w") as f:
        f.write(build_expr(t, vals))

# --- geometry (overlay architecture) ---
max_a = float(np.max(np.abs(a_corr)))
max_x = float(np.max(np.abs(x_corr)))
max_y = float(np.max(np.abs(y_corr)))
W, H = 3840, 2160
c, sn = np.cos(max_a), np.sin(max_a)
# rotate bbox (holds content at max |angle|)
wbb = int(np.ceil(W * c + H * sn)) // 2 * 2
hbb = int(np.ceil(H * c + W * sn)) // 2 * 2
# largest axis-aligned rect guaranteed inside content for |angle|<=max_a
w_in = W * c - H * sn
h_in = H * c - W * sn
mx = int(np.ceil(max_x)) + 6          # translation margin + safety
my = int(np.ceil(max_y)) + 6
cw = W + 2 * mx                        # static crop window
ch = H + 2 * my
f = max(cw / w_in, ch / h_in)          # required upscale factor
sw = int(np.ceil(wbb * f)) // 2 * 2
sh = int(np.ceil(hbb * f)) // 2 * 2
cw, ch = cw - cw % 2, ch - ch % 2      # even for yuv420
bx, by = (cw - W) // 2, (ch - H) // 2
limx, limy = cw - W, ch - H
with open("geometry2.txt", "w") as fo:
    fo.write(f"{wbb} {hbb} {sw} {sh} {cw} {ch} {bx} {by} {limx} {limy}\n")
print(f"target={target_deg:+.3f} deg  max|a_corr|={np.degrees(max_a):.3f} deg  "
      f"max|x|={max_x:.0f}px max|y|={max_y:.0f}px")
print(f"bbox={wbb}x{hbb} scale={sw}x{sh} crop={cw}x{ch} (zoom {f:.3f}x) overlay-base=({bx},{by})")
