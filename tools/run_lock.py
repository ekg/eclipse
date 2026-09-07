#!/usr/bin/env python3
"""Assemble and run the final stabilization encode (overlay-based translation).

Reads corr_a.txt / corr_x.txt / corr_y.txt + geometry2.txt from build_lock.py.
Pipeline: [0:v] rotate(bbox) -> lanczos scale -> static max-margin crop -> overlay
onto a 3840x2160 canvas with clamped dynamic x/y.
Usage: run_lock.py <input> <output> [crf] [preset]
"""
import subprocess, sys

inp, out = sys.argv[1], sys.argv[2]
crf = sys.argv[3] if len(sys.argv) > 3 else "16"
preset = sys.argv[4] if len(sys.argv) > 4 else "medium"
dur = sys.argv[5] if len(sys.argv) > 5 else None

A = open("corr_a.txt").read().strip()
X = open("corr_x.txt").read().strip()
Y = open("corr_y.txt").read().strip()
g = [int(float(x)) for x in open("geometry2.txt").read().split()]
WBB, HBB, SW, SH, CW, CH, BX, BY, LIMX, LIMY = g
CXS = (SW - CW) // 2
CYS = (SH - CH) // 2

fc = (
    f"[0:v]rotate=a='{A}':ow={WBB}:oh={HBB}:c=black,"
    f"scale={SW}:{SH}:flags=lanczos,"
    f"crop={CW}:{CH}:{CXS}:{CYS}[c];"
    f"[1:v][c]overlay="
    f"x='clip({BX}-({X})\\,0\\,{LIMX})':"
    f"y='clip({BY}-({Y})\\,0\\,{LIMY})':shortest=1,"
    f"format=yuv420p[fc_out]"
)
with open("filtergraph.txt", "w") as fg:
    fg.write(fc)
cmd = ["ffmpeg", "-y", "-v", "warning", "-stats"]
if dur:
    cmd += ["-t", dur]
cmd += ["-i", inp,
       "-f", "lavfi", "-i", "color=c=black:s=3840x2160:r=30000/1001",
       "-filter_complex_script", "filtergraph.txt",
       "-map", "[fc_out]",
       "-r", "30000/1001",
       "-c:v", "libx264", "-preset", preset, "-crf", crf,
       "-movflags", "+faststart", "-an", out]
print("encoding:", out)
r = subprocess.run(cmd)
sys.exit(r.returncode)
