"""Generates the app icons: app_icon.ico (Windows), app_icon.icns (macOS)
and app_icon.png (Linux / Tk window icon).

Pure standard library - the ICO, PNG and ICNS containers are written directly
so no image library is needed to build the app on any platform.

Usage:
    python make_icon.py                  write the three icon files
    python make_icon.py --iconset DIR    write an .iconset folder for iconutil

The --iconset form lets the macOS build hand the PNGs to Apple's own iconutil,
which produces a guaranteed-valid .icns. The hand-written one is the fallback.
"""

import os
import struct
import sys
import zlib

BG = (0x4C, 0x8B, 0xF5)      # button blue, RGB
FG = (0xFF, 0xFF, 0xFF)      # white

ICO_SIZES = (16, 32, 48, 64, 128, 256)
PNG_SIZE = 256

# macOS icon types -> pixel size. Everything here carries PNG data, which
# macOS 10.7+ accepts.
ICNS_TYPES = (
    (b"icp4", 16),
    (b"icp5", 32),
    (b"ic11", 32),    # 16pt @2x
    (b"ic12", 64),    # 32pt @2x
    (b"ic07", 128),
    (b"ic13", 256),   # 128pt @2x
    (b"ic08", 256),
    (b"ic14", 512),   # 256pt @2x
    (b"ic09", 512),
)

_cache = {}


def _rounded(x, y, size):
    """True if the pixel is inside a rounded square covering the canvas."""
    r = size * 0.22
    m = size * 0.04                      # small margin so edges stay clean
    lo, hi = m, size - m
    cx = min(max(x, lo + r), hi - r)
    cy = min(max(y, lo + r), hi - r)
    if not (lo <= x <= hi and lo <= y <= hi):
        return False
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= r * r


def _floppy(u, v):
    """True if the normalised (0..1) point is part of the white disk glyph."""
    if not (0.26 <= u <= 0.74 and 0.26 <= v <= 0.74):
        return False
    # shutter (top rectangle) with a notch cut out of its right side
    if 0.30 <= v <= 0.44:
        return 0.34 <= u <= 0.66 and not (0.56 <= u <= 0.62)
    # label (bottom rectangle)
    if 0.52 <= v <= 0.70:
        return 0.32 <= u <= 0.68
    # body outline
    return u <= 0.29 or u >= 0.71 or v <= 0.29 or v >= 0.71


def rgba_rows(size):
    """Top-down rows of RGBA bytes. Cached - several formats reuse these."""
    if size in _cache:
        return _cache[size]

    rows = []
    for y in range(size):
        row = bytearray()
        py = y + 0.5
        v = py / size
        for x in range(size):
            px = x + 0.5
            if not _rounded(px, py, size):
                row += b"\x00\x00\x00\x00"
            elif _floppy(px / size, v):
                row += bytes((FG[0], FG[1], FG[2], 0xFF))
            else:
                row += bytes((BG[0], BG[1], BG[2], 0xFF))
        rows.append(bytes(row))

    _cache[size] = rows
    return rows


# ----------------------------------------------------------------- PNG ---
def _chunk(tag, payload):
    body = tag + payload
    return (struct.pack(">I", len(payload)) + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def png_bytes(size):
    rows = rgba_rows(size)
    raw = b"".join(b"\x00" + row for row in rows)   # filter type 0 per scanline
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(raw, 9))
            + _chunk(b"IEND", b""))


# ----------------------------------------------------------------- ICO ---
def _ico_image(size):
    """BITMAPINFOHEADER + bottom-up BGRA pixels + empty AND mask."""
    rows = rgba_rows(size)
    pixels = bytearray()
    for row in reversed(rows):                      # ICO stores bottom-up
        for i in range(0, len(row), 4):
            r, g, b, a = row[i:i + 4]
            pixels += bytes((b, g, r, a))           # BGRA

    header = struct.pack(
        "<IiiHHIIiiII",
        40,                 # header size
        size, size * 2,     # width, height (doubled: XOR + AND masks)
        1, 32,              # planes, bits per pixel
        0, size * size * 4,
        0, 0, 0, 0,
    )
    and_mask = b"\x00" * (((size + 31) // 32) * 4 * size)
    return header + bytes(pixels) + and_mask


def ico_bytes():
    images = [_ico_image(s) for s in ICO_SIZES]
    out = struct.pack("<HHH", 0, 1, len(ICO_SIZES))
    offset = 6 + 16 * len(ICO_SIZES)
    for size, blob in zip(ICO_SIZES, images):
        dim = size if size < 256 else 0             # 0 means 256
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                           len(blob), offset)
        offset += len(blob)
    return out + b"".join(images)


# ---------------------------------------------------------------- ICNS ---
def icns_bytes():
    entries = b""
    for tag, size in ICNS_TYPES:
        data = png_bytes(size)
        entries += tag + struct.pack(">I", len(data) + 8) + data
    return b"icns" + struct.pack(">I", len(entries) + 8) + entries


# The exact file names Apple's iconutil expects inside a .iconset folder.
ICONSET = (
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
)


def write_iconset(folder):
    os.makedirs(folder, exist_ok=True)
    for name, size in ICONSET:
        data = png_bytes(size)
        with open(os.path.join(folder, name), "wb") as fh:
            fh.write(data)
        print(f"  {name} ({size}x{size}, {len(data):,} bytes)")
    print(f"wrote {len(ICONSET)} images to {folder}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "--iconset":
        if len(argv) < 2:
            print("usage: make_icon.py --iconset DIR", file=sys.stderr)
            return 2
        write_iconset(argv[1])
        return 0

    if argv:
        print(f"unknown argument: {argv[0]}", file=sys.stderr)
        return 2

    here = os.path.dirname(os.path.abspath(__file__))
    for name, data in (
        ("app_icon.ico", ico_bytes()),
        ("app_icon.png", png_bytes(PNG_SIZE)),
        ("app_icon.icns", icns_bytes()),
    ):
        path = os.path.join(here, name)
        with open(path, "wb") as fh:
            fh.write(data)
        print(f"wrote {name} ({len(data):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
