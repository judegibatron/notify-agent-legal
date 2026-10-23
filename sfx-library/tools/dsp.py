"""Small DSP toolkit for building the house SFX library (stereo, 48 kHz)."""
import numpy as np
from scipy import signal

SR = 48000
_rng = np.random.default_rng(2026)


def seed(s):
    global _rng
    _rng = np.random.default_rng(s)


def T(d):
    return np.arange(int(SR * d)) / SR


def n_of(d):
    return int(SR * d)


# ---------- sources ----------
def noise(n, color="white"):
    w = _rng.standard_normal(n)
    if color == "white":
        return w
    spec = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    spec *= {"pink": 1 / np.sqrt(f), "brown": 1 / f}[color]
    x = np.fft.irfft(spec, n)
    return x / (np.std(x) + 1e-9)


def osc(freq, kind="sine", phase=0.0):
    """freq: scalar or per-sample array (Hz). Phase-accumulating oscillator."""
    freq = np.asarray(freq, dtype=float)
    ph = 2 * np.pi * np.cumsum(freq) / SR + phase
    if kind == "sine":
        return np.sin(ph)
    if kind == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1) - 1
    if kind == "square":
        return np.sign(np.sin(ph))
    if kind == "tri":
        return 2 * np.abs(2 * ((ph / (2 * np.pi)) % 1) - 1) - 1
    raise ValueError(kind)


def fm(carrier, ratio, index):
    """Simple 2-op FM: carrier freq curve, modulator = carrier*ratio, index curve."""
    carrier = np.asarray(carrier, float)
    mod = osc(carrier * ratio) * np.asarray(index, float)
    ph = 2 * np.pi * np.cumsum(carrier) / SR + mod
    return np.sin(ph)


# ---------- envelopes / curves ----------
def curve(n, a, b, shape="exp"):
    x = np.linspace(0, 1, n)
    if shape == "lin":
        return a + (b - a) * x
    if shape == "exp":
        return a * (b / a) ** x
    if shape == "in":
        return a + (b - a) * x ** 2
    if shape == "out":
        return a + (b - a) * (1 - (1 - x) ** 2)
    if shape == "bell":  # a at edges, b in the middle
        return a + (b - a) * np.sin(np.pi * x)
    raise ValueError(shape)


def env_peak(n, peak=0.5, rise=2.0, fall=1.6):
    x = np.linspace(0, 1, n)
    up = np.clip(x / peak, 0, 1) ** rise
    dn = np.clip((1 - x) / (1 - peak), 0, 1) ** fall
    return np.where(x <= peak, up, dn)


def env_exp(n, decay, attack=0.002):
    t = np.arange(n) / SR
    return np.clip(t / max(attack, 1e-5), 0, 1) * np.exp(-t * decay)


# ---------- filters ----------
def _sos(kind, f, order=2):
    nyq = SR / 2 * 0.98
    if kind == "band":
        lo, hi = max(20, f[0]), min(nyq, f[1])
        if hi <= lo * 1.05:
            hi = lo * 1.05
        return signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.butter(order, min(nyq, max(20, f)), btype=kind, fs=SR, output="sos")


def lp(x, f, order=2):
    return signal.sosfilt(_sos("low", f, order), x)


def hp(x, f, order=2):
    return signal.sosfilt(_sos("high", f, order), x)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(_sos("band", (lo, hi), order), x)


def sweep(x, kind, fc, q=1.0, block=128):
    """Time-varying filter. fc: per-sample cutoff/center (Hz). kind: low|high|band (band width = fc/q)."""
    out = np.zeros_like(x)
    zi = None
    for i in range(0, len(x), block):
        f = float(np.mean(fc[i:i + block]))
        sos = _sos("band", (f / (1 + 0.5 / q), f * (1 + 0.5 / q))) if kind == "band" else _sos(kind, f)
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        out[i:i + block], zi = signal.sosfilt(sos, x[i:i + block], zi=zi)
    return out


def comb(x, delay_s, fb=0.6, mix=0.5):
    d = max(1, int(delay_s * SR))
    a = np.zeros(d + 1); a[0] = 1; a[-1] = -fb
    y = signal.lfilter([1.0], a, x)
    return (1 - mix) * x + mix * y * (1 - fb)


def formants(x, freqs, q=8):
    return sum(bp(x, f * (1 - 0.5 / q), f * (1 + 0.5 / q)) * (1 / (k + 1)) for k, f in enumerate(freqs))


# ---------- color ----------
def sat(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def crush(x, bits=6, down=4):
    y = np.repeat(x[::down], down)[: len(x)]
    q = 2 ** (bits - 1)
    return np.round(y * q) / q


def reverse(x):
    return x[..., ::-1].copy()


# ---------- space ----------
def pan(mono, pos):
    """Equal-power pan. pos: scalar or per-sample array in [-1, 1]."""
    pos = np.broadcast_to(np.asarray(pos, float), mono.shape)
    a = (pos + 1) * np.pi / 4
    return np.stack([mono * np.cos(a), mono * np.sin(a)])


def widen(mono, ms=0.6):
    """Haas-style width from a mono source."""
    d = int(ms / 1000 * SR)
    r = np.concatenate([np.zeros(d), mono[:-d] if d else mono])
    return np.stack([mono, r])


def stereo_noise(n, color="white", corr=0.3):
    a, b = noise(n, color), noise(n, color)
    return np.stack([a, corr * a + (1 - corr) * b])


def reverb(st, decay=1.2, wet=0.25, predelay=0.012, damp=6000, size=1.0):
    """Convolution with a synthetic decorrelated stereo IR."""
    n = int(SR * decay * 1.4 * size)
    t = np.arange(n) / SR
    out = []
    for ch in range(2):
        ir = noise(n) * np.exp(-t * 6.9 / decay)
        ir = lp(ir, damp)
        ir = np.concatenate([np.zeros(int(predelay * SR)), ir])
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        out.append(signal.fftconvolve(st[ch], ir)[: st.shape[1] + len(ir)])
    L = max(len(o) for o in out)
    wetst = np.stack([np.pad(o, (0, L - len(o))) for o in out])
    dry = np.pad(st, ((0, 0), (0, L - st.shape[1])))
    return (1 - wet) * dry + wet * wetst * 0.6


def mix(*parts):
    L = max(p.shape[-1] for p in parts)
    out = np.zeros((2, L))
    for p in parts:
        p = p if p.ndim == 2 else np.stack([p, p])
        out[:, : p.shape[1]] += p
    return out


def place(st, at, total):
    """Place a stereo clip at time `at` seconds inside a buffer of `total` seconds."""
    out = np.zeros((2, n_of(total)))
    i = n_of(at)
    seg = st[:, : max(0, out.shape[1] - i)]
    out[:, i:i + seg.shape[1]] += seg
    return out


def finalize(st, peak_db=-1.0, fade_in=0.002, fade_out=0.02, trim_db=-70, loud_db=-12.0):
    """Trim, fade, then level so the loudest 50 ms window sits at loud_db RMS (capped at peak_db).

    Matching short-term loudness rather than peaks keeps the cue-sheet dB levels meaningful across
    the whole library: a -12 dB whoosh and a -6 dB pop sound the way the levels say they will."""
    st = st if st.ndim == 2 else np.stack([st, st])
    st = st - np.mean(st, axis=1, keepdims=True)
    env = np.max(np.abs(st), axis=0)
    thr = np.max(env) * 10 ** (trim_db / 20)
    last = np.nonzero(env > thr)[0]
    if last.size:
        st = st[:, : last[-1] + 1]
    n = st.shape[1]
    fi, fo = max(1, int(fade_in * SR)), max(1, min(n // 2, int(fade_out * SR)))
    st[:, :fi] *= np.linspace(0, 1, fi)
    st[:, -fo:] *= np.linspace(1, 0, fo)
    win = max(1, int(0.05 * SR))
    pw = np.convolve(np.mean(st ** 2, axis=0), np.ones(win) / win, mode="same")
    loud = np.sqrt(np.max(pw)) + 1e-12
    g = min(10 ** (loud_db / 20) / loud, 10 ** (peak_db / 20) / (np.max(np.abs(st)) + 1e-12))
    return st * g
