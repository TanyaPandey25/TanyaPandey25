#!/usr/bin/env python3
"""Render Tanya Pandey's dark, glassmorphic GitHub profile cards.

Run: python scripts/render_cards.py
Static screenshot mode: STATIC=1 python scripts/render_cards.py
Refresh GitHub contribution data first: python scripts/render_cards.py --refresh
"""
from __future__ import annotations
import argparse, base64, calendar, datetime as dt, html, json, os, re, subprocess, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "contributions.json"
CARDS = ROOT / "cards"
STATIC = os.getenv("STATIC", "0") == "1"

CONFIG = {
    "name": "Tanya Pandey",
    "username": "TanyaPandey25",
    "tagline": "Computer science undergrad",
    "github": "https://github.com/TanyaPandey25",
    "linkedin": "https://www.linkedin.com/in/tanyapandey-dev/",
    "projects": "https://github.com/TanyaPandey25?tab=repositories",
    "portrait_url": "",
    "colors": {
        "bg": "#080916", "panel": "#111329", "panel2": "#171833",
        "violet": "#9B6CFF", "purple": "#6738B8", "blue": "#527BFF",
        "cyan": "#75C8F5", "pink": "#D58AEF", "white": "#F4F1FF",
        "muted": "#B3B2CE", "line": "#7770B5"
    },
    "repos": [
        {"name":"Civic-Lens","url":"https://github.com/TanyaPandey25/Civic-Lens",
         "description":"A campus issue reporting and resolution platform that makes everyday problems visible and actionable.",
         "stack":"React  ·  Vite  ·  Express  ·  MongoDB","index":"01","accent":"#9B6CFF"},
        {"name":"EcoSphere-AR","url":"https://github.com/TanyaPandey25/EcoSphere-AR",
         "description":"An augmented-reality biodiversity experience bringing species discovery into the real world.",
         "stack":"Unity  ·  C#  ·  AR Foundation  ·  ARCore","index":"02","accent":"#75C8F5"},
        {"name":"Deadline Decoder","url":"https://github.com/TanyaPandey25/deadline-decoder",
         "description":"Turns college notices into structured tasks, deadlines, submission methods and required materials.",
         "stack":"React  ·  FastAPI  ·  Gemma","index":"03","accent":"#D58AEF"}
    ]
}
FONT_URLS = {
    "manrope": "https://raw.githubusercontent.com/google/fonts/main/ofl/manrope/Manrope%5Bwght%5D.ttf",
    "cormorant": "https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf"
}
FONT_TEXT = "Tanya PandeyComputer Science undergraduate building thoughtful software across web AI and data.GITHUBLINKEDINPROJECTSCivic-LensEcoSphere-ARDeadline Decoder0123456789·—↗"
def esc(x): return html.escape(str(x), quote=True)
def read_data():
    if DATA_FILE.exists(): return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"months":[],"weeks":[],"total_contributions":0,"streak":0,"active_days":0,"busiest_day":"—"}
def refresh_data():
    token=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token: raise RuntimeError("--refresh requires GITHUB_TOKEN or GH_TOKEN")
    query="""query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){contributionCalendar{totalContributions weeks{contributionDays{contributionCount date weekday}}}}}}"""
    today=dt.date.today(); start=today-dt.timedelta(days=364)
    payload=json.dumps({"query":query,"variables":{"login":CONFIG["username"],"from":start.isoformat()+"T00:00:00Z","to":(today+dt.timedelta(days=1)).isoformat()+"T00:00:00Z"}}).encode()
    req=urllib.request.Request("https://api.github.com/graphql",data=payload,headers={"Authorization":f"Bearer {token}","Content-Type":"application/json","User-Agent":"profile-card-renderer"})
    with urllib.request.urlopen(req,timeout=30) as response: result=json.loads(response.read().decode())
    if result.get("errors"): raise RuntimeError(json.dumps(result["errors"]))
    cal=result["data"]["user"]["contributionsCollection"]["contributionCalendar"]; weeks=cal["weeks"]
    days=[d for w in weeks for d in w["contributionDays"]]; monthly={}; weekdays=[0]*7
    for d in days:
        key=d["date"][:7]; monthly[key]=monthly.get(key,0)+int(d["contributionCount"]); weekdays[int(d["weekday"])]+=int(d["contributionCount"])
    months=[{"month":k,"label":dt.datetime.strptime(k,"%Y-%m").strftime("%b"),"count":v} for k,v in sorted(monthly.items())][-12:]
    active=sum(int(d["contributionCount"])>0 for d in days); indexed={d["date"]:int(d["contributionCount"]) for d in days}
    cursor=today
    if indexed.get(cursor.isoformat(),0)==0: cursor-=dt.timedelta(days=1)
    streak=0
    while indexed.get(cursor.isoformat(),0)>0: streak+=1; cursor-=dt.timedelta(days=1)
    busiest=calendar.day_name[max(range(7),key=lambda i:weekdays[i])] if any(weekdays) else "—"
    data={"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"total_contributions":int(cal["totalContributions"]),"months":months,
          "weeks":[[{"date":d["date"],"count":int(d["contributionCount"]),"weekday":int(d["weekday"])} for d in w["contributionDays"]] for w in weeks],
          "streak":streak,"active_days":active,"busiest_day":busiest}
    DATA_FILE.parent.mkdir(parents=True,exist_ok=True); DATA_FILE.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    return data
def fonts():
    cache=ROOT/".font-cache"; cache.mkdir(exist_ok=True); result=[]
    for name,url in FONT_URLS.items():
        ttf=cache/f"{name}.ttf"; woff=cache/f"{name}.woff"
        if not woff.exists():
            if not ttf.exists():
                req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req,timeout=30) as r: ttf.write_bytes(r.read())
            subprocess.run([sys.executable,"-m","fontTools.subset",str(ttf),f"--text={FONT_TEXT}",f"--output-file={woff}","--flavor=woff","--layout-features=*"],check=True,stdout=subprocess.DEVNULL)
        result.append(base64.b64encode(woff.read_bytes()).decode("ascii"))
    return tuple(result)
def start_svg(w,h,title,order,fontdata):
    manrope,cormorant=fontdata; c=CONFIG["colors"]
    css=f"""@font-face{{font-family:Manrope;src:url(data:font/woff;base64,{manrope}) format('woff');font-weight:100 900}}
@font-face{{font-family:Cormorant;src:url(data:font/woff;base64,{cormorant}) format('woff');font-weight:300 700}}
:root{{--bg:{c['bg']};--panel:{c['panel']};--violet:{c['violet']};--blue:{c['blue']};--white:{c['white']};--muted:{c['muted']}}}
text{{font-family:Manrope,Arial,sans-serif;fill:var(--white)}}
.serif{{font-family:Cormorant,Georgia,serif}}
.kicker{{font-size:15px;font-weight:800;letter-spacing:3px;fill:{c['cyan']}}}
.body{{font-size:22px;fill:{c['muted']}}}
.small{{font-size:16px;fill:{c['muted']}}}
.card{{opacity:1;animation:{'none' if STATIC else 'rise .9s cubic-bezier(.2,.75,.2,1) both'};animation-delay:{0 if STATIC else order*.34:.2f}s}}
.glow{{animation:{'none' if STATIC else 'breathe 7s ease-in-out infinite alternate'}}}
.sheen{{animation:{'none' if STATIC else 'sheen 8s ease-in-out infinite'}}}
@keyframes rise{{from{{opacity:0;transform:translateY(22px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes breathe{{from{{opacity:.22}}to{{opacity:.62}}}}
@keyframes sheen{{0%,100%{{opacity:.12}}50%{{opacity:.34}}}}
@media(prefers-reduced-motion:reduce){{.card,.glow,.sheen{{animation:none!important;opacity:1!important;transform:none!important}}.smil{{display:none!important}}}}
"""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title><style>{css}</style>
<defs>
 <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#111329"/><stop offset=".55" stop-color="#0B0D20"/><stop offset="1" stop-color="#1C1232"/></linearGradient>
 <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#B68AFF" stop-opacity=".8"/><stop offset=".48" stop-color="#777DFF" stop-opacity=".25"/><stop offset="1" stop-color="#75C8F5" stop-opacity=".72"/></linearGradient>
 <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#6738B8"/><stop offset=".52" stop-color="#9B6CFF"/><stop offset="1" stop-color="#527BFF"/></linearGradient>
 <filter id="blur"><feGaussianBlur stdDeviation="28"/></filter>
 <filter id="glass"><feGaussianBlur in="SourceAlpha" stdDeviation="3" result="blur"/><feSpecularLighting in="blur" surfaceScale="3" specularConstant=".35" specularExponent="18" lighting-color="#FFFFFF" result="spec"><fePointLight x="0" y="-100" z="180"/></feSpecularLighting><feComposite in="spec" in2="SourceAlpha" operator="in" result="shine"/><feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="shine"/></feMerge></filter>
</defs>
<rect width="{w}" height="{h}" rx="28" fill="url(#bg)"/>
<g class="card">
'''
def panel(x,y,w,h,rx=24):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#FFFFFF" fill-opacity=".045" stroke="url(#edge)" stroke-opacity=".56" stroke-width="1.5" filter="url(#glass)"/>'
def end_svg(): return "</g></svg>\n"
def write(name,s):
    CARDS.mkdir(parents=True,exist_ok=True); (CARDS/name).write_text(s+end_svg(),encoding="utf-8")
def hero(fd):
    s=start_svg(1100,330,"Tanya Pandey — computer science undergrad",0,fd)
    s+=f'''<ellipse class="glow" cx="930" cy="55" rx="205" ry="135" fill="#6535B7" opacity=".40" filter="url(#blur)"/>
<ellipse class="glow" cx="780" cy="325" rx="190" ry="90" fill="#3456C8" opacity=".25" filter="url(#blur)"/>
<path d="M710 0 C790 110 770 220 1100 260" fill="none" stroke="#9B6CFF" stroke-opacity=".2" stroke-width="1.5"/>
<text x="70" y="92" class="serif" font-size="91" font-weight="600" letter-spacing="-2" clip-path="url(#nameClip)">{esc(CONFIG['name'])}</text>
<defs><clipPath id="nameClip"><rect x="64" y="0" width="0" height="210">
<animate attributeName="width" values="0;660;660;0;0" keyTimes="0;.40;.58;.94;1" dur="6.8s" repeatCount="indefinite"/>
</rect></clipPath></defs>
<rect x="66" y="25" width="4" height="82" rx="2" fill="#D9C5FF">
<animate attributeName="x" values="66;710;710;66;66" keyTimes="0;.40;.58;.94;1" dur="6.8s" repeatCount="indefinite"/>
<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;.38;.40;.94;1" dur="6.8s" repeatCount="indefinite"/>
</rect>
<text x="74" y="158" font-size="25" font-weight="600" letter-spacing="2.2" fill="#D9D3F3">Computer science undergrad</text>
<text x="74" y="218" class="small">BMSCE  ·  COMPUTER SCIENCE</text>
<circle cx="935" cy="170" r="124" fill="none" stroke="#A77BFF" stroke-opacity=".25" stroke-width="1.2"/>
<circle cx="935" cy="170" r="98" fill="#FFFFFF" fill-opacity=".025" stroke="url(#edge)" stroke-opacity=".55"/>
<circle class="glow" cx="935" cy="170" r="74" fill="#7044B6" fill-opacity=".16" filter="url(#blur)"/>
<text x="935" y="197" text-anchor="middle" class="serif" font-size="72" fill="#E5D7FF">TP</text>
'''
    if CONFIG["portrait_url"]:
        s+=f'<circle cx="935" cy="170" r="74" fill="#111329"/><image href="{esc(CONFIG["portrait_url"])}" x="861" y="96" width="148" height="148" preserveAspectRatio="xMidYMid slice" clip-path="circle(74px at 935px 170px)"/>'
    write("v3-01-hero.svg",s)
def links(fd):
    tiles=[("github","GITHUB","Code & experiments","GH","#9B6CFF"),("linkedin","LINKEDIN","Let’s connect","in","#75C8F5"),("projects","PROJECTS","Things I’m building","↗","#D58AEF")]
    for slug,title,sub,mark,accent in tiles:
        s=start_svg(330,164,title,1,fd)
        s+=f'''<ellipse class="glow" cx="275" cy="10" rx="90" ry="70" fill="{accent}" opacity=".22" filter="url(#blur)"/>
{panel(3,3,324,158,22)}
<circle cx="58" cy="58" r="28" fill="{accent}" fill-opacity=".17" stroke="{accent}" stroke-opacity=".72"/>
<text x="58" y="67" text-anchor="middle" font-size="23" font-weight="800">{mark}</text>
<text x="30" y="116" font-size="20" font-weight="800" letter-spacing="1.5">{title}</text>
<text x="30" y="142" font-size="15" fill="#B3B2CE">{sub}</text>
<path d="M276 130 l18 0 l0 -18" fill="none" stroke="{accent}" stroke-width="2.2" stroke-linecap="round"/>
'''
        write(f"v3-02-{slug}.svg",s)
def analytics(data,fd):
    c=CONFIG["colors"]; months=data.get("months",[])[-12:]; months=[{"label":"—","count":0}]*(12-len(months))+months
    maximum=max([int(m.get("count",0)) for m in months]+[1])
    s=start_svg(1100,430,"Contribution activity and developer statistics",2,fd)
    s+=f'''<ellipse class="glow" cx="1000" cy="0" rx="170" ry="110" fill="#6738B8" opacity=".24" filter="url(#blur)"/>
{panel(2,2,1096,426,26)}
<text x="54" y="62" class="kicker">YOUR YEAR IN CODE</text>
<text x="50" y="119" class="serif" font-size="58">Small steps. Real momentum.</text>
<text x="56" y="171" font-size="16" font-weight="800" letter-spacing="2" fill="#B3B2CE">CONTRIBUTIONS PER MONTH</text>'''
    for i,m in enumerate(months):
        x=58+i*80; h=max(4,int(118*int(m.get("count",0))/maximum)); y=319-h
        s+=f'''<rect x="{x}" y="200" width="48" height="119" rx="10" fill="#FFFFFF" fill-opacity=".055"/>
<rect x="{x}" y="{y}" width="48" height="{h}" rx="10" fill="url(#accent)">
{"" if STATIC else f'<animate class="smil" attributeName="height" from="0" to="{h}" dur=".85s" begin="{.35+i*.07:.2f}s" fill="freeze"/><animate class="smil" attributeName="y" from="319" to="{y}" dur=".85s" begin="{.35+i*.07:.2f}s" fill="freeze"/>'}</rect>
<text x="{x+24}" y="348" text-anchor="middle" font-size="14" fill="#B3B2CE">{esc(m.get("label",""))}</text>'''
    metrics=[("CURRENT STREAK",f'{int(data.get("streak",0))} days'),("ACTIVE DAYS",str(int(data.get("active_days",0)))),("BUSIEST DAY",str(data.get("busiest_day","—")))]
    for i,(label,value) in enumerate(metrics):
        x=58+i*340
        s+=f'<text x="{x}" y="393" font-size="14" font-weight="800" letter-spacing="1.5" fill="#B3B2CE">{label}</text><text x="{x+190}" y="393" font-size="23" font-weight="800" fill="#F4F1FF">{esc(value)}</text>'
    write("v2-03-activity.svg",s)
def repo_card(repo,i,fd):
    accent=repo["accent"]; slug=re.sub("[^a-z0-9]+","-",repo["name"].lower()).strip("-")
    description=repo["description"]
    # Two deliberate lines keep descriptions clear and away from the project metadata.
    words=description.split(); lines=["",""]
    for word in words:
        target=0 if len(lines[0])+len(word)+1<=76 else 1
        lines[target]=(lines[target]+" "+word).strip()
    s=start_svg(1100,260,f'{repo["name"]} project',3+i,fd)
    s+=f'''<ellipse class="glow" cx="990" cy="40" rx="180" ry="120" fill="{accent}" opacity=".20" filter="url(#blur)"/>
{panel(2,2,1096,256,25)}
<text x="58" y="56" font-size="14" font-weight="800" letter-spacing="2.5" fill="#75C8F5">PROJECT  /  {repo["index"]}</text>
<text x="55" y="126" class="serif" font-size="59" font-weight="600">{esc(repo["name"])}</text>
<text x="60" y="171" font-size="19" fill="#D0CDE5">{esc(lines[0])}</text>
<text x="60" y="198" font-size="19" fill="#D0CDE5">{esc(lines[1])}</text>
<text x="60" y="235" font-size="15" font-weight="700" fill="#A9A6C8">{esc(repo["stack"])}</text>
'''
    write(f"v3-04-project-{i:02d}-{slug}.svg",s)
def contribution_graph(data,fd):
    weeks=data.get("weeks",[])
    s=start_svg(1100,300,"Animated GitHub contribution calendar",6,fd)
    s+=f'''<ellipse class="glow" cx="880" cy="35" rx="240" ry="120" fill="#5936B3" opacity=".22" filter="url(#blur)"/>
{panel(2,2,1096,296,25)}
<text x="55" y="60" class="kicker">GITHUB CONTRIBUTIONS</text>
<text x="52" y="112" class="serif" font-size="54">A year in squares.</text>
<text x="1040" y="68" text-anchor="end" font-size="17" font-weight="700" fill="#C6C0E4">{int(data.get("total_contributions",0)):,} contributions</text>'''
    if weeks:
        cell,gap,sx,sy=13,5,65,137
        fills=["#24243D","#49316F","#68439D","#8B5DCE","#B28BFF"]
        for wi,week in enumerate(weeks[-53:]):
            for day in week:
                wd=int(day.get("weekday",0)); count=int(day.get("count",0))
                level=0 if count==0 else 1 if count<3 else 2 if count<6 else 3 if count<10 else 4
                x=sx+wi*(cell+gap); y=sy+wd*(cell+gap)
                if STATIC:
                    s+=f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{fills[level]}"><title>{esc(day.get("date",""))}: {count} contributions</title></rect>'
                else:
                    delay=wi*.075+wd*.035
                    s+=f'''<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{fills[level]}" opacity=".08">
<title>{esc(day.get("date",""))}: {count} contributions</title>
<animate class="smil" attributeName="opacity" values=".08;1;.55;1" keyTimes="0;.18;.68;1" dur="6.2s" begin="{delay:.3f}s" repeatCount="indefinite"/>
</rect>'''
    else: s+='<text x="65" y="180" class="body">Contribution data will appear after the next refresh.</text>'
    write("v3-99-contributions.svg",s)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--refresh",action="store_true"); args=parser.parse_args()
    data=refresh_data() if args.refresh else read_data(); fd=fonts()
    CARDS.mkdir(parents=True,exist_ok=True)
    hero(fd); links(fd)
    for i,repo in enumerate(CONFIG["repos"],1): repo_card(repo,i,fd)
    contribution_graph(data,fd)
    print(f"Rendered {len(list(CARDS.glob('*.svg')))} SVG cards in {CARDS}")
    print("STATIC=1: animations disabled; final visual state rendered." if STATIC else "Animated glassmorphic SVGs rendered.")
if __name__=="__main__": main()
