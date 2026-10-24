"""v6 "Divorced? Check This", in the approved reference style: dark-navy A-roll (Tom),
cream grid B-roll UI cards, small sans captions with blue serif-italic key words,
circle wipes, and 1-2-3 progress dots.

Sound: assembled from sfx_cues_v4.json onto separate family stems (WHOOSHES, TEXTURES,
RISERS, HITS), each cue's measured peak locked to its sync frame. Optional --voice is mixed
on top and never processed.

usage: python3 render_v4.py edit_v4.json sfx_cues_v4.json inventory.json OUTDIR [--tom tom.mp4] [--voice v.wav]
       ... --stills 10,120,300   (PNG key frames only)
"""
import argparse, json, math, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
SR = 48000
CREAM = (244, 241, 234)
GRID = (231, 227, 218)
INK = (27, 31, 42)
MUTED = (120, 124, 134)
BLUE = (47, 107, 255)
BLUE_ON_DARK = (122, 168, 255)
GREEN = (52, 199, 89)
NAVY_TOP, NAVY_BOT = (10, 24, 48), (20, 50, 94)
WHITE = (255, 255, 255)

_f = {}
def font(kind, size):
    paths = {"sans": "/usr/share/fonts/opentype/inter/Inter-Medium.otf",
             "sans_semi": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
             "sans_bold": "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
             "serif_it": "/usr/share/fonts/truetype/crosextra/Caladea-BoldItalic.ttf",
             "serif": "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf"}
    if (kind, size) not in _f:
        _f[(kind, size)] = ImageFont.truetype(paths[kind], size)
    return _f[(kind, size)]

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(f, f0, n): return clamp((f - f0) / max(n, 1e-6))
def ease_out(x): return 1 - (1 - x) ** 3
def ease_io(x): return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
def ease_back(x, s=1.6):
    x -= 1; return x * x * ((s + 1) * x + s) + 1

_cache = {}
def bg_cream():
    if "cream" not in _cache:
        img = Image.new("RGBA", (W, H), CREAM + (255,))
        d = ImageDraw.Draw(img)
        for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill=GRID, width=1)
        for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=GRID, width=1)
        vg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(vg).ellipse([-300, -200, W + 300, H + 200], fill=(255, 255, 255, 120))
        img.alpha_composite(vg.filter(ImageFilter.GaussianBlur(220)))
        _cache["cream"] = img
    return _cache["cream"].copy()

def shadow_card(img, box, r=44, fill=WHITE, alpha=46, blur=28, dy=14):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([box[0], box[1] + dy, box[2], box[3] + dy], r, fill=(30, 40, 70, alpha))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(img).rounded_rectangle(box, r, fill=fill)

# ---------- Tom ----------
class Tom:
    def __init__(self, path):
        self.proc = None; self.last = None
        if path:
            self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf",
                f"fps=30,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        else:
            y = np.linspace(0, 1, H)[:, None, None]
            px = np.array(NAVY_TOP) * (1 - y) + np.array(NAVY_BOT) * y
            yy, xx = np.mgrid[0:H, 0:W]
            px = px + (np.exp(-(((xx - 760) / 420.0) ** 2 + ((yy - 520) / 520.0) ** 2)) * 26)[..., None]
            img = Image.fromarray(np.clip(px, 0, 255).astype(np.uint8)).convert("RGBA")
            d = ImageDraw.Draw(img)
            x0, y0, x1, y1 = 250, 430, 830, 1030
            for xx_ in range(x0, x1, 40):
                d.line([(xx_, y0), (min(xx_ + 20, x1), y0)], fill=(255, 255, 255, 90), width=4)
                d.line([(xx_, y1), (min(xx_ + 20, x1), y1)], fill=(255, 255, 255, 90), width=4)
            for yy_ in range(y0, y1, 40):
                d.line([(x0, yy_), (x0, min(yy_ + 20, y1))], fill=(255, 255, 255, 90), width=4)
                d.line([(x1, yy_), (x1, min(yy_ + 20, y1))], fill=(255, 255, 255, 90), width=4)
            d.text((540, 710), "TOM", font=font("sans_bold", 64), fill=(255, 255, 255, 130), anchor="mm")
            d.text((540, 780), "Higgsfield clip goes here", font=font("sans", 34), fill=(255, 255, 255, 110), anchor="mm")
            self.ph = img.convert("RGB")

    def next(self):
        if not self.proc: return self.ph.copy()
        b = self.proc.stdout.read(W * H * 3)
        if len(b) == W * H * 3: self.last = Image.frombytes("RGB", (W, H), b)
        return (self.last or Image.new("RGB", (W, H), NAVY_TOP)).copy()

def zoom(img, s, cy=0.38):
    if s <= 1.0005: return img
    w, h = int(W * s), int(H * s)
    big = img.resize((w, h), Image.LANCZOS)
    x, y = (w - W) // 2, int((h - H) * cy)
    return big.crop((x, y, x + W, y + H))

# ---------- captions (reference style) ----------
def caption(img, f, cap, dark_bg, y_center):
    """Small sans words reveal one by one; the key phrase lands as big blue serif italic beneath."""
    d = ImageDraw.Draw(img)
    small_col = WHITE if dark_bg else INK
    fs = font("sans_semi", 46)
    words = [(w, wf) for w, wf in cap["small"]]
    if words:
        total = sum(fs.getlength(w) for w, _ in words) + fs.getlength(" ") * (len(words) - 1)
        x = (W - total) / 2
        for w, wf in words:
            p = ease_out(prog(f, wf, 4))
            if p > 0:
                d.text((x, y_center - 62 + 12 * (1 - p)), w, font=fs, fill=small_col + (int(255 * p),))
            x += fs.getlength(w + " ")
    p = ease_out(prog(f, cap["big_f"], 7))
    if p > 0:
        fb = font("serif_it", 112)
        col = BLUE_ON_DARK if dark_bg else BLUE
        layer = Image.new("RGBA", (W, 170), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((W / 2, 85), cap["big"], font=fb, fill=col + (255,), anchor="mm")
        if p < 1:
            layer = layer.filter(ImageFilter.GaussianBlur(6 * (1 - p)))
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * p)))
        img.alpha_composite(layer, (0, int(y_center - 20 + 26 * (1 - p))))

def dots(img, f, cx, cy, filled_at, appear_at, dark_bg):
    """1—2—3 progress UI. appear_at: frame each dot pops in; filled_at: frame each fills."""
    d = ImageDraw.Draw(img)
    gap = 120
    line_col = (255, 255, 255, 90) if dark_bg else (27, 31, 42, 60)
    xs = [cx - gap, cx, cx + gap]
    if f >= appear_at[1]: d.line([(xs[0] + 28, cy), (xs[1] - 28, cy)], fill=line_col, width=4)
    if f >= appear_at[2]: d.line([(xs[1] + 28, cy), (xs[2] - 28, cy)], fill=line_col, width=4)
    for i, x in enumerate(xs):
        p = ease_back(prog(f, appear_at[i], 6))
        if p <= 0: continue
        r = 26 * p
        done = filled_at is not None and f >= filled_at[i]
        if done:
            fp = ease_back(prog(f, filled_at[i], 5))
            fill = WHITE if dark_bg else INK
            d.ellipse([x - r * (0.9 + 0.1 * fp), cy - r * (0.9 + 0.1 * fp), x + r * (0.9 + 0.1 * fp), cy + r * (0.9 + 0.1 * fp)], fill=fill)
            d.text((x, cy + 1), str(i + 1), font=font("sans_bold", int(max(8, 26 * p))), fill=(INK if dark_bg else WHITE), anchor="mm")
        else:
            col = (255, 255, 255, 170) if dark_bg else (27, 31, 42, 120)
            d.ellipse([x - r, cy - r, x + r, cy + r], outline=col, width=4)
            d.text((x, cy + 1), str(i + 1), font=font("sans_bold", int(max(8, 24 * p))), fill=col, anchor="mm")

# ---------- scenes ----------
def rings_icon(img, f, f0, split):
    p = ease_back(prog(f, f0, 8))
    if p <= 0: return
    a = clamp(1 - prog(f, 26, 6))
    if a <= 0: return
    s = int(240 * p)
    layer = Image.new("RGBA", (260, 260), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rounded_rectangle([20, 20, 240, 240], 54, fill=WHITE)
    gap = 22 + 30 * ease_out(prog(f, split["f"], split["frames"]))
    for cx in (130 - gap, 130 + gap):
        dl.ellipse([cx - 44, 130 - 44, cx + 44, 130 + 44], outline=(214, 166, 52), width=12)
    layer = layer.resize((max(1, int(260 * s / 240)),) * 2, Image.LANCZOS)
    layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(layer, (540 - layer.width // 2, 1150 - layer.height // 2))

def scrim():
    if "scrim" not in _cache:
        y = np.linspace(0, 1, H)[:, None]
        a = np.clip((y - 0.5) / 0.28, 0, 1) ** 1.6 * 205
        px = np.zeros((H, W, 4), np.uint8); px[..., 0], px[..., 1], px[..., 2] = NAVY_TOP
        px[..., 3] = np.broadcast_to(a, (H, W)).astype(np.uint8)
        _cache["scrim"] = Image.fromarray(px, "RGBA")
    return _cache["scrim"]

def scene_A(f, tom_frame, cfg):
    z = 1.0
    sz = cfg["snap_zoom"]
    if f >= sz["f"] and f < 102:
        z = 1 + (sz["zoom"] - 1) * ease_out(prog(f, sz["f"], sz["frames"]))
    img = zoom(tom_frame, z).convert("RGBA")
    img.alpha_composite(scrim())
    if f < cfg["scenes"][0]["f1"]: rings_icon(img, f, cfg["hook_icon_f"], cfg["rings_split"])
    s3 = cfg["scenes"][2]
    if s3["f0"] <= f < s3["f1"]:
        dots(img, f, 540, 1530, None, cfg["dots_pop"], True)
    if f >= 440:
        p = ease_back(prog(f, cfg["success_f"], 7))
        if p > 0:
            d = ImageDraw.Draw(img); r = 46 * p; cx, cy = 540, 1190
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN)
            d.line([(cx - r * 0.42, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.34), (cx + r * 0.45, cy - r * 0.32)], fill=WHITE, width=max(2, int(9 * p)), joint="curve")
    return img

def scene_benefit(f, cfg):
    img = bg_cream()
    bc = cfg["benefit_cards"]
    for i, (lbl, ff) in enumerate((("Your benefit", bc["a_f"]), ("Your ex's benefit", bc["b_f"]))):
        p = ease_out(prog(f, ff, bc["slide"]))
        if p <= 0: continue
        x0 = 80 + i * 470; y0 = 760 + int(700 * (1 - p))
        box = [x0, y0, x0 + 450, y0 + 470]
        shadow_card(img, box)
        d = ImageDraw.Draw(img)
        d.text((x0 + 40, y0 + 46), lbl.upper(), font=font("sans_semi", 26), fill=MUTED)
        d.rounded_rectangle([x0 + 40, y0 + 110, x0 + 130, y0 + 200], 24, fill=(234, 240, 255))
        d.text((x0 + 85, y0 + 156), "$", font=font("serif", 60), fill=BLUE, anchor="mm")
        for k, wv in enumerate((300, 220, 260)):
            d.rounded_rectangle([x0 + 40, y0 + 240 + k * 52, x0 + 40 + wv, y0 + 262 + k * 52], 11, fill=(232, 234, 240))
        if i == 1:
            bp = ease_back(prog(f, bc["badge_f"], 7))
            if bp > 0:
                bw, bh = 250 * bp, 68 * bp
                bx, by = x0 + 225, y0 + 410
                d.rounded_rectangle([bx - bw / 2, by - bh / 2, bx + bw / 2, by + bh / 2], int(bh / 2), fill=(226, 247, 233))
                d.text((bx, by), "✓ No change", font=font("sans_bold", max(8, int(30 * bp))), fill=(22, 140, 64), anchor="mm")
    for cap in cfg["captions"]:
        if cap.get("where") == "top" and cap["f0"] <= f < cap["f1"]:
            caption(img, f, cap, False, 400)
    return img

def scene_checklist(f, cfg):
    ck = cfg["checklist"]
    img = bg_cream()
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    p = ease_out(prog(f, ck["title_f"], 10))
    if p > 0:
        yo = int(-50 * (1 - p)); a = int(255 * p)
        d.text((W / 2, 300 + yo), "Do you", font=font("sans_semi", 50), fill=INK + (a,), anchor="mm")
        d.text((W / 2, 400 + yo), "qualify?", font=font("serif_it", 128), fill=BLUE + (a,), anchor="mm")
    filled = [r["check_f"] for r in ck["rows"]]
    if p > 0: dots(layer, f, 540, 540, filled, [ck["title_f"]] * 3, False)
    for i, row in enumerate(ck["rows"]):
        rp = ease_out(prog(f, row["slide_f"], 12))
        if rp <= 0: continue
        x0 = 70 + int(760 * (1 - rp)); y0 = 690 + i * 210
        box = [x0, y0, x0 + 940, y0 + 170]
        shadow_card(layer, box, r=38)
        d = ImageDraw.Draw(layer)
        d.ellipse([x0 + 34, y0 + 51, x0 + 102, y0 + 119], fill=(234, 240, 255))
        d.text((x0 + 68, y0 + 86), str(i + 1), font=font("sans_bold", 34), fill=BLUE, anchor="mm")
        d.text((x0 + 132, y0 + 86), row["text"], font=font("sans_semi", 54), fill=INK, anchor="lm")
        tp = ease_out(prog(f, row["check_f"], 5))
        tx0, ty0 = x0 + 770, y0 + 52
        track = tuple(int(a + (b - a) * tp) for a, b in zip((226, 228, 234), GREEN))
        d.rounded_rectangle([tx0, ty0, tx0 + 132, ty0 + 66], 33, fill=track)
        kx = tx0 + 33 + 66 * tp
        d.ellipse([kx - 27, ty0 + 6, kx + 27, ty0 + 60], fill=WHITE)
    if f >= ck["ask_f"]:
        ap = ease_out(prog(f, ck["ask_f"], 6))
        d.text((W / 2, 1360 + 10 * (1 - ap)), "Check all three?", font=font("sans_semi", 50), fill=INK + (int(255 * ap),), anchor="mm")
    fp = prog(f, ck["rows"][0]["slide_f"] + 8, 10)
    if fp > 0:
        fnt = font("sans", 30); words = ck["fine_print"].split(); lines, cur = [], ""
        for w_ in words:
            t = (cur + " " + w_).strip()
            if fnt.getlength(t) > 880: lines.append(cur); cur = w_
            else: cur = t
        lines.append(cur)
        for k, ln in enumerate(lines):
            d.text((W / 2, 1460 + k * 42), ln, font=fnt, fill=MUTED + (int(255 * fp),), anchor="mm")
    pu = ck["push"]
    s = 1 + (pu["zoom"] - 1) * ease_io(prog(f, pu["f0"], pu["f1"] - pu["f0"]))
    img.alpha_composite(layer)
    return zoom(img.convert("RGB"), s, cy=0.45).convert("RGBA")

def scene_cta(f, cfg):
    c = cfg["cta"]
    img = bg_cream()
    p = ease_out(prog(f, c["card_f"], c["slide"]))
    y0 = 560 + int(900 * (1 - p))
    box = [80, y0, 1000, y0 + 760]
    shadow_card(img, box, r=56, alpha=56)
    d = ImageDraw.Draw(img)
    d.text((540, y0 + 100), c["brand"].upper(), font=font("sans_semi", 30), fill=MUTED, anchor="mm")
    d.text((540, y0 + 225), c["wordmark"], font=font("serif", 150), fill=INK, anchor="mm")
    d.line([(400, y0 + 318), (680, y0 + 318)], fill=(220, 222, 228), width=3)
    bp = ease_back(prog(f, c["button_f"], 8))
    if bp > 0:
        bw, bh = 820 * (0.85 + 0.15 * bp), 140 * (0.85 + 0.15 * bp)
        by = y0 + 440
        d.rounded_rectangle([540 - bw / 2, by - bh / 2, 540 + bw / 2, by + bh / 2], int(bh / 2), fill=BLUE)
        nud = 6 * math.sin(max(0, f - c["button_f"] - 8) * 0.25)
        label = c["button"]
        fl = font("sans_bold", 46)
        lw = fl.getlength(label)
        d.text((540 - 24, by), label, font=fl, fill=WHITE, anchor="mm")
        d.text((540 - 24 + lw / 2 + 40 + nud, by), "→", font=fl, fill=WHITE, anchor="mm")
    sp = ease_out(prog(f, c["sub_f"], 8))
    if sp > 0:
        d.text((540, y0 + 565), c["sub"], font=font("serif_it", 64), fill=BLUE + (int(255 * sp),), anchor="mm")
    fnt = font("sans", 26)
    lines, cur = [], ""
    for w_ in c["disclaimer"].split():
        t = (cur + " " + w_).strip()
        if fnt.getlength(t) > 800: lines.append(cur); cur = w_
        else: cur = t
    lines.append(cur)
    for k, ln in enumerate(lines):
        d.text((540, y0 + 670 + k * 34), ln, font=fnt, fill=MUTED, anchor="mm")
    return img

def scene_frame(f, sc, tom_frame, cfg):
    if sc["kind"] == "A":
        img = scene_A(f, tom_frame, cfg)
        for cap in cfg["captions"]:
            if cap.get("where") != "top" and cap["f0"] <= f < cap["f1"]:
                caption(img, f, cap, True, 1330)
        return img
    return {"B_benefit": scene_benefit, "B_checklist": scene_checklist, "B_cta": scene_cta}[sc["kind"]](f, cfg)

def circle_wipe(prev, nxt, p, cx=540, cy=960):
    far = max(math.hypot(cx - x, cy - y) for x in (0, W) for y in (0, H))
    r = int(far * ease_out(p))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    out = prev.copy(); out.paste(nxt, (0, 0), mask)
    return out

# ---------- audio ----------
def read_stereo(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T

def build_stems(cues, inv, lib_root, frames, fps):
    n = int(frames / fps * SR)
    meas = {}
    for folder, rows in inv.items():
        for r in rows: meas[r["file"]] = r
    stems = {}
    placed = []
    for c in cues["cues"]:
        x = read_stereo(os.path.join(lib_root, c["file"])) * (10 ** (c["db"] / 20))
        m = meas[c["file"]]
        # textures land their onset on the event frame; whooshes, risers and hits lock their peak
        lock_s = m["peak_s"] - m["attack_s"] if c["track"] == "TEXTURES" else m["peak_s"]
        start_s = c["sync"] / fps - lock_s
        i0 = int(round(start_s * SR)); src = 0
        if i0 < 0: src, i0 = -i0, 0
        seg = x[:, src: src + max(0, n - i0)]
        stems.setdefault(c["track"], np.zeros((2, n), np.float32))[:, i0:i0 + seg.shape[1]] += seg
        placed.append({**c, "start_frame": round(start_s * fps, 1)})
    return stems, placed, n

def duck_under_voice(sfx, voice, margin_db=6.0, active_db=-40.0, attack=0.03, release=0.18):
    """Voice is king: while the voice is active, pull the effects so they sit at least margin_db under it.
    Gain only ever goes down, and only while the voice talks, so builds keep full level in the pauses."""
    hop = int(0.01 * SR)
    def env(x):
        m = x.mean(0); k = len(m) // hop
        e = np.sqrt(np.mean(m[: k * hop].reshape(k, hop) ** 2, axis=1))
        e = np.convolve(e, np.ones(5) / 5, mode="same")
        return 20 * np.log10(e + 1e-9)
    ve, se = env(voice), env(sfx)
    want = np.where(ve > active_db, np.minimum(0.0, (ve - margin_db) - se), 0.0)
    g = np.zeros_like(want); a_c, r_c = math.exp(-0.01 / attack), math.exp(-0.01 / release)
    for i in range(len(want)):  # fast to duck, slow to recover
        prev = g[i - 1] if i else 0.0
        c = a_c if want[i] < prev else r_c
        g[i] = c * prev + (1 - c) * want[i]
    gain = np.repeat(10 ** (g / 20), hop)
    gain = np.pad(gain, (0, max(0, sfx.shape[1] - len(gain))), constant_values=1.0)[: sfx.shape[1]]
    return sfx * gain

def write_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1).T * 32767).astype("<i2").tobytes())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edit"); ap.add_argument("cues"); ap.add_argument("inventory"); ap.add_argument("out")
    ap.add_argument("--tom"); ap.add_argument("--voice"); ap.add_argument("--stills")
    a = ap.parse_args()
    cfg = json.load(open(a.edit)); cues = json.load(open(a.cues)); inv = json.load(open(a.inventory))
    os.makedirs(a.out, exist_ok=True)
    fps, N = cfg["fps"], cfg["frames"]
    tom = Tom(a.tom)
    scenes = cfg["scenes"]
    def scene_at(f): return next(s for s in scenes if s["f0"] <= f < s["f1"])

    def frame(f, tf):
        sc = scene_at(f)
        img = scene_frame(f, sc, tf, cfg)
        if sc["in"] == "wipe" and f < sc["f0"] + cfg["wipe_frames"]:
            prev = next(s for s in scenes if s["f1"] == sc["f0"])
            img = circle_wipe(scene_frame(sc["f0"] - 1, prev, tf, cfg).convert("RGB"), img.convert("RGB"),
                              (f - sc["f0"] + 1) / cfg["wipe_frames"], *sc.get("wipe_from", (540, 960)))
        return img.convert("RGB")

    if a.stills:
        tf = tom.next()
        for s in a.stills.split(","):
            frame(int(s), tf).save(os.path.join(a.out, f"still_{int(s):03d}.png"))
        return

    stems, placed, n = build_stems(cues, inv, os.path.join(os.path.dirname(os.path.abspath(a.cues)), cues["library_root"]), N, fps)
    for name, x in stems.items():
        write_wav(os.path.join(a.out, f"STEM_{name}.wav"), x)
    mix = sum(stems.values())
    if a.voice:
        v = read_stereo(a.voice); vv = np.zeros((2, n), np.float32); vv[:, :min(n, v.shape[1])] = v[:, :n]
        write_wav(os.path.join(a.out, "STEM_VOICE.wav"), vv)
        mix = duck_under_voice(mix, vv) + vv
        write_wav(os.path.join(a.out, "SFX_DUCKED.wav"), mix - vv)
    peak = float(np.max(np.abs(mix)))
    if peak > 0.89:  # protect against clipping by pulling only the HITS stem, never the voice
        print(f"mix peak {20*math.log10(peak):.1f} dBFS: pulling HITS by 3 dB")
        mix = mix - stems.get("HITS", 0) * (1 - 10 ** (-3 / 20))
    write_wav(os.path.join(a.out, "MIX.wav"), mix)
    json.dump(placed, open(os.path.join(a.out, "placed_cues.json"), "w"), indent=1)

    out = os.path.join(a.out, "ssme_divorced_v6.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-i", os.path.join(a.out, "MIX.wav"),
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for f in range(N):
        enc.stdin.write(frame(f, tom.next()).tobytes())
    enc.stdin.close(); enc.wait()
    print("wrote", out)

if __name__ == "__main__":
    main()
