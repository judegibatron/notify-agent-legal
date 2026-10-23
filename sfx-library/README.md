# House SFX library

120 generated sound effects for ad edits: 30 types, four takes each (A–D). Stereo, 48 kHz, 16-bit WAV.

Audition and pick favorites: https://claude.ai/artifact/QZiUyoECTtya9hGbMe659m

## Codes

Every sound has a code: category letter, type number, take letter. `W01B` is Whooshes, type 01 (Hollow whoosh), take B. Use the codes to ask for sounds ("use R01B as the bass riser").

| Code | Type | Use |
|---|---|---|
| **W — Whooshes** | | |
| W01 | Hollow whoosh | Standard slides and pans |
| W02 | Deep voice whoosh | Default for most animations |
| W03 | Futuristic whoosh | Textured, slightly sci-fi slides |
| W04 | Organic wind whoosh | Slow, methodical moves |
| W05 | Short whoosh | Very quick, small moves (rare) |
| W06 | Generic long whoosh | Slow build into a quick transition |
| W07 | Synthetic whoosh | Scene-to-scene transitions |
| W08 | Transition spacey whoosh | Scene-to-scene transitions |
| W09 | Water dropper | Scene-to-scene transitions |
| W10 | Classy airy whoosh | Large, weighty moves (rare) |
| **T — Textures** | | |
| T01 | Pop | Text pops up |
| T02 | UI click | UI element pops up |
| T03 | Sci-fi click | Something changes inside an animation |
| T04 | Sci-fi impact | A new UI or object is revealed |
| T05 | Digital camera click | Clip-to-clip cut or flash |
| T06 | Analog button / cardboard | Soft checks and toggles |
| T07 | Mechanical click | Mechanical pop-ups |
| T08 | Gears / tiny gearwheel | Letter-by-letter text |
| T09 | Complex mechanism gizmo | Several assets popping in sequence |
| T10 | Keyboard writing | Typing on screen |
| T11 | Activate energy | Entry into a new animation |
| T12 | Success reward | A conclusion is reached |
| T13 | Big reveal (choir) | A big reveal |
| T14 | Alarm buzzer | Low-volume tension |
| **R — Risers & hits** | | |
| R01 | Sharp bass riser | ~5 s after the hook |
| R02 | Metallic riser | Segment builds |
| R03 | Suck-back riser | Slow suck-in (very low or very loud only) |
| R04 | Suspense build | Tension, sparingly |
| R05 | Impact hit | Under a riser, to land it |
| R06 | Sci-fi hit | Between scenes |

## Files

- `W_WHOOSHES/`, `T_TEXTURES/`, `R_RISERS-AND-HITS/`: the sounds, one folder per type.
- `catalog.json`: every sound's code, description, duration, and **lock point**. `peak` means align the loudest point to the frame. `onset` means align the start (most textures).
- `picks.json`: the chosen take per type, once picks are made on the audition page.
- `tools/`: the generator. `python3 tools/build_library.py .` rebuilds every file the same way each time (fixed seeds). Needs numpy and scipy.

## Levels

Every file is leveled so its loudest 50 ms sits at −12 dBFS RMS, with peaks capped at −1 dBFS. The cue-sheet levels in `/videoedit` (whooshes −12 dB, textures −6/−7, risers −5) therefore mean the same thing on every file.

These are synthesized, not recorded. Where a real recorded library (such as Ultimate Editors) is available, it takes priority.
