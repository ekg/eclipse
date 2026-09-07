#!/usr/bin/env python3
"""Feature-based roll/translation trajectory: register every sample frame to a
reference frame with SIFT + RANSAC partial-affine (rot+scale+translation).
Usage: roll_sift.py video out.txt [fps] [ref_t]"""
import subprocess, sys, numpy as np, cv2

W = 960

def grab(video, t):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video,
                          "-frames:v", "1", "-vf", f"scale={W}:-2,format=gray",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(out, dtype=np.uint8)
    return a.reshape(a.size // W, W)

sift = cv2.SIFT_create(nfeatures=4000)
bf = cv2.BFMatcher()

def feats(img):
    k, d = sift.detectAndCompute(img, None)
    return k, d

def register(src_k, src_d, dst_k, dst_d):
    if src_d is None or dst_d is None or len(src_k) < 10 or len(dst_k) < 10:
        return None
    matches = bf.knnMatch(src_d, dst_d, k=2)
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]
    if len(good) < 12:
        return None
    src_pts = np.float32([src_k[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([dst_k[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    M, inl = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.RANSAC,
                                         ransacReprojThreshold=3.0, maxIters=5000)
    if M is None:
        return None
    n_in = int(inl.sum())
    if n_in < 10:
        return None
    ang = np.degrees(np.arctan2(M[1, 0], M[0, 0]))
    scale = np.hypot(M[0, 0], M[1, 0])
    return ang, scale, (M[0, 2], M[1, 2]), n_in, len(good)

def main():
    video, out = sys.argv[1], sys.argv[2]
    fps = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0
    ref_t = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0", video],
                               capture_output=True, text=True, check=True).stdout)
    ref = grab(video, ref_t)
    rk, rd = feats(ref)
    rows = []
    t = 0.0
    last_abs_ang, last_abs_tx, last_abs_ty = 0.0, 0.0, 0.0
    last_good_img, last_good_k, last_good_d, last_ang = ref, rk, rd, 0.0
    while t < dur:
        img = grab(video, t)
        if img.size == 0:
            break
        k, d = feats(img)
        # try absolute (vs main ref) and relative (vs last good) registration
        res_abs = register(rk, rd, k, d)
        res_rel = register(last_good_k, last_good_d, k, d)
        use_abs = res_abs is not None and res_abs[3] >= 15
        if use_abs:
            ang, scale, (tx, ty), n_in, n_good = res_abs
        elif res_rel is not None and res_rel[3] >= 10:
            ang_r, scale_r, (tx_r, ty_r), n_in, n_good = res_rel
            ang = last_ang + ang_r
            tx, ty = last_abs_tx + tx_r, last_abs_ty + ty_r
            last_good_img, last_good_k, last_good_d, last_ang = img, k, d, ang
        else:
            rows.append((t, np.nan, np.nan, np.nan, np.nan))
            t += 1.0 / fps
            continue
        if use_abs:
            last_ang = ang
            last_abs_tx, last_abs_ty = tx, ty
            if res_abs[3] >= 40:  # strong absolute -> update relative anchor
                last_good_img, last_good_k, last_good_d = img, k, d
        rows.append((t, ang, tx, ty, n_in))
        t += 1.0 / fps
    arr = np.array(rows)
    np.savetxt(out, arr, fmt="%.3f %.5f %.2f %.2f %d")
    g = arr[~np.isnan(arr[:, 1])]
    print(f"# {len(arr)} samples, {np.isnan(arr[:,1]).sum()} failed")
    print(f"# roll: {g[:,1].min():+.2f} to {g[:,1].max():+.2f} deg | inliers med {np.median(g[:,4]):.0f}")

if __name__ == "__main__":
    main()
