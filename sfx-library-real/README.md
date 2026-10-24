# House SFX library: real recordings

120 sound effects for ad edits: 30 types, four takes each (A–D). Every take is a single **real recording** released under **CC0 1.0** (public domain): free for commercial use, no attribution required. Nothing is synthesized or layered.

Audition and pick favorites: https://claude.ai/artifact/QZiUyoECTtya9hGbMe659m

## Sources
- **BigSoundBank** (bigsoundbank.com), recordings by Joseph Sardin, CC0. Each sound's page states "Free and royalty-free". Pages that described a sound as computer-made, sound-designed, processed or made with virtual instruments were excluded.
- **Kenney** (kenney.nl), CC0 foley packs: Impact Sounds, RPG Audio, Casino Audio.

`LICENSES.md` lists every file's original, author, license and the exact edits. `catalog.json` has the same data plus each file's lock point.

## Edits made
Only these, per take: the cleanest single take chosen from inside the recording, trimmed, short fades, loudness matched (loudest 50 ms at −12 dBFS RMS, peaks capped at −1 dBFS). The suck-back risers (R03) and three metallic risers (R02B–D) are real strikes **reversed**, and are labeled that way.

## Natural stand-ins
Some types in the editing doc are sci-fi by nature. They use the closest real recordings and are labeled as stand-ins: W03 (blades, whips), W07 (sport swings, flag snaps), W08 (wind and air), T03 (switches), T04 (hits), T11 (electricity), T13 (bowls, chimes, a cathedral), R01 (engines accelerating, thunder), R06 (anvil and metal strikes).

## Codes
W01–W10 whooshes, T01–T14 textures, R01–R06 risers and hits, take letter A–D (for example `W01B`). Same codes as the synthesized library in `../sfx-library/`, which this replaces.

## Rebuild
```bash
python3 tools/bsb_meta.py ids_slug.txt meta.json        # page metadata and license check
python3 tools/build_real.py sources.json . <cache> <kenney_dir> meta.json
```
`sources.json` is the recipe: one real recording per take.
