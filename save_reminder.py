"""Save Now! - a small desktop reminder that nags you to save your work.

Shows a pop-up on a fixed interval (default 15 minutes). The interval can be
changed from the main window at any time.

Runs on Windows, macOS and Linux from the same source.
"""

import datetime
import json
import os
import sys
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "Save Now!"

DEFAULT_INTERVAL = 15   # minutes
MIN_INTERVAL = 1
MAX_INTERVAL = 480      # 8 hours
SNOOZE_MINUTES = 5

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

# Aqua draws native buttons and ignores -bg/-fg, so the interface is built from
# frames and labels instead. That keeps one look on every platform.
BG = "#1f2430"          # window background
FG = "#ffffff"          # primary text
MUTED = "#9aa4b8"       # secondary text
BODY = "#dfe4ee"        # body text
ACCENT = "#4c8bf5"      # primary button / countdown
ACCENT_HOVER = "#3a76d8"
SUBTLE = "#333b4d"      # secondary button
SUBTLE_HOVER = "#414b61"
BORDER = "#4a5468"
DIM = "#6b7488"         # countdown while paused

_FONT_FAMILY = None
_HAND_CURSOR = None


def hand(master):
    """The pointing-hand cursor name this Tk build accepts.

    macOS spells it 'pointinghand'. An unknown cursor name raises TclError at
    widget creation, which would take the whole interface down, so probe once
    and fall back to the default cursor if nothing is accepted.
    """
    global _HAND_CURSOR
    if _HAND_CURSOR is None:
        names = ["pointinghand", "hand2", ""] if IS_MAC else ["hand2", ""]
        for name in names:
            try:
                tk.Frame(master, cursor=name).destroy()
                _HAND_CURSOR = name
                break
            except tk.TclError:
                continue
        else:
            _HAND_CURSOR = ""
    return _HAND_CURSOR


def resource_path(name):
    """Locate a bundled file, both when run from source and when frozen."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def config_path():
    """Per-user settings file, so a shared copy of the app stays read-only."""
    if IS_WINDOWS:
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = os.path.join(root, "SaveNow")
    elif IS_MAC:
        folder = os.path.expanduser("~/Library/Application Support/SaveNow")
    else:
        root = (os.environ.get("XDG_CONFIG_HOME")
                or os.path.expanduser("~/.config"))
        folder = os.path.join(root, "savenow")

    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        return os.path.join(os.path.expanduser("~"), ".savenow_settings.json")
    return os.path.join(folder, "settings.json")


CONFIG_PATH = config_path()


def pick_font():
    """Choose a UI font that actually exists on this machine."""
    global _FONT_FAMILY
    if _FONT_FAMILY is not None:
        return _FONT_FAMILY

    from tkinter import font as tkfont

    if IS_MAC:
        prefs = ["SF Pro Text", "Helvetica Neue", "Lucida Grande", "Arial"]
    elif IS_WINDOWS:
        prefs = ["Segoe UI", "Tahoma", "Arial"]
    else:
        prefs = ["Ubuntu", "Cantarell", "DejaVu Sans", "Liberation Sans"]

    try:
        available = set(tkfont.families())
    except tk.TclError:
        available = set()

    for name in prefs:
        if name in available:
            _FONT_FAMILY = name
            return _FONT_FAMILY

    try:  # whatever Tk is already using
        _FONT_FAMILY = tkfont.nametofont("TkDefaultFont").actual("family")
    except Exception:
        _FONT_FAMILY = "Helvetica"
    return _FONT_FAMILY


def font(size, weight="normal"):
    return (pick_font(), size, weight)


def log_path():
    return os.path.join(os.path.dirname(CONFIG_PATH), "error.log")


def log_error(message):
    """Record a problem next to the settings file. Best effort, never raises."""
    try:
        with open(log_path(), "a", encoding="utf-8") as fh:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fh.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def install_error_logging(root):
    """Send errors to a log file instead of the missing stderr.

    A windowed build (no console) has sys.stderr set to None. Tk's default
    handler writes tracebacks there, so the write fails inside the error
    handler and takes the whole application down - the reminder just silently
    stops. Logging to a file keeps the app alive and leaves something to read.
    """
    def report(exc, value, tb):
        log_error("Callback error:\n"
                  + "".join(traceback.format_exception(exc, value, tb)))

    root.report_callback_exception = report

    def hook(exc, value, tb):
        log_error("Unhandled error:\n"
                  + "".join(traceback.format_exception(exc, value, tb)))

    sys.excepthook = hook


def load_settings():
    try:
        # utf-8-sig so a hand-edited file saved with a BOM still parses
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"interval": DEFAULT_INTERVAL, "sound": True, "start_minimized": False}

    interval = data.get("interval", DEFAULT_INTERVAL)
    try:
        interval = int(interval)
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL
    return {
        "interval": max(MIN_INTERVAL, min(MAX_INTERVAL, interval)),
        "sound": bool(data.get("sound", True)),
        "start_minimized": bool(data.get("start_minimized", False)),
    }


def save_settings(settings):
    # Write to a temporary file and swap it in, so being killed mid-write
    # cannot leave a half-written settings file behind.
    tmp = CONFIG_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except OSError:
        # a read-only folder shouldn't stop the reminder from working
        try:
            os.remove(tmp)
        except OSError:
            pass


class FlatButton(tk.Frame):
    """A button drawn from a frame and a label.

    tk.Button ignores background colours on macOS, which would leave white
    native buttons sitting on the dark panel. This looks the same everywhere.
    """

    def __init__(self, master, text, command, bg=SUBTLE, fg=BODY,
                 hover=SUBTLE_HOVER, width=None, size=10, weight="normal",
                 padx=12, pady=6):
        cursor = hand(master)
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, cursor=cursor)
        self._bg, self._hover = bg, hover
        self._command = command
        self._pressed = False

        self.label = tk.Label(
            self, text=text, bg=bg, fg=fg, font=font(size, weight),
            padx=padx, pady=pady, cursor=cursor,
        )
        if width is not None:
            self.label.config(width=width)
        self.label.pack(fill="both", expand=True)

        for widget in (self, self.label):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<Button-1>", self._on_press)
            widget.bind("<ButtonRelease-1>", self._on_release)

    def _paint(self, colour):
        self.config(bg=colour)
        self.label.config(bg=colour)

    def _on_enter(self, _event=None):
        self._paint(self._hover)

    def _on_leave(self, _event=None):
        self._pressed = False
        self._paint(self._bg)

    def _on_press(self, _event=None):
        self._pressed = True
        self._paint(self._bg)

    def _on_release(self, _event=None):
        if self._pressed:
            self._pressed = False
            self._paint(self._hover)
            self._command()

    def set_text(self, text):
        self.label.config(text=text)


class CheckRow(tk.Frame):
    """A checkbox built from labels, for the same reason as FlatButton."""

    def __init__(self, master, text, variable, command):
        cursor = hand(master)
        super().__init__(master, bg=BG, cursor=cursor)
        self.var = variable
        self.command = command

        self.box = tk.Label(
            self, width=2, bg=BG, fg=ACCENT, font=font(10, "bold"),
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=BORDER, cursor=cursor,
        )
        self.box.pack(side="left")
        self.text = tk.Label(
            self, text=text, bg=BG, fg=MUTED, font=font(9), cursor=cursor,
        )
        self.text.pack(side="left", padx=(8, 0))

        for widget in (self, self.box, self.text):
            widget.bind("<Button-1>", self._toggle)
        self._refresh()

    def _refresh(self):
        self.box.config(text="✓" if self.var.get() else " ")

    def _toggle(self, _event=None):
        self.var.set(not self.var.get())
        self._refresh()
        self.command()


class ReminderPopup(tk.Toplevel):
    """The 'Save Now!' pop-up. Stays on top until dismissed or snoozed."""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app

        self.title(APP_NAME)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.dismiss)

        wrap = tk.Frame(self, bg=BG, padx=36, pady=28)
        wrap.pack()

        tk.Label(
            wrap, text="Save Now!", bg=BG, fg=FG, font=font(30, "bold"),
        ).pack()
        tk.Label(
            wrap, text="Take a second and save your work.",
            bg=BG, fg=MUTED, font=font(11),
        ).pack(pady=(8, 22))

        buttons = tk.Frame(wrap, bg=BG)
        buttons.pack()
        FlatButton(
            buttons, "Saved it", self.dismiss, bg=ACCENT, fg=FG,
            hover=ACCENT_HOVER, size=11, weight="bold", padx=22, pady=8,
        ).pack(side="left", padx=(0, 10))
        FlatButton(
            buttons, f"Snooze {SNOOZE_MINUTES} min", self.snooze,
            size=11, padx=18, pady=8,
        ).pack(side="left")

        self._centre()
        self.bind("<Escape>", lambda _e: self.dismiss())
        self.bind("<Return>", lambda _e: self.dismiss())

        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except tk.TclError:
            pass

        # macOS can place a new window behind the active app, so re-assert it
        # a moment after it is mapped.
        self.after(150, self._raise_again)

        if self.app.sound.get():
            try:
                self.bell()
            except tk.TclError:
                pass

    def _raise_again(self):
        if not self.winfo_exists():
            return
        try:
            self.attributes("-topmost", True)
            self.lift()
        except tk.TclError:
            pass

    def _centre(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"+{x}+{y}")

    def dismiss(self):
        self.app.popup_closed(snooze_minutes=None)
        self.destroy()

    def snooze(self):
        self.app.popup_closed(snooze_minutes=SNOOZE_MINUTES)
        self.destroy()


class SaveReminderApp:
    def __init__(self, root):
        self.root = root
        settings = load_settings()

        self.interval = tk.IntVar(value=settings["interval"])
        self.sound = tk.BooleanVar(value=settings["sound"])
        self.start_minimized = tk.BooleanVar(value=settings["start_minimized"])
        self.running = True
        self._applied_interval = settings["interval"]
        self.seconds_left = self.interval.get() * 60
        self._tick_job = None
        self._popup = None

        self._build_ui()
        self._tick()

        if self.start_minimized.get():
            try:
                self.root.iconify()
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        r = self.root
        r.title(APP_NAME)
        r.configure(bg=BG)
        r.resizable(False, False)
        r.protocol("WM_DELETE_WINDOW", self.quit)

        outer = tk.Frame(r, bg=BG, padx=28, pady=22)
        outer.pack(fill="both", expand=True)

        tk.Label(
            outer, text="Save Now!", bg=BG, fg=FG, font=font(18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            outer, text="Reminds you to save your work on a schedule.",
            bg=BG, fg=MUTED, font=font(9),
        ).pack(anchor="w", pady=(2, 18))

        # --- frequency ---
        freq = tk.Frame(outer, bg=BG)
        freq.pack(fill="x")
        tk.Label(
            freq, text="Remind me every", bg=BG, fg=BODY, font=font(10),
        ).pack(side="left")

        self.spin = tk.Spinbox(
            freq, from_=MIN_INTERVAL, to=MAX_INTERVAL, textvariable=self.interval,
            width=5, font=font(11), justify="center", command=self.apply_interval,
            bg="#ffffff", fg="#1f2430", insertbackground="#1f2430",
            relief="flat", highlightthickness=1, highlightbackground=BORDER,
        )
        self.spin.pack(side="left", padx=8)
        self.spin.bind("<Return>", lambda _e: self.apply_interval())
        self.spin.bind("<FocusOut>", lambda _e: self.apply_interval())

        tk.Label(
            freq, text="minutes", bg=BG, fg=BODY, font=font(10),
        ).pack(side="left")

        presets = tk.Frame(outer, bg=BG)
        presets.pack(fill="x", pady=(10, 0))
        for minutes in (5, 10, 15, 30, 60):
            FlatButton(
                presets, f"{minutes}m",
                lambda m=minutes: self.set_interval(m),
                size=9, padx=10, pady=4,
            ).pack(side="left", padx=(0, 6))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=18)

        # --- countdown ---
        self.countdown = tk.Label(
            outer, text="", bg=BG, fg=ACCENT, font=font(26, "bold"),
        )
        self.countdown.pack()
        self.status = tk.Label(
            outer, text="until the next reminder", bg=BG, fg=MUTED, font=font(9),
        )
        self.status.pack(pady=(0, 16))

        # --- controls ---
        controls = tk.Frame(outer, bg=BG)
        controls.pack()
        self.pause_btn = FlatButton(
            controls, "Pause", self.toggle_running, bg=ACCENT, fg=FG,
            hover=ACCENT_HOVER, width=9, weight="bold",
        )
        self.pause_btn.pack(side="left", padx=(0, 8))
        FlatButton(
            controls, "Reset timer", self.reset_timer, width=9,
        ).pack(side="left", padx=(0, 8))
        FlatButton(
            controls, "Test pop-up", self.show_popup, width=9,
        ).pack(side="left")

        # --- options ---
        opts = tk.Frame(outer, bg=BG)
        opts.pack(fill="x", pady=(18, 0))
        CheckRow(opts, "Play a sound", self.sound, self.persist).pack(
            anchor="w", pady=(0, 4))
        CheckRow(opts, "Start minimised", self.start_minimized,
                 self.persist).pack(anchor="w")

        self._centre()

    def _centre(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 3
        self.root.geometry(f"+{x}+{y}")

    # ----------------------------------------------------------- actions ---
    def set_interval(self, minutes):
        self.interval.set(minutes)
        self.apply_interval()

    def apply_interval(self):
        """Read the spinbox, clamp it, restart the countdown if it changed."""
        try:
            minutes = int(self.spin.get())
        except (ValueError, tk.TclError):
            minutes = self._applied_interval
        minutes = max(MIN_INTERVAL, min(MAX_INTERVAL, minutes))
        self.interval.set(minutes)

        # FocusOut fires whenever the field loses focus, so only restart the
        # countdown when the value actually moved.
        if minutes != self._applied_interval:
            self._applied_interval = minutes
            self.seconds_left = minutes * 60
            self.persist()
        self._refresh_countdown()

    def persist(self):
        save_settings({
            "interval": self.interval.get(),
            "sound": self.sound.get(),
            "start_minimized": self.start_minimized.get(),
        })

    def reset_timer(self):
        self.seconds_left = self.interval.get() * 60
        self._refresh_countdown()

    def toggle_running(self):
        self.running = not self.running
        self.pause_btn.set_text("Pause" if self.running else "Resume")
        self.status.config(
            text="until the next reminder" if self.running else "paused"
        )
        self._refresh_countdown()

    def show_popup(self):
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.lift()
            self._popup.focus_force()
            return

        try:
            self._popup = ReminderPopup(self)
        except Exception:                                       # noqa: BLE001
            # If the styled pop-up cannot be built on this platform, still
            # deliver the reminder rather than skipping it silently. Catching
            # everything is deliberate: an untested platform must degrade to a
            # plain dialog, never stop reminding.
            self._popup = None
            log_error("Pop-up failed, using the plain dialog:\n"
                      + traceback.format_exc())
            try:
                messagebox.showinfo(
                    APP_NAME, "Save Now!\n\nTake a second and save your work.")
            except Exception:                                   # noqa: BLE001
                log_error("Fallback dialog also failed:\n"
                          + traceback.format_exc())
            self.popup_closed(snooze_minutes=None)

    def popup_closed(self, snooze_minutes):
        self._popup = None
        self.seconds_left = (snooze_minutes * 60 if snooze_minutes
                             else self.interval.get() * 60)
        self._refresh_countdown()

    def quit(self):
        if self._tick_job is not None:
            self.root.after_cancel(self._tick_job)
        self.persist()
        self.root.destroy()

    # ------------------------------------------------------------- timer ---
    def _tick(self):
        # The timer must survive anything. If a tick raises and is not caught,
        # it never reschedules and the app goes quiet without any sign.
        try:
            if self.running and self._popup is None:
                self.seconds_left -= 1
                if self.seconds_left <= 0:
                    self.seconds_left = self.interval.get() * 60
                    self.show_popup()
            self._refresh_countdown()
        except Exception:                                       # noqa: BLE001
            log_error("Timer error:\n" + traceback.format_exc())
        finally:
            try:
                self._tick_job = self.root.after(1000, self._tick)
            except tk.TclError:
                pass    # the window is gone; nothing left to schedule

    def _refresh_countdown(self):
        total = max(0, self.seconds_left)
        hours, rem = divmod(total, 3600)
        mins, secs = divmod(rem, 60)
        text = (f"{hours}:{mins:02d}:{secs:02d}" if hours
                else f"{mins:02d}:{secs:02d}")
        self.countdown.config(text=text, fg=ACCENT if self.running else DIM)


def apply_window_icon(root):
    """Windows uses the .ico; everything else gets the PNG via iconphoto.

    In a macOS .app the Dock icon comes from the bundled .icns instead.
    """
    if IS_WINDOWS:
        ico = resource_path("app_icon.ico")
        if os.path.exists(ico):
            try:
                root.iconbitmap(default=ico)
                return
            except tk.TclError:
                pass

    png = resource_path("app_icon.png")
    if os.path.exists(png):
        try:
            image = tk.PhotoImage(file=png)
            root.iconphoto(True, image)
            root._icon_image = image  # keep a reference alive
        except tk.TclError:
            pass


def main():
    if IS_WINDOWS:  # crisper text on high-DPI Windows displays
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    install_error_logging(root)
    apply_window_icon(root)

    app = SaveReminderApp(root)

    if IS_MAC:  # clicking the Dock icon should bring the window back
        def reopen():
            root.deiconify()
            root.lift()
        try:
            root.createcommand("tk::mac::ReopenApplication", reopen)
            root.createcommand("tk::mac::Quit", app.quit)
        except tk.TclError:
            pass

    root.mainloop()


if __name__ == "__main__":
    sys.exit(main())
