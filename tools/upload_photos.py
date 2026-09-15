#!/usr/bin/env python3
"""Upload videos to Google Photos via the Library API (append-only friendly:
upload bytes -> mediaItems:batchCreate into the library, no album calls).
Reads OAuth credentials from the rclone gphotos remote config.
Usage: upload_photos.py <file1> [file2 ...]
"""
import subprocess, json, sys, os, configparser, time

cfg = configparser.ConfigParser()
cfg.read(os.path.expanduser("~/.config/rclone/rclone.conf"))
CLIENT_ID = cfg["gphotos"]["client_id"]
CLIENT_SECRET = cfg["gphotos"]["client_secret"]
REFRESH = json.loads(cfg["gphotos"]["token"])["refresh_token"]

def access_token():
    r = subprocess.run(["curl", "-s", "-X", "POST", "https://oauth2.googleapis.com/token",
                        "-d", f"client_id={CLIENT_ID}",
                        "-d", f"client_secret={CLIENT_SECRET}",
                        "-d", f"refresh_token={REFRESH}",
                        "-d", "grant_type=refresh_token"],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)["access_token"]

TOK = access_token()
print("access token refreshed", flush=True)

def upload(path):
    name = os.path.basename(path)
    size = os.path.getsize(path)
    print(f"uploading {name} ({size/1e6:.0f} MB) ...", flush=True)
    t0 = time.time()
    p = subprocess.run(["curl", "-s", "-X", "POST",
                        "https://photoslibrary.googleapis.com/v1/uploads",
                        "-H", f"Authorization: Bearer {TOK}",
                        "-H", "Content-Type: application/octet-stream",
                        "-H", "X-Goog-Upload-Protocol: RAW",
                        "-H", f"X-Goog-Upload-File-Name: {name}",
                        "--data-binary", f"@{path}"],
                       capture_output=True, text=True, check=True)
    token = p.stdout.strip()
    if not token or token.startswith("{"):
        print(f"UPLOAD_FAILED {name}: {p.stdout[:300]}", flush=True)
        return False
    mbps = size / 1e6 / (time.time() - t0)
    print(f"  upload token obtained ({mbps:.1f} MB/s), creating media item ...", flush=True)
    body = json.dumps({"newMediaItems": [
        {"description": "2026-08-12 total solar eclipse - stabilized",
         "simpleMediaItem": {"uploadToken": token, "fileName": name}}]})
    p = subprocess.run(["curl", "-s", "-X", "POST",
                        "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate",
                        "-H", f"Authorization: Bearer {TOK}",
                        "-H", "Content-Type: application/json",
                        "-d", body],
                       capture_output=True, text=True, check=True)
    res = json.loads(p.stdout)
    for item in res.get("newMediaItemResults", []):
        st = item.get("status", {})
        if st.get("code") == 0 or "SUCCESS" in str(st.get("code", "")) or st.get("status") == "OK" or "mediaItem" in item:
            mi = item.get("mediaItem", {})
            print(f"UPLOAD_DONE {name}: id={mi.get('id','?')} "
                  f"({mi.get('mediaMetadata',{}).get('width','?')}x{mi.get('mediaMetadata',{}).get('height','?')})",
                  flush=True)
            return True
    print(f"UPLOAD_FAILED {name}: {p.stdout[:400]}", flush=True)
    return False

ok = all(upload(f) for f in sys.argv[1:]) if sys.argv[1:] else False
print("ALL_DONE" if ok else "SOME_FAILED", flush=True)
sys.exit(0 if ok else 1)
