"""Builds the deployable web/ folder from save-now-web.html.

save-now-web.html holds the app itself. This wraps it into a complete HTML
document and adds everything a real web host needs: a manifest so the page can
be installed as its own window, icons, and a service worker for offline use.

    python make_web.py

Writes web/index.html, web/manifest.webmanifest, web/sw.js and the icons.
Only the standard library is used, so there is nothing to install.
"""

import json
import os
import re
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "save-now-web.html")
OUT_DIR = os.path.join(HERE, "web")

APP_NAME = "Save Now!"
DESCRIPTION = "A reminder to save your work, on a schedule you choose."
THEME_LIGHT = "#eef1f6"
THEME_DARK = "#14181f"
CACHE_VERSION = "savenow-v1"

ACCENT = (0x5B, 0x93, 0xF5)
WHITE = (0xFF, 0xFF, 0xFF)


# --------------------------------------------------------------- icons ---
# A rounded blue square with a floppy-disk mark, drawn pixel by pixel and
# written straight out as PNG. No image library required.
def _rounded(x, y, size):
    r = size * 0.22
    m = size * 0.04
    lo, hi = m, size - m
    if not (lo <= x <= hi and lo <= y <= hi):
        return False
    cx = min(max(x, lo + r), hi - r)
    cy = min(max(y, lo + r), hi - r)
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= r * r


def _floppy(u, v):
    if not (0.26 <= u <= 0.74 and 0.26 <= v <= 0.74):
        return False
    if 0.30 <= v <= 0.44:                       # shutter, with a notch
        return 0.34 <= u <= 0.66 and not (0.56 <= u <= 0.62)
    if 0.52 <= v <= 0.70:                       # label
        return 0.32 <= u <= 0.68
    return u <= 0.29 or u >= 0.71 or v <= 0.29 or v >= 0.71   # body outline


def _chunk(tag, payload):
    body = tag + payload
    return (struct.pack(">I", len(payload)) + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def png_bytes(size):
    rows = []
    for y in range(size):
        row = bytearray(b"\x00")                # filter type 0
        py = y + 0.5
        v = py / size
        for x in range(size):
            px = x + 0.5
            if not _rounded(px, py, size):
                row += b"\x00\x00\x00\x00"
            elif _floppy(px / size, v):
                row += bytes(WHITE) + b"\xff"
            else:
                row += bytes(ACCENT) + b"\xff"
        rows.append(bytes(row))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)   # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
            + _chunk(b"IEND", b""))


# The same mark as a scalable favicon.
FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
    "%3Crect width='100' height='100' rx='22' fill='%235b93f5'/%3E"
    "%3Cpath d='M26 26h48v48H26z' fill='none' stroke='%23fff' stroke-width='6'/%3E"
    "%3Cpath d='M36 30h30v14H36z' fill='%23fff'/%3E"
    "%3Cpath d='M56 30h6v14h-6z' fill='%235b93f5'/%3E"
    "%3Cpath d='M34 52h32v18H34z' fill='%23fff'/%3E"
    "%3C/svg%3E"
)

SERVICE_WORKER = """\
// Keeps the reminder working without a connection.
const CACHE = "%s";
const ASSETS = ["./", "./index.html", "./manifest.webmanifest",
                "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

// Network first, so a new deploy is picked up straight away; the cache is
// only the fallback when offline.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((c) => c.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match("./index.html")))
  );
});
""" % CACHE_VERSION

REGISTER_SW = """
<script>
  // Offline support and "install to dock". Harmless where unsupported.
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("./sw.js").catch(function () {});
    });
  }
</script>
"""


def build():
    with open(SOURCE, "r", encoding="utf-8") as fh:
        source = fh.read()

    match = re.search(r"<title>(.*?)</title>", source, re.S)
    if not match:
        print("error: no <title> found in save-now-web.html", file=sys.stderr)
        return 1
    title = match.group(1).strip()
    body = source.replace(match.group(0), "", 1).strip()

    if "<!doctype" in body.lower() or "<body" in body.lower():
        print("error: save-now-web.html already has a document wrapper",
              file=sys.stderr)
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{DESCRIPTION}">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="{THEME_LIGHT}" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="{THEME_DARK}" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{FAVICON}">
<link rel="apple-touch-icon" href="./icon-192.png">
<link rel="manifest" href="./manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{APP_NAME}">
<meta property="og:title" content="{APP_NAME}">
<meta property="og:description" content="{DESCRIPTION}">
<meta property="og:type" content="website">
</head>
<body>
{body}
{REGISTER_SW.strip()}
</body>
</html>
"""

    manifest = {
        "name": APP_NAME,
        "short_name": "Save Now",
        "description": DESCRIPTION,
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": THEME_DARK,
        "theme_color": THEME_DARK,
        "icons": [
            {"src": "./icon-192.png", "sizes": "192x192", "type": "image/png",
             "purpose": "any"},
            {"src": "./icon-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "any"},
        ],
    }

    written = []
    for name, data in (
        ("index.html", document.encode("utf-8")),
        ("manifest.webmanifest", json.dumps(manifest, indent=2).encode("utf-8")),
        ("sw.js", SERVICE_WORKER.encode("utf-8")),
        ("icon-192.png", png_bytes(192)),
        ("icon-512.png", png_bytes(512)),
    ):
        path = os.path.join(OUT_DIR, name)
        with open(path, "wb") as fh:
            fh.write(data)
        written.append((name, len(data)))

    for name, size in written:
        print(f"  web/{name} ({size:,} bytes)")
    print(f"built {len(written)} files into {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
