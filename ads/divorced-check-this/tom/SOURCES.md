# Tom: generated presenter (Higgsfield, 2026-10-23)

| Asset | Model | Higgsfield job |
|---|---|---|
| Voice ("Desmond" preset) | Eleven v4, stability 0.45 | e808cf70-48f7-4211-a6db-fe92a4a38703 |
| Portrait (take 4 of 4) | Soul 2.0, 9:16, 2K, seed 44 | 76246741-ec0f-4e5a-a6c5-a81fc7b09a0a |
| Talking video, 21 s | Seedance 2.5 omni_reference, 1080p, high bitrate | a3934a19-442f-4c8d-a9b5-9de1ce5ff26f |
| Voice swapped to Desmond (lips keep Seedance timing) | voice_change workflow | ab6021c5-040b-40c5-a97f-714fb72dfda6 |

Seedance re-performs the line from the audio reference, so its own timing drives the lips. The voice_change pass restores
Desmond's voice on that timing. `cutlist_final.json` then shortens only the pauses that fall under B-roll graphics, and the
same cuts are applied to the picture (`cut_to_voice.py`) and the audio. `phrases_final.json` holds the 13 phrase frames the
edit is locked to (`relock.py`).
