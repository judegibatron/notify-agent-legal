"""Build the house SFX library: 30 sound types x 4 versions (A-D), coded W/T/R + number + letter.

usage: python3 build_library.py <out_dir>
Writes <out_dir>/<Category>/<Code>_<Type>/<Code><Letter>_<slug>.wav (stereo 48 kHz 16-bit) and catalog.json.
Every sound is generated on its own (one per call) with a fixed seed, so rebuilding is reproducible.
"""
import json, os, re, sys, wave
import numpy as np
from dsp import *  # noqa: F401,F403
import dsp

# ================= WHOOSH ENGINE =================
def whoosh(dur=0.6, peak=0.5, color="pink", lo=300, hi=3000, q=1.2, kind="band", rise=2.0, fall=1.6,
           pan_from=-0.5, pan_to=0.5, tone=None, sub=None, comb_ms=None, verb=(0.6, 0.12), drive=1.0,
           crush_bits=None, flutter=0.0):
    n = n_of(dur); t = np.arange(n) / SR; pt = peak * dur
    e = env_peak(n, peak, rise, fall)
    if flutter:
        e = e * (1 - flutter * 0.5 * (1 + np.sin(2 * np.pi * 17 * t)))
    fc = lo * (hi / lo) ** env_peak(n, peak, 1.3, 1.1)
    src = stereo_noise(n, color, 0.35)
    st = np.stack([sweep(src[c], kind, fc, q) for c in (0, 1)]) * e
    if comb_ms:
        st = np.stack([comb(st[c], comb_ms / 1000 * (1 + 0.04 * c), 0.62, 0.7) for c in (0, 1)])
    mono = np.zeros(n)
    if tone:
        f0, depth, wave_, lvl = tone
        f = f0 * (1 + depth * np.tanh((pt - t) * 7))
        mono += lp(osc(f, wave_), f0 * 4) * e * lvl
    if sub:
        f0, lvl = sub
        mono += osc(f0 * (1 + 0.35 * np.tanh((pt - t) * 6))) * e ** 1.4 * lvl
    pos = np.linspace(pan_from, pan_to, n)
    a = (pos + 1) * np.pi / 4
    st = np.stack([st[0] * np.cos(a) * 1.41, st[1] * np.sin(a) * 1.41]) + pan(mono, pos)
    if crush_bits:
        st = np.stack([crush(st[c] / (np.max(np.abs(st)) + 1e-9), crush_bits, 3) for c in (0, 1)])
    if drive != 1.0:
        st = sat(st / (np.max(np.abs(st)) + 1e-9), drive)
    if verb:
        st = reverb(st, decay=verb[0], wet=verb[1])
    return st

# ================= TEXTURE HELPERS =================
def S(*parts):
    """Sum mono layers of different lengths (zero-padded to the longest)."""
    L = max(len(p) for p in parts); out = np.zeros(L)
    for p in parts: out[:len(p)] += p
    return out

def click(dur=0.03, hp_f=2000, decay=180, color="white"):
    n = n_of(dur)
    return hp(noise(n, color), hp_f) * env_exp(n, decay, 0.0005)

def tone_blip(f0, f1, dur, decay, wave_="sine", attack=0.001):
    n = n_of(dur)
    return osc(curve(n, f0, f1, "exp"), wave_) * env_exp(n, decay, attack)

def thock(body_f=165, body2=248, dur=0.25, nlp=1400, decay=55, body_decay=32, flap=0.25):
    n = n_of(dur); t = np.arange(n) / SR
    burst = lp(noise(n), nlp, 4) * env_exp(n, decay, 0.003) * 3
    body = (osc(body_f) * 0.6 + osc(body2) * 0.3) * env_exp(n, body_decay, 0.003)
    x = burst + body
    if flap:
        d = int(SR * 0.028); y = np.zeros(n); y[d:] = x[:-d] * flap; x = x + y
    return x

def chime(notes, dur=1.2, decay=4.5, bright=0.3, wave_="sine", spread=0.09):
    n = n_of(dur); t = np.arange(n) / SR; out = np.zeros(n)
    for k, f in enumerate(notes):
        st_ = k * spread; m = t >= st_; tt = np.clip(t - st_, 0, None)
        out += m * (osc(np.full(n, f), wave_) + bright * osc(np.full(n, 2 * f)) + 0.12 * osc(np.full(n, 3.01 * f))) * np.exp(-tt * decay) * np.clip(tt / 0.002, 0, 1)
    return out

def gear_ticks(count, span, f_ring=3200, jitter=0.15, decay=260, accel=0.0, dur=None):
    dur = dur or span + 0.15
    n = n_of(dur); out = np.zeros(n)
    times = np.linspace(0, span, count)
    if accel:
        times = span * (np.linspace(0, 1, count) ** (1 + accel))
    for k, t0 in enumerate(times):
        t0 += dsp._rng.uniform(-jitter, jitter) * span / max(count, 1) * 0.5
        i = max(0, int(t0 * SR)); m = n_of(0.03)
        tick = hp(noise(m), 2500) * env_exp(m, decay, 0.0003) + osc(np.full(m, f_ring * dsp._rng.uniform(0.9, 1.1))) * env_exp(m, decay * 1.3) * 0.4
        out[i:i + m] += tick[: max(0, n - i)] * dsp._rng.uniform(0.6, 1.0)
    return out

def impact(f_hi=110, f_lo=42, dur=1.6, decay=3.0, click_lvl=0.6, noise_lvl=0.5, noise_lp=3000):
    n = n_of(dur); t = np.arange(n) / SR
    boom = osc(f_lo + (f_hi - f_lo) * np.exp(-t * 14)) * np.exp(-t * decay)
    crack = lp(noise(n), noise_lp) * np.exp(-t * 28) * noise_lvl
    cl = hp(noise(n), 3000) * np.exp(-t * 300) * click_lvl
    return sat(boom + crack + cl, 1.6)

def riser_env(n, power=2.4, cut=0.985):
    x = np.linspace(0, 1, n)
    return x ** power * (x < cut)

# ================= SOUND DEFINITIONS =================
LIB = []  # (category, type_code, type_name, letter, slug, description, fn)
def add(cat, code, name, letter, slug, desc):
    def deco(fn):
        LIB.append((cat, code, name, letter, slug, desc, fn)); return fn
    return deco

W, Tx, R = "W_WHOOSHES", "T_TEXTURES", "R_RISERS-AND-HITS"

# ---- W01 Hollow whoosh (standard slides & pans) ----
@add(W, "W01", "Hollow-whoosh", "A", "soft-airy", "Soft airy hollow pass, gentle L-to-R pan. Standard text or card slide.")
def _(): return whoosh(0.6, 0.5, "pink", 350, 2600, 1.1, comb_ms=3.2, verb=(0.5, 0.12))
@add(W, "W01", "Hollow-whoosh", "B", "resonant-tube", "Tube-like resonance with more texture. Slides that need body.")
def _(): return whoosh(0.65, 0.5, "pink", 250, 2200, 1.6, comb_ms=5.5, verb=(0.6, 0.14), tone=(220, 0.3, "tri", 0.12))
@add(W, "W01", "Hollow-whoosh", "C", "fast-punchy", "Quick, tight hollow swish with a sharp peak. Fast slides.")
def _(): return whoosh(0.38, 0.45, "white", 600, 4500, 1.3, rise=2.6, fall=2.2, comb_ms=2.4, verb=(0.35, 0.08))
@add(W, "W01", "Hollow-whoosh", "D", "wide-pan", "Wide stereo hollow sweep traveling hard left to right. Pans and slide-ins from the side.")
def _(): return whoosh(0.75, 0.55, "pink", 300, 3000, 1.0, pan_from=-0.95, pan_to=0.95, comb_ms=4.0, verb=(0.7, 0.16))

# ---- W02 Deep voice whoosh (default sci-fi) ----
@add(W, "W02", "Deep-voice-whoosh", "A", "low-growl", "Low growling pass with a pitch drop after the peak. Default for most animations.")
def _(): return whoosh(0.7, 0.5, "brown", 120, 1400, 1.0, tone=(110, 0.45, "saw", 0.35), sub=(55, 0.3), verb=(0.6, 0.12), drive=1.6)
@add(W, "W02", "Deep-voice-whoosh", "B", "formant-vowel", "Vowel-like 'ooo-aaa' sci-fi sweep. Characterful UI moves.")
def _():
    st = whoosh(0.75, 0.5, "pink", 200, 1800, 1.4, tone=(130, 0.35, "saw", 0.3), verb=None)
    n = st.shape[1]; fset = [420, 900, 2400]
    st = np.stack([formants(st[c], fset, 5) * 2 + st[c] * 0.4 for c in (0, 1)])
    return reverb(st, 0.6, 0.12)
@add(W, "W02", "Deep-voice-whoosh", "C", "sub-rumble", "Heavy sub-weighted rumble pass. Bigger camera moves and zooms.")
def _(): return whoosh(0.85, 0.5, "brown", 80, 900, 0.9, sub=(42, 0.6), tone=(85, 0.4, "sine", 0.3), verb=(0.8, 0.12), drive=1.3)
@add(W, "W02", "Deep-voice-whoosh", "D", "gritty-scifi", "Gritty, slightly crushed sci-fi pass. Tech and UI animations.")
def _(): return whoosh(0.65, 0.5, "pink", 180, 2400, 1.2, tone=(140, 0.5, "square", 0.18), crush_bits=7, drive=1.8, verb=(0.5, 0.1))

# ---- W03 Futuristic whoosh ----
@add(W, "W03", "Futuristic-whoosh", "A", "digital-shimmer", "FM shimmer riding an airy sweep. Clean tech slides.")
def _():
    st = whoosh(0.6, 0.5, "white", 800, 7000, 1.4, verb=None)
    n = st.shape[1]; e = env_peak(n, 0.5)
    sh = fm(curve(n, 900, 1800, "bell"), 2.01, curve(n, 0.5, 4, "bell")) * e * 0.25
    return reverb(mix(st, pan(sh, np.linspace(-0.6, 0.6, n))), 0.7, 0.18)
@add(W, "W03", "Futuristic-whoosh", "B", "laser-zip", "Fast laser zip with a falling pitch. Quick sci-fi moves.")
def _(): return whoosh(0.4, 0.4, "white", 1200, 9000, 1.6, tone=(1400, 0.8, "saw", 0.22), rise=2.4, fall=2.0, verb=(0.4, 0.12))
@add(W, "W03", "Futuristic-whoosh", "C", "phaser-sweep", "Phaser-style swirl. Smooth futuristic transitions inside an animation.")
def _():
    st = whoosh(0.7, 0.5, "pink", 400, 5000, 1.2, verb=None)
    n = st.shape[1]; lfo = 0.003 + 0.002 * np.sin(np.linspace(0, 6 * np.pi, n))
    out = np.stack([st[c] + np.interp(np.arange(n) - lfo * SR, np.arange(n), st[c]) for c in (0, 1)])
    return reverb(out, 0.6, 0.14)
@add(W, "W03", "Futuristic-whoosh", "D", "bitcrush-sweep", "Lo-fi bitcrushed sweep. Glitchy, digital feel.")
def _(): return whoosh(0.55, 0.5, "white", 500, 6000, 1.3, crush_bits=5, verb=(0.4, 0.1))

# ---- W04 Organic wind ----
@add(W, "W04", "Organic-wind-whoosh", "A", "gentle-breeze", "Soft, slow breeze. Gentle slides and slow drifts.")
def _(): return whoosh(1.2, 0.55, "pink", 300, 1400, 0.8, kind="band", rise=1.4, fall=1.2, verb=(0.8, 0.1))
@add(W, "W04", "Organic-wind-whoosh", "B", "gust", "A single natural gust with flutter. Medium-slow movements.")
def _(): return whoosh(0.9, 0.5, "pink", 250, 2200, 0.9, rise=1.6, fall=1.3, flutter=0.35, verb=(0.7, 0.12))
@add(W, "W04", "Organic-wind-whoosh", "C", "long-drift", "Long, very soft drift. Slow camera push or pan.")
def _(): return whoosh(1.8, 0.6, "brown", 200, 1000, 0.7, rise=1.3, fall=1.1, pan_from=-0.3, pan_to=0.3, verb=(1.0, 0.12))
@add(W, "W04", "Organic-wind-whoosh", "D", "airy-whistle", "Breathy wind with a faint whistle. Calm reveals.")
def _(): return whoosh(1.1, 0.55, "pink", 400, 2600, 2.5, tone=(900, 0.15, "sine", 0.05), rise=1.5, fall=1.2, verb=(0.9, 0.15))

# ---- W05 Short whoosh ----
@add(W, "W05", "Short-whoosh", "A", "swish", "Cloth-like swish. Very quick, small moves.")
def _(): return whoosh(0.22, 0.45, "white", 900, 6000, 1.4, rise=2.2, fall=2.0, verb=(0.25, 0.06))
@add(W, "W05", "Short-whoosh", "B", "flick", "Tiny flick. Small icon or word nudges.")
def _(): return whoosh(0.16, 0.4, "white", 1500, 8000, 1.6, rise=2.6, fall=2.4, verb=None)
@add(W, "W05", "Short-whoosh", "C", "zip", "Fast zip with a hint of pitch. Snap zooms.")
def _(): return whoosh(0.26, 0.45, "white", 1000, 7000, 1.5, tone=(800, 0.5, "tri", 0.15), rise=2.4, fall=2.0, verb=(0.25, 0.06))
@add(W, "W05", "Short-whoosh", "D", "micro-swoop", "Soft micro-swoop, darker. Small UI slides.")
def _(): return whoosh(0.28, 0.5, "pink", 500, 3000, 1.2, rise=2.0, fall=1.8, verb=(0.3, 0.08))

# ---- W06 Generic long whoosh (half riser) ----
@add(W, "W06", "Generic-long-whoosh", "A", "slow-build", "1.8 s build that whips into a peak near the end. Builds into a quick transition.")
def _(): return whoosh(1.8, 0.85, "pink", 200, 4000, 1.0, rise=2.6, fall=1.5, verb=(0.7, 0.14))
@add(W, "W06", "Generic-long-whoosh", "B", "reverse-tail", "Reverse-swell into a sudden stop. Suck-in before a cut.")
def _(): return reverse(whoosh(1.6, 0.15, "pink", 250, 3500, 1.0, rise=1.5, fall=2.4, verb=(1.0, 0.25)))
@add(W, "W06", "Generic-long-whoosh", "C", "rising-tonal", "Long airy build with a rising tone. Anticipation before a reveal.")
def _(): return whoosh(1.6, 0.85, "pink", 300, 5000, 1.2, tone=(180, -0.6, "saw", 0.15), rise=2.4, fall=1.6, verb=(0.8, 0.14))
@add(W, "W06", "Generic-long-whoosh", "D", "filtered-pass-by", "Slow, distant filtered pass-by. Long camera moves.")
def _(): return whoosh(1.5, 0.6, "brown", 150, 2000, 0.9, kind="low", rise=1.8, fall=1.4, pan_from=-0.9, pan_to=0.9, verb=(0.9, 0.18))

# ---- W07 Synthetic whoosh (scene transitions) ----
@add(W, "W07", "Synthetic-whoosh", "A", "saw-sweep", "Saw-synth sweep with air. Scene-to-scene transitions.")
def _(): return whoosh(0.7, 0.55, "pink", 300, 4000, 1.2, tone=(160, 0.55, "saw", 0.3), verb=(0.6, 0.14), drive=1.4)
@add(W, "W07", "Synthetic-whoosh", "B", "pulse-up", "Pulse wave that sweeps upward into the cut.")
def _(): return whoosh(0.7, 0.7, "white", 400, 6000, 1.3, tone=(200, -0.6, "square", 0.16), rise=2.4, verb=(0.5, 0.12))
@add(W, "W07", "Synthetic-whoosh", "C", "down-sweep", "Downward synth dive out of a scene.")
def _(): return whoosh(0.7, 0.3, "pink", 300, 5000, 1.2, tone=(300, 0.7, "saw", 0.25), rise=1.6, fall=1.8, verb=(0.6, 0.14))
@add(W, "W07", "Synthetic-whoosh", "D", "detuned-stack", "Thick detuned synth stack, wide. Bold transitions.")
def _():
    st = whoosh(0.75, 0.55, "pink", 250, 3500, 1.1, verb=None)
    n = st.shape[1]; t = np.arange(n) / SR; e = env_peak(n, 0.55); pt = 0.55 * 0.75
    f = 150 * (1 + 0.5 * np.tanh((pt - t) * 7))
    L = (osc(f * 0.995, "saw") + osc(f * 1.01, "saw")) * e * 0.18
    Rr = (osc(f * 1.005, "saw") + osc(f * 0.99, "saw")) * e * 0.18
    return reverb(mix(st, np.stack([lp(L, 2500), lp(Rr, 2500)])), 0.6, 0.15)

# ---- W08 Transition spacey whoosh ----
@add(W, "W08", "Transition-spacey-whoosh", "A", "reverb-wash", "Spacey whoosh into a long reverb wash. Dreamy scene changes.")
def _(): return whoosh(0.7, 0.55, "pink", 400, 6000, 1.3, verb=(2.2, 0.45))
@add(W, "W08", "Transition-spacey-whoosh", "B", "shimmer-rise", "Rising shimmer with sparkle. Bright transitions.")
def _():
    st = whoosh(0.8, 0.7, "white", 900, 9000, 1.5, rise=2.4, verb=None)
    n = st.shape[1]; e = env_peak(n, 0.7, 2.4)
    sp = sum(osc(np.full(n, f)) for f in (2093, 2637, 3136)) * e * 0.08 * (0.6 + 0.4 * np.sin(np.linspace(0, 40, n)))
    return reverb(mix(st, widen(sp, 0.8)), 1.6, 0.35)
@add(W, "W08", "Transition-spacey-whoosh", "C", "tape-stop", "Pitch-diving tape-stop whoosh. Hard exits.")
def _(): return whoosh(0.7, 0.35, "pink", 300, 5000, 1.2, tone=(600, 1.2, "saw", 0.2), rise=1.4, fall=1.4, verb=(1.0, 0.25))
@add(W, "W08", "Transition-spacey-whoosh", "D", "tunnel", "Through-a-tunnel whoosh with resonant comb. Immersive transitions.")
def _(): return whoosh(0.8, 0.5, "pink", 300, 4000, 1.1, comb_ms=8.0, verb=(1.6, 0.3), pan_from=-0.8, pan_to=0.8)

# ---- W09 Water dropper ----
@add(W, "W09", "Water-dropper", "A", "droplet", "Single droplet blip with a little room. Clean scene switch.")
def _():
    x = S(tone_blip(700, 1900, 0.25, 22) * 0.8, click(0.01, 3000, 400) * 0.2)
    return reverb(widen(x, 0.5), 0.8, 0.25)
@add(W, "W09", "Water-dropper", "B", "bubble-rise", "Upward bubbly sweep. Light, playful transitions.")
def _():
    n = n_of(0.5); t = np.arange(n) / SR; out = np.zeros(n)
    for k in range(7):
        i = int(k * 0.06 * SR); m = n_of(0.08)
        b = tone_blip(500 + k * 180, 1400 + k * 300, 0.08, 45); out[i:i + m] += b[: n - i] * (0.5 + k * 0.07)
    return reverb(pan(out, np.linspace(-0.4, 0.4, n)), 0.7, 0.2)
@add(W, "W09", "Water-dropper", "C", "drip-verb", "Drip into a deep reverb. Moody transitions.")
def _(): return reverb(widen(tone_blip(500, 1500, 0.3, 18), 0.7), 2.0, 0.45)
@add(W, "W09", "Water-dropper", "D", "liquid-swoosh", "Liquid whoosh with bubbly modulation. Fluid scene changes.")
def _():
    st = whoosh(0.6, 0.5, "pink", 500, 3500, 2.0, verb=None)
    n = st.shape[1]; mod = 0.6 + 0.4 * np.sin(2 * np.pi * curve(n, 6, 24) * np.arange(n) / SR)
    return reverb(st * mod, 0.8, 0.2)

# ---- W10 Classy airy whoosh (big, heavy, rare) ----
@add(W, "W10", "Classy-airy-whoosh", "A", "big-heavy", "Big, slow, heavy air movement. Large, weighty moves only.")
def _(): return whoosh(1.2, 0.5, "pink", 150, 2500, 0.9, sub=(40, 0.35), rise=1.8, fall=1.4, verb=(1.4, 0.2))
@add(W, "W10", "Classy-airy-whoosh", "B", "cinematic-pass", "Cinematic pass-by with a low thump at the peak.")
def _():
    st = whoosh(1.1, 0.5, "pink", 200, 3500, 1.0, verb=None)
    thump = place(widen(impact(90, 40, 0.8, 5, 0.1, 0.2) * 0.5, 0.2), 0.5, 1.1 + 0.8)
    return reverb(mix(st, thump), 1.2, 0.2)
@add(W, "W10", "Classy-airy-whoosh", "C", "velvet", "Smooth, rounded, luxurious air. Elegant reveals.")
def _(): return whoosh(1.0, 0.5, "brown", 200, 1800, 0.8, kind="low", rise=1.6, fall=1.3, verb=(1.2, 0.22))
@add(W, "W10", "Classy-airy-whoosh", "D", "grand-sweep", "Grand wide sweep with a long tail. Hero moments.")
def _(): return whoosh(1.3, 0.5, "pink", 200, 4500, 1.0, pan_from=-0.9, pan_to=0.9, sub=(45, 0.25), verb=(2.0, 0.3))

# ---- T01 Pop ----
@add(Tx, "T01", "Pop", "A", "bubble", "Round bubble pop. Clean text or element pops.")
def _(): return reverb(widen(S(tone_blip(380, 1100, 0.12, 40), click(0.008, 2500, 600) * 0.3), 0.3), 0.3, 0.08)
@add(Tx, "T01", "Pop", "B", "mouth", "Mouth-style pop, warm and short. Friendly UI pops.")
def _(): return widen(S(lp(tone_blip(900, 250, 0.09, 55), 3000), lp(click(0.01, 400, 400), 3000) * 0.5), 0.2)
@add(Tx, "T01", "Pop", "C", "cork", "Snappy cork pop. Emphasis pops.")
def _(): return reverb(widen(S(click(0.02, 800, 220) * 0.8, tone_blip(600, 300, 0.07, 60) * 0.6), 0.3), 0.35, 0.1)
@add(Tx, "T01", "Pop", "D", "soft-plop", "Soft, muted plop. Subtle captions or small elements.")
def _(): return widen(lp(tone_blip(320, 160, 0.14, 35), 1500), 0.2)

# ---- T02 UI click ----
@add(Tx, "T02", "UI-click", "A", "crisp-tick", "Crisp, tiny tick. UI elements popping up.")
def _(): return widen(click(0.02, 3000, 400) + tone_blip(2400, 2200, 0.02, 250) * 0.3, 0.2)
@add(Tx, "T02", "UI-click", "B", "soft-tap", "Soft finger-tap. Gentle UI.")
def _(): return widen(lp(click(0.04, 300, 160), 2500) + tone_blip(900, 800, 0.04, 120) * 0.3, 0.2)
@add(Tx, "T02", "UI-click", "C", "double", "Quick double click. Toggles and confirmations.")
def _():
    a = click(0.02, 2500, 350) + tone_blip(1800, 1700, 0.02, 250) * 0.3
    return widen(np.concatenate([a, np.zeros(n_of(0.05)), a * 0.7]), 0.2)
@add(Tx, "T02", "UI-click", "D", "glassy", "Glassy click with a short ring. Premium UI buttons.")
def _(): return reverb(widen(S(click(0.015, 4000, 500) * 0.6, chime([2637], 0.25, 22, 0.1)), 0.3), 0.4, 0.1)

# ---- T03 Sci-fi click ----
@add(Tx, "T03", "Sci-fi-click", "A", "blip", "Short digital blip. Something changes inside the animation.")
def _(): return widen(tone_blip(1600, 1600, 0.05, 80, "square") * 0.4, 0.2)
@add(Tx, "T03", "Sci-fi-click", "B", "chirp", "Upward chirp. Color or state changes.")
def _(): return widen(tone_blip(900, 3200, 0.07, 45, "tri") * 0.6, 0.3)
@add(Tx, "T03", "Sci-fi-click", "C", "digital-ping", "Short FM ping. Data or UI updates.")
def _():
    n = n_of(0.2); return reverb(widen(fm(np.full(n, 1200), 3.5, curve(n, 3, 0.1)) * env_exp(n, 30), 0.3), 0.4, 0.12)
@add(Tx, "T03", "Sci-fi-click", "D", "crushed-tick", "Bitcrushed tick. Glitchy changes.")
def _(): return widen(crush(click(0.03, 1500, 200) + tone_blip(1000, 700, 0.03, 120), 5, 4), 0.2)

# ---- T04 Sci-fi impact (reveal) ----
@add(Tx, "T04", "Sci-fi-impact", "A", "punchy-zap", "Punchy thump with a zap. A new UI or object enters the scene.")
def _():
    n = n_of(0.7); t = np.arange(n) / SR
    x = osc(60 + 90 * np.exp(-t * 18)) * np.exp(-t * 7) + osc(2400 * np.exp(-t * 9) + 300) * np.exp(-t * 14) * 0.35
    return reverb(widen(sat(x + hp(noise(n), 4000) * np.exp(-t * 60) * 0.4, 1.4), 0.4), 0.6, 0.15)
@add(Tx, "T04", "Sci-fi-impact", "B", "metal-slam", "Metallic slam with ring. Heavier reveals.")
def _():
    n = n_of(1.0); t = np.arange(n) / SR
    ring = sum(osc(np.full(n, f)) / (k + 1) for k, f in enumerate([420, 1160, 2270, 3750])) * np.exp(-t * 6) * 0.4
    return reverb(widen(sat(impact(120, 50, 1.0, 6, 0.6, 0.4) * 0.8 + ring, 1.3), 0.4), 0.8, 0.18)
@add(Tx, "T04", "Sci-fi-impact", "C", "deep-boom", "Deep boom reveal. A big object appears.")
def _(): return reverb(widen(impact(100, 38, 1.4, 3.5, 0.3, 0.3), 0.3), 1.0, 0.15)
@add(Tx, "T04", "Sci-fi-impact", "D", "glitch", "Glitchy stutter impact. Digital reveals.")
def _():
    base = impact(140, 55, 0.6, 8, 0.6, 0.5)
    g = np.concatenate([base[:n_of(0.03)], np.zeros(n_of(0.02)), base[:n_of(0.03)] * 0.8, base])
    return reverb(widen(crush(g, 6, 2), 0.3), 0.5, 0.12)

# ---- T05 Digital camera click ----
@add(Tx, "T05", "Digital-camera-click", "A", "shutter", "Classic two-part shutter. Clip-to-clip cuts and flashes.")
def _():
    a = click(0.03, 1800, 180); b = click(0.03, 2500, 220) * 0.8
    return widen(np.concatenate([a, np.zeros(n_of(0.04)), b]), 0.3)
@add(Tx, "T05", "Digital-camera-click", "B", "shutter-winder", "Shutter plus a tiny motor wind. Photo-style transitions.")
def _():
    a = np.concatenate([click(0.03, 1800, 180), np.zeros(n_of(0.035)), click(0.03, 2500, 220) * 0.8])
    w = bp(noise(n_of(0.18)), 1800, 4200) * env_peak(n_of(0.18), 0.3) * 0.25 * (0.6 + 0.4 * np.sin(np.linspace(0, 70, n_of(0.18))))
    return widen(np.concatenate([a, np.zeros(n_of(0.02)), w]), 0.3)
@add(Tx, "T05", "Digital-camera-click", "C", "mirrorless", "Soft, quiet mirrorless click. Subtle cuts.")
def _(): return widen(lp(np.concatenate([click(0.025, 900, 220), np.zeros(n_of(0.03)), click(0.02, 1200, 260) * 0.6]), 5000), 0.2)
@add(Tx, "T05", "Digital-camera-click", "D", "flash-charge", "Flash charge whine and then a click. Big cut moments.")
def _():
    n = n_of(0.35); whine = osc(curve(n, 2000, 6000, "in")) * curve(n, 0.0, 0.15, "in")
    return widen(np.concatenate([whine, click(0.04, 1500, 150)]), 0.3)

# ---- T06 Analog button / cardboard (checklist) ----
@add(Tx, "T06", "Analog-button-cardboard", "A", "soft-thock", "Soft muffled thock with a paper flap. The checklist sound you asked for.")
def _(): return widen(thock(), 0.3)
@add(Tx, "T06", "Analog-button-cardboard", "B", "box-tap", "Knuckle tap on a cardboard box, hollow and warm.")
def _(): return reverb(widen(thock(120, 310, 0.3, 1100, 45, 22, 0.15), 0.3), 0.25, 0.1)
@add(Tx, "T06", "Analog-button-cardboard", "C", "felt-press", "Felt-dampened button press, very soft and satisfying.")
def _(): return widen(lp(thock(200, 300, 0.18, 800, 70, 45, 0.0), 1200), 0.2)
@add(Tx, "T06", "Analog-button-cardboard", "D", "paper-stamp", "Paper stamp: thock plus a crisp paper edge. Checks and stamps.")
def _(): return widen(thock(150, 260, 0.25, 1600, 50, 30, 0.2) + hp(noise(n_of(0.25)), 3000) * env_exp(n_of(0.25), 90, 0.002) * 0.25, 0.3)

# ---- T07 Mechanical click ----
@add(Tx, "T07", "Mechanical-click", "A", "switch", "Light toggle switch. Objects popping up.")
def _(): return widen(click(0.03, 1200, 250) + bp(noise(n_of(0.03)), 800, 2500) * env_exp(n_of(0.03), 200) * 0.6, 0.2)
@add(Tx, "T07", "Mechanical-click", "B", "latch", "Metal latch clack. Heavier mechanical pops.")
def _():
    n = n_of(0.12); t = np.arange(n) / SR
    return widen(click(0.12, 1000, 120) + sum(osc(np.full(n, f)) for f in (1900, 3100)) * np.exp(-t * 70) * 0.2, 0.3)
@add(Tx, "T07", "Mechanical-click", "C", "clicky-key", "Single clicky key. One-shot mechanical emphasis.")
def _(): return widen(np.concatenate([click(0.015, 2500, 500), np.zeros(n_of(0.02)), lp(click(0.03, 400, 200), 3000) * 0.8]), 0.2)
@add(Tx, "T07", "Mechanical-click", "D", "ratchet", "Three-step ratchet. Small mechanical sequences.")
def _(): return widen(gear_ticks(3, 0.12, 2200, 0.05, 220), 0.3)

# ---- T08 Gears / tiny gearwheel (letter-by-letter) ----
@add(Tx, "T08", "Gears-tiny-gearwheel", "A", "tick-run", "Even run of tiny gear ticks. Letter-by-letter text.")
def _(): return widen(gear_ticks(12, 0.6, 3400, 0.1), 0.3)
@add(Tx, "T08", "Gears-tiny-gearwheel", "B", "clockwork", "Clockwork tick-tock pattern. Mechanical write-outs.")
def _():
    a = gear_ticks(8, 0.7, 2600, 0.0, 300); b = gear_ticks(8, 0.7, 1800, 0.0, 300)
    n = max(len(a), len(b)); b = np.concatenate([np.zeros(n_of(0.045)), b])[:n]
    return widen(a[:n] + b * 0.7, 0.3)
@add(Tx, "T08", "Gears-tiny-gearwheel", "C", "spin-up", "Gear spinning up and speeding. Text that writes out faster and faster.")
def _(): return widen(gear_ticks(18, 0.7, 3000, 0.05, 260, accel=-0.5), 0.3)
@add(Tx, "T08", "Gears-tiny-gearwheel", "D", "single-cog", "One small cog click. One emphasis per letter or element.")
def _(): return widen(gear_ticks(1, 0.0, 3200, 0.0, 240, dur=0.08), 0.2)

# ---- T09 Complex mechanism gizmo (multiple assets in sequence) ----
@add(Tx, "T09", "Complex-mechanism-gizmo", "A", "clunk-whirr", "Clunk followed by a tiny whirr. One per element in a sequence.")
def _():
    n = n_of(0.25); whirr = bp(noise(n), 1500, 5000) * env_peak(n, 0.3) * 0.3 * (0.6 + 0.4 * np.sin(np.linspace(0, 90, n)))
    return widen(np.concatenate([click(0.04, 700, 150), whirr]), 0.3)
@add(Tx, "T09", "Complex-mechanism-gizmo", "B", "servo", "Short servo motor move. Mechanical UI.")
def _():
    n = n_of(0.22)
    return widen(S(osc(curve(n, 600, 900, "bell"), "square") * env_peak(n, 0.5, 1.2, 1.2) * 0.12, click(0.02, 2000, 300) * 0.3), 0.3)
@add(Tx, "T09", "Complex-mechanism-gizmo", "C", "lock-in", "Mechanism locks into place. Assets snapping in sequence.")
def _(): return widen(np.concatenate([gear_ticks(2, 0.05, 2600, 0, 300), click(0.05, 600, 120) * 1.2]), 0.3)
@add(Tx, "T09", "Complex-mechanism-gizmo", "D", "gizmo-chirp", "Mechanical tick with a tiny chirp. Playful gadget pops.")
def _(): return widen(np.concatenate([click(0.02, 2000, 300), tone_blip(1200, 2600, 0.06, 60, "tri") * 0.4]), 0.3)

# ---- T10 Keyboard typing ----
def typing(count, span, hp_f, lp_f, body, seed_=0, dur=None):
    dur = dur or span + 0.1; n = n_of(dur); out = np.zeros(n)
    for k in range(count):
        t0 = k * span / count + dsp._rng.uniform(0, span / count * 0.5)
        i = int(t0 * SR); m = n_of(0.05)
        key = lp(hp(noise(m), hp_f), lp_f) * env_exp(m, 160, 0.0005) + osc(np.full(m, body * dsp._rng.uniform(0.9, 1.1))) * env_exp(m, 90) * 0.3
        out[i:i + m] += key[: n - i] * dsp._rng.uniform(0.6, 1.0)
    return out
@add(Tx, "T10", "Keyboard-writing", "A", "mechanical", "Mechanical keyboard burst. Typing on screen.")
def _(): return widen(typing(8, 0.9, 1500, 9000, 420), 0.3)
@add(Tx, "T10", "Keyboard-writing", "B", "laptop", "Soft laptop keys. Quiet typing.")
def _(): return widen(typing(8, 0.9, 600, 4000, 300), 0.3)
@add(Tx, "T10", "Keyboard-writing", "C", "typewriter", "Typewriter strikes plus a bell. Retro write-outs.")
def _():
    x = typing(6, 0.8, 1000, 7000, 250)
    return widen(np.concatenate([x, chime([2093], 0.4, 10, 0.2) * 0.4]), 0.3)
@add(Tx, "T10", "Keyboard-writing", "D", "fast-burst", "Very fast typing burst. Quick text entry.")
def _(): return widen(typing(14, 0.6, 1400, 9000, 450), 0.3)

# ---- T11 Activate protection energy (entry into a new animation) ----
@add(Tx, "T11", "Activate-energy", "A", "power-up", "Rising power-up into a soft hit. Transition into a brand new animation.")
def _():
    n = n_of(0.8); t = np.arange(n) / SR
    up = osc(curve(n, 200, 1600, "in"), "saw") * curve(n, 0.05, 0.4, "in")
    return reverb(widen(np.concatenate([lp(up, 4000), impact(160, 70, 0.4, 9, 0.3, 0.3) * 0.6]), 0.5), 0.8, 0.2)
@add(Tx, "T11", "Activate-energy", "B", "shield-on", "Shield-on shimmer with a hum. Sci-fi entry.")
def _():
    n = n_of(1.0); t = np.arange(n) / SR
    hum = (osc(np.full(n, 110), "saw") * 0.2 + fm(np.full(n, 880), 1.5, curve(n, 3, 0.5)) * 0.3) * env_exp(n, 3, 0.05)
    return reverb(widen(lp(hum, 5000), 0.8), 1.0, 0.25)
@add(Tx, "T11", "Activate-energy", "C", "charge-zap", "Charge then zap. Energetic entries.")
def _():
    n = n_of(0.5); ch = osc(curve(n, 400, 3000, "in"), "square") * curve(n, 0.02, 0.2, "in")
    return reverb(widen(np.concatenate([ch, tone_blip(3000, 300, 0.25, 14, "saw") * 0.5]), 0.5), 0.6, 0.2)
@add(Tx, "T11", "Activate-energy", "D", "hum-swell", "Low energy hum that swells and settles. Calm sci-fi entry.")
def _():
    n = n_of(1.1); return reverb(widen(lp(osc(np.full(n, 82), "saw") + osc(np.full(n, 123), "saw") * 0.5, 1200) * env_peak(n, 0.4, 1.5, 1.5), 0.6), 1.0, 0.2)

# ---- T12 Success reward (conclusion reached) ----
@add(Tx, "T12", "Success-reward", "A", "three-note", "Three rising notes, warm. A conclusion is reached.")
def _(): return reverb(widen(chime([784, 988, 1319]), 0.4), 0.8, 0.2)
@add(Tx, "T12", "Success-reward", "B", "sparkle-ding", "Bright ding with sparkle. Wins and achievements.")
def _(): return reverb(widen(S(chime([1568, 2349], 1.0, 4, 0.4, spread=0.04), gear_ticks(6, 0.3, 6000, 0.3, 400) * 0.2), 0.5), 1.2, 0.25)
@add(Tx, "T12", "Success-reward", "C", "marimba", "Wooden marimba arpeggio. Friendly, human success.")
def _(): return reverb(widen(chime([523, 659, 784, 1047], 1.0, 9, 0.6, "tri", 0.07), 0.4), 0.6, 0.15)
@add(Tx, "T12", "Success-reward", "D", "soft-bell", "Single soft bell. Calm confirmations.")
def _(): return reverb(widen(chime([1046.5], 1.6, 2.5, 0.25), 0.4), 1.4, 0.25)

# ---- T13 Big reveal (heavenly choir) ----
def choir(chord, dur=2.0, vowel=(700, 1150, 2600), bright=1.0):
    n = n_of(dur); t = np.arange(n) / SR; out = np.zeros(n)
    for f in chord:
        for det in (0.995, 1.0, 1.006):
            vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t + det * 10)
            out += osc(f * det * vib, "saw")
    out = formants(out, vowel, 6) * env_peak(n, 0.3, 1.3, 1.6)
    return reverb(widen(out * bright, 1.2), 2.0, 0.35)
@add(Tx, "T13", "Big-reveal-choir", "A", "aah-choir", "Synthetic 'aah' choir swell. A big reveal that's a big deal.")
def _(): return choir([262, 330, 392, 523])
@add(Tx, "T13", "Big-reveal-choir", "B", "bright-pad", "Bright, airy pad swell. Uplifting reveals.")
def _(): return choir([392, 494, 587, 784], 1.8, (900, 1600, 3200))
@add(Tx, "T13", "Big-reveal-choir", "C", "angelic-shimmer", "Angelic high shimmer. Magical reveals.")
def _(): return mix(choir([523, 659, 784], 1.8, (800, 1400, 3000)) * 0.7, reverb(widen(chime([2093, 2637, 3136], 1.8, 2, 0.2, spread=0.12) * 0.4, 1), 1.5, 0.4))
@add(Tx, "T13", "Big-reveal-choir", "D", "organ-chord", "Warm organ chord. Dramatic, classic reveals.")
def _():
    n = n_of(2.0); out = sum(osc(np.full(n, f * h)) / h for f in (196, 247, 294, 392) for h in (1, 2, 3, 4))
    return reverb(widen(out * env_peak(n, 0.15, 1.2, 1.8), 1.0), 1.8, 0.3)

# ---- T14 Alarm buzzer (very low level) ----
@add(Tx, "T14", "Alarm-buzzer", "A", "soft-buzz", "Soft low buzz. Low-volume tension, use very quietly.")
def _():
    n = n_of(0.8); return widen(lp(osc(np.full(n, 110), "square"), 1500) * env_peak(n, 0.2, 1.2, 1.2) * 0.5, 0.3)
@add(Tx, "T14", "Alarm-buzzer", "B", "pulse-alarm", "Pulsing alarm beeps. Warnings and mistakes.")
def _():
    n = n_of(0.9); t = np.arange(n) / SR
    return widen(lp(osc(np.full(n, 880), "square"), 3000) * (np.sin(2 * np.pi * 5 * t) > 0) * 0.3, 0.3)
@add(Tx, "T14", "Alarm-buzzer", "C", "low-klaxon", "Low two-tone klaxon. Big 'wrong' moments.")
def _():
    n = n_of(1.0); t = np.arange(n) / SR
    f = np.where((t * 3) % 1 < 0.5, 330, 262)
    return reverb(widen(lp(osc(f, "saw"), 2000) * 0.4, 0.4), 0.6, 0.15)
@add(Tx, "T14", "Alarm-buzzer", "D", "tick-tock", "Tense ticking clock. Low-level countdown tension.")
def _(): return widen(gear_ticks(6, 1.25, 2000, 0.0, 300), 0.3)

# ---- R01 Sharp bass riser ----
def bass_riser(dur=1.6, f0=36, f1=110, grit=0.5, power=2.4, noise_hp=3000, roll=False):
    n = n_of(dur); t = np.arange(n) / SR; p = t / dur
    sub = osc(f0 * (f1 / f0) ** (p ** 1.5))
    g = hp(noise(n), noise_hp) * p ** 3 * grit
    if roll:
        g = g * (0.5 + 0.5 * (np.sin(2 * np.pi * curve(n, 8, 32) * t) > 0))
    x = sat(sub * 0.9 + g, 1.5) * riser_env(n, power)
    return widen(x, 0.6)
@add(R, "R01", "Sharp-bass-riser", "A", "classic", "Classic sub riser into a sharp stop. ~5 s after the hook.")
def _(): return bass_riser()
@add(R, "R01", "Sharp-bass-riser", "B", "snare-roll", "Bass riser with a tightening noise roll. More urgency.")
def _(): return bass_riser(1.6, 38, 120, 0.7, 2.2, 2500, roll=True)
@add(R, "R01", "Sharp-bass-riser", "C", "sub-swell", "Deep, smooth sub swell, little top end. Subtle builds.")
def _(): return bass_riser(1.8, 30, 80, 0.15, 2.0, 6000)
@add(R, "R01", "Sharp-bass-riser", "D", "aggressive", "Aggressive, distorted bass riser. Hard-hitting builds.")
def _():
    x = sat(bass_riser(1.4, 40, 160, 1.0, 2.6, 1800)[0] * 2.5, 2.5)
    return widen(x * riser_env(len(x), 1.2), 0.6)

# ---- R02 Metallic riser ----
def metal_riser(dur=1.6, base=330, ratios=(1.0, 2.76, 5.4, 8.93), bend=0.6, trem=(4, 16), grind=0.4, power=2.6):
    n = n_of(dur); t = np.arange(n) / SR; p = t / dur; out = np.zeros(n)
    for k, r in enumerate(ratios):
        out += osc(base * r * (1 + bend * p)) / (k + 1)
    out *= 0.7 + 0.3 * np.sin(2 * np.pi * curve(n, trem[0], trem[1]) * t)
    out += hp(noise(n), 4000) * p ** 3 * grind
    return reverb(widen(out * riser_env(n, power), 0.8), 0.6, 0.12)
@add(R, "R02", "Metallic-riser", "A", "bowed-metal", "Bowed-metal partials rising. The other favorite.")
def _(): return metal_riser()
@add(R, "R02", "Metallic-riser", "B", "ring-mod", "Ring-modulated metallic rise. Tense sci-fi build.")
def _():
    st = metal_riser(1.6, 280, (1, 2.4, 4.1), 0.8, (6, 28), 0.3)
    n = st.shape[1]; return st * osc(np.full(n, 47.0))
@add(R, "R02", "Metallic-riser", "C", "shimmer-glass", "Glassy high shimmer rising. Bright, clean build.")
def _(): return metal_riser(1.6, 880, (1, 2.0, 3.0, 4.2), 0.4, (8, 30), 0.15)
@add(R, "R02", "Metallic-riser", "D", "grind", "Grinding metal rise, gritty. Heavier transitions.")
def _(): return widen(sat(metal_riser(1.5, 200, (1, 1.5, 2.9, 4.7), 1.0, (10, 40), 0.9)[0] * 2, 2.0), 0.6)

# ---- R03 Suck-back risers (use very low or very loud) ----
@add(R, "R03", "Suck-back-riser", "A", "reverse-cymbal", "Reverse cymbal swell. Beautiful slow suck-in before a cut.")
def _():
    n = n_of(2.0); t = np.arange(n) / SR
    cym = hp(noise(n), 5000) * np.exp(-t * 2.2) + sum(osc(np.full(n, f)) for f in (3300, 5100, 7300)) * np.exp(-t * 3) * 0.05
    return reverse(reverb(widen(cym, 0.6), 1.0, 0.3))
@add(R, "R03", "Suck-back-riser", "B", "reverse-verb", "Reversed reverb of a soft hit. Ghostly pull-in.")
def _(): return reverse(reverb(widen(impact(200, 80, 0.3, 12, 0.6, 0.6), 0.3), 2.0, 0.8))
@add(R, "R03", "Suck-back-riser", "C", "reverse-boom", "Reverse boom, heavy low pull. Dramatic cuts.")
def _(): return reverse(reverb(widen(impact(120, 40, 1.8, 2.5, 0.4, 0.5), 0.4), 1.2, 0.3))
@add(R, "R03", "Suck-back-riser", "D", "reverse-shimmer", "Reverse shimmer chord, slow and pretty. Emotional transitions.")
def _(): return reverse(reverb(widen(chime([1047, 1319, 1568], 1.6, 3, 0.3, spread=0.0), 0.5), 2.2, 0.5))

# ---- R04 Suspenseful build-ups (sparingly) ----
@add(R, "R04", "Suspense-build", "A", "pulse-drone", "Pulsing low drone that speeds up. Sparing tension.")
def _():
    n = n_of(2.2); t = np.arange(n) / SR
    d = lp(osc(np.full(n, 55), "saw") + osc(np.full(n, 82.5), "saw") * 0.6, 900)
    return widen(d * (0.4 + 0.6 * (np.sin(2 * np.pi * curve(n, 2, 9) * t) > 0)) * curve(n, 0.2, 1, "in"), 0.6)
@add(R, "R04", "Suspense-build", "B", "tremolo-strings", "String-like tremolo cluster rising. Cinematic tension.")
def _():
    n = n_of(2.2); t = np.arange(n) / SR
    s = sum(osc(f * (1 + 0.04 * t / 2.2), "saw") for f in (220, 233, 330)) * (0.6 + 0.4 * np.sin(2 * np.pi * 11 * t))
    return reverb(widen(lp(s, 3000) * curve(n, 0.1, 1, "in") * 0.3, 0.8), 1.2, 0.2)
@add(R, "R04", "Suspense-build", "C", "heartbeat", "Heartbeat speeding up. Personal stakes, used sparingly.")
def _():
    out = np.zeros(n_of(2.4)); t0 = 0.0; gap = 0.75
    while t0 < 2.2:
        for off, lvl in ((0, 1.0), (0.14, 0.7)):
            b = impact(70, 40, 0.3, 14, 0.0, 0.1) * lvl * (0.5 + t0 / 4.4)
            i = int((t0 + off) * SR); out[i:i + len(b)] += b[: max(0, len(out) - i)]
        t0 += gap; gap = max(0.35, gap * 0.86)
    return widen(out, 0.3)
@add(R, "R04", "Suspense-build", "D", "dark-swell", "Dark noise and sub swell. Ominous build.")
def _():
    n = n_of(2.0); x = lp(noise(n, "pink"), 500) * 0.5 + osc(np.full(n, 41)) * 0.6
    return reverb(widen(x * riser_env(n, 2.2), 0.6), 0.4, 0.08)

# ---- R05 Impact hits (under risers) ----
@add(R, "R05", "Impact-hit", "A", "cinematic-boom", "Cinematic boom with a long tail. Lands a riser into the next segment.")
def _(): return reverb(widen(impact(), 0.3), 1.4, 0.2)
@add(R, "R05", "Impact-hit", "B", "punchy-thud", "Short, punchy thud. Tighter landings.")
def _(): return widen(impact(140, 55, 0.6, 9, 0.7, 0.6), 0.3)
@add(R, "R05", "Impact-hit", "C", "trailer-hit", "Big trailer-style hit with a huge reverb tail. The ad's biggest moment.")
def _(): return reverb(widen(impact(130, 40, 2.0, 2.2, 0.8, 0.8), 0.5), 2.4, 0.35)
@add(R, "R05", "Impact-hit", "D", "sub-drop", "Pure sub drop, no top. Felt more than heard.")
def _():
    n = n_of(1.6); t = np.arange(n) / SR
    return widen(osc(90 * np.exp(-t * 2) + 28) * np.exp(-t * 2.2), 0.1)

# ---- R06 Sci-fi hit (scene transitions) ----
@add(R, "R06", "Sci-fi-hit", "A", "laser-hit", "Laser-tinged hit. Very common between scenes.")
def _(): return reverb(widen(S(impact(120, 50, 0.8, 6, 0.6, 0.4) * 0.8, tone_blip(3200, 300, 0.4, 10, "saw") * 0.3), 0.4), 0.7, 0.18)
@add(R, "R06", "Sci-fi-hit", "B", "electric-thwack", "Electric thwack with crackle. Energetic scene switches.")
def _():
    n = n_of(0.6); t = np.arange(n) / SR
    crackle = hp(noise(n), 2500) * (dsp._rng.random(n) > 0.97) * np.exp(-t * 8) * 2
    return reverb(widen(impact(150, 60, 0.6, 8, 0.8, 0.5) + crackle, 0.4), 0.5, 0.15)
@add(R, "R06", "Sci-fi-hit", "C", "digital-slam", "Digital slam, crushed and wide. Bold transitions.")
def _(): return widen(crush(impact(130, 45, 0.9, 5, 0.6, 0.6), 6, 2), 0.5)
@add(R, "R06", "Sci-fi-hit", "D", "pulse-hit", "Hit with a resonant sci-fi pulse tail. Futuristic transitions.")
def _():
    n = n_of(1.2); t = np.arange(n) / SR
    tail = osc(np.full(n, 220), "square") * np.exp(-t * 4) * (np.sin(2 * np.pi * 12 * t) > 0) * 0.15
    return reverb(widen(impact(120, 45, 1.2, 5, 0.6, 0.4) + lp(tail, 2000), 0.4), 0.9, 0.2)

# ================= BUILD =================
PEAK_LOCK = {"T05D", "T07D", "T09C", "T11A", "T11C", "T14C"}   # wind-up before the hit: lock the hit
SERIES = {"T08A", "T08B", "T08C", "T10A", "T10B", "T10C", "T10D", "T14D"}
def write(path, st):
    st = np.clip(st, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st.T * 32767).astype("<i2").tobytes())

def main(out):
    catalog = []
    for k, (cat, code, name, letter, slug, desc, fn) in enumerate(LIB):
        seed(1000 + k)                       # one sound per generation, reproducible
        st = finalize(np.asarray(fn(), float))
        folder = os.path.join(out, cat, f"{code}_{name}")
        os.makedirs(folder, exist_ok=True)
        fname = f"{code}{letter}_{slug}.wav"
        write(os.path.join(folder, fname), st)
        lock = "peak" if (cat != Tx or f"{code}{letter}" in PEAK_LOCK) else "onset"
        if f"{code}{letter}" in SERIES: lock = "onset (series: each tick is an element)"
        catalog.append({"code": f"{code}{letter}", "lock": lock, "type_code": code, "type": name.replace("-", " "),
                        "category": cat.split("_", 1)[1].replace("-", " ").title(), "letter": letter,
                        "slug": slug, "description": desc,
                        "file": os.path.relpath(os.path.join(folder, fname), out),
                        "duration_s": round(st.shape[1] / SR, 3)})
        print(f"{code}{letter} {name} / {slug}  {st.shape[1] / SR:.2f}s")
    json.dump(catalog, open(os.path.join(out, "catalog.json"), "w"), indent=1)

if __name__ == "__main__":
    main(sys.argv[1])
