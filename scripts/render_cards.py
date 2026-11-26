#!/usr/bin/env python3
"""Render the animated SVG cards used by Tanya Pandey's GitHub profile.

Run:
  python scripts/render_cards.py
  STATIC=1 python scripts/render_cards.py
  GITHUB_TOKEN=... python scripts/render_cards.py --refresh

The optional --refresh mode reads GitHub's GraphQL contribution calendar and
writes data/contributions.json before rendering. No third-party runtime package
is required; fonttools + brotli are used only to subset/embed the brand fonts.
"""
from __future__ import annotations

import argparse
import base64
import calendar
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "contributions.json"
CARDS_DIR = ROOT / "cards"
CONFIG = {
    "name": "Tanya Pandey",
    "username": "TanyaPandey25",
    "tagline": "Computer Science undergraduate at BMSCE building practical software across web, AI and data.",
    "github": "https://github.com/TanyaPandey25",
    "linkedin": "https://www.linkedin.com/in/tanyapandey-dev/",
    "third_link": "https://github.com/TanyaPandey25?tab=repositories",
    "third_label": "PROJECTS",
    "portfolio_url": "",
    "portrait_url": "",
    "colors": {
        "paper": "#F5F3EC", "ink": "#123B35", "deep": "#164B49",
        "jade": "#9AB9A5", "gold": "#D6BD88", "muted": "#71847B",
        "line": "#D9DED5", "soft": "#E9EEE7",
    },
    "featured_repos": [
        {"name": "Civic-Lens", "url": "https://github.com/TanyaPandey25/Civic-Lens",
         "description": "A campus issue reporting and resolution platform built to make problems visible and actionable.",
         "stack": "React · Vite · Express · MongoDB", "number": "01"},
        {"name": "EcoSphere-AR", "url": "https://github.com/TanyaPandey25/EcoSphere-AR",
         "description": "An augmented-reality biodiversity encyclopedia with image recognition, live species data and voice narration.",
         "stack": "Unity 6 · C# · AR Foundation · ARCore", "number": "02"},
        {"name": "Deadline Decoder", "url": "https://github.com/TanyaPandey25/deadline-decoder",
         "description": "Turns college notices into clear tasks, deadlines, submission methods and required materials.",
         "stack": "React · FastAPI · Gemma", "number": "03"},
    ],
}
FONT_URLS = {
    "dm": "https://raw.githubusercontent.com/google/fonts/main/ofl/dmsans/DMSans%5Bwght%5D.ttf",
    "playfair": "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
}
FONT_TEXT = "Tanya PandeyComputer Science undergraduate at BMSCE building practical software across web, AI and data.GITHUBLINKEDINPROJECTSCivic-LensEcoSphere-ARDeadline Decoder"
STATIC = os.getenv("STATIC", "0") == "1"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def read_data() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"months": [], "weeks": [], "total_contributions": 0,
            "streak": 0, "active_days": 0, "busiest_day": "—",
            "generated_at": None}


def refresh_contributions() -> dict:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise RuntimeError("--refresh requires GITHUB_TOKEN (or GH_TOKEN).")
    query = """query($login:String!,$from:DateTime!,$to:DateTime!){
      user(login:$login){
        contributionsCollection(from:$from,to:$to){
          contributionCalendar{
            totalContributions
            weeks{contributionDays{contributionCount date weekday}}
          }
        }
      }
    }"""
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    payload = json.dumps({"query": query, "variables": {
        "login": CONFIG["username"], "from": start.isoformat() + "T00:00:00Z",
        "to": (today + dt.timedelta(days=1)).isoformat() + "T00:00:00Z"}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-card-renderer"})
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode())
    if result.get("errors"):
        raise RuntimeError("GitHub GraphQL: " + json.dumps(result["errors"]))
    calendar_data = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = calendar_data["weeks"]
    days = [day for week in weeks for day in week["contributionDays"]]
    monthly: dict[str, int] = {}
    weekday_totals = [0] * 7
    for day in days:
        key = day["date"][:7]
        monthly[key] = monthly.get(key, 0) + int(day["contributionCount"])
        weekday_totals[int(day["weekday"])] += int(day["contributionCount"])
    months = [{"month": key, "label": dt.datetime.strptime(key, "%Y-%m").strftime("%b"),
               "count": count} for key, count in sorted(monthly.items())][-12:]
    active_days = sum(1 for d in days if int(d["contributionCount"]) > 0)
    # Current streak includes today, or starts yesterday if today has no activity.
    streak = 0
    indexed = {d["date"]: int(d["contributionCount"]) for d in days}
    cursor = today
    if indexed.get(cursor.isoformat(), 0) == 0:
        cursor -= dt.timedelta(days=1)
    while indexed.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= dt.timedelta(days=1)
    busiest = calendar.day_name[max(range(7), key=lambda i: weekday_totals[i])] if any(weekday_totals) else "—"
    clean_weeks = [[{"date": d["date"], "count": int(d["contributionCount"]),
                     "weekday": int(d["weekday"])} for d in w["contributionDays"]] for w in weeks]
    data = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "total_contributions": int(calendar_data["totalContributions"]),
            "months": months, "weeks": clean_weeks, "streak": streak,
            "active_days": active_days, "busiest_day": busiest}
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def font_data() -> tuple[str, str]:
    """Download, subset and embed WOFF fonts when fonttools is available."""
    if STATIC:
        # Fonts remain embedded in static exports too; only motion is disabled.
        pass
    cache = ROOT / ".font-cache"
    cache.mkdir(exist_ok=True)
    embedded = []
    for key, url in FONT_URLS.items():
        ttf = cache / f"{key}.ttf"
        woff = cache / f"{key}.woff"
        if not woff.exists():
            try:
                if not ttf.exists():
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=25) as response:
                        ttf.write_bytes(response.read())
                subprocess.run([sys.executable, "-m", "fontTools.subset", str(ttf),
                    f"--text={FONT_TEXT}", f"--output-file={woff}", "--flavor=woff",
                    "--layout-features=*", "--name-IDs=0,1,2,4,6"], check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as exc:
                print(f"Font embedding skipped for {key}: {exc}", file=sys.stderr)
                embedded.append("")
                continue
        embedded.append(base64.b64encode(woff.read_bytes()).decode("ascii") if woff.exists() else "")
    return tuple(embedded) if len(embedded) == 2 else ("", "")


def svg_start(width: int, height: int, title: str, index: int,
              fonts: tuple[str, str]) -> str:
    paper, ink, deep, jade, gold, muted, line, soft = CONFIG["colors"].values()
    dm, playfair = fonts
    font_css = ""
    if dm:
        font_css += f"@font-face{{font-family:DM;src:url(data:font/woff;base64,{dm}) format('woff');font-weight:100 900}}"
    if playfair:
        font_css += f"@font-face{{font-family:Playfair;src:url(data:font/woff;base64,{playfair}) format('woff');font-weight:100 900}}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title>
<style>
{font_css}
:root{{--paper:{paper};--ink:{ink};--deep:{deep};--jade:{jade};--gold:{gold};--muted:{muted};--line:{line};--soft:{soft}}}
text{{font-family:DM,'Arial',sans-serif;fill:var(--ink)}}
.serif{{font-family:Playfair,Georgia,serif}}
.kicker{{font-size:14px;font-weight:700;letter-spacing:2.5px;fill:var(--muted)}}
.label{{font-size:14px;font-weight:700;letter-spacing:1.4px;fill:var(--muted)}}
.body{{font-size:19px;fill:var(--deep)}}
.card-motion{{opacity:1;transform:translateY(0);animation:rise .85s cubic-bezier(.2,.7,.2,1) both;animation-delay:{index * 0.42:.2f}s}}
@keyframes rise{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
@media(prefers-reduced-motion:reduce){{.card-motion{{animation:none!important;opacity:1!important;transform:none!important}}.smil{{display:none!important}}}}
</style>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="24" fill="{paper}" stroke="{line}" stroke-width="2"/>
<g class="card-motion">
'''

def svg_end() -> str:
    return "</g></svg>\n"


def write_svg(name: str, content: str) -> None:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    (CARDS_DIR / name).write_text(content, encoding="utf-8")


def hero(fonts: tuple[str, str]) -> None:
    c = CONFIG["colors"]; portrait = CONFIG["portrait_url"]
    image = (f'<clipPath id="portraitClip"><circle cx="850" cy="160" r="92"/></clipPath>'
             f'<image href="{esc(portrait)}" x="758" y="68" width="184" height="184" '
             f'preserveAspectRatio="xMidYMid slice" clip-path="url(#portraitClip)"/>'
             if portrait else
             f'<circle cx="850" cy="160" r="92" fill="{c["soft"]}"/>'
             f'<text x="850" y="180" text-anchor="middle" font-size="58" class="serif" fill="{c["deep"]}">TP</text>')
    s = svg_start(1000, 320, "Tanya Pandey — developer profile", 0, fonts)
    s += f'''<circle cx="930" cy="30" r="100" fill="{c["jade"]}" opacity=".18"/>
<path d="M0 258 C210 220 360 320 570 275 S850 245 1000 275" fill="none" stroke="{c["jade"]}" stroke-width="2" opacity=".7"/>
<text x="62" y="72" class="kicker">HELLO, I'M</text>
<text x="60" y="157" class="serif" font-size="66" font-weight="600">{esc(CONFIG["name"])}</text>
<text x="64" y="207" class="body">{esc(CONFIG["tagline"])}</text>
<rect x="64" y="246" width="150" height="34" rx="17" fill="{c["deep"]}"/>
<text x="139" y="268" text-anchor="middle" font-size="12" font-weight="700" letter-spacing="1.4" fill="{c["paper"]}">BUILD · LEARN · SHIP</text>
{image}
<circle cx="850" cy="160" r="100" fill="none" stroke="{c["gold"]}" stroke-width="3"/>
'''
    s += svg_end(); write_svg("01-hero.svg", s)


def links(fonts: tuple[str, str]) -> None:
    c = CONFIG["colors"]
    tiles = [("GITHUB", "Code, projects & experiments", CONFIG["github"], "GH"),
             ("LINKEDIN", "Connect professionally", CONFIG["linkedin"], "in"),
             (CONFIG["third_label"], "Explore what I'm building", CONFIG["third_link"], "↗")]
    s = svg_start(1000, 184, "Find Tanya online", 1, fonts)
    for i, (title, subtitle, url, mark) in enumerate(tiles):
        x = 22 + i * 326
        s += f'''<a href="{esc(url)}" target="_blank">
<rect x="{x}" y="20" width="310" height="144" rx="18" fill="{c["soft"]}" stroke="{c["line"]}"/>
<circle cx="{x+43}" cy="65" r="22" fill="{c["deep"]}"/>
<text x="{x+43}" y="72" text-anchor="middle" font-size="18" font-weight="700" fill="{c["paper"]}">{esc(mark)}</text>
<text x="{x+25}" y="112" font-size="17" font-weight="800" letter-spacing="1.3">{esc(title)}</text>
<text x="{x+25}" y="139" font-size="13" fill="{c["muted"]}">{esc(subtitle)}</text>
</a>'''
    s += svg_end(); write_svg("02-links.svg", s)


def analytics(data: dict, fonts: tuple[str, str]) -> None:
    c = CONFIG["colors"]; months = data.get("months", [])[-12:]
    months = ([{"label": "—", "count": 0}] * (12-len(months))) + months
    maximum = max([int(m.get("count", 0)) for m in months] + [1])
    s = svg_start(1000, 390, "Contribution activity analytics", 2, fonts)
    s += f'''<text x="55" y="55" class="kicker">CONSISTENCY OVER TIME</text>
<text x="55" y="96" class="serif" font-size="34">A little progress, every month.</text>
<text x="55" y="145" class="label">CONTRIBUTIONS / MONTH</text>'''
    for i, m in enumerate(months):
        x = 64 + i * 75
        h = int(132 * int(m.get("count", 0)) / maximum)
        y = 302 - h
        s += f'''<rect x="{x}" y="168" width="42" height="134" rx="8" fill="{c["soft"]}"/>
<rect x="{x}" y="{y}" width="42" height="{h}" rx="8" fill="{c["jade"]}">
<animate class="smil" attributeName="height" from="0" to="{h}" dur=".9s" begin="{1.1+i*.055:.2f}s" fill="freeze"/>
<animate class="smil" attributeName="y" from="302" to="{y}" dur=".9s" begin="{1.1+i*.055:.2f}s" fill="freeze"/>
</rect>
<text x="{x+21}" y="326" text-anchor="middle" font-size="12" fill="{c["muted"]}">{esc(m.get("label",""))}</text>'''
    metrics = [("CURRENT STREAK", f'{int(data.get("streak",0))} days'),
               ("ACTIVE DAYS", str(int(data.get("active_days",0)))),
               ("BUSIEST DAY", str(data.get("busiest_day","—")))]
    for i, (label, value) in enumerate(metrics):
        x = 55 + i * 310
        s += f'''<text x="{x}" y="365" class="label">{esc(label)}</text>
<text x="{x+160}" y="365" font-size="19" font-weight="700">{esc(value)}</text>'''
    s += svg_end(); write_svg("03-activity.svg", s)


def repo_card(repo: dict, index: int, fonts: tuple[str, str]) -> None:
    c = CONFIG["colors"]; filename = f'04-project-{index:02d}-{re.sub("[^a-z0-9]+","-",repo["name"].lower()).strip("-")}.svg'
    s = svg_start(1000, 230, f'{repo["name"]} featured project', 3+index, fonts)
    s += f'''<text x="58" y="54" class="kicker">FEATURED PROJECT / {esc(repo["number"])}</text>
<text x="58" y="112" class="serif" font-size="39" font-weight="600">{esc(repo["name"])}</text>
<text x="60" y="151" class="body">{esc(repo["description"])}</text>
<text x="60" y="193" font-size="15" font-weight="700" fill="{c["muted"]}">{esc(repo["stack"])}</text>
<rect x="825" y="75" width="120" height="52" rx="26" fill="{c["deep"]}"/>
<a href="{esc(repo["url"])}"><text x="885" y="108" text-anchor="middle" font-size="15" font-weight="700" fill="{c["paper"]}">VIEW ↗</text></a>
<path d="M770 20 L770 210" stroke="{c["line"]}" stroke-width="2"/>
'''
    s += svg_end(); write_svg(filename, s)


def contribution_graph(data: dict, fonts: tuple[str, str]) -> None:
    c = CONFIG["colors"]; weeks = data.get("weeks", [])
    s = svg_start(1000, 270, "GitHub contribution graph", 3+len(CONFIG["featured_repos"]), fonts)
    s += f'''<text x="55" y="55" class="kicker">THE WORK ADDS UP</text>
<text x="55" y="96" class="serif" font-size="34">Contribution rhythm</text>
<text x="945" y="63" text-anchor="end" font-size="14" fill="{c["muted"]}">{int(data.get("total_contributions",0)):,} contributions in the last year</text>'''
    if weeks:
        cell, gap, start_x, start_y = 12, 4, 65, 125
        for wi, week in enumerate(weeks[-53:]):
            for day in week:
                weekday = int(day.get("weekday", 0))
                count = int(day.get("count", 0))
                level = 0 if count == 0 else 1 if count < 3 else 2 if count < 6 else 3 if count < 10 else 4
                fills = [c["soft"], "#D6E5D9", "#AFCBB8", c["jade"], c["deep"]]
                x, y = start_x + wi*(cell+gap), start_y + weekday*(cell+gap)
                s += f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{fills[level]}"><title>{esc(day.get("date",""))}: {count} contributions</title></rect>'
    else:
        s += f'<text x="60" y="165" class="body">Contribution data will appear after the first scheduled refresh.</text>'
    s += f'''<text x="65" y="246" font-size="12" fill="{c["muted"]}">LESS</text>'''
    for i, fill in enumerate(["#E9EEE7","#D6E5D9","#AFCBB8",c["jade"],c["deep"]]):
        s += f'<rect x="{115+i*20}" y="234" width="13" height="13" rx="3" fill="{fill}"/>'
    s += f'<text x="225" y="246" font-size="12" fill="{c["muted"]}">MORE</text>'
    s += svg_end(); write_svg("99-contributions.svg", s)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Fetch contribution data from GitHub GraphQL first.")
    args = parser.parse_args()
    data = refresh_contributions() if args.refresh else read_data()
    fonts = font_data()
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    hero(fonts); links(fonts); analytics(data, fonts)
    for i, repo in enumerate(CONFIG["featured_repos"], start=1):
        repo_card(repo, i, fonts)
    contribution_graph(data, fonts)
    print(f"Rendered {len(list(CARDS_DIR.glob('*.svg')))} SVG cards in {CARDS_DIR}")
    print("STATIC=1: final-frame SVGs" if STATIC else "Animated SVGs generated.")


if __name__ == "__main__":
    main()
