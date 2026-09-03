#!/usr/bin/env python3
"""Render weapon sprites from editable text grids into PNGs.

Zero dependencies: PNGs are written with the standard library only.

Inputs  : assets/weapons/src/<id>.txt   (palette header + 32 rows of glyphs)
Outputs : assets/weapons/<id>.png                 1x sprite, transparent
          assets/weapons/preview/<id>@8x.png      8x nearest-neighbour preview
          assets/weapons/spritesheet.png          all sprites on one sheet
          assets/weapons/spritesheet.json         atlas (id -> x, y, w, h)
          assets/weapons/preview/contact-sheet.png  all sprites, scaled, on a dark ground

Grid format
-----------
    # any comment
    . = none            <- transparent (the '.' glyph is always transparent)
    o = #14101c         <- glyph = hex colour (6 or 8 digit, 8th pair = alpha)
    ---                 <- separator, then exactly `size` rows of `size` glyphs
    ................................
    ...

Run:  python3 tools/render_sprites.py [--size 32] [--scale 8]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "assets" / "weapons" / "src"
OUT_DIR = ROOT / "assets" / "weapons"
PREVIEW_DIR = OUT_DIR / "preview"

RGBA = tuple[int, int, int, int]
TRANSPARENT: RGBA = (0, 0, 0, 0)


# --------------------------------------------------------------------------- png
def write_png(path: Path, rows: list[list[RGBA]]) -> None:
    """Write an 8-bit RGBA PNG. `rows` is a list of rows of (r, g, b, a)."""
    height = len(rows)
    width = len(rows[0]) if rows else 0
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter type 0 (None) for this scanline
        for px in row:
            raw.extend(px)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def scale_rows(rows: list[list[RGBA]], factor: int) -> list[list[RGBA]]:
    """Nearest-neighbour upscale (keeps pixels crisp)."""
    out: list[list[RGBA]] = []
    for row in rows:
        wide = [px for px in row for _ in range(factor)]
        out.extend([list(wide) for _ in range(factor)])
    return out


# ------------------------------------------------------------------------- parse
def parse_hex(value: str) -> RGBA:
    value = value.strip().lstrip("#")
    if len(value) == 6:
        value += "ff"
    if len(value) != 8:
        raise ValueError(f"bad colour {value!r}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore[return-value]


def load_grid(path: Path, size: int) -> tuple[dict[str, RGBA], list[str]]:
    palette: dict[str, RGBA] = {".": TRANSPARENT}
    rows: list[str] = []
    in_pixels = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip("\n")
        if not in_pixels:
            stripped = line.strip()
            if stripped == "---":
                in_pixels = True
                continue
            if not stripped or stripped.startswith("#"):
                continue
            glyph, _, colour = stripped.partition("=")
            glyph = glyph.strip()
            colour = colour.split(";")[0].strip()  # allow "; comment" after colour
            if len(glyph) != 1:
                raise ValueError(f"{path.name}: palette glyph must be 1 char: {glyph!r}")
            palette[glyph] = TRANSPARENT if colour.lower() == "none" else parse_hex(colour)
        else:
            if not line.strip():
                continue
            rows.append(line)
    if len(rows) != size:
        raise ValueError(f"{path.name}: expected {size} rows, got {len(rows)}")
    for i, row in enumerate(rows):
        if len(row) != size:
            raise ValueError(f"{path.name}: row {i} has {len(row)} glyphs, expected {size}")
        for glyph in row:
            if glyph not in palette:
                raise ValueError(f"{path.name}: row {i} uses undefined glyph {glyph!r}")
    return palette, rows


def grid_to_rows(palette: dict[str, RGBA], rows: list[str]) -> list[list[RGBA]]:
    return [[palette[g] for g in row] for row in rows]


# ------------------------------------------------------------------------ render
def render_all(size: int, scale: int) -> list[str]:
    paths = sorted(SRC_DIR.glob("*.txt"))
    if not paths:
        sys.exit(f"no sprite sources found in {SRC_DIR}")

    sprites: dict[str, list[list[RGBA]]] = {}
    for path in paths:
        palette, rows = load_grid(path, size)
        sprites[path.stem] = grid_to_rows(palette, rows)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    for sprite_id, rows in sprites.items():
        write_png(OUT_DIR / f"{sprite_id}.png", rows)
        write_png(PREVIEW_DIR / f"{sprite_id}@{scale}x.png", scale_rows(rows, scale))

    # spritesheet: one row, in the order the ids sort (stable for the atlas)
    ids = list(sprites)
    sheet = [[TRANSPARENT] * (size * len(ids)) for _ in range(size)]
    atlas = {"size": size, "frames": {}}
    for index, sprite_id in enumerate(ids):
        x0 = index * size
        for y in range(size):
            sheet[y][x0 : x0 + size] = sprites[sprite_id][y]
        atlas["frames"][sprite_id] = {"x": x0, "y": 0, "w": size, "h": size}
    write_png(OUT_DIR / "spritesheet.png", sheet)
    (OUT_DIR / "spritesheet.json").write_text(json.dumps(atlas, indent=2) + "\n")

    # contact sheet: 4 columns on a dark ground, for eyeballing everything at once
    cols = 4
    gutter = 1
    cell = size + gutter * 2
    rows_n = (len(ids) + cols - 1) // cols
    ground: RGBA = (36, 32, 46, 255)
    contact = [[ground] * (cell * cols) for _ in range(cell * rows_n)]
    for index, sprite_id in enumerate(ids):
        cy, cx = divmod(index, cols)
        for y in range(size):
            for x in range(size):
                px = sprites[sprite_id][y][x]
                if px[3]:
                    contact[cy * cell + gutter + y][cx * cell + gutter + x] = px
    write_png(PREVIEW_DIR / "contact-sheet.png", scale_rows(contact, scale))
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", type=int, default=32, help="sprite size in pixels (square)")
    parser.add_argument("--scale", type=int, default=8, help="preview upscale factor")
    args = parser.parse_args()
    ids = render_all(args.size, args.scale)
    print(f"rendered {len(ids)} sprites -> {OUT_DIR.relative_to(ROOT)}/")
    for sprite_id in ids:
        print(f"  {sprite_id}")


if __name__ == "__main__":
    main()
