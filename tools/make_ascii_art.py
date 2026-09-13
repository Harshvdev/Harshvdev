#!/usr/bin/env python3
"""
Animate Harsh's ASCII avatar (assets/ascii-art.txt) as a terminal card.

The art is hand-picked; this tool wraps it in a pure-SMIL animated SVG
(no JS, so it animates on GitHub):

  - boot lines type in, rows cascade in like a render log
  - the '+' cells are the glowing eyes: left renders neon red, right neon
    purple; '@' cells sandwiched between '+' runs are the pupils and get a
    dim, pulsing shade
  - eyes breathe, blink every ~7s, and surge their glow
  - two rows glitch, a scanline sweeps the panel, a progress bar fills and
    swaps to a blinking cursor

Outputs (relative to repo root):
  assets/harsh_ascii_dark.svg    shown when prefers-color-scheme: dark
  assets/harsh_ascii_light.svg   shown when prefers-color-scheme: light

Run:  python3 tools/make_ascii_art.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets" / "ascii-art.txt"

# ---- geometry (viewBox units) ------------------------------------------
COLS = 96          # widest line in ascii-art.txt
F, LH = 11, 13     # font-size / line-height
ADV = round(F * 0.602, 3)   # advance of DejaVu Sans Mono (widest common mono)
ART_X = 17         # left edge of the art block
ART_Y0 = 96        # baseline of the first art row
CARD_W = round(ART_X + COLS * ADV + 18)
HEADER_H = 34
BAR_H, BAR_W = 7, 150
REVEAL_T0, REVEAL_STEP, REVEAL_DUR = 0.90, 0.045, 0.18
BAR_T0, BAR_DUR = 0.85, 2.0
SWAP_T = BAR_T0 + BAR_DUR + 1.0

# rows containing '+' eye cells (from the art) and per-eye column zones
EYE_ROWS = range(20, 30)
LEFT_ZONE, RIGHT_ZONE = range(10, 42), range(56, 86)
SCAN_RADIUS = 4    # '@' this close to '+' runs on both sides = pupil

# rows that glitch: hair bridge, an eye row, lower aura — keyTimes in an 8s cycle
GLITCH_ROWS = {8: "0.40", 21: "0.62", 33: "0.78"}

PALETTES = {
    "dark": dict(
        panel="#060a12", header="#0d1420", border="#2b3442",
        fg="#e6edf3", dim="#7d8590", title="#8b98ab",
        red="#ff2d40", red_dim="#8c1b26", red_deep="#5c1017",
        purple="#b45cff", purple_dim="#6f34ad", purple_deep="#4a2378",
        cyan="#58e6d9", scan="#58e6d9",
    ),
    "light": dict(
        panel="#f6f8fa", header="#eaeef2", border="#d0d7de",
        fg="#24292f", dim="#57606a", title="#57606a",
        red="#d1242f", red_dim="#a01b24", red_deep="#7d141b",
        purple="#8250df", purple_dim="#6b45b8", purple_deep="#553590",
        cyan="#1a7fbd", scan="#1a7fbd",
    ),
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_art():
    lines = ART.read_text().rstrip("\n").split("\n")
    assert lines and max(len(l) for l in lines) <= COLS, "art wider than COLS"
    return [l.ljust(COLS) for l in lines]


def cell_kind(lines, i, j):
    """'red' | 'purple' | 'red_pupil' | 'purple_pupil' | 'fg' for a cell."""
    ch = lines[i][j] if j < len(lines[i]) else " "
    if i not in EYE_ROWS:
        return None if ch == " " else "fg"
    zone = LEFT_ZONE if j in LEFT_ZONE else RIGHT_ZONE if j in RIGHT_ZONE else None
    if zone is None:
        return None if ch == " " else "fg"
    if ch == "+":
        return "red" if zone is LEFT_ZONE else "purple"
    if ch == "@":
        row = lines[i]
        has_left = any(c == "+" for c in row[max(0, j - SCAN_RADIUS):j])
        has_right = any(c == "+" for c in row[j + 1:j + 1 + SCAN_RADIUS])
        if has_left and has_right:
            base = "red" if zone is LEFT_ZONE else "purple"
            return base + "_pupil"
    return None if ch == " " else "fg"


def eye_tspan(kind, text, p):
    """Neon tspan for one run of eye cells ('+' glow or '@' pupil)."""
    base_kind = kind.replace("_pupil", "")
    col = p["red_deep"] if kind == "red_pupil" else (
          p["purple_deep"] if kind == "purple_pupil" else p[kind])
    out = f'<tspan fill="{col}"'
    if not kind.endswith("_pupil"):
        out += (f' stroke="{col}" stroke-width="1.2" paint-order="stroke">'
                f'<animate attributeName="stroke-opacity" values="0.55;0.15;0.55" '
                f'dur="2.8s" repeatCount="indefinite"/>')
    else:  # pupil: dim base shade breathing toward its glow color
        out += ">"
        out += (f'<animate attributeName="fill" values="{col};{p[base_kind]};{col}" '
                f'dur="2.8s" repeatCount="indefinite"/>')
    out += (f'<animate attributeName="fill-opacity" '
            f'values="1;1;0.06;0.12;1;1" '
            f'keyTimes="0;0.84;0.86;0.878;0.895;1" dur="7.3s" repeatCount="indefinite"/>')
    if not kind.endswith("_pupil"):
        out += (f'<animate attributeName="stroke-width" values="1.2;1.2;3;1.2" '
                f'keyTimes="0;0.615;0.63;1" dur="8s" repeatCount="indefinite"/>')
    return out + f"{esc(text)}</tspan>"


def row_svg(lines, i, p, glitch):
    y = ART_Y0 + i * LH
    line = lines[i].ljust(COLS)
    kinds = [cell_kind(lines, i, j) for j in range(COLS)]
    parts, cur, start = [], None, 0
    for j in range(COLS + 1):
        k = kinds[j] if j < COLS else None
        if k != cur:
            chunk = line[start:j]
            if cur in ("red", "purple", "red_pupil", "purple_pupil"):
                parts.append(eye_tspan(cur, chunk, p))
            elif cur in ("fg", None):
                parts.append(esc(chunk))
            cur, start = k, j
    body = f'<text x="{ART_X}" y="{y}" xml:space="preserve" font-size="{F}px" fill="{p["fg"]}">{"".join(parts)}</text>'

    animates = [
        f'<animate attributeName="opacity" begin="{REVEAL_T0 + i * REVEAL_STEP:.3f}s" '
        f'dur="{REVEAL_DUR}s" values="0;1" fill="freeze"/>'
    ]
    if glitch:
        g = float(glitch)
        animates += [
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="0 0;0 0;5 0;-4 0;0 0;0 0" '
            f'keyTimes="0;{glitch};{g + 0.012:.3f};{g + 0.024:.3f};{g + 0.036:.3f};1" '
            f'dur="8s" repeatCount="indefinite"/>',
            f'<animate attributeName="fill" '
            f'values="{p["fg"]};{p["fg"]};{p["cyan"]};{p["fg"]};{p["fg"]}" '
            f'keyTimes="0;{glitch};{g + 0.012:.3f};{g + 0.036:.3f};1" '
            f'dur="8s" repeatCount="indefinite"/>',
        ]
    return f'<g opacity="0">{"".join(animates)}{body}</g>'


def emit_svg(lines, p):
    rows_n = len(lines)
    art_rows = [row_svg(lines, i, p, GLITCH_ROWS.get(i)) for i in range(rows_n)]

    last_row_y = ART_Y0 + (rows_n - 1) * LH
    bar_y = last_row_y + 24
    card_h = bar_y + 28

    boot = [
        (f'<tspan fill="{p["purple"]}">$</tspan> whoami', p["fg"]),
        ("harsh — builder · in", p["dim"]),
        (f'<tspan fill="{p["purple"]}">$</tspan> ./animate pfp.ascii --eyes=neon', p["fg"]),
    ]
    boot_lines = "".join(
        f'<g opacity="0"><animate attributeName="opacity" begin="{0.15 + i * 0.22:.2f}s" '
        f'dur="0.15s" values="0;1" fill="freeze"/>'
        f'<text x="{ART_X}" y="{52 + i * LH}" font-size="{F}px" fill="{fill}">{txt}</text></g>'
        for i, (txt, fill) in enumerate(boot)
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {card_h}"
 width="{CARD_W}" height="{card_h}" role="img" xml:space="preserve"
 font-family="'JetBrains Mono','Fira Code','Cascadia Code',Menlo,Consolas,'DejaVu Sans Mono',monospace"
 font-size="{F}px">
<title>Harsh — ASCII terminal avatar</title>
<desc>Terminal window revealing an ASCII render of Harsh's avatar with
glowing red and purple eyes that blink and surge.</desc>
<defs>
<linearGradient id="eyegrad" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="{p["red"]}"/><stop offset="1" stop-color="{p["purple"]}"/>
</linearGradient>
<clipPath id="card"><rect x="1" y="1" width="{CARD_W - 2}" height="{card_h - 2}" rx="10"/></clipPath>
<clipPath id="hdr"><rect x="1" y="1" width="{CARD_W - 2}" height="{HEADER_H}" rx="9"/></clipPath>
</defs>
<rect x="0.5" y="0.5" width="{CARD_W - 1}" height="{card_h - 1}" rx="10"
 fill="{p["panel"]}" stroke="{p["border"]}"/>
<rect x="1" y="1" width="{CARD_W - 2}" height="{HEADER_H}" fill="{p["header"]}" clip-path="url(#hdr)"/>
<rect x="14" y="10" width="18" height="14" rx="2.5" fill="none" stroke="{p["title"]}" stroke-width="1.2" opacity="0.8"/>
<path d="M17 14 l3 3 -3 3 M23 20 h4" stroke="{p["title"]}" stroke-width="1.2" fill="none" stroke-linecap="round" opacity="0.8"/>
<text x="{CARD_W // 2}" y="{HEADER_H // 2 + 4}" text-anchor="middle" font-size="10.5"
 fill="{p["title"]}">harsh@linux: ~/profile — bash</text>
<g opacity="0.75">
<line x1="{CARD_W - 58}" y1="{HEADER_H // 2 + 1}" x2="{CARD_W - 48}" y2="{HEADER_H // 2 + 1}" stroke="{p["title"]}" stroke-width="1.2" stroke-linecap="round"/>
<rect x="{CARD_W - 39}" y="{HEADER_H // 2 - 4}" width="10" height="10" rx="1.5" fill="none" stroke="{p["title"]}" stroke-width="1.2"/>
<path d="M{CARD_W - 20} {HEADER_H // 2 - 4} l8 8 M{CARD_W - 12} {HEADER_H // 2 - 4} l-8 8" stroke="{p["title"]}" stroke-width="1.2" stroke-linecap="round"/>
</g>
{boot_lines}
<g><animate attributeName="opacity" values="1;1;0.95;1;1;0.97;1;1"
 keyTimes="0;0.13;0.14;0.15;0.55;0.56;0.57;1" dur="9s" repeatCount="indefinite"/>
{"".join(art_rows)}</g>
<g opacity="0">
<animate attributeName="opacity" begin="{BAR_T0}s" dur="0.2s" values="0;1" fill="freeze"/>
<animate attributeName="opacity" begin="{SWAP_T:.2f}s" dur="0.25s" values="1;0" fill="freeze"/>
<rect x="{ART_X}" y="{bar_y}" width="{BAR_W}" height="{BAR_H}" rx="4" fill="none"
 stroke="{p["dim"]}" stroke-opacity="0.6"/>
<rect x="{ART_X + 1}" y="{bar_y + 1}" width="0" height="{BAR_H - 2}" rx="3" fill="url(#eyegrad)">
<animate attributeName="width" values="0;{BAR_W - 2}" begin="{BAR_T0 + 0.05:.2f}s"
 dur="{BAR_DUR}s" calcMode="spline" keySplines="0.3 0 0.7 1" keyTimes="0;1" fill="freeze"/>
</rect>
<text x="{ART_X + BAR_W + 10}" y="{bar_y + BAR_H}" font-size="10.5" fill="{p["dim"]}">rendering pfp.ascii → svg…</text>
</g>
<g opacity="0">
<animate attributeName="opacity" begin="{SWAP_T + 0.15:.2f}s" dur="0.3s" values="0;1" fill="freeze"/>
<text x="{ART_X}" y="{bar_y + BAR_H}"><tspan fill="{p["purple"]}">$</tspan><tspan fill="{p["fg"]}"> █</tspan></text>
<text x="{ART_X + 24}" y="{bar_y + BAR_H}" font-size="10.5" fill="{p["dim"]}"># eyes: online · smoke: not detected</text>
</g>
<rect x="1" width="{CARD_W - 2}" height="3" fill="{p["scan"]}" opacity="0.05"
 clip-path="url(#card)">
<animate attributeName="y" values="{HEADER_H};{card_h - 8};{HEADER_H}" dur="11s"
 repeatCount="indefinite"/>
</rect>
</svg>
'''


def main():
    lines = load_art()
    print(f"art: {len(lines)} rows, max width {max(len(l) for l in lines)}")
    n_glow = sum(1 for i in EYE_ROWS for j in list(LEFT_ZONE) + list(RIGHT_ZONE)
                 if cell_kind(lines, i, j) in ("red", "purple"))
    n_pupil = sum(1 for i in EYE_ROWS for j in list(LEFT_ZONE) + list(RIGHT_ZONE)
                  if cell_kind(lines, i, j) in ("red_pupil", "purple_pupil"))
    print(f"eye cells: {n_glow} glow, {n_pupil} pupil")
    for name, p in PALETTES.items():
        out = ROOT / "assets" / f"harsh_ascii_{name}.svg"
        out.write_text("".join(emit_svg(lines, p).splitlines()) + "\n")
        print(f"wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
