"""Fetch BigSoundBank page metadata for sound ids: title, length, license line, UCS category, description, synth flags.

usage: python3 bsb_meta.py ids_slug.txt out.json   (lines: "<id> <slug>")
"""
import html as H, json, re, sys, time, urllib.request

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (sfx-library builder)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "replace")

pairs = [l.split() for l in open(sys.argv[1]) if l.strip()]
out = {}
for sid, slug in pairs:
    try:
        url, page = get(f"https://bigsoundbank.com/{slug}-s{sid}.html")
    except Exception as e:
        print("!", sid, e, file=sys.stderr); continue
    txt = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    txt = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", txt)))
    title = re.search(r"<title>(.*?) — ", page)
    lic = re.search(r"License ([^()]{0,60})\(", txt)
    ucs = re.search(r"UCS Category : ([^:]{0,80}?) Type", txt)
    length = re.search(r"Length : (\d\d:\d\d)", txt)
    desc = re.search(r"Donations or merchandise purchases are appreciated\. Make a donation (.{0,300}?) Listen", txt)
    d = desc.group(1) if desc else ""
    out[sid] = {"id": sid, "url": url, "title": H.unescape(title.group(1)) if title else slug,
                "license": lic.group(1).strip() if lic else "", "free_royalty_free": "Free and royalty-free" in txt,
                "ucs": ucs.group(1).strip() if ucs else "", "length": length.group(1) if length else "",
                "description": d.strip(), "synth_flag": bool(re.search(r"synth|generat|electronic music|software|plugin|designed with|virtual", d, re.I))}
    time.sleep(0.4)
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(len(out), "pages read", file=sys.stderr)
