"""Build the real-recording SFX library from sources.json (CC0 recordings only, no synthesis).

usage: python3 build_real.py <sources.json> <out_dir> <cache_dir> <kenney_root> <bsb_meta.json>

Per take the only edits are: pick the cleanest take inside the recording, trim, short fades,
loudness match (loudest 50 ms at -12 dBFS RMS, peaks capped at -1 dBFS), and reverse for *_rev modes.
Writes <out_dir>/<Category>/<Code>_<Type>/<Code><Letter>_<slug>.wav, catalog.json and LICENSES.md.
"""
import json, os, re, subprocess, sys, time, urllib.error, urllib.request, wave
import numpy as np

SR = 48000
CATS = {"W": "W_WHOOSHES", "T": "T_TEXTURES", "R": "R_RISERS-AND-HITS"}


def fetch_bsb(sid, cache):
    """Lossless FLAC when the site has it, else its full-quality MP3. Returns (path, format)."""
    for fmt in ("flac", "mp3"):
        path = os.path.join(cache, f"bsb_{sid}.{fmt}")
        if os.path.exists(path):
            return path, fmt
        req = urllib.request.Request(f"https://bigsoundbank.com/UPLOAD/{fmt}/{sid}.{fmt}",
                                     headers={"User-Agent": "Mozilla/5.0 (sfx-library builder)"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
        except urllib.error.HTTPError:
            continue
        open(path, "wb").write(data); time.sleep(0.4)
        return path, fmt
    raise RuntimeError(f"BigSoundBank {sid}: no FLAC or MP3 download")


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T.copy()


def env_db(x, hop):
    m = x.mean(0); n = len(m) // hop
    e = np.sqrt(np.mean(m[: n * hop].reshape(n, hop) ** 2, axis=1))
    return 20 * np.log10(e + 1e-9)


def pick_event(x, dmin, dmax, tail_db=50):
    hop = int(0.005 * SR); e = env_db(x, hop)
    floor, peak = np.percentile(e, 10), e.max()
    on = e > max(floor + 12, peak - 40)
    segs, i, n = [], 0, len(e)
    while i < n:
        if on[i]:
            j = i
            while j < n and (on[j] or np.any(on[j:j + int(0.08 / 0.005)])):
                j += 1
            segs.append([i, j]); i = j
        else:
            i += 1
    best, best_score = None, -1e9
    for k, (a, b) in enumerate(segs):
        sp = e[a:b].max()
        stop = segs[k + 1][0] if k + 1 < len(segs) else n
        end = b
        while end < stop and e[end] > max(floor + 6, sp - tail_db):
            end += 1
        start = max(0, a - 3, segs[k - 1][1] if k else 0)
        dur = (end - start) * hop / SR
        score = sp - floor - (10 if dur < dmin else 0)
        if score > best_score:
            best, best_score = (start, end), score
    a, b = best
    sp = e[a:b].max()
    # keep follow-on parts of the same event (swing follow-through, impact debris and ring-out)
    for c, d in segs:
        if c >= b and (c - b) * hop / SR <= 0.25 and e[c:d].max() > sp - 25:
            b = d
            while b < n and e[b] > max(floor + 6, sp - 50):
                b += 1
    # never shorter than the type's minimum while the recording still has natural tail
    b = max(b, min(n, a + int(dmin * SR / hop)))
    b = min(b, a + int(dmax * SR / hop))
    return x[:, a * hop: b * hop], dict(start_s=round(a * hop / SR, 3), end_s=round(b * hop / SR, 3))


def pick_window(x, length, mode):
    hop = int(0.02 * SR); e = env_db(x, hop); L = max(1, int(length * SR / hop))
    if len(e) <= L:
        return x, dict(start_s=0.0, end_s=round(x.shape[1] / SR, 3))
    p = 10 ** (e / 10)
    best, best_score = 0, -1e9
    for s in range(0, len(e) - L):
        w = e[s:s + L]
        if mode == "rise":
            head, tail = w[: L // 3].mean(), w[-max(1, L // 6):].mean()
            score = (tail - head) + 0.5 * tail
            if w.argmax() < 0.75 * L: score -= 20
        else:
            score = 10 * np.log10(p[s:s + L].mean())
        if score > best_score:
            best, best_score = s, score
    a, b = best * hop, (best + L) * hop
    return x[:, a:b], dict(start_s=round(a / SR, 3), end_s=round(b / SR, 3))


def fades(x, fin, fout):
    x = x.copy(); n = x.shape[1]
    fi, fo = max(1, min(n // 2, int(fin * SR))), max(1, min(n // 2, int(fout * SR)))
    x[:, :fi] *= np.linspace(0, 1, fi); x[:, -fo:] *= np.linspace(1, 0, fo)
    return x


def level(x, loud_db=-12.0, peak_db=-1.0):
    x = x - x.mean(axis=1, keepdims=True)
    win = int(0.05 * SR)
    pw = np.convolve(np.mean(x ** 2, axis=0), np.ones(win) / win, mode="same")
    g = min(10 ** (loud_db / 20) / (np.sqrt(pw.max()) + 1e-12), 10 ** (peak_db / 20) / (np.abs(x).max() + 1e-12))
    return x * g


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def main(src_json, out, cache, kenney_root, meta_json):
    spec = json.load(open(src_json))["types"]; meta = json.load(open(meta_json))
    os.makedirs(cache, exist_ok=True); catalog = []
    for code, t in spec.items():
        folder = os.path.join(out, CATS[code[0]], f"{code}_{t['name'].replace(' / ', '-').replace(' ', '-')}")
        os.makedirs(folder, exist_ok=True)
        for letter, (src, mode, (dmin, dmax), note) in zip("ABCD", t["takes"]):
            kind, ref = src.split(":", 1)
            if kind == "bsb":
                path, fmt = fetch_bsb(ref, cache); m = meta[ref]
                source = {"site": "BigSoundBank", "id": ref, "title": m["title"], "url": m["url"],
                          "author": "Joseph Sardin", "license": "CC0 1.0", "page_says": m["license"], "recorded_as": m["description"], "format": fmt}
            else:
                path = os.path.join(kenney_root, ref); pack = ref.split("/")[0]
                source = {"site": "Kenney", "pack": pack, "file": os.path.basename(ref), "url": f"https://kenney.nl/assets/{pack}",
                          "author": "Kenney (kenney.nl)", "license": "CC0 1.0"}
            x = decode(path)
            if mode in ("event", "event_rev"):
                y, cut = pick_event(x, dmin, dmax, tail_db=60 if mode == "event_rev" else 50)
            else:
                y, cut = pick_window(x, dmax, "rise" if mode == "rise" else "loud")
            steps = [f"trimmed {cut['start_s']}-{cut['end_s']} s of the original"]
            if mode == "event_rev":
                y = fades(y, 0.004, 0.25)[:, ::-1].copy(); steps.append("reversed")
                y = fades(y, 0.25, 0.004)
            elif mode == "rise":
                y = fades(y, 0.3, 0.012)
            elif mode in ("window", "series"):
                y = fades(y, 0.08 if mode == "window" else 0.02, 0.12 if mode == "window" else 0.03)
            else:
                y = fades(y, 0.003, min(0.12, y.shape[1] / SR / 4))
            y = level(y); steps += ["short fades", "loudness matched"]
            name = f"{code}{letter}_{slug(note)}.wav"
            with wave.open(os.path.join(folder, name), "wb") as w:
                w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes((np.clip(y, -1, 1).T * 32767).astype("<i2").tobytes())
            lock = ("peak" if code[0] in "WR" else "onset")
            if mode == "series": lock = "onset (series: each hit is an element)"
            catalog.append({"code": f"{code}{letter}", "type_code": code, "type": t["name"], "use": t["use"],
                            "category": CATS[code[0]].split("_", 1)[1].replace("-", " ").title(), "letter": letter,
                            "slug": slug(note), "description": note[0].upper() + note[1:] + ".",
                            "file": os.path.relpath(os.path.join(folder, name), out), "duration_s": round(y.shape[1] / SR, 3),
                            "lock": lock, "source": source, "processing": steps})
            print(f"{code}{letter} {y.shape[1] / SR:5.2f}s  {source['site']:12} {source.get('title', source.get('file'))[:40]}")
    json.dump(catalog, open(os.path.join(out, "catalog.json"), "w"), indent=1)
    with open(os.path.join(out, "LICENSES.md"), "w") as f:
        f.write("# Sources and licenses\n\nEvery file is a single real recording released under CC0 1.0 (public domain): free for commercial use, no attribution required.\n\n")
        f.write("| Code | Source | Original | Author | Processing |\n|---|---|---|---|---|\n")
        for c in catalog:
            s = c["source"]; orig = s.get("title") or f"{s['pack']}/{s['file']}"
            f.write(f"| {c['code']} | [{s['site']}]({s['url']}) | {orig} | {s['author']} | {', '.join(c['processing'])} |\n")


if __name__ == "__main__":
    main(*sys.argv[1:6])
