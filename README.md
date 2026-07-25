# Save Now!

A reminder to save your work, on a schedule you choose. It runs in the
browser — nothing to install.

**Live:** deployed on Vercel from this repository.

## What it does

Set an interval and leave the tab open. When the time is up, a full-screen
reminder appears; dismiss it and the countdown starts again.

- **Any interval from 1 to 480 minutes**, by typing or with the `5 / 10 / 15 /
  30 / 60` preset buttons
- **Pause, resume and reset** the countdown at any time
- **Snooze 5 minutes** when a reminder catches you mid-thought
- **A sound** when the reminder appears (optional)
- **Desktop notifications** (optional) so the reminder reaches you while you
  are working in another window
- Your settings are remembered on that browser
- Light and dark themes, following your system

The countdown is measured against a target time rather than by counting
seconds, so it stays accurate when the browser throttles a background tab or
the machine goes to sleep.

### Install it as an app

In Chrome or Edge, use the install button in the address bar. The page then
opens in its own window, appears in the Dock or taskbar, and works offline.

## Repository layout

| File | Purpose |
| --- | --- |
| `save-now-web.html` | The app itself — all the markup, styles and logic |
| `make_web.py` | Build script: turns the above into the deployable `web/` folder |
| `web/` | What Vercel serves. Generated, but committed on purpose |
| `vercel.json` | Points Vercel at `web/`. No build step, no dependencies |

## Making changes

Edit `save-now-web.html`, then:

```
python make_web.py
```

That regenerates `web/` — a complete HTML document, a web app manifest, the
icons, and a service worker for offline use. It uses only the Python standard
library, so there is nothing to install.

**Commit `web/` along with your change**, or the deployed site will lag behind
the source. Pushing to `main` redeploys automatically.

## Why the build step

`save-now-web.html` has no `<!doctype>`, `<head>` or `<body>` of its own, so
`make_web.py` wraps it into a full document and adds the character set,
viewport, theme colours, manifest link and icons that a real host needs. Keeping
one source file avoids maintaining two copies of the same app.
