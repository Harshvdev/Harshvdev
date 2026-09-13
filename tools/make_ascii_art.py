#!/usr/bin/env python3
"""
Regenerate the animated ASCII-terminal SVGs of Harsh's profile picture.

Outputs (relative to repo root):
  assets/harsh_ascii_dark.svg    shown when prefers-color-scheme: dark
  assets/harsh_ascii_light.svg   shown when prefers-color-scheme: light
  assets/harsh_ascii.txt         raw art, for terminals / gists / fun

The SVGs are pure SMIL (no JS) so they animate anywhere GitHub renders
images. The eyes (red + purple in the source art) are pulled out as neon
tspans that breathe, blink and occasionally surge. Rows cascade in like a
terminal boot log, a scanline sweeps the panel, and two rows glitch.

Run:  python3 tools/make_ascii_art.py   (needs Pillow + numpy)
"""

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "Harshvdev.png"

# ---- grid --------------------------------------------------------------
COLS = 76
FIGURE_BBOX = (145, 198, 1105, 1029)  # x0 y0 x1 y1 — tuned to the pfp
RAMP = " .,:;=+*#%@"  # faint -> dense

# ---- geometry (px, viewBox units) --------------------------------------
F, LH = 13, 14          # font-size / line-height
ADV = F * 0.602         # advance of a typical monospace glyph (DejaVu)
ART_X = 19              # left edge of the art block
ART_Y0 = 108            # baseline of the first art row
CARD_W, CARD_H = 636, 592
HEADER_H = 36
BAR_Y, BAR_H = 566, 8   # progress bar / cursor line
ART_W = round(COLS * ADV)

REVEAL_T0, REVEAL_STEP, REVEAL_DUR = 0.90, 0.045, 0.18
BAR_T0, BAR_DUR = 0.85, 2.0
SWAP_T = BAR_T0 + BAR_DUR + 1.0  # when progress bar swaps to the cursor line

PALETTES = {
    "dark": dict(
        panel="#060a12", header="#0d1420", border="#2b3442",
        fg="#e6edf3", dim="#7d8590", title="#8b98ab",
        red="#ff2d40", red_dim="#b31e2c",
        purple="#b45cff", purple_dim="#7c39c4",
        cyan="#58e6d9", scan="#58e6d9",
    ),
    "light": dict(
        panel="#f6f8fa", header="#eaeef2", border="#d0d7de",
        fg="#24292f", dim="#57606a", title="#57606a",
        red="#d1242f", red_dim="#9e1b23",
        purple="#8250df", purple_dim="#6b45b8",
        cyan="#1a7fbd", scan="#1a7fbd",
    ),
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_grid():
    """Return (chars, kinds) — kinds[i][j] in {'space','fg','red','purple'}."""
    im = Image.open(SRC).convert("RGB")
    a = np.asarray(im).astype(int)
    x0, y0, x1, y1 = FIGURE_BBOX
    crop = a[y0:y1, x0:x1]

    rows = max(8, round(COLS * crop.shape[0] / crop.shape[1] / 2))
    g = np.asarray(
        Image.fromarray(crop.astype(np.uint8)).resize((COLS, rows), Image.BOX)
    ).astype(int)

    lum = g.mean(axis=2)
    r, gr, b = g[..., 0], g[..., 1], g[..., 2]
    white_dist = np.abs(g - np.array([254, 254, 254])).sum(axis=2)

    red = (r > 150) & (gr < 95) & (b < 95) & (r - gr > 70)
    purple = (b > 140) & (r > 80) & (gr < 110) & (b - gr > 60)
    content = white_dist > 30

    # shrink masks on the grid itself (threshold ~40% coverage of a cell)
    def shrink(m):
        return (
            np.asarray(
                Image.fromarray((m * 255).astype(np.uint8)).resize((COLS, rows), Image.BOX)
            )
            > 100
        )

    red, purple = shrink(red), shrink(purple)

    chars, kinds = [], []
    for i in range(rows):
        crow, krow = [], []
        for j in range(COLS):
            if red[i, j]:
                crow.append("@"); krow.append("red")
            elif purple[i, j]:
                crow.append("@"); krow.append("purple")
            elif not content[i, j]:
                crow.append(" "); krow.append("space")
            else:
                t = (255 - lum[i, j]) / 255.0
                idx = 1 + min(9, int(t * 10))
                crow.append(RAMP[idx]); krow.append("fg")
        chars.append("".join(crow))
        kinds.append(krow)
    return chars, kinds


def eye_tspan(kind: str, text: str, p: dict) -> str:
    """A neon tspan for one run of eye cells."""
    col = p["red"] if kind == "red" else p["purple"]
    dim = p["red_dim"] if kind == "red" else p["purple_dim"]
    return (
        f'<tspan fill="{col}" stroke="{col}" stroke-width="1.4" '
        f'paint-order="stroke">'
        f'<animate attributeName="fill" values="{col};{dim};{col}" '
        f'dur="2.8s" repeatCount="indefinite"/>'
        f'<animate attributeName="stroke-opacity" values="0.55;0.15;0.55" '
        f'dur="2.8s" repeatCount="indefinite"/>'
        f'<animate attributeName="fill-opacity" '
        f'values="1;1;0.06;0.12;1;1" '
        f'keyTimes="0;0.84;0.86;0.878;0.895;1" dur="7.3s" '
        f'repeatCount="indefinite"/>'
        f'<animate attributeName="stroke-width" values="1.4;1.4;3.4;1.4" '
        f'keyTimes="0;0.615;0.63;1" dur="8s" repeatCount="indefinite"/>'
        f"{esc(text)}</tspan>"
    )


def row_svg(chars: list[str], kinds: list[list[str]], i: int, p: dict,
            glitch: str | None) -> str:
    y = ART_Y0 + i * LH
    # group consecutive same-kind cells into segments
    segs = []
    for j, k in enumerate(kinds[i]):
        if segs and segs[-1][0] == k:
            segs[-1][2] = j + 1
        else:
            segs.append([k, j, j + 1])
    parts = []
    for k, a, b in segs:
        text = chars[i][a:b]
        if k in ("red", "purple"):
            parts.append(eye_tspan(k, text, p))
        else:
            parts.append(esc(text))
    body = f'<text x="{ART_X}" y="{y}" fill="{p["fg"]}">{"".join(parts)}</text>'

    animates = [
        f'<animate attributeName="opacity" begin="{REVEAL_T0 + i * REVEAL_STEP:.3f}s" '
        f'dur="{REVEAL_DUR}s" values="0;1" fill="freeze"/>'
    ]
    if glitch:  # quick horizontal jitter at one point in an 8s cycle
        animates.append(
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="0 0;0 0;5 0;-4 0;0 0;0 0" '
            f'keyTimes="0;{glitch};{float(glitch) + 0.012:.3f};'
            f'{float(glitch) + 0.024:.3f};{float(glitch) + 0.036:.3f};1" '
            f'dur="8s" repeatCount="indefinite"/>'
        )
        animates.append(
            f'<animate attributeName="fill" '
            f'values="{p["fg"]};{p["fg"]};{p["cyan"]};{p["fg"]};{p["fg"]}" '
            f'keyTimes="0;{glitch};{float(glitch) + 0.012:.3f};'
            f'{float(glitch) + 0.036:.3f};1" dur="8s" repeatCount="indefinite"/>'
        )
    return f'<g opacity="0">{"".join(animates)}{body}</g>'


def emit_svg(chars, kinds, p: dict) -> str:
    rows_n = len(chars)
    art_h = ART_Y0 + (rows_n - 1) * LH

    # rows that glitch: one hair row, the two eye rows
    glitch_rows = {}
    if rows_n >= 23:
        glitch_rows = {8: "0.400", rows_n - 14: "0.782", rows_n - 10: "0.406"}

    boot = [
        (f'<tspan fill="{p["purple"]}">$</tspan> whoami', ""),
        ("harsh — builder · uttar pradesh · in", "dim"),
        (f'<tspan fill="{p["purple"]}">$</tspan> ./render pfp.png '
         f'--style=ascii --eyes=neon', ""),
    ]
    boot_lines = []
    for i, (txt, style) in enumerate(boot):
        fill = p["dim"] if style == "dim" else p["fg"]
        boot_lines.append(
            f'<g opacity="0"><animate attributeName="opacity" '
            f'begin="{0.15 + i * 0.22:.2f}s" dur="0.15s" values="0;1" '
            f'fill="freeze"/><text x="{ART_X}" y="{58 + i * LH}" '
            f'fill="{fill}">{txt}</text></g>'
        )

    art_rows = [
        row_svg(chars, kinds, i, p, glitch_rows.get(i)) for i in range(rows_n)
    ]

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}"
     width="{CARD_W}" height="{CARD_H}" role="img" xml:space="preserve"
     font-family="'JetBrains Mono','Fira Code','Cascadia Code',Menlo,Consolas,'DejaVu Sans Mono',monospace">
<title>Harsh — ASCII terminal avatar</title>
<desc>Terminal window revealing an ASCII render of Harsh's avatar with
glowing red and purple eyes that blink and surge.</desc>
<defs>
<linearGradient id="eyegrad" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="{p["red"]}"/><stop offset="1" stop-color="{p["purple"]}"/>
</linearGradient>
<clipPath id="card"><rect x="1" y="1" width="{CARD_W - 2}" height="{CARD_H - 2}" rx="10"/></clipPath>
<clipPath id="hdr"><rect x="1" y="1" width="{CARD_W - 2}" height="{HEADER_H}" rx="9"/></clipPath>
</defs>
<rect x="0.5" y="0.5" width="{CARD_W - 1}" height="{CARD_H - 1}" rx="10"
 fill="{p["panel"]}" stroke="{p["border"]}"/>
<rect x="1" y="1" width="{CARD_W - 2}" height="{HEADER_H}" fill="{p["header"]}"
 clip-path="url(#hdr)"/>
<circle cx="20" cy="{HEADER_H // 2 + 1}" r="5" fill="#ff5f57"/>
<circle cx="38" cy="{HEADER_H // 2 + 1}" r="5" fill="#febc2e"/>
<circle cx="56" cy="{HEADER_H // 2 + 1}" r="5" fill="#28c840"/>
<text x="{CARD_W // 2}" y="{HEADER_H // 2 + 5}" text-anchor="middle" font-size="11"
 fill="{p["title"]}">harsh@github: ~/profile — zsh</text>
{"".join(boot_lines)}
<g><animate attributeName="opacity" values="1;1;0.95;1;1;0.97;1;1"
 keyTimes="0;0.13;0.14;0.15;0.55;0.56;0.57;1" dur="9s" repeatCount="indefinite"/>
{"".join(art_rows)}</g>
<g opacity="0">
<animate attributeName="opacity" begin="{BAR_T0}s" dur="0.2s" values="0;1" fill="freeze"/>
<animate attributeName="opacity" begin="{SWAP_T:.2f}s" dur="0.25s" values="1;0" fill="freeze"/>
<rect x="{ART_X}" y="{BAR_Y}" width="140" height="{BAR_H}" rx="4" fill="none"
 stroke="{p["dim"]}" stroke-opacity="0.6"/>
<rect x="{ART_X + 1}" y="{BAR_Y + 1}" width="0" height="{BAR_H - 2}" rx="3"
 fill="url(#eyegrad)">
<animate attributeName="width" values="0;{138}" begin="{BAR_T0 + 0.05:.2f}s"
 dur="{BAR_DUR}s" calcMode="spline" keySplines="0.3 0 0.7 1" keyTimes="0;1"
 fill="freeze"/>
</rect>
<text x="{ART_X + 150}" y="{BAR_Y + BAR_H}" font-size="11" fill="{p["dim"]}">rendering harsh.pfp → ascii…</text>
</g>
<g opacity="0">
<animate attributeName="opacity" begin="{SWAP_T + 0.15:.2f}s" dur="0.3s" values="0;1" fill="freeze"/>
<text x="{ART_X}" y="{BAR_Y + BAR_H}" font-size="{F}">
<tspan fill="{p["purple"]}">$</tspan><tspan fill="{p["dim"]}"> </tspan><tspan fill="{p["fg"]}" font-size="{F - 1}">█</tspan></text>
<text x="{ART_X + 22}" y="{BAR_Y + BAR_H}" font-size="11" fill="{p["dim"]}"># eyes: online · smoke: not detected</text>
</g>
<rect x="1" width="{CARD_W - 2}" height="3" fill="{p["scan"]}" opacity="0.05"
 clip-path="url(#card)">
<animate attributeName="y" values="{HEADER_H};{CARD_H - 8};{HEADER_H}" dur="11s"
 repeatCount="indefinite"/>
</rect>
</svg>
'''


def main():
    chars, kinds = build_grid()
    for name, p in PALETTES.items():
        out = ROOT / "assets" / f"harsh_ascii_{name}.svg"
        out.write_text("".join(emit_svg(chars, kinds, p).splitlines()) + "\n")
        print(f"wrote {out} ({out.stat().st_size:,} bytes)")
    (ROOT / "assets" / "harsh_ascii.txt").write_text("\n".join(chars) + "\n")
    print("wrote assets/harsh_ascii.txt")


if __name__ == "__main__":
    main()
