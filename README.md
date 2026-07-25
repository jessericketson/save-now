# Save Now!

A small desktop reminder that pops up every 15 minutes and tells you to save
your work. The interval is adjustable from the main window.

One codebase runs on **Windows**, **macOS** and **Linux**.

## Using it

- **Windows:** run `dist\Save Now.exe`
- **macOS:** run `Save Now.app` (build it first — see below)
- **From source, anywhere:** `python save_reminder.py`

The main window shows a live countdown to the next reminder, and lets you:

- **Set the frequency** — type a number of minutes (1–480), use the arrows, or
  hit one of the `5m / 10m / 15m / 30m / 60m` preset buttons.
- **Pause / Resume** — stop the reminders without closing the app.
- **Reset timer** — start the current interval over.
- **Test pop-up** — see what the reminder looks like right now.
- **Play a sound** — a chime when the pop-up appears (on by default).
- **Start minimised** — open straight to the taskbar/Dock next time.

When the timer runs out, a pop-up appears centred and on top of other windows:

- **Saved it** — dismiss it and start the next interval. (`Enter` or `Esc` also
  work.)
- **Snooze 5 min** — remind me again shortly.

The countdown pauses while a pop-up is on screen, so an ignored reminder never
stacks up a queue of them.

Minimise the window to get it out of the way — closing it exits the app.

## Building and sharing

### Windows

```
build_exe.bat
```

Produces `dist\Save Now.exe`, a self-contained ~10 MB file. Copy it to any
64-bit Windows machine and double-click — no Python, no install.

> Windows SmartScreen may warn about an unrecognised publisher the first time
> someone runs it, because the exe isn't code-signed. Choosing *More info →
> Run anyway* clears it, and the warning doesn't reappear.

### macOS

**This must be run on a Mac.** PyInstaller cannot cross-compile, so a macOS
build cannot be produced from Windows.

```
chmod +x build_app.sh
./build_app.sh
```

Produces `dist/Save Now.app` plus `dist/Save Now.zip` for sharing. Send the
**zip** — it is created with `ditto`, which preserves the bundle structure that
a plain zip can corrupt. Recipients unzip it and drag the app to
`/Applications`.

Requires Python 3.8+ with tkinter. The python.org installer includes it; with
Homebrew you also need `brew install python-tk`.

> The app isn't code-signed or notarised, so the first launch on someone else's
> Mac is blocked by Gatekeeper. They should **right-click the app → Open**,
> then confirm — after that it opens normally. Alternatively:
> `xattr -dr com.apple.quarantine "/Applications/Save Now.app"`.
>
> Signing and notarising requires a paid Apple Developer account.

### Starting it automatically

- **Windows:** press `Win+R`, enter `shell:startup`, and drop a shortcut to the
  exe in the folder that opens.
- **macOS:** System Settings → General → Login Items → **+**, and add the app.

Tick **Start minimised** in the app so it opens quietly.

## The browser version

`save-now-web.html` is the same reminder as a web page — no install, no
Gatekeeper warning, works on any machine. It is the easiest thing to share.

```
python make_web.py
```

builds the deployable site into `web/`: a complete HTML document, a web app
manifest and icons (so it can be installed to the Dock or taskbar), and a
service worker so it keeps working offline.

`web/` is committed so Vercel can serve it with no build step. **After editing
`save-now-web.html`, re-run `make_web.py` and commit `web/` again**, or the
deployed site will lag behind.

Deployment settings live in `vercel.json` — it just points Vercel at `web/`.

The one trade-off versus the desktop app: the tab has to stay open. Turning on
"Also show a desktop notification" lets the reminder reach you while you are
working in another window.

## Files

| File | Purpose |
| --- | --- |
| `save_reminder.py` | The whole application, cross-platform |
| `make_icon.py` | Generates the `.ico`, `.icns` and `.png` icons |
| `build_exe.bat` | Builds the Windows exe |
| `build_app.sh` | Builds the macOS app bundle (run on a Mac) |
| `Save Now.bat` | Runs from source on Windows, without a console window |

## Notes on the macOS build

Two things the shared code does specifically for macOS:

- The interface is drawn from frames and labels rather than `tk.Button` and
  `tk.Checkbutton`. Aqua renders those natively and **ignores background
  colours**, which would leave white buttons sitting on the dark panel.
- Settings are stored in `~/Library/Application Support/SaveNow/settings.json`
  (Windows uses `%APPDATA%\SaveNow`, Linux `~/.config/savenow`), so the app
  itself stays read-only and is safe to share.

The UI font is chosen at runtime from what the system actually has — SF Pro
Text on macOS, Segoe UI on Windows.
