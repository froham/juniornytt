import anthropic
import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── Konstantar ────────────────────────────────────────────────────────────────
SAKER_NAT  = 10
SAKER_LOK  = 10
SAKER_SPEL =  8

STD_LAT  = 62.3439
STD_LON  =  5.8467
STD_STAD = "Ulsteinvik"

# ── RSS-kjelder ───────────────────────────────────────────────────────────────
RSS_NASJONAL = [
    ("https://www.nrk.no/toppsaker.rss",   "NRK"),
    ("https://www.aftenposten.no/rss",     "Aftenposten"),
    ("https://www.vg.no/rss/feed/",        "VG"),
    ("https://www.tv2.no/rss/nyheter/",    "TV2"),
]
RSS_LOKAL = [
    ("https://www.smp.no/rss/",            "Sunnmørsposten"),
    ("https://www.vikebladet.no/rss/",     "Vikebladet"),
    ("https://www.vestlandsnytt.no/rss/",  "Vestlandsnytt"),
]
RSS_SPEL = [
    ("https://www.vg.no/rss/feed/?categories=sport",  "VG Sport"),
    ("https://www.nrk.no/sport/toppsaker.rss",        "NRK Sport"),
    ("https://www.eurogamer.net/feed",                "Eurogamer"),
    ("https://www.pcgamer.com/rss/",                  "PC Gamer"),
]

# ── Emoji-kart ────────────────────────────────────────────────────────────────
EMOJI_MAP = [
    (["krig","ukraina","russland","angrep","soldat","forsvar","nato"],        "⚔️"),
    (["fotball","sport","idrett","vm","em","lag","kamp","turnering"],         "⚽"),
    (["skole","elev","lærer","utdanning","barnehage","ungdom"],               "🏫"),
    (["klima","natur","miljø","skog","hav","dyr","fisk","storm"],             "🌿"),
    (["helse","sykehus","lege","sykdom","medisin","vaksine"],                 "🏥"),
    (["politikk","regjering","stortinget","statsminister","valg"],            "🏛️"),
    (["penger","økonomi","priser","strøm","rente","inflasjon","toll"],        "💰"),
    (["brann","ulykke","redning","politi","kriminalitet"],                    "🚒"),
    (["teknologi","ai","robot","data","internett","app"],                     "💻"),
    (["kultur","musikk","film","kunst","teater","konsert"],                   "🎭"),
    (["romfart","forskning","vitenskap","oppdagelse"],                        "🔭"),
    (["spel","game","gaming","roblox","minecraft","pokemon"],                 "🎮"),
    (["ski","svømming","friidrett","handball","basket","sykkel"],             "🏅"),
]

VÆR_SYMBOL = {
    "clearsky":"☀️","fair":"🌤️","partlycloudy":"⛅","cloudy":"☁️",
    "rainshowers":"🌦️","lightrainshowers":"🌦️","rain":"🌧️","lightrain":"🌧️",
    "heavyrain":"🌧️","sleet":"🌨️","lightsleet":"🌨️","sleetshowers":"🌨️",
    "snow":"❄️","lightsnow":"❄️","snowshowers":"🌨️","fog":"🌫️",
    "thunder":"⛈️","rainandthunder":"⛈️","lightrainandthunder":"⛈️",
    "heavyrainandthunder":"⛈️","rainshowersandthunder":"⛈️",
    "snowandthunder":"⛈️","sleetandthunder":"⛈️",
}

# ── Hjelpe-funksjonar ─────────────────────────────────────────────────────────
def velg_emoji(tittel, brodtekst=""):
    tekst = (tittel + " " + brodtekst).lower()
    for nokkelord, emoji in EMOJI_MAP:
        if any(o in tekst for o in nokkelord):
            return emoji
    return "📰"

def symbol_til_emoji(kode):
    base = re.sub(r"_(day|night|polartwilight)$", "", kode or "")
    return VÆR_SYMBOL.get(base, "🌡️")

def farevarsel(vind, base, nedbor):
    f = []
    if vind >= 15: f.append("💨🚨")
    if vind >= 25: f.append("🌀")
    if "thunder" in base: f.append("⚡")
    if nedbor >= 5: f.append("🌊")
    return " ".join(f)

# ── Vêr ───────────────────────────────────────────────────────────────────────
def hent_vaer():
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={STD_LAT:.4f}&lon={STD_LON:.4f}"
    req = urllib.request.Request(url, headers={"User-Agent": "JuniorNytt/1.0 github.com/froham/juniornytt"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        ts_list = data["properties"]["timeseries"]
        now = ts_list[0]["data"]
        temp  = round(now["instant"]["details"]["air_temperature"])
        vind  = round(now["instant"]["details"]["wind_speed"])
        sym   = now.get("next_1_hours", now.get("next_6_hours", {})).get("summary", {}).get("symbol_code", "")
        ndb   = now.get("next_1_hours", now.get("next_6_hours", {})).get("details", {}).get("precipitation_amount", 0)
        base  = re.sub(r"_(day|night|polartwilight)$", "", sym)
        dagar_map = defaultdict(list)
        for ts in ts_list:
            dato = ts["time"][:10]
            d = ts["data"]
            t = d["instant"]["details"].get("air_temperature")
            s = d.get("next_6_hours", d.get("next_1_hours", {})).get("summary", {}).get("symbol_code", "")
            n = d.get("next_6_hours", d.get("next_1_hours", {})).get("details", {}).get("precipitation_amount", 0)
            if t is not None:
                dagar_map[dato].append({"temp": t, "symbol": s, "nedbor": n or 0})
        ukedagar = ["Man","Tys","Ons","Tor","Fre","Lau","Sun"]
        today = datetime.now().strftime("%Y-%m-%d")
        dagar = []
        for dato, vals in sorted(dagar_map.items()):
            if dato == today or len(dagar) >= 4: continue
            symboler = [v["symbol"] for v in vals if v["symbol"]]
            sym_dag = symboler[len(symboler)//2] if symboler else ""
            base_dag = re.sub(r"_(day|night|polartwilight)$", "", sym_dag)
            mx = max(v["nedbor"] for v in vals)
            dagar.append({
                "dag":   ukedagar[datetime.strptime(dato, "%Y-%m-%d").weekday()],
                "min":   round(min(v["temp"] for v in vals)),
                "maks":  round(max(v["temp"] for v in vals)),
                "emoji": symbol_til_emoji(sym_dag),
                "fare":  "⚡" if "thunder" in base_dag else ("💨🚨" if mx > 10 else ""),
            })
        return {"temp": temp, "vind": vind, "symbol": symbol_til_emoji(sym),
                "fare": farevarsel(vind, base, ndb), "nedbor": round(ndb, 1), "dagar": dagar}
    except Exception as e:
        print(f"  Vêrfeil: {e}")
        return None

# ── RSS-henting ───────────────────────────────────────────────────────────────
def hent_rss(feeds, maks_per_kilde=6):
    artiklar = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JuniorNytt/1.0)"}
    for url, kilde in feeds:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                root = ET.fromstring(r.read())
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            for item in items[:maks_per_kilde]:
                tittel = (item.findtext("title") or
                          item.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
                desc   = (item.findtext("description") or
                          item.findtext("{http://www.w3.org/2005/Atom}summary") or
                          item.findtext("{http://www.w3.org/2005/Atom}content") or "").strip()
                desc = re.sub(r"<[^>]+>", "", desc).strip()
                if tittel:
                    artiklar.append({"kilde": kilde, "tittel": tittel, "ingress": desc[:300]})
        except Exception as e:
            print(f"  Kunne ikkje hente {kilde}: {e}")
    return artiklar

# ── Promptar ──────────────────────────────────────────────────────────────────
OMSKRIV_PROMPT = """Du er redaktør for JuniorNytt – ei nyhetsside for barn mellom 8 og 12 år.

Vel dei {antall} mest interessante og viktige sakene og skriv dei om til barnevenleg nynorsk i stilen til Sunnmøre-aviser (Vikebladet, Vestlandsnytt).

VIKTIG – prioriter saker om:
- Natur, dyr, miljø og klima
- Vitskap og teknologi
- Sport og idrett
- Politikk og samfunn (forklart enkelt)
- Lokale og nasjonale hendingar

VIKTIG – unngå eller ton ned:
- Drap, drapssaker og kriminalitet med mange detaljar
- Skremmande ulukker med grafiske detaljar
- Saker som er for tunge eller angstfremkallande for barn
- Viss ei sak om noko alvorleg MÅ vere med, skriv ho nøkternt utan skremmande detaljar

Reglar:
- Nynorsk: "ikkje", "òg", "kva", "dei", "ho", "heime", "skule"
- 6–9 setningar per sak, engasjerande og sakleg
- Viss ein kjend person vert nemnt, legg til ei kort forklaring i parentes første gong
- Ordforklaring (1–4 ord) for vanskelege omgrep
- Felt "emoji" med passande emoji
- Felt "land" med namn og flagg viss saka er frå eit anna land enn Noreg

Artiklar:
{artiklar}

Svar KUN med JSON-array:
[{{"tittel":"...","brodtekst":"...","kilde":"...","emoji":"...","ordforklaring":[{{"ord":"...","forklaring":"..."}}],"land":{{"namn":"...","flagg":"..."}}}}]"""

SPEL_PROMPT = """Du er redaktør for JuniorNytt si spel- og sportsseksjon for barn mellom 8 og 12 år.

Vel dei {antall} mest eigna sakene og skriv dei om til barnevenleg nynorsk. Ver entusiastisk!

PRIORITER saker om:
- Sport: fotball, ski, svømming, friidrett, handball – gjerne norske utøvarar
- Spel som passar for barn under 12 år: Minecraft, Roblox, Mario, Pokémon, Fortnite (berre barnevenleg innhald)
- Nye spel og oppdateringar for barn
- Esport for ungdom

FILTRER BORT:
- Spel med PEGI 16 eller 18 (vald, horror, krigsspel for vaksne)
- Saker som primært handlar om gambling eller pengebruk i spel
- Vaksent innhald

Reglar:
- Nynorsk Sunnmøre-stil: "ikkje", "òg", "kva", "dei"
- 4–6 setningar per sak
- Ordforklaring for spelordar og sportsuttrykk
- Felt "emoji" – spel- eller sportselemoji

Artiklar:
{artiklar}

Svar KUN med JSON-array:
[{{"tittel":"...","brodtekst":"...","kilde":"...","emoji":"...","ordforklaring":[{{"ord":"...","forklaring":"..."}}]}}]"""

# ── Omskriving ────────────────────────────────────────────────────────────────
def omskriv(artiklar, antall=8, retries=4, wait=60, prompt_mal=None):
    if not artiklar:
        return []
    if prompt_mal is None:
        prompt_mal = OMSKRIV_PROMPT
    tekst = "\n\n".join(f"[{a['kilde']}] {a['tittel']}\n{a['ingress']}" for a in artiklar)
    prompt = prompt_mal.format(antall=antall, artiklar=tekst)
    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5", max_tokens=6000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = resp.content[0].text.replace("```json","").replace("```","").strip()
            s, e = text.find("["), text.rfind("]")
            if s == -1:
                print(f"  Ingen JSON, prøver igjen...")
                continue
            saker = json.loads(text[s:e+1])
            ts = datetime.now().strftime("%H:%M")
            for sak in saker:
                sak["tidspunkt"] = ts
                if not sak.get("emoji"):
                    sak["emoji"] = velg_emoji(sak.get("tittel",""), sak.get("brodtekst",""))
            return saker
        except json.JSONDecodeError as je:
            print(f"  JSON-feil ({attempt+1}/{retries}): {je}")
            time.sleep(5)
        except anthropic.RateLimitError:
            if attempt < retries - 1:
                print(f"  Rate limit – ventar {wait}s...")
                time.sleep(wait)
            else:
                return []
    return []

# ── Duplikatfilter ────────────────────────────────────────────────────────────
def fjern_duplikatar(lokale, nasjonale, terskel=0.4):
    def nok(t):
        stop = {"og","i","er","på","en","et","de","det","som","til","av","for","med","at","har","om"}
        return {w.lower() for w in t.split() if w.lower() not in stop and len(w) > 2}
    nat_ord = [nok(s["tittel"]) for s in nasjonale]
    ut = []
    for sak in lokale:
        lok_ord = nok(sak["tittel"])
        for n in nat_ord:
            if lok_ord and n and len(lok_ord & n) / min(len(lok_ord), len(n)) >= terskel:
                print(f"  Duplikat: «{sak['tittel']}»")
                break
        else:
            ut.append(sak)
    return ut

# ── HTML-bygging ──────────────────────────────────────────────────────────────
COLORS  = ["#FEF9C3","#DBEAFE","#DCFCE7","#FCE7F3","#F3E8FF","#FFEDD5",
           "#FEF3C7","#E0F2FE","#F0FDF4","#FDF2F8","#F5F3FF","#FFF7ED",
           "#FEFCE8","#EFF6FF","#F0FDF4","#FDF4FF"]
BORDERS = ["#FDE047","#93C5FD","#86EFAC","#F9A8D4","#C4B5FD","#FCA5A1",
           "#FCD34D","#7DD3FC","#6EE7B7","#F0ABFC","#A78BFA","#FB923C",
           "#FACC15","#60A5FA","#34D399","#E879F9"]

def card(sak, idx):
    bg, border = COLORS[idx % len(COLORS)], BORDERS[idx % len(BORDERS)]
    emoji = sak.get("emoji") or velg_emoji(sak.get("tittel",""), sak.get("brodtekst",""))
    ts  = f'<span class="tidspunkt">🕐 {sak["tidspunkt"]}</span>' if sak.get("tidspunkt") else ""
    land = ""
    if sak.get("land") and sak["land"].get("namn"):
        land = f'<span class="land-badge">{sak["land"].get("flagg","")} {sak["land"]["namn"]}</span>'
    ordf = ""
    if sak.get("ordforklaring"):
        items = "".join(f'<div class="ord-item"><strong>{o["ord"]}:</strong> {o["forklaring"]}</div>'
                        for o in sak["ordforklaring"])
        ordf = f'<div class="ordbox"><div class="ord-title">📖 Visste du at…?</div>{items}</div>'
    return f'''<div class="card" style="background:{bg};border-color:{border}">
      <div class="card-meta">{ts}{land}</div>
      <div class="card-emoji">{emoji}</div>
      <h3>{sak["tittel"]}</h3>
      <p>{sak["brodtekst"]}</p>
      {ordf}
      <span class="kilde">📰 {sak["kilde"]}</span>
    </div>'''

def vaer_html(vaer):
    if not vaer: return ""
    dagar_html = "".join(f'''<div class="dag">
      <span class="dag-namn">{d['dag']}</span>
      <span class="dag-emoji">{d['emoji']}</span>
      {f'<span class="dag-fare">{d["fare"]}</span>' if d.get('fare') else ''}
      <span class="dag-temp"><span class="dag-maks">{d['maks']}°</span><span class="dag-min">{d['min']}°</span></span>
    </div>''' for d in vaer.get("dagar",[]))
    fare = f'<span class="no-fare">{vaer["fare"]}</span>' if vaer.get("fare") else ""
    return f'''<div class="vaer-boks">
      <div class="vaer-no">
        <span class="vaer-symbol">{vaer['symbol']}</span>
        <div class="vaer-detaljar">
          <span class="vaer-temp">{vaer['temp']}°C {fare}</span>
          <span class="vaer-vind">💨 {vaer['vind']} m/s · 🌧 {vaer['nedbor']} mm</span>
          <span class="vaer-sted">{STD_STAD}</span>
        </div>
      </div>
      <div class="vaer-dagar">{dagar_html}</div>
    </div>'''

def build_html(nasjonal, lokal, spel, vaer):
    ukedagar = ["Måndag","Tysdag","Onsdag","Torsdag","Fredag","Laurdag","Sundag"]
    ukedag = ukedagar[datetime.now().weekday()]
    dato = datetime.now().strftime("%-d. %B %Y").lower()
    nat_cards  = "".join(card(s,i) for i,s in enumerate(nasjonal))
    lok_cards  = "".join(card(s,i) for i,s in enumerate(lokal))
    spel_cards = "".join(card(s,i) for i,s in enumerate(spel))
    vaer_boks  = vaer_html(vaer)

    return f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JuniorNytt</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;background:linear-gradient(to bottom,#e0f2fe,#fff);min-height:100vh}}
  header{{background:linear-gradient(to right,#3b82f6,#06b6d4);color:white;padding:24px 16px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.2)}}
  header h1{{font-size:2.5rem;font-weight:900;letter-spacing:-1px}}
  .dato{{font-size:.85rem;opacity:.85;margin-top:4px}}
  .sub{{font-size:.8rem;opacity:.85;margin-top:4px;padding:0 12px}}
  .ki-merknad{{font-size:.7rem;opacity:.65;margin-top:4px;font-style:italic;padding:0 12px}}
  .oppdatert{{font-size:.7rem;opacity:.6;margin-top:6px}}
  .vaer-boks{{display:flex;flex-direction:column;gap:10px;max-width:720px;margin:16px auto 0;
    background:rgba(255,255,255,.15);border-radius:16px;padding:12px 20px}}
  .vaer-no{{display:flex;align-items:center;gap:12px}}
  .vaer-symbol{{font-size:2.8rem}}
  .vaer-detaljar{{display:flex;flex-direction:column;gap:2px}}
  .vaer-temp{{font-size:1.4rem;font-weight:800;display:flex;align-items:center;gap:6px}}
  .no-fare{{font-size:1rem}}
  .vaer-vind{{font-size:.75rem;opacity:.8}}
  .vaer-sted{{font-size:.72rem;opacity:.7;font-style:italic}}
  .vaer-dagar{{display:flex;gap:8px;justify-content:space-around;border-top:1px solid rgba(255,255,255,.2);padding-top:10px}}
  .dag{{display:flex;flex-direction:column;align-items:center;gap:2px;flex:1}}
  .dag-namn{{font-size:.72rem;font-weight:700;opacity:.85;text-transform:uppercase}}
  .dag-emoji{{font-size:1.5rem}}
  .dag-fare{{font-size:.7rem}}
  .dag-temp{{display:flex;gap:4px;align-items:baseline}}
  .dag-maks{{font-size:.9rem;font-weight:800}}
  .dag-min{{font-size:.78rem;opacity:.65}}
  .tabs{{display:flex;max-width:720px;margin:20px auto 0;padding:0 16px;border-radius:16px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
  .tab{{flex:1;padding:12px 4px;font-weight:700;font-size:.8rem;border:none;cursor:pointer;transition:.2s;display:flex;align-items:center;justify-content:center;gap:6px}}
  .tab-nat{{background:#3b82f6;color:white}}
  .tab-nat.inactive{{background:white;color:#6b7280}}.tab-nat.inactive:hover{{background:#eff6ff}}
  .tab-lok{{background:#10b981;color:white}}
  .tab-lok.inactive{{background:white;color:#6b7280}}.tab-lok.inactive:hover{{background:#f0fdf4}}
  .tab-spel{{background:#8b5cf6;color:white}}
  .tab-spel.inactive{{background:white;color:#6b7280}}.tab-spel.inactive:hover{{background:#f5f3ff}}
  .badge{{background:rgba(255,255,255,.3);border-radius:99px;padding:2px 7px;font-size:.68rem}}
  .inactive .badge{{background:#e5e7eb;color:#6b7280}}
  .sources{{max-width:720px;margin:6px auto 0;padding:0 20px;font-size:.72rem;color:#9ca3af}}
  .varsel-boks{{max-width:720px;margin:8px auto 0;padding:10px 20px;border-radius:12px;font-size:.78rem;line-height:1.5;display:none;background:#fef3c7;border:1px solid #fde047;color:#92400e}}
  main{{max-width:720px;margin:0 auto;padding:16px}}
  .panel{{display:none}}.panel.active{{display:block}}
  .card{{border-radius:16px;border:2px solid;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
  .card-meta{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
  .tidspunkt{{font-size:.7rem;color:#9ca3af}}
  .land-badge{{font-size:.72rem;font-weight:600;background:rgba(255,255,255,.6);border:1px solid #e5e7eb;border-radius:99px;padding:2px 10px}}
  .card-emoji{{font-size:2rem;margin-bottom:8px}}
  .card h3{{font-size:1.15rem;font-weight:800;color:#1f2937;margin-bottom:10px;line-height:1.3}}
  .card p{{font-size:.9rem;color:#374151;line-height:1.7;margin-bottom:12px}}
  .ordbox{{background:rgba(255,255,255,.7);border:1px solid #e5e7eb;border-radius:12px;padding:12px;margin-bottom:12px}}
  .ord-title{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af;margin-bottom:8px}}
  .ord-item{{font-size:.85rem;color:#374151;margin-bottom:4px}}
  .ord-item strong{{color:#1f2937}}
  .kilde{{font-size:.72rem;font-weight:600;color:#6b7280;background:white;padding:4px 12px;border-radius:99px;border:1px solid #e5e7eb}}
  footer{{text-align:center;font-size:.72rem;color:#9ca3af;padding:24px 16px;line-height:1.8}}
  @media(max-width:480px){{header h1{{font-size:2rem}}}}
</style>
<script>
  const SRC = {{
    nasjonal: "Kjelder: NRK · Aftenposten · VG · TV2",
    lokal:    "Kjelder: Vikebladet · Vestlandsnytt · Sunnmørsposten",
    spel:     "Kjelder: VG Sport · Eurogamer · PC Gamer · Rock Paper Shotgun"
  }};
  function show(tab) {{
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.getElementById("panel-" + tab).classList.add("active");
    document.querySelectorAll(".tab").forEach(t => t.classList.add("inactive"));
    document.getElementById("tab-" + tab).classList.remove("inactive");
    document.getElementById("src-line").textContent = SRC[tab] || "";
    document.getElementById("varsel-spel").style.display = tab === "spel" ? "block" : "none";
  }}
</script>
</head>
<body>
<header>
  <div style="font-size:2.5rem">📰</div>
  <h1>JuniorNytt</h1>
  <div class="dato">{ukedag} {dato}</div>
  <div class="sub">Nyhende på nynorsk for deg mellom 8 og 12 år – nye saker vert publisert kl. 07.00, 12.00 og 19.00 kvar dag.</div>
  <div class="ki-merknad">Sida nyttar KI og skrivefeil kan førekomme. JuniorNytt er ikkje tilknytt eller sponsa av nokon av kjeldene som er omtala.</div>
  <div class="oppdatert">Oppdatert kl. {datetime.now().strftime("%H:%M")}</div>
  {vaer_boks}
</header>

<div class="tabs">
  <button class="tab tab-nat" id="tab-nasjonal" onclick="show('nasjonal')">🇳🇴 Nasjonalt <span class="badge">{len(nasjonal)}</span></button>
  <button class="tab tab-lok inactive" id="tab-lokal" onclick="show('lokal')">📍 Lokalt <span class="badge">{len(lokal)}</span></button>
  <button class="tab tab-spel inactive" id="tab-spel" onclick="show('spel')">🎮 Spel & Sport <span class="badge">{len(spel)}</span></button>
</div>

<div class="sources" id="src-line">Kjelder: NRK · Aftenposten · VG · TV2</div>
<div class="varsel-boks" id="varsel-spel">⚠️ I spel der du kan møte framande på nett – hugs å aldri dele personleg informasjon, og fortel alltid ein vaksen viss nokon oppfører seg rart.</div>

<main>
  <div class="panel active" id="panel-nasjonal">{nat_cards}</div>
  <div class="panel" id="panel-lokal">{lok_cards}</div>
  <div class="panel" id="panel-spel">{spel_cards}</div>
</main>

<footer>
  JuniorNytt • Laga for nysgjerrige barn 🌟<br>
  © 2026 JuniorNytt – Innhald er utvalt, tilpassa og omskrive frå opne nyheitskjelder av kunstig intelligens.<br>
  JuniorNytt omtalar spel og tenester som informasjon, og dette er ikkje å rekne som ei tilråding eller eit samarbeid.<br>
  Foreldre oppfordrast til å følgje med på kva spel barna nyttar.
</footer>
</body>
</html>"""

# ── Hovudprogram ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    now = datetime.now()
    print(f"Køyring kl. {now.strftime('%H:%M')}")

    print(f"Hentar vêr for {STD_STAD}...")
    vaer = hent_vaer()

    print("Hentar RSS – nasjonalt...")
    nat_rss = hent_rss(RSS_NASJONAL)
    print(f"  → {len(nat_rss)} artiklar")
    print("Skriv om nasjonale nyhende...")
    nasjonal = omskriv(nat_rss, antall=SAKER_NAT) or omskriv(nat_rss[:12], antall=6)
    nasjonal = (nasjonal or [])[:SAKER_NAT]
    print(f"  → {len(nasjonal)} saker")

    print("Hentar RSS – lokalt...")
    lok_rss = hent_rss(RSS_LOKAL)
    print(f"  → {len(lok_rss)} artiklar")
    print("Skriv om lokale nyhende...")
    lokal = omskriv(lok_rss, antall=SAKER_LOK) or omskriv(lok_rss[:12], antall=6)
    lokal = fjern_duplikatar(lokal or [], nasjonal or [])[:SAKER_LOK]
    print(f"  → {len(lokal)} saker")

    print("Hentar RSS – spel & sport...")
    spel_rss = hent_rss(RSS_SPEL, maks_per_kilde=5)
    print(f"  → {len(spel_rss)} artiklar")
    print("Skriv om spel & sport...")
    spel = omskriv(spel_rss, antall=SAKER_SPEL, prompt_mal=SPEL_PROMPT) or []
    spel = spel[:SAKER_SPEL]
    print(f"  → {len(spel)} saker")

    html = build_html(nasjonal, lokal, spel, vaer)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ docs/index.html er oppdatert!")
