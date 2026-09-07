# eclipse

Drone eclipse footage: stabilization, timelapse, and exposure-pumping repair
tooling. One directory per trip under `trips/`; shared pipeline in `tools/`.

Media files (`.MP4`/`.mp4`, GBs) are **not** tracked — see each trip's README
for source provenance and exact reproduction steps from the originals.

## Trips
- [`trips/2026_rillo`](trips/2026_rillo/README.md) — 2026-08-12 total solar
  eclipse, drone at 4K/29.97, ~10:46. Final deliverables: horizon/position
  locked stabilized master + 10x timelapse with jitter-free displayed frames
  and auto-exposure pumping repair.

## Pipeline overview (see `tools/README.md` for details)
1. **Measure** camera motion: SIFT+RANSAC registration vs a reference frame
   (`roll_sift.py`), optionally at exactly the frames a timelapse will show
   (`measure_displayed.py`), and pairwise subpixel ECC between consecutive
   displayed frames (`ecc_pairs.py`, terrain-masked so sun glare can't fool it).
2. **Repair** failed measurements (low-texture/dark sections) by interpolation
   (`repair_traj.py`), **fuse** trajectories (`fuse_traj.py`).
3. **Build corrections** (`build_lock.py`): rotation locked to the median
   angle, translation locked to a heavily smoothed path; emitted as flat
   piecewise-linear ffmpeg expressions plus crop/overlay geometry.
4. **Encode** (`run_lock.py` master, `run_timelapse.py` timelapse): rotate ->
   lanczos scale -> static margin crop -> dynamic overlay; the timelapse puts
   `select` BEFORE the corrections so only kept frames are processed.
5. **Repair auto-exposure pumping** (`luma_fix.py`): terrain-referenced,
   slope-gated band-stop gain (the AE wobble band overlaps the eclipse light
   curve, so a plain deflicker/normalization destroys totality).
6. **Verify** (`verify_tl2.py`): pairwise ECC jitter measurement.

## Requirements
- ffmpeg 6.x (Ubuntu 6.1.1 tested; see tools/README.md for build-specific
  gotchas), python3 with numpy, scipy, opencv-python-headless (5.x).
