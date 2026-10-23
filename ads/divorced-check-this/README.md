# Divorced? Check This — 20 s ad (v5, final take)

Rendered by `render_v5.py` from `edit_v5.json` (scenes, captions, animation frames) and `sfx_cues_v5.json` (sound cue sheet, house-library picks).

Re-render once Tom's Higgsfield clip and voice exist:

```bash
python3 ../../.claude/skills/videoedit/scripts/sfx_inventory.py ../../sfx-library --fps 30 --json inventory.json
python3 render_v5.py edit_v5.json sfx_cues_v5.json inventory.json out --tom tom.mp4 --voice voice.wav
```

Word frames in `edit_v5.json` are estimates. Re-lock captions and cues to the real voice before the final export.
