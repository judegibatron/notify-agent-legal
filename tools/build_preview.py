#!/usr/bin/env python3
"""Build docs/index.html: a gallery of every weapon with its sprite and stats.

Reads data/weapons.json and the 1x PNGs in assets/weapons/, embeds the sprites
as data URIs so the page is a single self-contained file, and re-derives DPS to
catch stale figures in the JSON.

    python3 tools/build_preview.py                 # writes docs/index.html
    python3 tools/build_preview.py --fragment PATH # also writes the page without
                                                   # the <html>/<head>/<body> wrapper
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "weapons.json"
SPRITES = ROOT / "assets" / "weapons"
DOCS = ROOT / "docs" / "index.html"

# Which common weapon each premium one is priced against.
BASELINE_BY_CLASS = {
    "sword": "iron_sword", "greatsword": "iron_sword", "katana": "iron_sword",
    "spear": "iron_sword", "warhammer": "iron_sword",
    "dagger": "iron_dagger", "bow": "short_bow", "staff": "oak_staff",
}
STAT_ROWS = (
    ("damage", "Damage", "{:g}"),
    ("attack_speed", "Speed", "{:.1f}/s"),
    ("range", "Range", "{:g}"),
    ("crit_chance", "Crit", "{:.0%}"),
)
TIER_ORDER = ("legendary", "epic", "common")


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def round_half_up(value: float, places: int = 1) -> float:
    """Round the way a designer with a calculator does (32.25 -> 32.3), not half-even."""
    factor = 10 ** places
    return math.floor(value * factor + 0.5 + 1e-9) / factor


def derive(stats: dict) -> tuple[float, float]:
    dps = stats["damage"] * stats["attack_speed"]
    eff = dps * (1 + stats["crit_chance"] * (stats["crit_multiplier"] - 1))
    return round_half_up(dps), round_half_up(eff)


def money(value: int) -> str:
    return f"{value:,} g"


def card(w: dict, tiers: dict, by_id: dict, maxes: dict, sprite_uri: str, compact: bool) -> str:
    tier = tiers[w["tier"]]
    esc = html.escape
    scale = 3 if compact else 5
    base = by_id.get(BASELINE_BY_CLASS.get(w["class"], ""))
    if base and base["id"] != w["id"]:
        cost_x = w["cost"] / base["cost"]
        dps_x = w["effective_dps"] / base["effective_dps"]
        versus = (f'<p class="versus"><b>×{cost_x:.0f}</b> the price of the {esc(base["name"])}, '
                  f'<b>×{dps_x:.1f}</b> its effective DPS.</p>')
    else:
        versus = '<p class="versus">Baseline for its class.</p>'

    rows = []
    for key, label, fmt in STAT_ROWS:
        val = w["stats"][key]
        pct = 100 * val / maxes[key]
        rows.append(
            f'<div class="stat"><span class="k">{label}</span>'
            f'<span class="bar"><i style="width:{pct:.0f}%"></i></span>'
            f'<span class="v">{fmt.format(val)}</span></div>'
        )
    passive = w["passive"]
    passive_html = (
        f'<p class="passive"><b>{esc(passive["name"])}.</b> {esc(passive["description"])}</p>'
        if passive else '<p class="passive none">No passive.</p>'
    )
    return f"""<article class="card tier-{w['tier']}{' compact' if compact else ''}">
  <div class="tile"><img src="{sprite_uri}" width="{32 * scale}" height="{32 * scale}" alt="{esc(w['name'])} sprite"></div>
  <div class="body">
    <header>
      <h3>{esc(w['name'])}</h3>
      <span class="chip">{esc(tier['label'])} · {esc(w['class'])}</span>
    </header>
    <p class="cost"><span class="num">{money(w['cost'])}</span><span class="dps">{w['effective_dps']:.1f} <small>eff. DPS</small></span></p>
    {versus}
    <div class="stats">{''.join(rows)}</div>
    {passive_html}
    <p class="flavor">{esc(w['flavor'])}</p>
  </div>
</article>"""


def build(fragment_path: Path | None) -> None:
    doc = json.loads(DATA.read_text())
    tiers, weapons = doc["tiers"], doc["weapons"]
    by_id = {w["id"]: w for w in weapons}

    for w in weapons:
        dps, eff = derive(w["stats"])
        if abs(dps - w["dps"]) > 0.05 or abs(eff - w["effective_dps"]) > 0.05:
            print(f"warning: {w['id']} stored dps/eff {w['dps']}/{w['effective_dps']} but derived {dps}/{eff}")

    maxes = {key: max(w["stats"][key] for w in weapons) for key, _, _ in STAT_ROWS}
    uris = {w["id"]: data_uri(SPRITES / f"{w['id']}.png") for w in weapons}

    sections = []
    for tier_id in TIER_ORDER:
        group = [w for w in weapons if w["tier"] == tier_id]
        if not group:
            continue
        tier = tiers[tier_id]
        compact = tier_id == "common"
        cards = "\n".join(card(w, tiers, by_id, maxes, uris[w["id"]], compact) for w in group)
        heading = "Common baseline" if compact else tier["label"]
        sections.append(f"""<section class="tier tier-{tier_id}">
  <div class="tier-head">
    <h2>{html.escape(heading)}</h2>
    <p>{html.escape(tier['notes'])}</p>
  </div>
  <div class="grid{' compact' if compact else ''}">
{cards}
  </div>
</section>""")

    ordered = [w for t in TIER_ORDER for w in weapons if w["tier"] == t]
    scale_rows = []
    for scale in (1, 2, 3):
        imgs = "".join(
            f'<img src="{uris[w["id"]]}" width="{32 * scale}" height="{32 * scale}" alt="{html.escape(w["name"])} at {scale}x">'
            for w in ordered
        )
        scale_rows.append(f'<div class="scale-row"><span class="k">{scale}×</span><div class="strip">{imgs}</div></div>')

    n_premium = sum(1 for w in weapons if w["tier"] != "common")
    n_common = len(weapons) - n_premium

    body = f"""<title>Top Shelf Armory</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Pixelify+Sans:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  :root {{
    --ground: #17141d;
    --surface: #211c2a;
    --surface-2: #2a2436;
    --checker: #2f2940;
    --line: #332c42;
    --ink: #efe9f6;
    --muted: #a297b6;
    --legendary: #f2b632;
    --epic: #a24dff;
    --common: #9aa0b0;
    --display: "Pixelify Sans", "Trebuchet MS", sans-serif;
    --body: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
    --mono: "IBM Plex Mono", "SFMono-Regular", Menlo, monospace;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--ground);
    color: var(--ink);
    font-family: var(--body);
    font-size: 15px;
    line-height: 1.5;
  }}
  img {{ image-rendering: pixelated; image-rendering: crisp-edges; display: block; }}
  .page {{ max-width: 1180px; margin: 0 auto; padding: 40px 24px 72px; display: flex; flex-direction: column; gap: 48px; }}

  .masthead {{ display: grid; gap: 12px; max-width: 64ch; }}
  .eyebrow {{ font-family: var(--mono); font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin: 0; }}
  h1 {{ font-family: var(--display); font-weight: 700; font-size: clamp(36px, 5vw, 52px); line-height: 1; margin: 0; text-wrap: balance; }}
  .masthead p.lede {{ margin: 4px 0 0; color: var(--muted); }}
  .masthead p.lede b {{ color: var(--ink); font-weight: 500; }}

  .tier {{ display: grid; gap: 20px; }}
  .tier-head {{ display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap; border-bottom: 1px solid var(--line); padding-bottom: 10px; }}
  .tier-head h2 {{ font-family: var(--display); font-weight: 500; font-size: 26px; margin: 0; letter-spacing: 0.01em; }}
  .tier-head p {{ margin: 0; color: var(--muted); max-width: 72ch; }}
  .tier-legendary .tier-head h2 {{ color: var(--legendary); }}
  .tier-epic .tier-head h2 {{ color: var(--epic); }}
  .tier-common .tier-head h2 {{ color: var(--common); }}

  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 18px; }}
  .grid.compact {{ grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }}

  .card {{ background: var(--surface); border: 1px solid var(--line); display: grid; grid-template-rows: auto 1fr; }}
  .card.tier-legendary {{ border-color: color-mix(in srgb, var(--legendary) 45%, var(--line)); }}
  .card.tier-epic {{ border-color: color-mix(in srgb, var(--epic) 45%, var(--line)); }}
  .tile {{
    display: grid; place-items: center; padding: 18px;
    background-color: var(--surface-2);
    background-image: linear-gradient(45deg, var(--checker) 25%, transparent 25%, transparent 75%, var(--checker) 75%),
                      linear-gradient(45deg, var(--checker) 25%, transparent 25%, transparent 75%, var(--checker) 75%);
    background-size: 16px 16px; background-position: 0 0, 8px 8px;
    border-bottom: 1px solid var(--line);
  }}
  .body {{ padding: 16px 18px 18px; display: grid; gap: 10px; align-content: start; }}
  .body header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 10px; flex-wrap: wrap; }}
  h3 {{ font-family: var(--display); font-weight: 500; font-size: 22px; margin: 0; line-height: 1.1; }}
  .chip {{ font-family: var(--mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; padding: 3px 8px; border: 1px solid; border-radius: 999px; white-space: nowrap; }}
  .tier-legendary .chip {{ color: var(--legendary); border-color: var(--legendary); }}
  .tier-epic .chip {{ color: var(--epic); border-color: var(--epic); }}
  .tier-common .chip {{ color: var(--common); border-color: var(--common); }}

  .cost {{ margin: 0; display: flex; justify-content: space-between; align-items: baseline; gap: 12px; font-family: var(--mono); font-variant-numeric: tabular-nums; }}
  .cost .num {{ font-size: 22px; font-weight: 500; }}
  .tier-legendary .cost .num {{ color: var(--legendary); }}
  .tier-epic .cost .num {{ color: var(--epic); }}
  .cost .dps {{ font-size: 16px; }}
  .cost .dps small {{ font-size: 11px; color: var(--muted); letter-spacing: 0.06em; text-transform: uppercase; }}
  .versus {{ margin: 0; color: var(--muted); font-size: 13.5px; }}
  .versus b {{ color: var(--ink); font-family: var(--mono); font-weight: 500; }}

  .stats {{ display: grid; gap: 5px; font-family: var(--mono); font-size: 12.5px; font-variant-numeric: tabular-nums; }}
  .stat {{ display: grid; grid-template-columns: 58px 1fr 52px; align-items: center; gap: 10px; }}
  .stat .k {{ color: var(--muted); letter-spacing: 0.04em; }}
  .stat .v {{ text-align: right; }}
  .bar {{ height: 8px; background: var(--ground); border: 1px solid var(--line); display: block; }}
  .bar i {{ display: block; height: 100%; background: var(--common); }}
  .tier-legendary .bar i {{ background: var(--legendary); }}
  .tier-epic .bar i {{ background: var(--epic); }}

  .passive {{ margin: 0; font-size: 13.5px; }}
  .passive.none {{ color: var(--muted); }}
  .flavor {{ margin: 0; color: var(--muted); font-style: italic; font-size: 13px; }}
  .card.compact .flavor {{ display: none; }}

  .scale {{ display: grid; gap: 14px; }}
  .scale-row {{ display: grid; grid-template-columns: 40px 1fr; align-items: center; gap: 12px; }}
  .scale-row .k {{ font-family: var(--mono); color: var(--muted); font-size: 12px; }}
  .strip {{
    display: flex; gap: 12px; align-items: flex-end; overflow-x: auto; padding: 12px;
    background-color: var(--surface-2); border: 1px solid var(--line);
  }}
  .note {{ color: var(--muted); font-size: 13.5px; max-width: 72ch; margin: 0; }}
  .note code {{ font-family: var(--mono); font-size: 12.5px; color: var(--ink); }}
  a:focus-visible, img:focus-visible {{ outline: 2px solid var(--legendary); outline-offset: 2px; }}
</style>
<div class="page">
  <div class="masthead">
    <p class="eyebrow">Weapon set · 32×32 pixel art · {len(weapons)} sprites</p>
    <h1>Top Shelf Armory</h1>
    <p class="lede"><b>{n_premium} premium weapons</b> priced 30–60× the starter gear, hitting about 3× as hard, each with a passive that changes how it plays. The <b>{n_common} commons</b> at the bottom are the baseline they were scaled against. Every sprite is shown blown up here and at true game scale at the end.</p>
  </div>
{chr(10).join(sections)}
  <section class="scale">
    <div class="tier-head">
      <h2>At game scale</h2>
      <p>Legendary, then epic, then common, on a ground the colour of a typical dungeon floor. Judge silhouettes here, not in the cards.</p>
    </div>
    {''.join(scale_rows)}
    <p class="note">Sprites live in <code>assets/weapons/&lt;id&gt;.png</code>, the strip in <code>spritesheet.png</code> with its atlas in <code>spritesheet.json</code>. Stats are in <code>data/weapons.json</code>.</p>
  </section>
</div>
"""
    DOCS.parent.mkdir(parents=True, exist_ok=True)
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            + body + '</head>\n<body></body>\n</html>\n')
    # The <title>/<link>/<style> block sits in <head>; move the page div into <body>.
    head_part, _, page_part = body.partition('<div class="page">')
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            + head_part + '</head>\n<body>\n<div class="page">' + page_part + '</body>\n</html>\n')
    DOCS.write_text(full, encoding="utf-8")
    print(f"wrote {DOCS.relative_to(ROOT)} ({len(full):,} bytes)")
    if fragment_path:
        fragment_path.parent.mkdir(parents=True, exist_ok=True)
        fragment_path.write_text(body, encoding="utf-8")
        print(f"wrote {fragment_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fragment", type=Path, default=None, help="also write a wrapper-less copy here")
    build(parser.parse_args().fragment)
