"""Serves app/static with the same Content-Security-Policy as the real app, for the browser scripts of scripts/dev
(ui_smoke.py and screenshots.py): the API is not served, the scripts answer /api calls themselves in Playwright."""
import functools
import http.server
import pathlib
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
# Same as SECURITY_HEADERS in app/main.py: keep in sync, the point is to catch inline scripts and styles.
CSP = ("default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self'; "
       "script-src 'self'; frame-ancestors 'none'")


def start_server(port):
    site = pathlib.Path(tempfile.mkdtemp(prefix="melomancer-ui-"))
    (site / "static").symlink_to(ROOT / "app" / "static")
    (site / "index.html").write_text((ROOT / "app/static/index.html").read_text(encoding="utf-8").replace("__VERSION__", "test"),
                                     encoding="utf-8")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Content-Security-Policy", CSP)
            super().end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
