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
BUFFER        =  3   # Ekstra saker som hentes i tilfelle duplikater fjernes

SAKER_FIL_NAT = "docs/saker_nasjonal.json"
SAKER_FIL_LOK = "docs/saker_lokal.json"

# Standard posisjon: Ulsteinvik
STD_LAT = 62.3439
STD_LON =  5.8467
STD_STAD = "Ulsteinvik"

RSS_NASJONAL = [
    ("https://www.nrk.no/toppsaker.rss",         "NRK"),
    ("https://www.nrk.no/moreogromsdal/rss.xml",  "NRK Møre og Romsdal"),
    ("https://www.aftenposten.no/rss",            "Aftenposten"),
    ("https://www.vg.no/rss/feed/",               "VG"),
    ("https://www.dagbladet.no/rss",              "Dagbladet"),
]
RSS_LOKAL = [
    ("https://www.smp.no/rss/",            "Sunnmørsposten"),
    ("https://www.vikebladet.no/rss/",     "Vikebladet"),
    ("https://www.vestlandsnytt.no/rss/",  "Vestlandsnytt"),
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
]

VÆR_SYMBOL = {
    "clearsky":                    "☀️",
    "fair":                        "🌤️",
    "partlycloudy":                "⛅",
    "cloudy":                      "☁️",
    "rainshowers":                 "🌦️",
    "lightrainshowers":            "🌦️",
    "rain":                        "🌧️",
    "lightrain":                   "🌧️",
    "heavyrain":                   "🌧️",
    "sleet":                       "🌨️",
    "lightsleet":                  "🌨️",
    "sleetshowers":                "🌨️",
    "snow":                        "❄️",
    "lightsnow":                   "❄️",
    "snowshowers":                 "🌨️",
    "fog":                         "🌫️",
    "thunder":                     "⛈️",
    "rainandthunder":              "⛈️",
    "lightrainandthunder":         "⛈️",
    "heavyrainandthunder":         "⛈️",
    "rainshowersandthunder":       "⛈️",
    "snowandthunder":              "⛈️",
    "sleetandthunder":             "⛈️",
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
    """Returnerer ekstra fareikoner ved ekstremvær."""
    farar = []
    if vind >= 15:
        farar.append("💨🚨")  # Sterk vind
    if vind >= 25:
        farar.append("🌀")    # Storm
    if "thunder" in symbol_base:
        farar.append("⚡")
    if nedbor >= 5:
        farar.append("🌊")    # Kraftig nedbør
    return " ".join(farar)

def hent_vaer(lat=STD_LAT, lon=STD_LON):
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat:.4f}&lon={lon:.4f}"
    req = urllib.request.Request(url, headers={"User-Agent": "JuniorNytt/1.0 github.com/froham/juniornytt"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        ts_list = data["properties"]["timeseries"]

        # --- Nå ---
        now = ts_list[0]["data"]
        temp_no = round(now["instant"]["details"]["air_temperature"])
        vind_no = round(now["instant"]["details"]["wind_speed"])
        symbol_no = now.get("next_1_hours", now.get("next_6_hours", {})).get("summary", {}).get("symbol_code", "")
        nedbor_no = now.get("next_1_hours", now.get("next_6_hours", {})).get("details", {}).get("precipitation_amount", 0)
        base_no = re.sub(r"_(day|night|polartwilight)$", "", symbol_no)

        # --- Finn dagsprognose for 4 dagar ---
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
        ukedagar_no = ["Man","Tys","Ons","Tor","Fre","Lør","Sun"]
        today_str = datetime.now().strftime("%Y-%m-%d")
        for dato, vals in sorted(dagar.items()):
            if dato == today_str:
                continue
            if len(dag_prognose) >= 4:
                break
            temps = [v["temp"] for v in vals]
            symboler = [v["symbol"] for v in vals if v["symbol"]]
            maks_nedbor = max(v["nedbor"] for v in vals)
            maks_vind = 0  # vind per dag ikkje tilgjengeleg direkte i compact
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
            "temp": temp_no,
            "vind": vind_no,
            "symbol": symbol_til_emoji(symbol_no),
            "fare": farevarsel(vind_no, base_no, nedbor_no),
            "nedbor": round(nedbor_no, 1),
            "dagar": dag_prognose,
        }
    except Exception as e:
        print(f"  Kunne ikkje hente vêr: {e}")
        return None

def hent_rss(feeds, maks_per_kilde=4):
    artikler = []
    headers = {"User-Agent": "JuniorNytt/1.0"}
    for url, kilde in feeds:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                root = ET.fromstring(r.read())
            items = root.findall(".//item")[:maks_per_kilde]
            for item in items:
                tittel = (item.findtext("title") or "").strip()
                desc   = (item.findtext("description") or "").strip()
                desc   = re.sub(r"<[^>]+>", "", desc).strip()
                if tittel:
                    artikler.append({"kilde": kilde, "tittel": tittel, "ingress": desc[:300]})
        except Exception as e:
            print(f"  Kunne ikke hente {kilde}: {e}")
    return artikler


OMSKRIV_PROMPT = """Du er redaktør for JuniorNytt – ei nyhetsside for barn mellom 8 og 12 år.

Her er nyhetsartiklar frå norske medium. Vel dei {antall} mest interessante og viktige sakene (ingen kjendisnyheiter/underhaldningssladder), og skriv dei om til eit barnevenleg språk.

Språkregler – SVÆRT VIKTIG:
- Skriv på nynorsk i stilen til Sunnmøre/Romsdal-aviser som Vikebladet og Vestlandsnytt – ikkje Hordaland-nynorsk
- Bruk typiske Sunnmøre-nynorsk-former: "ikkje" (ikke), "òg" (også), "kva" (hva), "når" (når), "dei" (de), "han/ho" (han/hun), "me/vi" (vi), "med" (med), "heime" (hjemme), "skule" (skole), "hjelpe" (hjelpe)
- Enkle ord og korte setningar tilpassa 8–12-åringar
- 6–9 setningar per sak – engasjerande men sakleg
- Behald det viktigaste innhaldet
- Legg til ordforklaring (1–4 ord) for vanskelege omgrep – ordforklaringane skal også vere på nynorsk
- Bruk kjeldenamnet frå artikkelen
- Legg til eitt felt "emoji" med éin passande emoji for saka
- Viss saka handlar om noko som skjer i eit anna land enn Noreg, legg til feltet "land" med landsnamnet på norsk og flagg-emoji, t.d. {{"namn": "Ukraina", "flagg": "🇺🇦"}}. Ikkje legg til "land" for saker som berre handlar om Noreg.

Artiklar:
{artiklar}

Svar KUN med JSON-array, ingen annan tekst:
[{{"tittel":"...","brodtekst":"...","kilde":"...","emoji":"...","ordforklaring":[{{"ord":"...","forklaring":"..."}}],"land":{{"namn":"...","flagg":"..."}}}}]"""


def omskriv(artikler, antall=8, retries=4, wait=60):
    tekst = "\n\n".join(f"[{a['kilde']}] {a['tittel']}\n{a['ingress']}" for a in artikler)
    prompt = OMSKRIV_PROMPT.format(antall=antall, artiklar=tekst)
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
            if s == -1:
                return []
            saker = json.loads(text[s:e+1])
            ts = datetime.now().strftime("%H:%M")
            for sak in saker:
                sak["tidspunkt"] = ts
                if not sak.get("emoji"):
                    sak["emoji"] = velg_emoji(sak["tittel"], sak.get("brodtekst", ""))
            return saker
        except anthropic.RateLimitError:
            if attempt < retries - 1:
                print(f"  Rate limit – venter {wait}s ({attempt+1}/{retries})...")
                time.sleep(wait)
            else:
                print("  Ga opp etter maks forsøk.")
                return []


def fjern_duplikater(lokale, nasjonale, terskel=0.4):
    def nokkelord(tittel):
        stopord = {"og","i","er","på","en","et","de","det","som","til","av","for","med","at","har","om"}
        return {w.lower() for w in tittel.split() if w.lower() not in stopord and len(w) > 2}
    nat_ord = [nokkelord(s["tittel"]) for s in nasjonale]
    filtrerte = []
    for sak in lokale:
        lok_ord = nokkelord(sak["tittel"])
        for n_ord in nat_ord:
            if not lok_ord or not n_ord:
                continue
            overlapp = len(lok_ord & n_ord) / min(len(lok_ord), len(n_ord))
            if overlapp >= terskel:
                print(f"  Duplikat fjernet: «{sak['tittel']}»")
                break
        else:
            filtrerte.append(sak)
    return filtrerte


def oppdater_saker(nye, fil, er_morgen):
    eksisterende = []
    if not er_morgen and os.path.exists(fil):
        try:
            with open(fil, encoding="utf-8") as f:
                eksisterende = json.load(f)
        except Exception:
            eksisterende = []
    eksist_titler = {s["tittel"].lower() for s in eksisterende}
    nye_unike = [s for s in nye if s["tittel"].lower() not in eksist_titler]
    kombinert = nye_unike + eksisterende
    if not er_morgen and len(kombinert) >= FALLER_UT:
        kombinert = kombinert[:-FALLER_UT]
    kombinert = kombinert[:MAKS_SAKER]
    os.makedirs("docs", exist_ok=True)
    with open(fil, "w", encoding="utf-8") as f:
        json.dump(kombinert, f, ensure_ascii=False, indent=2)
    return kombinert


def vaer_html(vaer):
    if not vaer:
        return ""
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
          <span class="vaer-sted" id="vaer-sted">{STD_STAD}</span>
        </div>
      </div>
      <div class="vaer-dagar">{dagar_html}</div>
    </div>"""


def card(sak, idx):
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
    if sak.get("land") and sak["land"].get("navn"):
        land_html = f'<span class="land-badge">{sak["land"].get("flagg","")} {sak["land"]["navn"]}</span>'

    forklaringer = ""
    if sak.get("ordforklaring"):
        items = "".join(
            f'<div class="ord-item"><strong>{o["ord"]}:</strong> {o["forklaring"]}</div>'
            for o in sak["ordforklaring"]
        )
        forklaringer = f'<div class="ordbox"><div class="ord-title">📖 Visste du at…?</div>{items}</div>'

    return f'''<div class="card" style="background:{bg};border-color:{border}">
      <div class="card-meta">{ts_html}{land_html}</div>
      <div class="card-emoji">{emoji}</div>
      <h3>{sak["tittel"]}</h3>
      <p>{sak["brodtekst"]}</p>
      {forklaringer}
      <span class="kilde">📰 {sak["kilde"]}</span>
    </div>'''


def build_html(nasjonal, lokal, vaer):
    ukedager = ["Mandag","Tirsdag","Onsdag","Torsdag","Fredag","Lørdag","Søndag"]
    ukedag = ukedager[datetime.now().weekday()]
    dato = datetime.now().strftime("%-d. %B %Y").lower()
    nat_cards = "".join(card(s, i) for i, s in enumerate(nasjonal))
    lok_cards = "".join(card(s, i) for i, s in enumerate(lokal))
    vaer_boks = vaer_html(vaer)

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
  .sub{{font-size:.75rem;opacity:.7;font-style:italic;margin-top:2px}}
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
  .tab{{flex:1;padding:12px;font-weight:700;font-size:.85rem;border:none;cursor:pointer;transition:.2s;display:flex;align-items:center;justify-content:center;gap:8px}}
  .tab-nat{{background:#3b82f6;color:white}}
  .tab-nat.inactive{{background:white;color:#6b7280}}.tab-nat.inactive:hover{{background:#eff6ff}}
  .tab-lok{{background:#10b981;color:white}}
  .tab-lok.inactive{{background:white;color:#6b7280}}.tab-lok.inactive:hover{{background:#f0fdf4}}
  .badge{{background:rgba(255,255,255,.3);border-radius:99px;padding:2px 8px;font-size:.7rem}}
  .inactive .badge{{background:#e5e7eb;color:#6b7280}}
  .sources{{max-width:720px;margin:6px auto 0;padding:0 20px;font-size:.72rem;color:#9ca3af}}
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
  footer{{text-align:center;font-size:.72rem;color:#9ca3af;padding:24px 0}}
  @media(max-width:480px){{header h1{{font-size:2rem}}.vaer-boks{{flex-wrap:wrap}}}}
</style>
<script>
  // Hent vær basert på brukerens posisjon
  function oppdaterVaer(lat, lon, stedNavn) {{
    fetch(`https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=${{lat.toFixed(4)}}&lon=${{lon.toFixed(4)}}`, {{
      headers: {{"User-Agent": "JuniorNytt/1.0"}}
    }})
    .then(r => r.json())
    .then(data => {{
      const ts = data.properties.timeseries[0].data;
      const temp = Math.round(ts.instant.details.air_temperature);
      const vind = Math.round(ts.instant.details.wind_speed);
      const symbol = (ts.next_1_hours || ts.next_6_hours || {{}}).summary?.symbol_code || "";
      const nedbor = ((ts.next_1_hours || ts.next_6_hours || {{}}).details?.precipitation_amount || 0).toFixed(1);
      const symbolMap = {{
        clearsky:"☀️",fair:"🌤️",partlycloudy:"⛅",cloudy:"☁️",
        rainshowers:"🌦️",lightrainshowers:"🌦️",rain:"🌧️",lightrain:"🌧️",
        heavyrain:"🌧️",sleet:"🌨️",lightsleet:"🌨️",sleetshowers:"🌨️",
        snow:"❄️",lightsnow:"❄️",snowshowers:"🌨️",fog:"🌫️",
        thunder:"⛈️",rainandthunder:"⛈️",lightrainandthunder:"⛈️",
        heavyrainandthunder:"⛈️",rainshowersandthunder:"⛈️",
        snowandthunder:"⛈️",sleetandthunder:"⛈️"
      }};
      const toEmoji = s => symbolMap[s.replace(/_(day|night|polartwilight)$/, "")] || "🌡️";
      const toFare = (vind, base, nedbor) => {{
        let f = "";
        if (vind >= 15) f += "💨🚨";
        if ("thunder".includes(base)) f += "⚡";
        return f;
      }};
      const base = symbol.replace(/_(day|night|polartwilight)$/, "");
      document.querySelector(".vaer-symbol").textContent = toEmoji(symbol);
      document.querySelector(".vaer-temp").innerHTML = `${{temp}}°C ${{toFare(vind, base, nedbor)}}`;
      document.querySelector(".vaer-vind").textContent = `💨 ${{vind}} m/s · 🌧 ${{nedbor}} mm`;
      if (stedNavn) document.getElementById("vaer-sted").textContent = stedNavn;
    }})
    .catch(() => {{}});
  }}

  // Spør om posisjon
  if (navigator.geolocation) {{
    navigator.geolocation.getCurrentPosition(pos => {{
      oppdaterVaer(pos.coords.latitude, pos.coords.longitude, "Din posisjon");
    }}, () => {{}}, {{timeout: 5000}});
  }}

  function show(tab) {{
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.getElementById("panel-" + tab).classList.add("active");
    document.querySelectorAll(".tab").forEach(t => t.classList.add("inactive"));
    document.getElementById("tab-" + tab).classList.remove("inactive");
    document.getElementById("src-line").textContent = tab === "nasjonal"
      ? "Kjelder: NRK · NRK Møre og Romsdal · Aftenposten · VG · Dagbladet"
      : "Kjelder: Vikebladet · Vestlandsnytt · Sunnmørsposten";
  }}
</script>
</head>
<body>
<header>
  <div style="font-size:2.5rem">📰</div>
  <h1>JuniorNytt</h1>
  <div class="dato">{ukedag} {dato}</div>
  <div class="sub">Nyheter for deg mellom 8 og 12 år</div>
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
</div>
<div class="sources" id="src-line">Kjelder: NRK · NRK Møre og Romsdal · Aftenposten · VG · Dagbladet</div>
<main>
  <div class="panel active" id="panel-nasjonal">{nat_cards}</div>
  <div class="panel" id="panel-lokal">{lok_cards}</div>
</main>
<footer>JuniorNytt • Laget for nysgjerrige barn 🌟</footer>
</body>
</html>"""


if __name__ == "__main__":
    time_now = datetime.now()
    er_morgen = time_now.hour < 9

    print(f"Kjøring kl. {time_now.strftime('%H:%M')} – {'morgen (nullstiller)' if er_morgen else 'oppdatering'}")

    print(f"Henter vær for {STD_STAD}...")
    vaer = hent_vaer()
    print(f"  → {vaer}")

    print("Henter RSS – nasjonalt...")
    nat_rss = hent_rss(RSS_NASJONAL, maks_per_kilde=6)
    print(f"  → {len(nat_rss)} artikler")
    print("Omskriver nasjonale nyheter...")
    nye_nat = omskriv(nat_rss, antall=NYE_PER_RUNDE + BUFFER)
    nasjonal = oppdater_saker(nye_nat[:NYE_PER_RUNDE], SAKER_FIL_NAT, er_morgen)
    print(f"  → {len(nasjonal)} saker totalt")

    print("Henter RSS – lokalt...")
    lok_rss = hent_rss(RSS_LOKAL, maks_per_kilde=6)
    print(f"  → {len(lok_rss)} artikler")
    print("Omskriver lokale nyheter...")
    nye_lok = omskriv(lok_rss, antall=NYE_PER_RUNDE + BUFFER)

    print("Sjekker for duplikater...")
    nye_lok = fjern_duplikater(nye_lok, nye_nat)
    # Behold maks NYE_PER_RUNDE etter filtrering
    lokal = oppdater_saker(nye_lok[:NYE_PER_RUNDE], SAKER_FIL_LOK, er_morgen)
    print(f"  → {len(lokal)} saker totalt")

    html = build_html(nasjonal, lokal, vaer)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ docs/index.html er oppdatert!")
