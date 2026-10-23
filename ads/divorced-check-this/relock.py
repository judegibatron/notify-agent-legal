"""Re-lock the edit and the sound cues to a voice track's 13 measured phrases.

usage: python3 relock.py phrases.json edit_in.json cues_in.json edit_out.json cues_out.json
phrases.json: [[start_frame, end_frame], ...] for the 13 script phrases, in order:
  0 Divorced? | 1 You might be owed Social Security on your ex's record | 2 and it won't lower their check.
  3 Here's how to tell. | 4 One: | 5 married ten years or more. | 6 Two: | 7 not remarried. | 8 Three:
  9 sixty-two or older. | 10 Check all three? | 11 You may qualify. | 12 Visit the ClearPath website for more information.
Word frames inside a phrase are spread by syllable count. Rules follow /videoedit: risers peak 2 frames
before the wipe and sit in the voice gap; textures land on their event; whooshes on the fastest frame.
"""
import json, sys

P = [tuple(p) for p in json.load(open(sys.argv[1]))]
e = json.load(open(sys.argv[2])); c = json.load(open(sys.argv[3]))
assert len(P) == 13, f"need 13 phrases, got {len(P)}"

def words(i, syl):
    """Start frame of each word in phrase i, spread by syllables."""
    s, t = P[i]; total = sum(n for _, n in syl); out, acc = {}, 0
    for w, n in syl:
        out[w] = round(s + (t - s) * acc / total); acc += n
    return out

w1 = words(1, [("You", 1), ("might", 1), ("be", 1), ("owed", 1), ("Social", 2), ("Security", 4), ("on", 1), ("your", 1), ("ex's", 1), ("record", 2)])
w2 = words(2, [("and", 1), ("it", 1), ("won't", 1), ("lower", 2), ("their", 1), ("check", 1)])
w3 = words(3, [("Here's", 1), ("how", 1), ("to", 1), ("tell", 1)])
w11 = words(11, [("You", 1), ("may", 1), ("qualify", 3)])
w12 = words(12, [("Visit", 2), ("the", 1), ("ClearPath", 2), ("website", 2), ("for", 1), ("more", 1), ("information", 4)])

cut1 = P[2][0] - 3                                   # A -> B (benefit cards) just before "and"
cut2 = P[3][0] - 1                                   # B -> A on "Here's"
wipe1 = min(P[4][0] - 2, P[3][1] + 10)               # into the checklist, in the gap before "One:"
gap2 = (P[10][1], P[11][0]); wipe2 = max(gap2[0] + 2, gap2[1] - 5)   # back to Tom, in the gap before "You may qualify"
cut3 = max(P[11][1] + 3, P[12][0] - 5)               # to the CTA, in the gap before "Visit"
N = e["frames"]

e["scenes"] = [
    {"id": "S1", "kind": "A", "f0": 0, "f1": cut1, "in": "start"},
    {"id": "S2", "kind": "B_benefit", "f0": cut1, "f1": cut2, "in": "cut"},
    {"id": "S3", "kind": "A", "f0": cut2, "f1": wipe1, "in": "cut"},
    {"id": "S4", "kind": "B_checklist", "f0": wipe1, "f1": wipe2, "in": "wipe", "wipe_from": [540, 1530]},
    {"id": "S5", "kind": "A", "f0": wipe2, "f1": cut3, "in": "wipe", "wipe_from": [910, 1180]},
    {"id": "S6", "kind": "B_cta", "f0": cut3, "f1": N, "in": "cut"}]
e["captions"] = [
    {"f0": P[0][0], "f1": w1["You"] - 1, "small": [], "big": "Divorced?", "big_f": P[0][0]},
    {"f0": w1["You"], "f1": w1["on"], "small": [[k, w1[k]] for k in ("You", "might", "be", "owed")], "big": "Social Security", "big_f": w1["Social"]},
    {"f0": w1["on"], "f1": cut1, "small": [[k, w1[k]] for k in ("on", "your")], "big": "ex's record.", "big_f": w1["ex's"]},
    {"f0": cut1 + 1, "f1": cut2, "small": [[k, w2[k]] for k in ("and", "it", "won't", "lower")], "big": "their check.", "big_f": w2["their"], "where": "top"},
    {"f0": cut2 + 1, "f1": wipe1, "small": [[k, w3[k]] for k in ("Here's", "how")], "big": "to tell.", "big_f": w3["to"]},
    {"f0": P[11][0], "f1": cut3, "small": [["You", w11["You"]]], "big": "may qualify.", "big_f": w11["may"]}]
e["hook_icon_f"] = 3
e["snap_zoom"] = {"f": w1["ex's"], "zoom": 1.1, "frames": 4}
e["benefit_cards"] = {"a_f": cut1 + 2, "b_f": cut1 + 12, "slide": 14, "badge_f": w2["check"]}
e["dots_pop"] = [P[3][1] - 7, P[3][1] - 3, P[3][1] + 1]
ck = e["checklist"]
ck["title_f"] = wipe1 + 8
ck["rows"][0].update(slide_f=max(wipe1 + 14, P[4][0]), check_f=P[5][1] - 3)
ck["rows"][1].update(slide_f=P[6][0], check_f=P[7][1] - 4)
ck["rows"][2].update(slide_f=P[8][0], check_f=P[9][1] - 3)
ck["push"] = {"f0": P[10][0], "f1": P[10][1] + 1, "zoom": 1.05}; ck["ask_f"] = P[10][0]
e["success_f"] = P[11][1] - 9
e["cta"].update(card_f=cut3 + 2, button_f=w12["ClearPath"], sub_f=w12["for"])
e["voice_gaps"] = [[P[i][1], P[i + 1][0]] for i in range(12)]

rows = ck["rows"]
sync = {"W01": 7, "W02": w1["ex's"] + 1, "W03": cut1 + 3, "W04": cut1 + 13, "W05": wipe1, "W06": ck["title_f"] + 1,
        "W07": rows[0]["slide_f"] + 1, "W08": rows[1]["slide_f"] + 1, "W09": rows[2]["slide_f"] + 1,
        "W10": (ck["push"]["f0"] + ck["push"]["f1"]) // 2, "W11": wipe2, "W12": e["cta"]["card_f"] + 1,
        "T01": cut1, "T02": w2["check"], "T03": cut2, "T04": e["dots_pop"][0], "T05": e["dots_pop"][1], "T06": e["dots_pop"][2],
        "T07": rows[0]["check_f"], "T08": rows[1]["check_f"], "T09": rows[2]["check_f"], "T10": e["success_f"],
        "T11": cut3, "T12": e["cta"]["button_f"], "R01": wipe1 - 2, "R02": wipe2 - 2, "H01": 3, "H02": wipe1, "H03": wipe2}
for q in c["cues"]:
    q["sync"] = sync[q["id"]]
json.dump(e, open(sys.argv[4], "w"), indent=1); json.dump(c, open(sys.argv[5], "w"), indent=1)
print(f"cuts {cut1}/{cut2}, wipes {wipe1}/{wipe2}, CTA {cut3}; riser peaks {wipe1 - 2}/{wipe2 - 2} in gaps "
      f"{e['voice_gaps'][3]} / {e['voice_gaps'][10]}")
