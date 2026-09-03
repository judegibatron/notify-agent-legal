#!/usr/bin/env python3
"""Drafting tool: builds the 32x32 diagonal weapon sprites procedurally and
writes them out as editable text grids in assets/weapons/src/.

The text grids are the source of truth for the art. This script is how the
first draft of each grid was produced, and it is the fastest way to rough out a
new weapon in the same style before hand-tuning pixels in the .txt file.

    python3 tools/draft_weapons.py               # writes only grids that don't exist yet
    python3 tools/draft_weapons.py --overwrite   # regenerate everything (discards hand edits!)
    python3 tools/draft_weapons.py --only twin_fangs --overwrite

Weapon space for a 45-degree weapon (hilt bottom-left, tip top-right):
    s = r + c   (anti-diagonal index)   v = s - S0   (across the blade; v<0 = upper-left = lit side)
    d = r - c   (diagonal index)        u = (D0 - d) / 2   (along the blade; 0 = hilt end)
Pixel parity: v even <-> u integer, v odd <-> u half-integer.
Pixel distance^2 between two weapon-space points = 2*du^2 + dv^2/2.
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path

SIZE = 32
OUT = Path(__file__).resolve().parent.parent / "assets" / "weapons" / "src"


class Sprite:
    def __init__(self, name: str, title: str, palette: dict[str, str], outline: str = "o", s0: int = 31, d0: int = 27):
        self.name, self.title = name, title
        self.palette = {".": "none", **palette}
        self.outline = outline
        self.s0, self.d0 = s0, d0
        self.g = [["."] * SIZE for _ in range(SIZE)]

    # ---- coordinate helpers
    def uv(self, r: int, c: int) -> tuple[float, float]:
        return (self.d0 - (r - c)) / 2.0, float((r + c) - self.s0)

    def rc(self, u: float, v: float) -> tuple[int, int]:
        s = self.s0 + v
        d = self.d0 - 2 * u
        return int(round((s + d) / 2)), int(round((s - d) / 2))

    def put(self, r: int, c: int, ch: str) -> None:
        if 0 <= r < SIZE and 0 <= c < SIZE:
            self.g[r][c] = ch

    def get(self, r: int, c: int) -> str:
        if 0 <= r < SIZE and 0 <= c < SIZE:
            return self.g[r][c]
        return "."

    def wpx(self, u: float, v: float, ch: str) -> None:
        """Set a pixel at weapon coords, snapping u to the parity that v needs."""
        v = int(round(v))
        u = round(u) if v % 2 == 0 else math.floor(u) + 0.5
        r, c = self.rc(u, v)
        self.put(r, c, ch)

    def paint(self, fn) -> None:
        """fn(u, v) -> glyph or None, evaluated at every pixel."""
        for r in range(SIZE):
            for c in range(SIZE):
                u, v = self.uv(r, c)
                ch = fn(u, v)
                if ch:
                    self.g[r][c] = ch

    def outline_pass(self, glyph: str | None = None, skip: str = "") -> None:
        """Any transparent pixel 4-adjacent to a solid one becomes outline."""
        glyph = glyph or self.outline
        to_set = []
        for r in range(SIZE):
            for c in range(SIZE):
                if self.g[r][c] != ".":
                    continue
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = self.get(r + dr, c + dc)
                    if n != "." and n not in skip:
                        to_set.append((r, c))
                        break
        for r, c in to_set:
            self.g[r][c] = glyph

    def mirror_h(self) -> None:
        self.g = [row[::-1] for row in self.g]

    def composite_over(self, other: "Sprite") -> None:
        """Draw `other` under self (self wins where both are solid)."""
        for r in range(SIZE):
            for c in range(SIZE):
                if self.g[r][c] == "." and other.g[r][c] != ".":
                    self.g[r][c] = other.g[r][c]

    def write(self, overwrite: bool = False) -> None:
        target = OUT / f"{self.name}.txt"
        if target.exists() and not overwrite:
            print("skip (exists, pass --overwrite to replace)", self.name)
            return
        used = {ch for row in self.g for ch in row}
        lines = [f"# {self.title}", f"# {SIZE}x{SIZE} - glyph = colour; '.' is transparent", ""]
        for glyph, colour in self.palette.items():
            if glyph in used or glyph == ".":
                lines.append(f"{glyph} = {colour}")
        lines.append("---")
        lines.extend("".join(row) for row in self.g)
        OUT.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n")
        print("wrote", self.name)


# ----------------------------------------------------------------- shape helpers
def band(u0, u1, v0, v1, shade):
    def f(u, v):
        if u0 <= u <= u1 and v0 <= v <= v1:
            return shade(u, v) if callable(shade) else shade
    return f


def blade(u0, u_tip, hw, colors, taper=1.5, center=lambda u: 0.0):
    """Symmetric blade. colors: dict of v-offset -> glyph."""
    def f(u, v):
        vc = center(u)
        off = int(round(v - vc))
        if abs(off) > hw or u < u0:
            return None
        if u > u_tip - taper * abs(off):
            return None
        return colors.get(off)
    return f


def disc(uc, vc, radius, shade):
    def f(u, v):
        du, dv = u - uc, v - vc
        if 2 * du * du + dv * dv / 2 <= radius * radius:
            return shade(u, v) if callable(shade) else shade
    return f


def wrap(a, b, period=2.0):
    """Alternating grip wrap glyphs along u."""
    return lambda u, v: a if int(u // period) % 2 == 0 else b


OUTLINE = "#14101c"


# ================================================================== COMMON TIER
def iron_sword():
    s = Sprite("iron_sword", "Iron Sword (common)", {
        "o": OUTLINE, "H": "#e6e8ee", "B": "#b4b8c4", "D": "#7c8090", "S": "#565a68",
        "l": "#6e4b32", "k": "#4a3121",
    })
    s.paint(band(0.5, 1.5, -1, 1, "S"))                      # pommel
    s.paint(band(1.5, 6, -1, 0, wrap("l", "k")))            # grip
    s.paint(band(6, 7, -3, 3, lambda u, v: "B" if v <= 0 else "D"))  # guard
    s.paint(blade(7.5, 25, 1, {-1: "H", 0: "B", 1: "D"}, taper=1.5))
    s.outline_pass()
    return s


def short_bow():
    s = Sprite("short_bow", "Short Bow (common)", {
        "o": OUTLINE, "W": "#8a5a2b", "w": "#6b4420", "x": "#4d2f14", "t": "#d9c9a0",
    })
    def limb(u, v):
        if not 2 <= u <= 25:
            return None
        t = (u - 2) / 23
        vc = -6 * math.sin(math.pi * t)
        tol = 0.6 + 0.6 * math.sin(math.pi * t)
        if abs(v - vc) <= tol:
            if 12 <= u <= 15:
                return "x"
            return "W" if v < vc else "w"
    s.paint(band(2.5, 24.5, 0, 0, "t"))
    s.paint(limb)
    s.outline_pass()
    return s


def iron_dagger():
    s = Sprite("iron_dagger", "Iron Dagger (common)", {
        "o": OUTLINE, "H": "#e6e8ee", "B": "#b4b8c4", "D": "#7c8090", "S": "#565a68",
        "l": "#6e4b32", "k": "#4a3121",
    }, d0=27 - 2 * 5)  # shift hilt toward centre
    s.paint(band(0.5, 1.5, -1, 1, "S"))
    s.paint(band(1.5, 5, -1, 0, wrap("l", "k")))
    s.paint(band(5, 5.5, -2, 2, "S"))
    s.paint(blade(6, 16, 1, {-1: "H", 0: "B", 1: "D"}, taper=1.5))
    s.outline_pass()
    return s


def oak_staff():
    s = Sprite("oak_staff", "Oak Staff (common)", {
        "o": OUTLINE, "W": "#8a5a2b", "w": "#6b4420", "x": "#4d2f14", "k": "#5c3a1c",
    })
    s.paint(band(0.5, 23, -1, 0, lambda u, v: "W" if v < 0 else "w"))
    for u in (5, 11, 17):
        s.wpx(u, 0, "x")
    s.paint(disc(24.5, 0, 2.2, lambda u, v: "W" if v < 0 else ("k" if v > 1 else "w")))
    s.outline_pass()
    return s


# ================================================================= PREMIUM TIER
def voidreaver():
    s = Sprite("voidreaver_greatsword", "Voidreaver Greatsword (legendary)", {
        "o": "#0d0616", "y": "#f6d36a", "Y": "#d4a63a", "Z": "#9b7222",
        "E": "#c9b8e6", "L": "#7a5ca3", "B": "#4a3570", "D": "#33254f", "S": "#261b3d",
        "C": "#c46bff", "c": "#f6d8ff", "w": "#2f2340", "x": "#211830", "G": "#b45cff",
    })
    s.paint(band(0.5, 2, -1, 1, lambda u, v: "y" if v < 0 else "Y"))     # pommel
    s.wpx(1, 0, "G")                                                        # pommel gem
    s.paint(band(2, 7, -1, 0, wrap("w", "x")))                              # grip
    s.paint(band(7, 8.5, -6, 6, lambda u, v: "y" if v < -2 else ("Y" if v <= 2 else "Z")))  # wide guard
    for v in (-6, 6):                                                       # up-swept guard spikes
        s.wpx(9, v, "Y"); s.wpx(9.5, v, "Y"); s.wpx(10, v, "y" if v < 0 else "Z")
    s.paint(blade(8.5, 26.5, 2, {-2: "E", -1: "L", 0: "B", 1: "D", 2: "S"}, taper=1.5))
    # void seam down the fuller, with cracks branching off it
    for u in range(11, 25):
        s.wpx(u, 0, "C")
    for u, v in ((13.5, -1), (14, -2), (17.5, 1), (18, 2), (21.5, -1), (22, -2), (15.5, 1), (19.5, -1), (23.5, 1)):
        s.wpx(u, v, "C")
    for u in (12, 16, 20, 24):
        s.wpx(u, 0, "c")
    s.outline_pass()
    # drifting void motes (after outline so they float free)
    for r, c in ((6, 18), (10, 27), (14, 11), (3, 24), (19, 9), (23, 14)):
        s.put(r, c, "C")
    s.put(4, 25, "c"); s.put(13, 10, "c")
    return s


def solaris():
    s = Sprite("solaris_blade", "Solaris Blade (legendary)", {
        "o": "#2b1a08", "H": "#fff6c8", "L": "#ffe082", "B": "#f2b632", "D": "#c98a1a", "S": "#8f5f10",
        "F": "#fffbe6", "R": "#e8283a", "r": "#a3121f", "w": "#9c2a2a", "x": "#6e1b1b", "*": "#ffffff",
    })
    s.paint(band(0.5, 2, -1, 1, lambda u, v: "L" if v < 0 else "D"))        # pommel
    s.wpx(1, 0, "R")
    s.paint(band(2, 6.5, -1, 0, wrap("w", "x")))                             # red leather grip
    # sun guard: a disc of gold with rays flaring out of it
    s.paint(disc(7.5, 0, 2.6, lambda u, v: "L" if v < -1 else ("B" if v <= 1 else "D")))
    for v in (-5, -4, 4, 5):                                                 # long side rays
        s.wpx(7.5, v, "B")
    for v in (-6, 6):
        s.wpx(7.5, v, "L" if v < 0 else "D")
    for u, v in ((9.5, -3), (10, -4), (9.5, 3), (10, 4), (5.5, -3), (5, -4), (5.5, 3), (5, 4)):  # diagonal rays
        s.wpx(u, v, "L" if v < 0 else "D")
    s.wpx(7.5, 0, "R"); s.wpx(7, -1, "R"); s.wpx(8, -1, "R"); s.wpx(7, 1, "r"); s.wpx(8, 1, "r")   # ruby
    s.paint(blade(8.5, 26.5, 2, {-2: "H", -1: "L", 0: "F", 1: "B", 2: "D"}, taper=1.5))
    s.outline_pass()
    for r, c in ((4, 22), (12, 26), (17, 10), (7, 29)):                       # sparkles
        s.put(r, c, "*")
    s.put(3, 22, "L"); s.put(5, 22, "L"); s.put(4, 21, "L"); s.put(4, 23, "L")  # 4-point star
    return s


def frostbite():
    s = Sprite("frostbite_katana", "Frostbite Katana (legendary)", {
        "o": "#0f1a2e", "E": "#ffffff", "B": "#b7ecff", "D": "#6fc4ea", "S": "#3e8fbd", "f": "#e0fbff",
        "n": "#1f2c5c", "i": "#dfe7ff", "z": "#3c4a6e", "Z": "#5b6d99", "k": "#2b365c", "c": "#9fe3ff",
    })
    s.paint(band(0.5, 1.5, -1, 0, "k"))                                      # kashira
    s.paint(band(1.5, 9, -1, 0, lambda u, v: "i" if int(u * 2) % 3 == 0 else "n"))  # diamond wrap
    s.paint(band(9, 10, -2, 2, lambda u, v: "Z" if v < 0 else "z"))          # tsuba
    center = lambda u: 0.0 if u < 19 else -1.0                               # sori (curve)
    def kat(u, v):
        vc = center(u)
        off = int(round(v - vc))
        if u < 10 or off < -1 or off > 1:
            return None
        # edge side reaches the tip; spine falls short
        if u > 27 - 1.2 * (off + 1):
            return None
        if off == -1:
            return "E"
        if off == 0:
            return "f" if int(u) % 3 == 0 and u > 12 else "B"   # hamon shimmer
        return "D"
    s.paint(kat)
    for u in (13, 17, 21, 24):                                               # ice shards off the spine
        vc = center(u)
        s.wpx(u, vc + 2, "c"); s.wpx(u + 0.5, vc + 3, "f")
    s.outline_pass()
    for r, c in ((5, 20), (9, 27), (15, 14), (2, 26)):                       # frost motes
        s.put(r, c, "f")
    return s


def stormcaller():
    s = Sprite("stormcaller_spear", "Stormcaller Spear (epic)", {
        "o": "#0e1a1a", "w": "#2f4f4f", "x": "#213a3a", "m": "#c9d3dd", "M": "#8f9aa8",
        "H": "#f0f6ff", "B": "#a9b8cc", "D": "#6b7d96", "Y": "#ffe94d", "y": "#fff9b0", "t": "#7be0e0",
    })
    s.paint(band(0.5, 20, -1, 0, lambda u, v: "w" if v < 0 else "x"))       # shaft
    for u in (3, 9, 15):                                                     # silver bands
        s.paint(band(u, u + 0.5, -1, 0, lambda u_, v: "m" if v < 0 else "M"))
    s.paint(band(19.5, 21, -1, 1, lambda u, v: "m" if v < 0 else "M"))      # socket
    def head(u, v):
        if u < 21 or u > 27.4:
            return None
        hw = 2 if u < 24.5 else (1 if u < 26.5 else 0)
        if abs(v) > hw:
            return None
        if v == 0 and 22 <= u <= 25:
            return "m"                                                       # bright ridge
        return "H" if v < 0 else ("B" if v == 0 else "D")
    s.paint(head)
    s.outline_pass()
    # stepped lightning bolts either side of the head (pixel space)
    for r, c in ((8, 20), (7, 21), (6, 20), (5, 21), (4, 22), (3, 21), (2, 22), (1, 23), (1, 24)):
        s.put(r, c, "Y")
    for r, c in ((10, 27), (9, 28), (8, 29), (7, 28), (6, 29), (5, 30), (4, 29), (3, 30)):
        s.put(r, c, "Y")
    for r, c in ((6, 20), (3, 21), (7, 28), (4, 29)):
        s.put(r, c, "y")
    for r, c in ((12, 24), (9, 18), (13, 30), (2, 26), (0, 22), (15, 27)):   # static sparks
        s.put(r, c, "t")
    return s


def inferno():
    s = Sprite("inferno_warhammer", "Inferno Warhammer (legendary)", {
        "o": "#140a08", "L": "#6e6e7c", "B": "#45454f", "D": "#2e2e36", "S": "#1f1f26",
        "M": "#ff6a1a", "m": "#ffd23f", "R": "#c62a12", "w": "#4a2c1a", "x": "#35200f",
        "r": "#8b1e1e", "Q": "#b52a2a", "e": "#ff9a3c",
    })
    s.paint(band(0, 1.5, -1, 1, lambda u, v: "L" if v < 0 else "D"))         # iron cap
    s.paint(band(1.5, 20, -1, 0, lambda u, v: "w" if v < 0 else "x"))        # haft
    s.paint(band(2, 7, -1, 0, wrap("Q", "r")))                               # red wrap
    s.paint(band(18, 19.5, -2, 2, lambda u, v: "L" if v < 0 else "D"))       # collar
    def head(u, v):
        if not (19.5 <= u <= 26 and -7 <= v <= 7):
            return None
        if u >= 25.5:                                                        # top face, lit
            return "L" if v < 4 else "B"
        if u <= 20:                                                          # underside, dark
            return "S" if v > -4 else "D"
        if v <= -6:                                                          # striking face (lit)
            return "L"
        if v >= 6:                                                           # far striking face
            return "S"
        return "B" if v < 2 else "D"
    s.paint(head)
    # one main magma fissure across the head, with two branches and a hot core
    crack = [(25, -6), (24.5, -5), (24, -4), (24.5, -3), (24, -2), (23.5, -1), (23, 0), (22.5, 1),
             (23, 2), (22.5, 3), (22, 4), (21.5, 5), (21, 6),
             (23, -4), (22.5, -3), (22, -2),          # lower branch
             (24, 2), (24.5, 3), (25, 4)]             # upper branch
    for u, v in crack:
        s.wpx(u, v, "M")
    for u, v in ((24, -4), (23.5, -1), (23, 0), (22.5, 3), (22, 4)):
        s.wpx(u, v, "m")
    for u, v in ((22, -2), (25, 4), (21, 6)):
        s.wpx(u, v, "R")
    s.outline_pass()
    for r, c in ((2, 19), (5, 16), (16, 30), (0, 24), (12, 31), (8, 15)):     # embers
        s.put(r, c, "e")
    s.put(3, 17, "M"); s.put(14, 29, "M")
    return s


def dragonbone():
    s = Sprite("dragonbone_bow", "Dragonbone Bow (epic)", {
        "o": "#1a1410", "H": "#fff8e8", "B": "#e9dcc0", "D": "#b8a684", "S": "#85735a",
        "G": "#63ff85", "g": "#2fbf55", "e": "#63ff85", "k": "#5a4a3a",
    })
    def limb(u, v):
        if not 1 <= u <= 26:
            return None
        t = (u - 2) / 23
        vc = -7 * math.sin(math.pi * max(0.0, min(1.0, t)))
        if u < 2 or u > 25:                                                  # recurve hooks
            return "S" if abs(v - 1.5) <= 1.0 else None
        tol = 0.9 + 1.1 * math.sin(math.pi * t)
        if abs(v - vc) <= tol:
            if v < vc - 0.6:
                return "H"
            if v > vc + 0.7:
                return "D"
            return "B"
    s.paint(band(2.5, 24.5, 0, 0, "G"))                                       # glowing string
    s.paint(limb)
    for u in (5, 7, 20, 22):                                                 # vertebrae ridges
        vc = -7 * math.sin(math.pi * (u - 2) / 23)
        s.wpx(u, vc + 1, "S")
    # dragon skull mounted on the grip (pixel space, up-left of the limb's midpoint)
    skull = {
        "H": ((6, 8), (6, 9), (6, 10), (7, 7), (11, 8), (11, 10)),
        "B": ((7, 8), (7, 9), (7, 10), (7, 11), (8, 7), (8, 9), (8, 11), (9, 8), (9, 10), (10, 9)),
        "D": ((9, 7), (9, 9), (9, 11), (10, 8), (10, 10), (10, 11), (11, 12)),
        "S": ((10, 7), (11, 11)),
        "e": ((8, 8), (8, 10)),
        "k": ((5, 7), (5, 11), (4, 6), (4, 12)),
    }
    for glyph, cells in skull.items():
        for r, c in cells:
            s.put(r, c, glyph)
    s.outline_pass()
    for r, c in ((13, 18), (20, 6), (16, 22), (24, 11), (9, 19)):              # green motes
        s.put(r, c, "g")
    return s


def twin_fangs():
    pal = {
        "o": "#0f0c18", "H": "#c9bce6", "B": "#7d6aa6", "D": "#4d3d75", "S": "#2e2450",
        "k": "#1f1830", "K": "#3a2d55", "w": "#262036", "x": "#16121f",
        "P": "#8dff3a", "p": "#4fbf1c", "a": "#b8ff7a",
    }
    def dagger(name):
        d = Sprite(name, "Twin Fangs (epic)", pal)
        d.paint(band(3.5, 4.5, -1, 0, "K"))                                  # pommel
        d.paint(band(4.5, 9, -1, 0, wrap("w", "x")))                         # grip
        d.paint(band(9, 10, -2, 2, lambda u, v: "K" if v < 0 else "k"))      # guard
        center = lambda u: 0.0 if u < 19 else -1.0
        d.paint(blade(10, 24, 1, {-1: "H", 0: "B", 1: "D"}, taper=1.3, center=center))
        d.wpx(22, -1, "P"); d.wpx(22.5, -2, "P"); d.wpx(23, -1, "a")          # venom on the fang
        d.outline_pass()
        return d
    a = dagger("twin_fangs")
    b = dagger("_tmp")
    b.mirror_h()
    a.composite_over(b)
    # venom drips falling from the crossed tips
    a.put(9, 25, "P"); a.put(11, 25, "p"); a.put(9, 6, "P"); a.put(11, 6, "p"); a.put(13, 6, "a")
    return a


def astral():
    s = Sprite("astral_scepter", "Astral Scepter (legendary)", {
        "o": "#120a24", "w": "#2a2352", "x": "#1a163a", "Y": "#f0c85a", "y": "#b8902c",
        "H": "#ffffff", "L": "#ffb8f2", "B": "#ff5cd6", "D": "#c22ba0", "S": "#7d1a6c",
        "*": "#ffffff", "s": "#ffd2f7",
    })
    s.paint(band(0, 1.5, -1, 1, lambda u, v: "Y" if v < 0 else "y"))          # pommel
    s.paint(band(1.5, 21, -1, 0, lambda u, v: "w" if v < 0 else "x"))         # shaft
    for u in (3, 9, 15):
        s.paint(band(u, u + 0.5, -1, 0, lambda u_, v: "Y" if v < 0 else "y"))  # gold rings
    s.paint(band(21, 22.5, -2, 2, lambda u, v: "Y" if v < 0 else "y"))        # cup
    for u, v in ((23, -3), (23.5, -4), (24, -3), (23, 3), (23.5, 4), (24, 3), (25, -4), (25, 4)):  # horns
        s.wpx(u, v, "Y" if v < 0 else "y")
    def orb(u, v):
        du, dv = u - 24.7, v
        d2 = 2 * du * du + dv * dv / 2
        if d2 > 9.5:
            return None
        if 2 * (du - 0.6) ** 2 + (dv + 1.6) ** 2 / 2 <= 0.8:
            return "H"
        if dv < -1.5 or (du > 0.8 and dv < 0):
            return "L"
        if dv > 2.2 or (du < -0.8 and dv > 0.5):
            return "S"
        if dv > 0.8:
            return "D"
        return "B"
    s.paint(orb)
    s.outline_pass()
    for r, c in ((2, 21), (9, 30), (12, 24), (1, 27)):                          # sparkles
        s.put(r, c, "*")
    for r, c in ((7, 21), (6, 20), (8, 20), (7, 19)):                           # 4-point star
        s.put(r, c, "s")
    s.put(7, 20, "*")
    return s


BUILDERS = (iron_sword, short_bow, iron_dagger, oak_staff,
            voidreaver, solaris, frostbite, stormcaller, inferno, dragonbone, twin_fangs, astral)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Draft weapon sprite grids.")
    parser.add_argument("--overwrite", action="store_true", help="replace existing grids (loses hand edits)")
    parser.add_argument("--only", nargs="*", default=None, help="sprite ids to build, e.g. twin_fangs")
    args = parser.parse_args()
    for build in BUILDERS:
        sprite = build()
        if args.only and sprite.name not in args.only:
            continue
        sprite.write(overwrite=args.overwrite)
