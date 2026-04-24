import anthropic
import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MAKS_SAKER    = 20
NYE_PER_RUNDE = 10
FALLER_UT     =  5
BUFFER        =  3

SAKER_FIL_NAT  = "docs/saker_nasjonal.json"
SAKER_FIL_LOK  = "docs/saker_lokal.json"
SAKER_FIL_SPEL = "docs/saker_spel.json"
MAKS_SPEL      = 12
NYE_SPEL       =  8

STD_LAT  = 62.3439
STD_LON  =  5.8467
STD_STAD = "Ulsteinvik"

RSS_NASJONAL = [
    ("https://www.nrk.no/toppsaker.rss",          "NRK"),
    ("https://www.nrk.no/moreogromsdal/rss.xml",   "NRK Møre og Romsdal"),
    ("https://www.aftenposten.no/rss",             "Aftenposten"),
    ("https://www.vg.no/rss/feed/",                "VG"),
    ("https://www.dagbladet.no/rss",               "Dagbladet"),
]
RSS_LOKAL = [
    ("https://www.smp.no/rss/",                    "Sunnmørsposten"),
    ("https://www.vikebladet.no/rss/",             "Vikebladet"),
    ("https://www.vestlandsnytt.no/rss/",          "Vestlandsnytt"),
]
RSS_SPEL = [
    ("https://blog.roblox.com/feed/",              "Roblox"),
    ("https://www.minecraft.net/en-us/feeds/community-content.atom", "Minecraft"),
    ("https://blog.playstation.com/feed/",         "PlayStation"),
    ("https://news.xbox.com/en-us/feed/",          "Xbox"),
    ("https://www.nintendo.com/en-US/feed.rss",    "Nintendo"),
    ("https://www.pokemon.com/us/pokemon-news/rss","Pokémon"),
    ("https://www.nrk.no/sport/rss.xml",           "NRK Sport"),
]

EMOJI_MAP = [
    (["krig","ukraina","russland","angrep","soldat","forsvar","nato","våpen"], "⚔️"),
    (["fotball","sport","idrett","vm","em","lag","kamp","turnering","mål"],   "⚽"),
    (["skole","elev","lærer","utdanning","barnehage","ungdom","barn"],        "🏫"),
    (["klima","natur","miljø","skog","hav","dyr","fisk","vær","snø","storm"], "🌿"),
    (["helse","sykehus","lege","sykdom","medisin","vaksine","virus"],         "🏥"),
    (["politikk","regjering","stortinget","statsminister","valg","parti"],    "🏛️"),
    (["penger","økonomi","priser","strøm","rente","inflasjon","toll"],        "💰"),
    (["brann","ulykke","redning","politi","kriminalitet","ran"],              "🚒"),
    (["teknologi","ai","robot","data","internett","app"],                     "💻"),
    (["kultur","musikk","film","kunst","teater","konsert"],                   "🎭"),
    (["romfart","forskning","vitenskap","oppdagelse"],                        "🔭"),
    (["mat","restaurant","landbruk","jordbruk"],                              "🍽️"),
    (["roblox","minecraft","pokemon","playstation","xbox","nintendo","spel","game","gaming"], "🎮"),
    (["fotball","basketball","ski","svømming","friidrett","sport","idrett"],  "🏅"),
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

def velg_emoji(tittel, brodtekst=""):
    tekst = (tittel + " " + brodtekst).lower()
    for nokkelord, emoji in EMOJI_MAP:
        if any(o in tekst for o in nokkelord):
            return emoji
    return "📰"

def symbol_til_emoji(symbol_code):
    base = re.sub(r"_(day|night|polartwilight)$", "", symbol_code or "")
    return VÆR_SYMBOL.get(base, "🌡️")

def farevarsel(vind, symbol_base, nedbor):
    farar = []
    if vind >= 15: farar.append("💨🚨")
    if vind >= 25: farar.append("🌀")
    if "thunder" in symbol_base: farar.append("⚡")
    if nedbor >= 5: farar.append("🌊")
    return " ".join(farar)

def hent_vaer(lat=STD_LAT, lon=STD_LON):
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat:.4f}&lon={lon:.4f}"
    req = urllib.request.Request(url, headers={"User-Agent": "JuniorNytt/1.0 github.com/froham/juniornytt"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        ts_list = data["properties"]["timeseries"]
        now = ts_list[0]["data"]
        temp_no = round(now["instant"]["details"]["air_temperature"])
        vind_no = round(now["instant"]["details"]["wind_speed"])
        symbol_no = now.get("next_1_hours", now.get("next_6_hours", {})).get("summary", {}).get("symbol_code", "")
        nedbor_no = now.get("next_1_hours", now.get("next_6_hours", {})).get("details", {}).get("precipitation_amount", 0)
        base_no = re.sub(r"_(day|night|polartwilight)$", "", symbol_no)
        from collections import defaultdict
        dagar = defaultdict(list)
        for ts in ts_list:
            dato = ts["time"][:10]
            d = ts["data"]
            temp = d["instant"]["details"].get("air_temperature")
            symbol = d.get("next_6_hours", d.get("next_1_hours", {})).get("summary", {}).get("symbol_code", "")
            nedbor = d.get("next_6_hours", d.get("next_1_hours", {})).get("details", {}).get("precipitation_amount", 0)
            if temp is not None:
                dagar[dato].append({"temp": temp, "symbol": symbol, "nedbor": nedbor or 0})
        dag_prognose = []
        ukedagar_no = ["Man","Tys","Ons","Tor","Fre","Lau","Sun"]
        today_str = datetime.now().strftime("%Y-%m-%d")
        for dato, vals in sorted(dagar.items()):
            if dato == today_str: continue
            if len(dag_prognose) >= 4: break
            temps = [v["temp"] for v in vals]
            symboler = [v["symbol"] for v in vals if v["symbol"]]
            maks_nedbor = max(v["nedbor"] for v in vals)
            symbol_dag = symboler[len(symboler)//2] if symboler else ""
            base_dag = re.sub(r"_(day|night|polartwilight)$", "", symbol_dag)
            ukedag_idx = datetime.strptime(dato, "%Y-%m-%d").weekday()
            dag_prognose.append({
                "dag": ukedagar_no[ukedag_idx],
                "min": round(min(temps)),
                "maks": round(max(temps)),
                "emoji": symbol_til_emoji(symbol_dag),
                "fare": "⚡" if "thunder" in base_dag else ("💨🚨" if maks_nedbor > 10 else ""),
            })
        return {
            "temp": temp_no, "vind": vind_no,
            "symbol": symbol_til_emoji(symbol_no),
            "fare": farevarsel(vind_no, base_no, nedbor_no),
            "nedbor": round(nedbor_no, 1),
            "dagar": dag_prognose,
        }
    except Exception as e:
        print(f"  Kunne ikkje hente vêr: {e}")
        return None

def hent_rss(feeds, maks_per_kilde=6):
    artiklar = []
    headers = {"User-Agent": "JuniorNytt/1.0"}
    for url, kilde in feeds:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                root = ET.fromstring(r.read())
            items = root.findall(".//item")
            if not items:
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            items = items[:maks_per_kilde]
            for item in items:
                tittel = (item.findtext("title") or
                          item.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
                desc = (item.findtext("description") or
                        item.findtext("{http://www.w3.org/2005/Atom}summary") or
                        item.findtext("{http://www.w3.org/2005/Atom}content") or "").strip()
                desc = re.sub(r"<[^>]+>", "", desc).strip()
                if tittel:
                    artiklar.append({"kilde": kilde, "tittel": tittel, "ingress": desc[:300]})
        except Exception as e:
            print(f"  Kunne ikkje hente {kilde}: {e}")
    return artiklar


OMSKRIV_PROMPT = """Du er redaktør for JuniorNytt – ei nyhetsside for barn mellom 8 og 12 år.

Her er nyhetsartiklar frå norske medium. Vel dei {antall} mest interessante og viktige sakene (ingen kjendisnyheiter/underhaldningssladder), og skriv dei om til eit barnevenleg språk.

Språkregler – SVÆRT VIKTIG:
- Skriv på nynorsk i stilen til Sunnmøre/Romsdal-aviser som Vikebladet og Vestlandsnytt
- Bruk typiske former: "ikkje", "òg", "kva", "dei", "ho", "me/vi", "heime", "skule"
- Enkle ord og korte setningar tilpassa 8–12-åringar
- 6–9 setningar per sak – engasjerande men sakleg
- Legg til ordforklaring (1–4 ord) for vanskelege omgrep
- Bruk kjeldenamnet frå artikkelen
- Legg til eitt felt "emoji" med éin passande emoji for saka
- Viss saka handlar om noko i eit anna land enn Noreg, legg til feltet "land" med landsnamn og flagg-emoji. Ikkje legg til "land" for saker berre om Noreg.

Artiklar:
{artiklar}

Svar KUN med JSON-array, ingen annan tekst:
[{{"tittel":"...","brodtekst":"...","kilde":"...","emoji":"...","ordforklaring":[{{"ord":"...","forklaring":"..."}}],"land":{{"namn":"...","flagg":"..."}}}}]"""

SPEL_PROMPT = """Du er redaktør for JuniorNytt si spel- og sportsseksjon for barn mellom 8 og 12 år.

Her er artiklar frå spelverda og sporten. Vel dei {antall} mest interessante sakene og skriv dei om til barnevenleg nynorsk.

Språkregler:
- Skriv på nynorsk (Sunnmøre-stil): "ikkje", "òg", "kva", "dei", "ho"
- Enkle ord og korte setningar for 8–12-åringar
- 4–6 setningar per sak – entusiastisk og engasjerande
- Legg til ordforklaring for vanskelege omgrep (spelordar, sportsuttrykk o.l.)
- Bruk kjeldenamnet frå artikkelen
- Legg til eitt felt "emoji" – bruk spel- eller sportselemoji

Artiklar:
{artiklar}

Svar KUN med JSON-array, ingen annan tekst:
[{{"tittel":"...","brodtekst":"...","kilde":"...","emoji":"...","ordforklaring":[{{"ord":"...","forklaring":"..."}}]}}]"""


def omskriv(artiklar, antall=8, retries=4, wait=60, prompt_mal=None):
    if prompt_mal is None:
        prompt_mal = OMSKRIV_PROMPT
    tekst = "\n\n".join(f"[{a['kilde']}] {a['tittel']}\n{a['ingress']}" for a in artiklar)
    prompt = prompt_mal.format(antall=antall, artiklar=tekst)
    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = resp.content[0].text
            text = text.replace("```json", "").replace("```", "").strip()
            s, e = text.find("["), text.rfind("]")
            if s == -1: return []
            saker = json.loads(text[s:e+1])
            ts = datetime.now().strftime("%H:%M")
            for sak in saker:
                sak["tidspunkt"] = ts
                if not sak.get("emoji"):
                    sak["emoji"] = velg_emoji(sak["tittel"], sak.get("brodtekst", ""))
            return saker
        except anthropic.RateLimitError:
            if attempt < retries - 1:
                print(f"  Rate limit – ventar {wait}s ({attempt+1}/{retries})...")
                time.sleep(wait)
            else:
                print("  Ga opp etter maks forsøk.")
                return []


def fjern_duplikatar(lokale, nasjonale, terskel=0.4):
    def nokkelord(tittel):
        stopord = {"og","i","er","på","en","et","de","det","som","til","av","for","med","at","har","om"}
        return {w.lower() for w in tittel.split() if w.lower() not in stopord and len(w) > 2}
    nat_ord = [nokkelord(s["tittel"]) for s in nasjonale]
    filtrerte = []
    for sak in lokale:
        lok_ord = nokkelord(sak["tittel"])
        for n_ord in nat_ord:
            if not lok_ord or not n_ord: continue
            overlapp = len(lok_ord & n_ord) / min(len(lok_ord), len(n_ord))
            if overlapp >= terskel:
                print(f"  Duplikat fjerna: «{sak['tittel']}»")
                break
        else:
            filtrerte.append(sak)
    return filtrerte


def oppdater_saker(nye, fil, er_morgen, maks=None, faller_ut=None):
    if maks is None: maks = MAKS_SAKER
    if faller_ut is None: faller_ut = FALLER_UT
    eksisterande = []
    if not er_morgen and os.path.exists(fil):
        try:
            with open(fil, encoding="utf-8") as f:
                eksisterande = json.load(f)
        except Exception:
            eksisterande = []
    eksist_titlar = {s["tittel"].lower() for s in eksisterande}
    nye_unike = [s for s in nye if s["tittel"].lower() not in eksist_titlar]
    kombinert = nye_unike + eksisterande
    if not er_morgen and len(kombinert) >= faller_ut:
        kombinert = kombinert[:-faller_ut]
    kombinert = kombinert[:maks]
    os.makedirs("docs", exist_ok=True)
    with open(fil, "w", encoding="utf-8") as f:
        json.dump(kombinert, f, ensure_ascii=False, indent=2)
    return kombinert


def vaer_html(vaer):
    if not vaer: return ""
    dagar_html = ""
    for d in vaer.get("dagar", []):
        dagar_html += f"""<div class="dag">
          <span class="dag-namn">{d['dag']}</span>
          <span class="dag-emoji">{d['emoji']}</span>
          {f'<span class="dag-fare">{d["fare"]}</span>' if d.get('fare') else ''}
          <span class="dag-temp"><span class="dag-maks">{d['maks']}°</span><span class="dag-min">{d['min']}°</span></span>
        </div>"""
    fare_html = f'<span class="no-fare">{vaer["fare"]}</span>' if vaer.get("fare") else ""
    return f"""<div class="vaer-boks">
      <div class="vaer-no">
        <span class="vaer-symbol">{vaer['symbol']}</span>
        <div class="vaer-detaljar">
          <span class="vaer-temp">{vaer['temp']}°C {fare_html}</span>
          <span class="vaer-vind">💨 {vaer['vind']} m/s · 🌧 {vaer['nedbor']} mm</span>
          <span class="vaer-sted">{STD_STAD}</span>
        </div>
      </div>
      <div class="vaer-dagar">{dagar_html}</div>
    </div>"""


def card(sak, idx, er_spel=False):
    colors  = ["#FEF9C3","#DBEAFE","#DCFCE7","#FCE7F3","#F3E8FF","#FFEDD5",
               "#FEF3C7","#E0F2FE","#F0FDF4","#FDF2F8","#F5F3FF","#FFF7ED",
               "#FEFCE8","#EFF6FF","#F0FDF4","#FDF4FF"]
    borders = ["#FDE047","#93C5FD","#86EFAC","#F9A8D4","#C4B5FD","#FCA5A1",
               "#FCD34D","#7DD3FC","#6EE7B7","#F0ABFC","#A78BFA","#FB923C",
               "#FACC15","#60A5FA","#34D399","#E879F9"]
    bg, border = colors[idx % len(colors)], borders[idx % len(borders)]
    emoji = sak.get("emoji") or velg_emoji(sak.get("tittel",""), sak.get("brodtekst",""))
    ts_html = f'<span class="tidspunkt">🕐 {sak["tidspunkt"]}</span>' if sak.get("tidspunkt") else ""
    land_html = ""
    if sak.get("land") and sak["land"].get("namn"):
        land_html = f'<span class="land-badge">{sak["land"].get("flagg","")} {sak["land"]["namn"]}</span>'
    forklaringar = ""
    if sak.get("ordforklaring"):
        items = "".join(
            f'<div class="ord-item"><strong>{o["ord"]}:</strong> {o["forklaring"]}</div>'
            for o in sak["ordforklaring"]
        )
        forklaringar = f'<div class="ordbox"><div class="ord-title">📖 Visste du at…?</div>{items}</div>'
    return f'''<div class="card" style="background:{bg};border-color:{border}">
      <div class="card-meta">{ts_html}{land_html}</div>
      <div class="card-emoji">{emoji}</div>
      <h3>{sak["tittel"]}</h3>
      <p>{sak["brodtekst"]}</p>
      {forklaringar}
      <span class="kilde">📰 {sak["kilde"]}</span>
    </div>'''


def build_html(nasjonal, lokal, spel, vaer):
    ukedagar = ["Måndag","Tysdag","Onsdag","Torsdag","Fredag","Laurdag","Sundag"]
    ukedag = ukedagar[datetime.now().weekday()]
    dato = datetime.now().strftime("%-d. %B %Y").lower()
    nat_cards  = "".join(card(s, i) for i, s in enumerate(nasjonal))
    lok_cards  = "".join(card(s, i) for i, s in enumerate(lokal))
    spel_cards = "".join(card(s, i, er_spel=True) for i, s in enumerate(spel))
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
  .ki-merknad{{font-size:.7rem;opacity:.65;margin-top:4px;font-style:italic}}
  .oppdatert{{font-size:.7rem;opacity:.6;margin-top:6px}}
  .vaer-boks{{display:flex;flex-direction:column;gap:10px;max-width:720px;margin:16px auto 0;
    background:rgba(255,255,255,.15);border-radius:16px;padding:12px 20px;backdrop-filter:blur(4px)}}
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
  .tab{{flex:1;padding:10px 4px;font-weight:700;font-size:.78rem;border:none;cursor:pointer;transition:.2s;display:flex;align-items:center;justify-content:center;gap:6px}}
  .tab-nat{{background:#3b82f6;color:white}}
  .tab-nat.inactive{{background:white;color:#6b7280}}.tab-nat.inactive:hover{{background:#eff6ff}}
  .tab-lok{{background:#10b981;color:white}}
  .tab-lok.inactive{{background:white;color:#6b7280}}.tab-lok.inactive:hover{{background:#f0fdf4}}
  .tab-spel{{background:#8b5cf6;color:white}}
  .tab-spel.inactive{{background:white;color:#6b7280}}.tab-spel.inactive:hover{{background:#f5f3ff}}
  .badge{{background:rgba(255,255,255,.3);border-radius:99px;padding:2px 7px;font-size:.68rem}}
  .inactive .badge{{background:#e5e7eb;color:#6b7280}}
  .sources{{max-width:720px;margin:6px auto 0;padding:0 20px;font-size:.72rem;color:#9ca3af}}
  .spel-varsel{{max-width:720px;margin:8px auto 0;padding:10px 20px;
    background:#fef3c7;border:1px solid #fde047;border-radius:12px;
    font-size:.78rem;color:#92400e;line-height:1.5}}
  main{{max-width:720px;margin:0 auto;padding:16px}}
  .panel{{display:none}}.panel.active{{display:block}}
  .card{{border-radius:16px;border:2px solid;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
  .card-meta{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:8px}}
  .tidspunkt{{font-size:.7rem;color:#9ca3af}}
  .land-badge{{font-size:.72rem;font-weight:600;background:rgba(255,255,255,.6);
    border:1px solid #e5e7eb;border-radius:99px;padding:2px 10px}}
  .card-emoji{{font-size:2rem;margin-bottom:8px}}
  .card h3{{font-size:1.15rem;font-weight:800;color:#1f2937;margin-bottom:10px;line-height:1.3}}
  .card p{{font-size:.9rem;color:#374151;line-height:1.7;margin-bottom:12px}}
  .ordbox{{background:rgba(255,255,255,.7);border:1px solid #e5e7eb;border-radius:12px;padding:12px;margin-bottom:12px}}
  .ord-title{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af;margin-bottom:8px}}
  .ord-item{{font-size:.85rem;color:#374151;margin-bottom:4px}}
  .ord-item strong{{color:#1f2937}}
  .kilde{{font-size:.72rem;font-weight:600;color:#6b7280;background:white;padding:4px 12px;border-radius:99px;border:1px solid #e5e7eb}}
  footer{{text-align:center;font-size:.72rem;color:#9ca3af;padding:24px 16px;line-height:1.8}}
  @media(max-width:480px){{header h1{{font-size:2rem}}.vaer-boks{{flex-wrap:wrap}}}}
</style>
<script>
  function show(tab) {{
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.getElementById("panel-" + tab).classList.add("active");
    document.querySelectorAll(".tab").forEach(t => t.classList.add("inactive"));
    document.getElementById("tab-" + tab).classList.remove("inactive");
    const src = {{
      nasjonal: "Kjelder: NRK · NRK Møre og Romsdal · Aftenposten · VG · Dagbladet",
      lokal:    "Kjelder: Vikebladet · Vestlandsnytt · Sunnmørsposten",
      spel:     "Kjelder: Roblox · Minecraft · PlayStation · Xbox · Nintendo · Pokémon · NRK Sport"
    }};
    document.getElementById("src-line").textContent = src[tab] || "";
    document.getElementById("spel-varsel").style.display = tab === "spel" ? "block" : "none";
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
  <button class="tab tab-nat" id="tab-nasjonal" onclick="show('nasjonal')">
    🇳🇴 Nasjonalt <span class="badge">{len(nasjonal)}</span>
  </button>
  <button class="tab tab-lok inactive" id="tab-lokal" onclick="show('lokal')">
    📍 Lokalt <span class="badge">{len(lokal)}</span>
  </button>
  <button class="tab tab-spel inactive" id="tab-spel" onclick="show('spel')">
    🎮 Spel & Sport <span class="badge">{len(spel)}</span>
  </button>
</div>

<div class="sources" id="src-line">Kjelder: NRK · NRK Møre og Romsdal · Aftenposten · VG · Dagbladet</div>

<div class="spel-varsel" id="spel-varsel" style="display:none">
  ⚠️ I spel der du kan møte framande på nett – hugs å aldri dele personleg informasjon, og fortel alltid ein vaksen viss nokon oppfører seg rart.
</div>

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


if __name__ == "__main__":
    time_now = datetime.now()
    er_morgen = time_now.hour < 9
    er_middag = 9 <= time_now.hour < 14

    print(f"Kjøring kl. {time_now.strftime('%H:%M')} – {'morgen (nullstiller)' if er_morgen else 'oppdatering'}")

    print(f"Hentar vêr for {STD_STAD}...")
    vaer = hent_vaer()

    print("Hentar RSS – nasjonalt...")
    nat_rss = hent_rss(RSS_NASJONAL, maks_per_kilde=6)
    print(f"  → {len(nat_rss)} artiklar")
    print("Skriv om nasjonale nyhende...")
    nye_nat = omskriv(nat_rss, antall=NYE_PER_RUNDE + BUFFER)
    nasjonal = oppdater_saker(nye_nat[:NYE_PER_RUNDE], SAKER_FIL_NAT, er_morgen)
    print(f"  → {len(nasjonal)} saker totalt")

    print("Hentar RSS – lokalt...")
    lok_rss = hent_rss(RSS_LOKAL, maks_per_kilde=6)
    print(f"  → {len(lok_rss)} artiklar")
    print("Skriv om lokale nyhende...")
    nye_lok = omskriv(lok_rss, antall=NYE_PER_RUNDE + BUFFER)
    print("Sjekkar duplikatar...")
    nye_lok = fjern_duplikatar(nye_lok, nye_nat)
    lokal = oppdater_saker(nye_lok[:NYE_PER_RUNDE], SAKER_FIL_LOK, er_morgen)
    print(f"  → {len(lokal)} saker totalt")

    # Spel & Sport: berre oppdater kl. 12 (middag) eller morgen
    if er_morgen or er_middag:
        print("Hentar RSS – spel & sport...")
        spel_rss = hent_rss(RSS_SPEL, maks_per_kilde=4)
        print(f"  → {len(spel_rss)} artiklar")
        print("Skriv om spel & sport...")
        nye_spel = omskriv(spel_rss, antall=NYE_SPEL, prompt_mal=SPEL_PROMPT)
        spel = oppdater_saker(nye_spel, SAKER_FIL_SPEL, er_morgen,
                              maks=MAKS_SPEL, faller_ut=4)
        print(f"  → {len(spel)} saker totalt")
    else:
        # Kl. 19: last inn eksisterande spelsaker utan å oppdatere
        spel = []
        if os.path.exists(SAKER_FIL_SPEL):
            with open(SAKER_FIL_SPEL, encoding="utf-8") as f:
                spel = json.load(f)
        print(f"  → Spel ikkje oppdatert (kl. 19-køyring), brukar {len(spel)} eksisterande saker")

    html = build_html(nasjonal, lokal, spel, vaer)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ docs/index.html er oppdatert!")
