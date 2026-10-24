"""Search BigSoundBank (CC0 recordings by Joseph Sardin) and collect candidate sounds per query.

usage: python3 bsb_search.py queries.json out.json
queries.json: {"W01": ["whoosh", "swish"], ...}  ->  out.json: {"W01": [{"id": "0572", "title": "...", "q": "whoosh"}, ...]}
"""
import json, re, sys, time, urllib.parse, urllib.request

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (sfx-library builder)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

queries = json.load(open(sys.argv[1])); out = {}
for code, qs in queries.items():
    seen, items = set(), []
    for q in qs:
        for page in (1, 2):
            url = "https://bigsoundbank.com/search?q=" + urllib.parse.quote(q) + (f"&p={page}" if page > 1 else "")
            try:
                html = get(url)
            except Exception as e:
                print("!", url, e, file=sys.stderr); continue
            found = re.findall(r'/([a-z0-9-]+)-s(\d{4})\.html', html)
            new = [(slug, sid) for slug, sid in found if sid not in seen]
            for slug, sid in new:
                seen.add(sid); items.append({"id": sid, "slug": slug, "q": q})
            time.sleep(0.4)
            if not new: break
    out[code] = items
    print(code, len(items), "candidates", file=sys.stderr)
json.dump(out, open(sys.argv[2], "w"), indent=1)
