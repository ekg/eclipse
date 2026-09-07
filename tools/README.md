# Stabilization / timelapse pipeline tools

Scripts run from a scratch working directory; they read/write small text
artifacts (trajectories, correction expressions, filtergraphs, geometry) in
the CWD. See the trip READMEs for exact end-to-end command sequences.

## Motion measurement
- `roll_sift.py <video> <out.txt> <fps> <ref_t>` — SIFT+RANSAC partial-affine
  (rotation+translation) registration of every sampled frame vs a reference
  frame. ~±0.03° roll accuracy, ~±0.5-2px translation on good texture; fails
  on dark/featureless sections (low inlier counts mark the failures).
  Output: `t, ang_deg, tx@960w, ty@960w, inliers`.
- `measure_displayed.py <video> <out.txt> <step>` — same SIFT measurement at
  exactly the frames a step-N timelapse will display.
- `ecc_pairs.py <video> <out.txt> <step>` — pairwise OpenCV ECC
  (MOTION_EUCLIDEAN, terrain mask below 42% height, 1280w) between
  consecutive *displayed* frames; cumulative sums give a subpixel relative
  trajectory. One decode pass, no per-frame seeks.
- `repair_traj.py <in.txt> <out.txt>` — flags outliers (low inliers, wild
  jumps, rolling-median residual) and interpolates across them.
- `fuse_traj.py <ecc_pairs> <sift_traj> <out> [sigma_s]` — ECC micro-structure
  + SIFT low-frequency anchor (this is what makes timelapses jitter-free).

## Corrections & encoding
- `build_lock.py <traj.txt> <rot_sigma_s> <trans_path_sigma_s> [target_deg]` —
  writes `corr_a.txt` (rotate angle, radians), `corr_x/y.txt` (translation,
  px @4K) as flat piecewise-linear expressions `v0 + sum dv*clip(...)`, plus
  `geometry2.txt` (rotate bbox, scale, static crop, overlay base/limits).
  Rotation is smoothed by rot_sigma; translation corrections use 1s-smoothed
  measurements locked against a trans_path_sigma-smoothed path (sigma=300 is
  near-total lock).
- `run_lock.py <in> <out> [crf] [preset] [dur]` — full-rate master encode:
  `rotate -> lanczos scale -> static margin crop -> overlay onto 4K canvas`
  via `-filter_complex_script filtergraph.txt`.
- `run_timelapse.py <in> <out> [speed] [crf] [preset]` — timelapse encode
  with `select` BEFORE the correction filters (only kept frames are
  processed: 10x faster), then `setpts` retimes to CFR.
- `luma_fix.py <in> <out> [crf] [preset] [sigma_f]` — auto-exposure pumping
  repair: terrain-band-referenced, slope-gated band-stop gain (Y plane only).
  The gate is dilated ±8s to protect eclipse transitions from the band
  filter's memory; correction is transparent during steep light changes.

## Verification & calibration
- `verify_tl2.py <timelapse.mp4>` — pairwise ECC jitter between consecutive
  displayed frames (dx/dy/droll distributions + worst pairs).
- `round_trip.py` — historical sign-calibration harness (inject known
  rotation+translation, build corrections, verify cancellation). Kept for
  documentation; it references the older crop-based apply step.

## Hard-won gotchas (ffmpeg 6.1.1 / OpenCV 5.0 / Linux)
1. `crop` x/y expressions do **not** update per frame in this build (and
   `rotate`/`overlay` `t` works in full encodes but input-seek `-ss` resets
   PTS making expressions evaluate at t≈0 — verify only with no-seek runs).
   Use `overlay` for dynamic translation.
2. Overlay correction sign is inverted vs crop semantics: overlay x is the
   *content position*, so corrections apply as `base - corr`.
3. ffmpeg expression if-chains blow the 128KB exec arg limit; use flat
   sum-of-`clip()` terms and `-filter_complex_script <file>`.
4. `ffprobe -count_frames` decodes the entire file; use duration×fps.
5. OpenCV 5.x `findTransformECC` returns `(cc, warpMatrix)` — unpack
   accordingly; its `inputMask` must be uint8.
6. ECC vs a fixed reference breaks over long baselines (sun glare migrates,
   exposure changes): use pairwise ECC between nearby frames + fusion.
7. Locking to noisy measurements bakes measurement noise into the output as
   jitter; measure exactly where it matters (displayed frames) and smooth
   measurements before building corrections.
8. Luminance: a plain trend-following deflicker destroys real eclipse
   dimming (AE wobble 37-73s cycles overlap the light-curve transitions);
   band-stop + slope gating is the safe compromise.
