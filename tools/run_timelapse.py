#!/usr/bin/env python3
"""Encode the 10x timelapse directly from the source with displayed-frame lock.

select runs BEFORE the correction filters so only kept frames are processed.
Usage: run_timelapse.py <input> <output> [speed] [crf] [preset]
"""
import subprocess, sys

inp, out = sys.argv[1], sys.argv[2]
speed = int(sys.argv[3]) if len(sys.argv) > 3 else 10
crf = sys.argv[4] if len(sys.argv) > 4 else "16"
preset = sys.argv[5] if len(sys.argv) > 5 else "medium"

A = open("corr_a.txt").read().strip()
X = open("corr_x.txt").read().strip()
Y = open("corr_y.txt").read().strip()
g = [int(float(x)) for x in open("geometry2.txt").read().split()]
WBB, HBB, SW, SH, CW, CH, BX, BY, LIMX, LIMY = g
CXS = (SW - CW) // 2
CYS = (SH - CH) // 2
SEL = f"select='not(mod(n\\,{speed}))'"

fc = (
    f"[0:v]{SEL},"
    f"rotate=a='{A}':ow={WBB}:oh={HBB}:c=black,"
    f"scale={SW}:{SH}:flags=lanczos,"
    f"crop={CW}:{CH}:{CXS}:{CYS}[c];"
    f"[1:v]{SEL}[bg];"
    f"[bg][c]overlay="
    f"x='clip({BX}-({X})\\,0\\,{LIMX})':"
    f"y='clip({BY}-({Y})\\,0\\,{LIMY})':shortest=1,"
    f"setpts=N/(30000/1001)/TB,"
    f"format=yuv420p[fc_out]"
)
with open("filtergraph_tl.txt", "w") as f:
    f.write(fc)
cmd = ["ffmpeg", "-y", "-v", "warning", "-stats",
       "-i", inp,
       "-f", "lavfi", "-i", "color=c=black:s=3840x2160:r=30000/1001",
       "-filter_complex_script", "filtergraph_tl.txt",
       "-map", "[fc_out]",
       "-r", "30000/1001",
       "-c:v", "libx264", "-preset", preset, "-crf", crf,
       "-movflags", "+faststart", "-an", out]
print("encoding:", out)
r = subprocess.run(cmd)
sys.exit(r.returncode)
