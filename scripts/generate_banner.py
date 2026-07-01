#!/usr/bin/env python3
"""
Generates a self-looping, neon-glow "typing" SVG banner for a GitHub profile
README, using SMIL animations (works inside an <img> tag on GitHub — no JS
required). Timing is computed precisely in Python rather than hand-written
CSS keyframe percentages, so lines of any length stay in sync.

Run locally:      python scripts/generate_banner.py
Run in CI:         GITHUB_TOKEN is picked up automatically from env if present
"""

import os
import json
import datetime
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# CONFIG — edit these to personalize
# ---------------------------------------------------------------------------
CONFIG = {
    "username": os.environ.get("GH_USERNAME", "YOUR_GITHUB_USERNAME"),
    "taglines": [
        "Hi, I'm Seth 👋 ",
        "I'm a Web Specialist based out of the North Shore, US",
        "Currently: building modular, CRM-native Quality Control App",
    ],
    "width": 1200,
    "height": 300,
    "font_family": "'Fira Code', 'JetBrains Mono', Consolas, monospace",
    "font_size": 30,
    "type_speed_ms": 55,     # per character, typing in
    "erase_speed_ms": 32,    # per character, erasing
    "hold_ms": 1400,         # pause once fully typed
    "gap_ms": 300,           # pause once fully erased
    # Neon palette
    "colors": {
        "bg_top": "#0d0221",
        "bg_bottom": "#1a0b2e",
        "neon_a": "#ff00e6",   # magenta
        "neon_b": "#00f0ff",   # cyan
        "neon_c": "#7000ff",   # violet
        "text": "#f5f5ff",
    },
    "output_path": os.path.join(os.path.dirname(__file__), "..", "assets", "banner.svg"),
}

API_URL = "https://api.github.com"


def fetch_stats(username: str) -> dict:
    """Best-effort fetch of live stats. Falls back gracefully if rate-limited
    or offline, so the banner still renders."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-banner-script"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    stats = {"public_repos": None, "followers": None, "stars": None}

    def _get(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    try:
        user = _get(f"{API_URL}/users/{username}")
        stats["public_repos"] = user.get("public_repos")
        stats["followers"] = user.get("followers")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        pass

    try:
        stars = 0
        page = 1
        while True:
            repos = _get(f"{API_URL}/users/{username}/repos?per_page=100&page={page}")
            if not repos:
                break
            stars += sum(r.get("stargazers_count", 0) for r in repos)
            if len(repos) < 100:
                break
            page += 1
        stats["stars"] = stars
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        pass

    return stats


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_svg(cfg: dict, stats: dict) -> str:
    W, H = cfg["width"], cfg["height"]
    c = cfg["colors"]
    lines = cfg["taglines"]
    font_size = cfg["font_size"]

    # Rough monospace character width estimate for clip-rect sizing
    char_w = font_size * 0.6

    # Compute absolute timings for each line, chained end-to-end
    segments = []
    t = 0.0
    for line in lines:
        L = len(line)
        type_dur = (L * cfg["type_speed_ms"]) / 1000.0
        erase_dur = (L * cfg["erase_speed_ms"]) / 1000.0
        hold = cfg["hold_ms"] / 1000.0
        gap = cfg["gap_ms"] / 1000.0
        segments.append({
            "text": line,
            "width_px": L * char_w,
            "type_begin": t,
            "type_dur": type_dur,
            "erase_begin": t + type_dur + hold,
            "erase_dur": erase_dur,
        })
        t += type_dur + hold + erase_dur + gap
    total = t

    text_x = 60
    text_y = H / 2 + font_size * 0.35

    # --- Build per-line clip + text groups ---
    line_groups = []
    for i, seg in enumerate(segments):
        clip_id = f"clip{i}"
        line_groups.append(f'''
      <clipPath id="{clip_id}">
        <rect x="{text_x}" width="0" height="{font_size * 1.6:.0f}" y="{text_y - font_size:.0f}">
          <animate attributeName="width" from="0" to="{seg['width_px']:.1f}"
                   begin="loop.begin+{seg['type_begin']:.3f}s" dur="{seg['type_dur']:.3f}s"
                   fill="freeze" calcMode="linear"/>
          <animate attributeName="width" from="{seg['width_px']:.1f}" to="0"
                   begin="loop.begin+{seg['erase_begin']:.3f}s" dur="{seg['erase_dur']:.3f}s"
                   fill="freeze" calcMode="linear"/>
        </rect>
      </clipPath>''')

    text_elements = "\n".join(
        f'      <g clip-path="url(#clip{i})">'
        f'<text x="{text_x}" y="{text_y:.1f}" class="typed">{esc(seg["text"])}</text></g>'
        for i, seg in enumerate(segments)
    )

    clip_defs = "\n".join(line_groups)

    # --- Stats line ---
    stats_parts = []
    if stats.get("stars") is not None:
        stats_parts.append(f"★ {stats['stars']} stars")
    if stats.get("public_repos") is not None:
        stats_parts.append(f"{stats['public_repos']} repos")
    if stats.get("followers") is not None:
        stats_parts.append(f"{stats['followers']} followers")
    updated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    stats_line = "  ·  ".join(stats_parts) if stats_parts else "auto-updating"
    stats_text = f"{stats_line}  ·  last updated {updated} UTC"

    svg = f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c['bg_top']}"/>
      <stop offset="100%" stop-color="{c['bg_bottom']}"/>
    </linearGradient>

    <linearGradient id="neonGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{c['neon_a']}">
        <animate attributeName="stop-color"
          values="{c['neon_a']};{c['neon_b']};{c['neon_c']};{c['neon_a']}"
          dur="6s" repeatCount="indefinite"/>
      </stop>
      <stop offset="50%" stop-color="{c['neon_b']}">
        <animate attributeName="stop-color"
          values="{c['neon_b']};{c['neon_c']};{c['neon_a']};{c['neon_b']}"
          dur="6s" repeatCount="indefinite"/>
      </stop>
      <stop offset="100%" stop-color="{c['neon_c']}">
        <animate attributeName="stop-color"
          values="{c['neon_c']};{c['neon_a']};{c['neon_b']};{c['neon_c']}"
          dur="6s" repeatCount="indefinite"/>
      </stop>
    </linearGradient>

    <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="4.2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <filter id="softGlow" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="10"/>
    </filter>

    {clip_defs}

    <style>
      .typed {{
        font-family: {cfg['font_family']};
        font-size: {font_size}px;
        fill: {c['text']};
        filter: url(#glow);
        dominant-baseline: middle;
      }}
      .prompt {{
        font-family: {cfg['font_family']};
        font-size: {font_size}px;
        fill: {c['neon_b']};
        filter: url(#glow);
      }}
      .stats {{
        font-family: {cfg['font_family']};
        font-size: 13px;
        fill: #a89bd8;
        letter-spacing: 0.5px;
      }}
      .cursor {{
        fill: {c['neon_b']};
        filter: url(#glow);
      }}
    </style>
  </defs>

  <!-- invisible master clock all animations sync to; this is what makes the whole banner loop -->
  <rect x="0" y="0" width="1" height="1" opacity="0">
    <animate id="loop" attributeName="opacity" from="0" to="0" dur="{total:.3f}s" begin="0s;loop.end" repeatCount="indefinite"/>
  </rect>

  <rect x="0" y="0" width="{W}" height="{H}" rx="18" fill="url(#bgGrad)"/>

  <!-- animated border glow -->
  <rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="16" fill="none"
        stroke="url(#neonGrad)" stroke-width="2.5" filter="url(#softGlow)" opacity="0.9"/>
  <rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="16" fill="none"
        stroke="url(#neonGrad)" stroke-width="1.5"/>

  <!-- floating glow particles -->
  <circle cx="{W - 90}" cy="50" r="46" fill="{c['neon_a']}" opacity="0.12" filter="url(#softGlow)">
    <animate attributeName="cy" values="50;70;50" dur="7s" repeatCount="indefinite"/>
  </circle>
  <circle cx="{W - 180}" cy="150" r="60" fill="{c['neon_b']}" opacity="0.10" filter="url(#softGlow)">
    <animate attributeName="cy" values="150;120;150" dur="9s" repeatCount="indefinite"/>
  </circle>
  <circle cx="{W - 40}" cy="170" r="30" fill="{c['neon_c']}" opacity="0.14" filter="url(#softGlow)">
    <animate attributeName="cx" values="{W - 40};{W - 70};{W - 40}" dur="8s" repeatCount="indefinite"/>
  </circle>

  <text x="{text_x - 42}" y="{text_y:.1f}" class="prompt">&gt;</text>
{text_elements}
  <rect x="{text_x - 20}" y="{text_y - font_size:.1f}" width="{font_size * 0.55:.1f}" height="{font_size * 1.2:.1f}" class="cursor" opacity="0">
    <animate attributeName="x" attributeType="XML"
      values="{'; '.join(f'{text_x + s['width_px']:.1f}' for s in segments)}"
      dur="{total:.3f}s" begin="loop.begin" repeatCount="indefinite" calcMode="discrete"
      keyTimes="{'; '.join(f'{(s['type_begin'])/total:.4f}' for s in segments)}"/>
    <animate attributeName="opacity" values="0;1;1;0" dur="{total:.3f}s" begin="loop.begin" repeatCount="indefinite"/>
    <animate attributeName="fill-opacity" values="1;0;1" dur="0.9s" begin="loop.begin" repeatCount="indefinite"/>
  </rect>

  <text x="{W - 20}" y="{H - 18}" text-anchor="end" class="stats">{esc(stats_text)}</text>
</svg>
'''
    return svg


def main():
    cfg = CONFIG
    stats = fetch_stats(cfg["username"])
    svg = build_svg(cfg, stats)
    out_path = os.path.abspath(cfg["output_path"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {out_path}")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()
