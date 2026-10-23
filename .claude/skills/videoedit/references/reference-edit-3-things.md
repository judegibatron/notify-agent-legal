# Calibration: "3 things — Edit v1 (SFX)" (approved, high-quality pass)

A finished edit sound-designed with this workflow and signed off as high quality. Use it as the ground truth when a rule in SKILL.md leaves room for judgment. Measured from the delivered MP4: 1080×1920, 30 fps, 49.7 s, stereo 48 kHz.

## How it was measured
The voice is centered (mono), so `L − R` cancels it and leaves the stereo SFX layer on its own. Event timing and character come from that side channel. Voice level comes from `L + R`. Sound effects panned dead center are under-counted, so treat SFX levels here as lower bounds.

## Picture
- Talking head (A-roll, dark blue backdrop) intercut with clean cream/white UI animations (B-roll): app-icon cards, slider "Beginner → Professional", 1-2-3 progress dots, color swatches, logo constellations.
- Kinetic captions: small sans words, with the key phrase in a large blue serif italic ("three mistakes", "screams beginner", "more high-end").
- Big section transitions are an **expanding white circle wipe** (8.67 s, 37.10 s). Others are hard cuts.

## Sound: what the approved pass actually does

| Time | Picture | Sound | Note |
|---|---|---|---|
| 0.30–0.70 s | Hook: "These three mistakes", red 1-2-3 circles pop in | Short bright swell into the first circle, then a texture at 0.90 s | Textures on each circle pop |
| 1.1–3.2 s | Talking head only | **Nothing.** Side channel silent. | Dry A-roll is fine. No sound without motion. |
| 3.3–5.3 s | Slider UI slides in, knob travels | Whoosh peaking at 3.90 s, then fine tick "ladder" at 5.9–6.2 s | Mechanical ticks while the knob moves |
| 6.7–8.6 s → **cut 8.67 s** | "Number 1" → circle wipe into B-roll | **Riser peaking at 8.60 s, 2 frames before the wipe**, sub tail ringing to ~11.4 s | The "~5 s after the hook" build. Loudest moment of the opening. |
| 13.2–14.4 s | Card slides in after the 13.47 s cut | Whoosh peaking 7 frames after the cut | Peak on the movement, not the cut |
| 14.4–15.8 s | Talking head only | Nothing | — |
| 17.3 s | Small UI change | Single click | — |
| 26.2–27.9 s | Eyeball object revealed ("Reserve your visual effects") | Big swell peaking at 26.83 s, as loud as the opening riser | Big reveal = scene's one impact |
| 36.1–37.1 s → **cut 37.10 s** | Color-swatch section → circle wipe | **Riser peaking at 37.07 s, 1 frame before the wipe** | Second build |
| 42.4–43.6 s → **cut 43.67 s** | Luxury-logo B-roll → back to A-roll | **Riser peaking at 43.63 s, 1 frame before the cut**, steep 37-frame rise, short 8-frame release | Third build |
| 44.5–49.7 s | Outro, progress dots fill | Whooshes and clicks on each dot | — |

## Numbers to copy
- **Risers peak 1–2 frames before the transition frame**, never after. Their tails (with the hit) ring 1–3 s into the new segment.
- **Builds sit in voice gaps.** At the three riser peaks the side layer alone reaches about −18 to −21 dBFS while the voice is pausing. The riser is the loudest thing on screen only because the voice has stopped. Under live dialogue, effects sat 9–15 dB below the voice.
- **Whooshes:** side peaks about −29 to −36 dBFS against a voice around −20 to −22 dBFS, so roughly 10–15 dB under the voice. That's consistent with the −12 dB rule.
- **Density:** about 25 distinct effect events in 50 s, clustered on B-roll animations. Talking-head-only stretches of 1–2 s are left completely dry.
- **Music:** none audible in the voice pauses checked (1.1–3.2 s, 14.4–15.8 s, 46.3–47.9 s). The floor there is about −40 dBFS of room tone, with no tonal bed. This approved pass shipped without music.
- **Final mix:** −19.3 LUFS integrated, true peak −1.4 dBTP, loudness range 3.7 LU. Match this if the user asks for the house loudness.
