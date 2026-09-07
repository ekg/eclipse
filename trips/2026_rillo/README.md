# 2026_rillo — 2026-08-12 total solar eclipse

Drone footage of the eclipse, 4K/29.97, no audio, 2× 3.6GB DJI split files,
~10:46 combined. Final deliverables (kept OUT of git):

| file | what |
|---|---|
| `eclipse_2026_stabilized_4k.mp4` | locked master (rotation to median, translation to σ=300s path) |
| `eclipse_2026_timelapse10x_4k_v4.mp4` | 10x timelapse: displayed-frame lock + AE pumping repair |
| `eclipse_2026_timelapse10x_4k_v4_posonly.mp4` | same lock, no luminance repair |
| `eclipse_2026_timelapse10x_4k.mp4` | v1 timelapse (from master, superseded) |
| `DJI_0362_0363_combined.MP4` | lossless concat of the two sources |

## Sources
- `DJI_0362.MP4`, `DJI_0363.MP4` (H.264 High@5.1, yuv420p, 3840×2160,
  30000/1001 fps, no audio). Checksums in `checksums.txt`.

## Exact reproduction

Software used: ffmpeg 6.1.1-3ubuntu5, OpenCV 5.0.0.93 (opencv-python-headless),
numpy 2.3.2, scipy 1.17.0, python 3.12. Scripts in `../../tools/` (run from a
scratch dir; trajectories/corrections for this trip are committed in
`trajectories/`).

```bash
# 0) concat sources (lossless)
ffmpeg -y -f concat -safe 0 -i <(printf "file '$PWD/DJI_0362.MP4'\nfile '$PWD/DJI_0363.MP4'\n") \
    -c copy -movflags +faststart DJI_0362_0363_combined.MP4

# 1) measure + repair trajectory (full-rate reference for the master)
python3 roll_sift.py DJI_0362_0363_combined.MP4 sift_full.txt 4 5.0
python3 repair_traj.py sift_full.txt sift_clean.txt

# 2) master: corrections were built by the *original* build_lock.py (before
#    the 1s measurement-smoothing change). The exact graph is committed:
#    trajectories/filtergraph.txt. Rebuild encode:
python3 run_lock.py DJI_0362_0363_combined.MP4 eclipse_2026_stabilized_4k.mp4 16 medium
#    (run_lock regenerates corr_* from CWD; to reproduce THIS master exactly,
#     copy trajectories/filtergraph.txt into the CWD first — it is the exact
#     filtergraph of the shipped master.)

# 3) timelapse v4: SIFT at displayed frames + pairwise ECC, fused
python3 measure_displayed.py DJI_0362_0363_combined.MP4 sift_displayed.txt 10
python3 repair_traj.py sift_displayed.txt sift_disp_clean.txt
python3 ecc_pairs.py DJI_0362_0363_combined.MP4 ecc_pairs.txt 10
python3 fuse_traj.py ecc_pairs.txt sift_disp_clean.txt fused_traj.txt 3.0
python3 build_lock.py fused_traj.txt 1.0 300
python3 run_timelapse.py DJI_0362_0363_combined.MP4 tl_v4_raw.mp4 10 16 medium
#    (trajectories/filtergraph_tl.txt is the exact shipped filtergraph)

# 4) auto-exposure pumping repair (terrain-referenced, slope-gated band-stop)
python3 luma_fix.py tl_v4_raw.mp4 eclipse_2026_timelapse10x_4k_v4.mp4 16 medium
cp tl_v4_raw.mp4 eclipse_2026_timelapse10x_4k_v4_posonly.mp4

# 5) verify
python3 verify_tl2.py eclipse_2026_timelapse10x_4k_v4.mp4
```

## Measured results
- Master (bright sections, SIFT verification): roll p5-p95 span 0.73°→0.15°;
  wander tx 114→63px, ty 75→30px @4K. 30s-drift windows mostly 2-4× better.
- Timelapse v4 vs v1: consecutive displayed-frame dx @4K p95 6.3→2.1px,
  median 1.5→0.6px. Remaining worst jumps (display t≈2.4s) are real initial
  drone settle. AE pumping (±5.6 luma terrain wobble, 37-73s cycles)
  reduced 33-45% with totality protected (worst case +6 luma, mostly ≤+2).

## Findings worth remembering
- The gimbal held roll flat (±0.5°) the whole flight; the visible "shifting"
  was slow positional wander (±85px @4K) — lock translation, not rotation.
- Horizon-edge detectors lie during an eclipse (illumination changes read as
  tilt); trust feature registration (validated with synthetic + injected-motion
  round trips).
- No clouds here → terrain = constant reference → terrain-band brightness is
  the camera's own gain: that's the AE wobble signal (and the repair anchor).
