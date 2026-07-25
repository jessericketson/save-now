#!/usr/bin/env bash
#
# Builds "Save Now.app" on macOS - a shareable application bundle.
#
# Run this ON A MAC. PyInstaller cannot cross-compile, so a Mac build has to
# happen on macOS; the Windows .exe is built separately by build_exe.bat.
#
#   chmod +x build_app.sh
#   ./build_app.sh
#
# Options:
#   --check      run the environment checks only, build nothing
#   --no-smoke   skip the "does the built app actually launch" test
#   --help       show this message
#
# If anything fails, the script stops and explains what to do. Nothing is
# installed system-wide: PyInstaller goes into a local .venv-build folder.

set -euo pipefail

APP_NAME="Save Now"
BUNDLE_ID="com.savenow.reminder"
VENV_DIR=".venv-build"

RUN_SMOKE=1
CHECK_ONLY=0

# ---------------------------------------------------------------- output ---
if [ -t 1 ]; then
    C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'
    C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
    C_OK=""; C_WARN=""; C_ERR=""; C_DIM=""; C_OFF=""
fi

step() { printf '\n%s==> %s%s\n' "$C_DIM" "$1" "$C_OFF"; }
ok()   { printf '%s  ok%s  %s\n' "$C_OK" "$C_OFF" "$1"; }
warn() { printf '%s  warning%s  %s\n' "$C_WARN" "$C_OFF" "$1" >&2; }
die()  { printf '\n%serror%s  %s\n' "$C_ERR" "$C_OFF" "$1" >&2; exit 1; }

# ----------------------------------------------------------------- checks ---
check_macos() {
    if [ "$(uname -s)" != "Darwin" ]; then
        die "This script builds the macOS app and must be run on macOS.
       On Windows use build_exe.bat instead."
    fi
    ok "macOS $(sw_vers -productVersion 2>/dev/null || echo '(version unknown)') on $(uname -m)"
}

# Print the first usable Python, or return 1. Explicit install locations come
# before bare 'python3': on a Mac without Xcode tools /usr/bin/python3 is only
# a stub that pops up a developer-tools installer when run.
find_python() {
    local candidates=() candidate
    [ -n "${PYTHON:-}" ] && candidates+=("$PYTHON")
    candidates+=(
        /opt/homebrew/bin/python3
        /usr/local/bin/python3
        /Library/Frameworks/Python.framework/Versions/Current/bin/python3
        python3 python3.13 python3.12 python3.11 python3.10 python3.9 python3.8
        python
    )

    for candidate in "${candidates[@]}"; do
        command -v "$candidate" >/dev/null 2>&1 || continue
        "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' \
            >/dev/null 2>&1 || continue
        "$candidate" -c 'import tkinter' >/dev/null 2>&1 || continue
        printf '%s\n' "$candidate"
        return 0
    done
    return 1
}

check_python() {
    if ! PY="$(find_python)"; then
        die "No Python 3.8+ with tkinter was found.

       Easiest fix - install the official build, which bundles tkinter:
           https://www.python.org/downloads/macos/

       If you use Homebrew, tkinter is a separate package:
           brew install python python-tk

       Then run this script again. To point it at a specific interpreter:
           PYTHON=/path/to/python3 ./build_app.sh"
    fi
    export PY
    ok "Python $("$PY" -c 'import sys; print(sys.version.split()[0])') at $(command -v "$PY")"

    local tkver
    tkver="$("$PY" -c 'import tkinter; print(tkinter.TkVersion)')"
    if "$PY" -c 'import sys, tkinter; sys.exit(0 if tkinter.TkVersion >= 8.6 else 1)'; then
        ok "Tk $tkver"
    else
        # 8.5 is the ancient system Tk; it has known crashes on modern macOS.
        die "Tk $tkver is too old and is unreliable on current macOS.
       Install Python from python.org (it ships Tk 8.6), then re-run."
    fi
}

check_sources() {
    local missing=0 f
    for f in save_reminder.py make_icon.py; do
        [ -f "$f" ] || { warn "missing $f"; missing=1; }
    done
    [ "$missing" -eq 0 ] || die "Run this script from the folder containing the app source."
    "$PY" -c 'import ast,sys; [ast.parse(open(f,encoding="utf-8").read(), f) for f in ("save_reminder.py","make_icon.py")]' \
        || die "The Python source does not parse."
    ok "sources present and parse cleanly"
}

# ------------------------------------------------------------ build steps ---
setup_venv() {
    step "Setting up a local build environment"
    if [ ! -x "$VENV_DIR/bin/python" ]; then
        # A venv keeps PyInstaller out of the system Python, which also avoids
        # Homebrew's "externally-managed-environment" pip refusal (PEP 668).
        "$PY" -m venv "$VENV_DIR" || die "Could not create a virtualenv at $VENV_DIR.
       Try:  $PY -m ensurepip --upgrade"
    fi
    VPY="$VENV_DIR/bin/python"
    export VPY

    "$VPY" -c 'import tkinter' >/dev/null 2>&1 \
        || die "The build virtualenv cannot import tkinter.
       Delete $VENV_DIR and re-run, or install python-tk for $PY."

    "$VPY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
    "$VPY" -m pip install --quiet --upgrade pyinstaller \
        || die "Could not install PyInstaller into $VENV_DIR.
       Check your network connection and try again."
    ok "PyInstaller $("$VPY" -m PyInstaller --version 2>/dev/null || echo '?') ready"
}

make_icons() {
    step "Generating icons"
    "$VPY" make_icon.py >/dev/null || die "Icon generation failed."

    # Prefer Apple's own iconutil - it produces a guaranteed-valid .icns.
    # The hand-written one in make_icon.py is the fallback.
    if command -v iconutil >/dev/null 2>&1; then
        rm -rf build/AppIcon.iconset
        mkdir -p build
        if "$VPY" make_icon.py --iconset build/AppIcon.iconset >/dev/null \
           && iconutil -c icns build/AppIcon.iconset -o app_icon.icns 2>/dev/null; then
            ok "app_icon.icns built with iconutil"
        else
            warn "iconutil failed; keeping the built-in .icns"
        fi
    else
        warn "iconutil not found; using the built-in .icns"
    fi

    if command -v sips >/dev/null 2>&1; then
        if sips -g pixelWidth app_icon.icns >/dev/null 2>&1; then
            ok "app_icon.icns validates"
        else
            warn "macOS could not read app_icon.icns - the app will build but may show a blank icon"
        fi
    fi
}

clean_previous() {
    step "Clearing previous build output"
    # A running copy would hold files open; stale bytecode could be bundled
    # instead of the current source.
    pkill -f "$APP_NAME.app/Contents/MacOS/$APP_NAME" 2>/dev/null || true
    rm -rf build dist __pycache__ "$APP_NAME.spec"
    ok "cleaned"
}

build_bundle() {
    step "Building the app bundle"
    # Note the ':' data separator - macOS uses ':' where Windows uses ';'.
    "$VPY" -m PyInstaller \
        --windowed \
        --name "$APP_NAME" \
        --icon app_icon.icns \
        --add-data "app_icon.png:." \
        --osx-bundle-identifier "$BUNDLE_ID" \
        --clean \
        --noconfirm \
        save_reminder.py \
        || die "PyInstaller failed. The output above should say why."

    [ -d "dist/$APP_NAME.app" ] || die "The build finished but dist/$APP_NAME.app is missing."
    ok "dist/$APP_NAME.app"
}

sign_bundle() {
    step "Signing"
    # An ad-hoc signature is free and needs no Apple account. On Apple Silicon
    # an unsigned bundle can be killed outright, so this matters.
    if codesign --force --deep --sign - "dist/$APP_NAME.app" 2>/dev/null; then
        if codesign --verify --deep --strict "dist/$APP_NAME.app" 2>/dev/null; then
            ok "ad-hoc signed and verified"
        else
            warn "signed, but verification complained - usually still fine"
        fi
    else
        warn "could not ad-hoc sign; the app may need right-click -> Open on this Mac too"
    fi
    # The freshly built copy shouldn't be treated as downloaded.
    xattr -dr com.apple.quarantine "dist/$APP_NAME.app" 2>/dev/null || true
}

smoke_test() {
    [ "$RUN_SMOKE" -eq 1 ] || return 0
    step "Checking the app actually launches"
    local proc="dist/$APP_NAME.app/Contents/MacOS/$APP_NAME"

    if ! open "dist/$APP_NAME.app" 2>/dev/null; then
        warn "could not launch the app automatically - open it by hand to check"
        return 0
    fi

    local waited=0
    while [ "$waited" -lt 15 ]; do
        if pgrep -f "$proc" >/dev/null 2>&1; then
            sleep 3   # let it get past any early crash
            if pgrep -f "$proc" >/dev/null 2>&1; then
                ok "it launches and stays running"
                pkill -f "$proc" 2>/dev/null || true
                return 0
            fi
            break
        fi
        sleep 1
        waited=$((waited + 1))
    done

    warn "the app did not stay running. To see the error, run:
           '$PWD/dist/$APP_NAME.app/Contents/MacOS/$APP_NAME'
         That prints the crash to the terminal."
}

package() {
    step "Packaging for sharing"
    rm -f "dist/$APP_NAME.zip"
    # ditto preserves the bundle structure; a plain zip can corrupt the .app.
    ditto -c -k --keepParent "dist/$APP_NAME.app" "dist/$APP_NAME.zip" \
        || die "Could not create the zip."
    ok "dist/$APP_NAME.zip ($(du -h "dist/$APP_NAME.zip" | cut -f1 | tr -d ' '))"
    if command -v shasum >/dev/null 2>&1; then
        printf '  %sSHA-256 %s%s\n' "$C_DIM" "$(shasum -a 256 "dist/$APP_NAME.zip" | cut -d' ' -f1)" "$C_OFF"
    fi
}

summary() {
    cat <<EOF

$(printf '%sBuild complete.%s' "$C_OK" "$C_OFF")

  App:   $PWD/dist/$APP_NAME.app
  Share: $PWD/dist/$APP_NAME.zip

Send the zip, not the .app folder.

On the Mac that receives it, the first launch is blocked because the app is
not notarised (that needs a paid Apple Developer account). To open it:

  right-click the app -> Open -> Open

Only needed once. If macOS refuses outright, run:

  xattr -dr com.apple.quarantine "/Applications/$APP_NAME.app"

Note: this build matches this Mac's architecture ($(uname -m)). An Apple
Silicon build will not run on an Intel Mac.
EOF
}

usage() {
    sed -n '3,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

main() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --check)    CHECK_ONLY=1 ;;
            --no-smoke) RUN_SMOKE=0 ;;
            --help|-h)  usage; exit 0 ;;
            *)          die "Unknown option: $1  (try --help)" ;;
        esac
        shift
    done

    cd "$(dirname "${BASH_SOURCE[0]}")"

    step "Checking the environment"
    check_macos
    check_python
    check_sources

    if [ "$CHECK_ONLY" -eq 1 ]; then
        printf '\n%sEnvironment looks good.%s Re-run without --check to build.\n' "$C_OK" "$C_OFF"
        exit 0
    fi

    setup_venv
    clean_previous
    make_icons
    build_bundle
    sign_bundle
    smoke_test
    package
    summary
}

# Only run when executed, so the functions above can be sourced and tested.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
