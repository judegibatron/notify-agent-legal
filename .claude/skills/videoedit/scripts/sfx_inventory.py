#!/usr/bin/env python3
"""Audition sheet for an SFX library: measure every sound so variations can be compared.

For each audio file: duration, peak time (and peak frame at --fps), attack (onset -> peak),
tail (peak -> fade below -40 dB), peak and RMS level in dBFS, and spectral centroid
(higher = brighter/airier, lower = darker/heavier). Grouped by folder.

usage: python3 sfx_inventory.py <library_dir> [--fps 30] [--json out.json]
requires: ffmpeg on PATH, numpy
"""
import argparse, json, os, subprocess, sys
import numpy as np

SR = 48000
EXTS = {".wav", ".mp3", ".aif", ".aiff", ".flac", ".ogg", ".m4a", ".opus"}


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def db(x):
    return 20 * np.log10(max(float(x), 1e-9))


def analyze(path, fps):
    a = decode(path)
    if a.size == 0:
        return None
    win = int(SR * 0.01)  # 10 ms RMS envelope
    n = len(a) // win
    env = np.sqrt(np.mean(a[: n * win].reshape(n, win) ** 2, axis=1)) if n else np.array([np.abs(a).max()])
    pk_i = int(np.argmax(env))
    pk = env[pk_i]
    thresh = pk * 10 ** (-40 / 20)
    above = np.nonzero(env >= thresh)[0]
    onset_i = int(above[0]) if above.size else 0
    end_i = int(above[-1]) if above.size else n
    spec = np.abs(np.fft.rfft(a[: min(len(a), SR * 10)]))
    freqs = np.fft.rfftfreq(min(len(a), SR * 10), 1 / SR)
    centroid = float((spec * freqs).sum() / max(spec.sum(), 1e-9))
    t = lambda i: i * win / SR
    return {
        "duration_s": round(len(a) / SR, 3),
        "peak_s": round(t(pk_i), 3),
        "peak_frame": int(round(t(pk_i) * fps)),
        "attack_s": round(t(pk_i) - t(onset_i), 3),
        "tail_s": round(t(end_i) - t(pk_i), 3),
        "peak_dbfs": round(db(np.abs(a).max()), 1),
        "rms_dbfs": round(db(np.sqrt(np.mean(a ** 2))), 1),
        "centroid_hz": int(centroid),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("library")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--json")
    args = ap.parse_args()

    groups = {}
    for root, _, files in os.walk(args.library):
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() not in EXTS:
                continue
            p = os.path.join(root, f)
            try:
                info = analyze(p, args.fps)
            except subprocess.CalledProcessError:
                print(f"! could not decode {p}", file=sys.stderr)
                continue
            if info:
                groups.setdefault(os.path.relpath(root, args.library), []).append({"file": os.path.relpath(p, args.library), **info})

    for folder in sorted(groups):
        rows = groups[folder]
        print(f"\n## {folder}  ({len(rows)} file{'s' if len(rows) != 1 else ''})\n")
        print("| file | dur s | peak s | peak f | attack s | tail s | peak dBFS | RMS dBFS | centroid Hz |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            print(f"| {os.path.basename(r['file'])} | {r['duration_s']} | {r['peak_s']} | {r['peak_frame']} | "
                  f"{r['attack_s']} | {r['tail_s']} | {r['peak_dbfs']} | {r['rms_dbfs']} | {r['centroid_hz']} |")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(groups, fh, indent=2)
        print(f"\nwrote {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
