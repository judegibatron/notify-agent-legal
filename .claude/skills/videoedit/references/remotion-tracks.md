# Remotion patterns for /videoedit

How to lay sound on the composition timeline so every decision shows up as an editable, named layer in Remotion Studio.

## Contents
1. Tracks = named Sequences
2. Levels: dB → `volume`
3. Locking a sound's peak to a frame
4. Muting original audio
5. Sound cue data file (recommended structure)
6. Checking the mix

---

## 1. Tracks = named Sequences

Remotion has no mixer tracks; a "track" is a named `<Sequence>` (or a component) that holds one sound family. The `name` prop is what Joseph sees in the Studio timeline, so name every layer.

```tsx
import {Audio} from '@remotion/media';   // or: import {Audio} from 'remotion' on older projects
import {Sequence, staticFile} from 'remotion';

export const SfxWhooshes: React.FC = () => (
  <Sequence name="WHOOSHES" layout="none">
    {WHOOSHES.map((c) => (
      <Sequence key={c.id} name={`${c.id} · ${c.label}`} from={c.from} durationInFrames={c.durationInFrames} layout="none">
        <Audio src={staticFile(c.file)} volume={db(c.db)} />
      </Sequence>
    ))}
  </Sequence>
);
```

- One component per family: `SfxWhooshes`, `SfxTextures` (plus sub-tracks if they overlap), `SfxRisers`, `SfxHits`, `Music`.
- Mount them in the composition after the existing layers. Don't edit layers Joseph already laid.
- One cue = one whole `<Sequence>` with one `<Audio>`, so each can be slid, swapped or deleted on its own.
- Check which `Audio` import the project already uses (`grep -r "Audio" src`) and match it. Newer Remotion uses `trimBefore`/`trimAfter` to trim a clip; older versions use `startFrom`/`endAt`.

## 2. Levels: dB → `volume`

`volume` is linear gain, so convert from dB:

```ts
export const db = (d: number) => Math.pow(10, d / 20);
// -12 dB → 0.251   -10 → 0.316   -7 → 0.447   -6 → 0.501   -5 → 0.562   -19 → 0.112
```

These levels are relative to the file's own loudness. If the inventory shows a file is much hotter or quieter than its siblings (peak dBFS / RMS columns), mention it in the pass report. Don't silently re-level it.

## 3. Locking a sound's peak to a frame

`scripts/sfx_inventory.py` reports `peak_frame` (frames from the file's start to its loudest point) at the project fps.

```
from = syncFrame - peakFrame
```

- Whoosh: `syncFrame` = the fastest frame of the movement. For an `interpolate` over `[a, b]` with an ease-in-out, that's around the midpoint. For a `spring`, it's early, about 20–35% into its settle. When it matters, compute the per-frame delta of the animated value and take the max.
- Texture: `syncFrame` = the event frame. Use the sound's onset, not its peak, when the attack is long: compute `onset_frame = peak_frame − attack_frames`.
- Riser: the riser's end (or its peak, if it peaks at the end) on the transition frame. The hit's peak goes on that same frame.
- Transitions: lead by 2–3 frames (`syncFrame − 2`), except the exact-frame cases above.
- If `from` comes out negative, trim the head with `trimBefore={-from}` and set `from={0}`.

## 4. Muting original audio

Mute, don't delete: `<OffthreadVideo src=… muted />`, or `volume={0}` on an existing `<Audio>`, with a `// muted by /videoedit — set back to 1 to restore` comment. Never touch the voice layer.

## 5. Sound cue data file (recommended)

Keep every placement in one data file, so a pass report, a sequence-wide replacement and Joseph's hand edits all touch one place:

```ts
// src/sfx/cues.ts
export type Cue = {id: string; family: 'WHOOSHES'|'TEXTURES'|'RISERS'|'HITS'|'MUSIC';
  label: string; file: string; from: number; durationInFrames: number; db: number;
  sync: {frame: number; kind: 'fastest-frame'|'event'|'transition'}; why: string};
```

The `why` field is the reasoning ("fastest frame of title slide; hollow whoosh v2 — shortest attack of 3"). It doubles as the per-pass report, and it gives Step 8 a record to compare against when Joseph changes something.

## 6. Checking the mix

To find the loudest stack and clipping, render audio only and measure:

```bash
npx remotion render <CompId> out/mix.wav --codec=wav
ffmpeg -i out/mix.wav -af ebur128=peak=true -f null - 2>&1 | tail -12      # true peak + loudness
ffmpeg -i out/mix.wav -af astats=metadata=1:reset=0 -f null - 2>&1 | grep -E "Peak level|RMS level" | tail -4
```

A true peak above about −1 dBTP means it will clip. Pull the hit down; never the voice.
