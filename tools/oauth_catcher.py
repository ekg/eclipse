#!/usr/bin/env python3
"""One-shot OAuth redirect catcher: prints OAUTH_CODE=... and serves a
'you can close this tab' page."""
import http.server, urllib.parse, sys

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(q.query)
        if "code" in params:
            print(f"OAUTH_CODE={params['code'][0]}", flush=True)
            body = b"<html><body style=\"font-family:sans-serif;background:#111;color:#eee;text-align:center;padding-top:40px\"><h2>&#10004; Token received</h2><p>You can close this tab now.</p></body></html>"
            self.send_response(200)
        elif "error" in params:
            print(f"OAUTH_ERROR={params['error'][0]}", flush=True)
            body = b"<html><body><h2>Consent failed - tell the terminal.</h2></body></html>"
            self.send_response(400)
        else:
            body = b"waiting..."
            self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass

http.server.HTTPServer(("127.0.0.1", 53682), H).serve_forever()
