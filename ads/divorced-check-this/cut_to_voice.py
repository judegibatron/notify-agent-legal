"""Cut Tom's Seedance clip with the same keep-segments used to tighten the voice, so picture and voice stay in sync.

usage: python3 cut_to_voice.py tom_source.mp4 cutlist.json tom_tight.mp4 [--fps 30]
Each output frame is mapped to its exact source time through the keep-segments (no per-cut rounding),
so the result matches the tightened voice frame for frame. Cuts should fall where Tom is off screen.
"""
import argparse, json, subprocess
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("cutlist"); ap.add_argument("out"); ap.add_argument("--fps", type=float, default=30)
a = ap.parse_args()
keep = json.load(open(a.cutlist))["keep_segments_s"]

probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,r_frame_rate", "-of", "json", a.src],
                                  capture_output=True, check=True).stdout)["streams"][0]
W, H = probe["width"], probe["height"]
num, den = map(int, probe["r_frame_rate"].split("/")); src_fps = num / den

total = sum(b - s for s, b in keep)
n_out = int(round(total * a.fps))
starts = np.cumsum([0] + [b - s for s, b in keep])  # tight-timeline start of each segment

def src_time(t):
    k = min(np.searchsorted(starts, t, side="right") - 1, len(keep) - 1)
    return keep[k][0] + (t - starts[k])

dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", a.src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps),
                        "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", a.out],
                       stdin=subprocess.PIPE)
size = W * H * 3
cur_idx, cur = -1, None
for i in range(n_out):
    want = int(round(src_time(i / a.fps) * src_fps))
    while cur_idx < want:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        cur, cur_idx = buf, cur_idx + 1
    enc.stdin.write(cur)
enc.stdin.close(); enc.wait(); dec.kill()
print(f"wrote {a.out}: {n_out} frames ({n_out / a.fps:.3f}s) from {src_fps:g} fps source")
