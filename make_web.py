"""Builds the deployable web/ folder from save-now-web.html.

save-now-web.html is written for the Artifact platform, which supplies the
<!doctype>, <head> and <body> wrapper itself. A real web host does not, so
this wraps the same markup into a complete document rather than keeping a
second copy of the app that could drift out of step.

    python make_web.py

Writes web/index.html, web/manifest.webmanifest, web/sw.js and the PWA icons.
"""

import json
import os
import re
import sys

import make_icon

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "save-now-web.html")
OUT_DIR = os.path.join(HERE, "web")

APP_NAME = "Save Now!"
DESCRIPTION = "A reminder to save your work, on a schedule you choose."
THEME_LIGHT = "#eef1f6"
THEME_DARK = "#14181f"
CACHE_VERSION = "savenow-v1"

# The floppy-disk mark, as a scalable favicon. Mirrors app_icon.png.
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
        ("icon-192.png", make_icon.png_bytes(192)),
        ("icon-512.png", make_icon.png_bytes(512)),
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
