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
MAKS_SAKER    = 20
NYE_PER_RUNDE = 10
FALLER_UT     =  5
BUFFER        =  3
MAKS_SPEL     = 12
NYE_SPEL      =  8

SAKER_FIL_NAT  = "docs/saker_nasjonal.json"
SAKER_FIL_LOK  = "docs/saker_lokal.json"
SAKER_FIL_SPEL = "docs/saker_spel.json"
SAKER_FIL_KINO = "docs/saker_kino.json"

STD_LAT  = 62.3439
STD_LON  =  5.8467
STD_STAD = "Ulsteinvik"

# ── RSS-kjelder ───────────────────────────────────────────────────────────────
RSS_NASJONAL = [
    ("https://www.nrk.no/toppsaker.rss",              "NRK"),
    ("https://www.aftenposten.no/rss",                "Aftenposten"),
    ("https://www.vg.no/rss/feed/",                   "VG"),
    ("https://www.tv2.no/rss/nyheter/",               "TV2"),
]
RSS_LOKAL = [
    ("https://www.smp.no/rss/",                       "Sunnmørsposten"),
    ("https://www.vikebladet.no/rss/",                "Vikebladet"),
    ("https://www.vestlandsnytt.no/rss/",             "Vestlandsnytt"),
]
RSS_SPEL = [
    ("https://dotesports.com/minecraft/feed",      "Minecraft"),
    ("https://dotesports.com/roblox/feed",         "Roblox"),
    ("https://dotesports.com/pokemon/feed",        "Pokémon"),
    ("https://www.vg.no/rss/feed/?categories=sport", "VG Sport"),
    ("https://www.nrk.no/sport/rss.xml",           "NRK Sport"),
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
    headers = {"User-Agent": "JuniorNytt/1.0"}
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

# ── TMDB kino ─────────────────────────────────────────────────────────────────
def hent_kinofilmar():
    api_key = os.environ.get("TMDB_API_KEY", "")
    if not api_key:
        print("  Ingen TMDB_API_KEY, hoppar over kino.")
        return []
    try:
        url = f"https://api.themoviedb.org/3/movie/now_playing?api_key={api_key}&language=nb-NO&region=NO"
        req = urllib.request.Request(url, headers={"User-Agent": "JuniorNytt/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        filmar = []
        for film in data.get("results", []):
            fid = film["id"]
            det_url = f"https://api.themoviedb.org/3/movie/{fid}?api_key={api_key}&language=nb-NO&append_to_response=release_dates"
            req2 = urllib.request.Request(det_url, headers={"User-Agent": "JuniorNytt/1.0"})
            with urllib.request.urlopen(req2, timeout=10) as r2:
                det = json.loads(r2.read())
            aldersgrense = ""
            for entry in det.get("release_dates", {}).get("results", []):
                if entry["iso_3166_1"] == "NO":
                    for rd in entry.get("release_dates", []):
                        cert = rd.get("certification", "")
                        if cert:
                            aldersgrense = cert
                            break
            if aldersgrense not in ["A", "6", ""]:
                print(f"  Filtrert ({aldersgrense}): {film.get('title')}")
                continue
            filmar.append({
                "tittel": film.get("title", ""),
                "oversikt": film.get("overview", "")[:300],
                "aldersgrense": aldersgrense or "A",
            })
            if len(filmar) >= 6:
                break
        return filmar
    except Exception as e:
        print(f"  TMDB-feil: {e}")
        return []

# ── Promptar ──────────────────────────────────────────────────────────────────
OMSKRIV_PROMPT = """Du er redaktør for JuniorNytt – ei nyhetsside for barn mellom 8 og 12 år.

Vel dei {antall} mest interessante og viktige sakene (ingen kjendisnyheiter/underhaldningssladder) og skriv dei om til barnevenleg nynorsk i stilen til Sunnmøre-aviser (Vikebladet, Vestlandsnytt).

Reglar:
- Nynorsk: "ikkje", "òg", "kva", "dei", "ho", "heime", "skule"
- 6–9 setningar per sak, engasjerande og sakleg
- Ordforklaring (1–4 ord) for vanskelege omgrep
- Felt "emoji" med passande emoji
- Felt "land" med namn og flagg viss saka er frå eit anna land enn Noreg

Artiklar:
{artiklar}

Svar KUN med JSON-array:
[{{"tittel":"...","brodtekst":"...","kilde":"...","emoji":"...","ordforklaring":[{{"ord":"...","forklaring":"..."}}],"land":{{"namn":"...","flagg":"..."}}}}]"""

SPEL_PROMPT = """Du er redaktør for JuniorNytt si spel- og sportsseksjon for barn mellom 8 og 12 år.

Vel dei {antall} mest eigna sakene og skriv dei om til barnevenleg nynorsk. Ver entusiastisk!

VIKTIG – filtrer bort:
- Saker om vald, horror, blod eller vaksent innhald i spel
- Saker med aldersgrense over 12 år (PEGI 16/18)
- Saker som ikkje eignar seg for barn

Reglar:
- Nynorsk Sunnmøre-stil: "ikkje", "òg", "kva", "dei"
- 4–6 setningar per sak
- Ordforklaring for spelordar og sportsuttrykk
- Felt "emoji" – spel- eller sportselemoji

Artiklar:
{artiklar}

Svar KUN med JSON-array:
[{{"tittel":"...","brodtekst":"...","kilde":"...","emoji":"...","ordforklaring":[{{"ord":"...","forklaring":"..."}}]}}]"""

KINO_PROMPT = """Du er redaktør for JuniorNytt si kino-seksjon for barn mellom 8 og 12 år.

Skriv ein kort og engasjerande presentasjon av kvar film på nynorsk. Fang nysgjerrigheita til barnet!

Reglar:
- Nynorsk Sunnmøre-stil
- 3–4 setningar per film
- Felt "emoji" som passar til filmen
- Aldersgrense skal med

Filmar:
{filmar}

Svar KUN med JSON-array:
[{{"tittel":"...","brodtekst":"...","aldersgrense":"...","emoji":"..."}}]"""

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
                print("  Ingen JSON funnen i svaret, prøver igjen...")
                continue
            saker = json.loads(text[s:e+1])
            ts = datetime.now().strftime("%H:%M")
            for sak in saker:
                sak["tidspunkt"] = ts
                if not sak.get("emoji"):
                    sak["emoji"] = velg_emoji(sak.get("tittel",""), sak.get("brodtekst",""))
            return saker
        except json.JSONDecodeError as je:
            print(f"  JSON-feil ({attempt+1}/{retries}): {je} – prøver igjen...")
            time.sleep(5)
        except anthropic.RateLimitError:
            if attempt < retries - 1:
                print(f"  Rate limit – ventar {wait}s...")
                time.sleep(wait)
            else:
                return []
    return []

def omskriv_kino(filmar):
    if not filmar:
        return []
    tekst = "\n\n".join(
        f"Tittel: {f['tittel']}\nAldersgrense: {f['aldersgrense']}\nHandling: {f['oversikt']}"
        for f in filmar
    )
    prompt = KINO_PROMPT.format(filmar=tekst)
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5", max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.content[0].text.replace("```json","").replace("```","").strip()
        s, e = text.find("["), text.rfind("]")
        if s == -1: return []
        saker = json.loads(text[s:e+1])
        for sak in saker:
            sak["tidspunkt"] = datetime.now().strftime("%H:%M")
            sak["kilde"] = "TMDB / Filmweb"
        return saker
    except Exception as ex:
        print(f"  Kino-feil: {ex}")
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

# ── Lagring ───────────────────────────────────────────────────────────────────
def oppdater_saker(nye, fil, er_morgen, maks=None, faller_ut=None):
    if maks is None: maks = MAKS_SAKER
    if faller_ut is None: faller_ut = FALLER_UT
    eksist = []
    if not er_morgen and os.path.exists(fil):
        try:
            with open(fil, encoding="utf-8") as f:
                eksist = json.load(f)
        except Exception:
            pass
    titlar = {s["tittel"].lower() for s in eksist}
    kombinert = [s for s in nye if s["tittel"].lower() not in titlar] + eksist
    if not er_morgen and len(kombinert) >= faller_ut:
        kombinert = kombinert[:-faller_ut]
    kombinert = kombinert[:maks]
    os.makedirs("docs", exist_ok=True)
    with open(fil, "w", encoding="utf-8") as f:
        json.dump(kombinert, f, ensure_ascii=False, indent=2)
    return kombinert

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

def kino_card(sak, idx):
    bg, border = COLORS[idx % len(COLORS)], BORDERS[idx % len(BORDERS)]
    emoji = sak.get("emoji", "🎬")
    alder = sak.get("aldersgrense", "A")
    alder_stil = "background:#dcfce7;color:#166534" if alder in ["A","6"] else "background:#fef9c3;color:#854d0e"
    alder_tekst = "Alle" if alder == "A" else f"{alder} år"
    return f'''<div class="card" style="background:{bg};border-color:{border}">
      <div class="card-meta">
        <span class="tidspunkt">🎬 No på kino</span>
        <span style="font-size:.72rem;font-weight:700;padding:2px 10px;border-radius:99px;{alder_stil}">{alder_tekst}</span>
      </div>
      <div class="card-emoji">{emoji}</div>
      <h3>{sak["tittel"]}</h3>
      <p>{sak["brodtekst"]}</p>
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

def build_html(nasjonal, lokal, spel, kino, vaer):
    ukedagar = ["Måndag","Tysdag","Onsdag","Torsdag","Fredag","Laurdag","Sundag"]
    ukedag = ukedagar[datetime.now().weekday()]
    dato = datetime.now().strftime("%-d. %B %Y").lower()
    nat_cards  = "".join(card(s,i) for i,s in enumerate(nasjonal))
    lok_cards  = "".join(card(s,i) for i,s in enumerate(lokal))
    spel_cards = "".join(card(s,i) for i,s in enumerate(spel))
    kino_cards = "".join(kino_card(s,i) for i,s in enumerate(kino))
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
  .tab{{flex:1;padding:10px 2px;font-weight:700;font-size:.75rem;border:none;cursor:pointer;transition:.2s;display:flex;align-items:center;justify-content:center;gap:4px}}
  .tab-nat{{background:#3b82f6;color:white}}
  .tab-nat.inactive{{background:white;color:#6b7280}}.tab-nat.inactive:hover{{background:#eff6ff}}
  .tab-lok{{background:#10b981;color:white}}
  .tab-lok.inactive{{background:white;color:#6b7280}}.tab-lok.inactive:hover{{background:#f0fdf4}}
  .tab-spel{{background:#8b5cf6;color:white}}
  .tab-spel.inactive{{background:white;color:#6b7280}}.tab-spel.inactive:hover{{background:#f5f3ff}}
  .tab-kino{{background:#f59e0b;color:white}}
  .tab-kino.inactive{{background:white;color:#6b7280}}.tab-kino.inactive:hover{{background:#fffbeb}}
  .badge{{background:rgba(255,255,255,.3);border-radius:99px;padding:2px 7px;font-size:.68rem}}
  .inactive .badge{{background:#e5e7eb;color:#6b7280}}
  .sources{{max-width:720px;margin:6px auto 0;padding:0 20px;font-size:.72rem;color:#9ca3af}}
  .varsel-boks{{max-width:720px;margin:8px auto 0;padding:10px 20px;border-radius:12px;font-size:.78rem;line-height:1.5;display:none}}
  .varsel-spel{{background:#fef3c7;border:1px solid #fde047;color:#92400e}}
  .varsel-kino{{background:#e0f2fe;border:1px solid #7dd3fc;color:#0c4a6e}}
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
    spel:     "Kjelder: Minecraft · Roblox · Pokémon · VG Sport · NRK Sport",
    kino:     "Kjelde: The Movie Database (TMDB)"
  }};
  function show(tab) {{
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.getElementById("panel-" + tab).classList.add("active");
    document.querySelectorAll(".tab").forEach(t => t.classList.add("inactive"));
    document.getElementById("tab-" + tab).classList.remove("inactive");
    document.getElementById("src-line").textContent = SRC[tab] || "";
    document.getElementById("varsel-spel").style.display = tab === "spel" ? "block" : "none";
    document.getElementById("varsel-kino").style.display = tab === "kino" ? "block" : "none";
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
  <button class="tab tab-kino inactive" id="tab-kino" onclick="show('kino')">🎬 Kino <span class="badge">{len(kino)}</span></button>
</div>

<div class="sources" id="src-line">Kjelder: NRK · Aftenposten · VG · Dagbladet · Nettavisen</div>
<div class="varsel-boks varsel-spel" id="varsel-spel">⚠️ I spel der du kan møte framande på nett – hugs å aldri dele personleg informasjon, og fortel alltid ein vaksen viss nokon oppfører seg rart.</div>
<div class="varsel-boks varsel-kino" id="varsel-kino">🎬 Her finn du filmar som går på norske kinoar no – berre filmar for barn under 8 år er med!</div>

<main>
  <div class="panel active" id="panel-nasjonal">{nat_cards}</div>
  <div class="panel" id="panel-lokal">{lok_cards}</div>
  <div class="panel" id="panel-spel">{spel_cards}</div>
  <div class="panel" id="panel-kino">{kino_cards}</div>
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
    er_morgen = now.hour < 9
    er_middag = 9 <= now.hour < 15
    print(f"Køyring kl. {now.strftime('%H:%M')} – {'morgen' if er_morgen else 'middag' if er_middag else 'kveld'}")

    print(f"Hentar vêr for {STD_STAD}...")
    vaer = hent_vaer()

    print("Hentar RSS – nasjonalt...")
    nat_rss = hent_rss(RSS_NASJONAL)
    print(f"  → {len(nat_rss)} artiklar")
    print("Skriv om nasjonale nyhende...")
    nye_nat = omskriv(nat_rss, antall=NYE_PER_RUNDE + BUFFER)
    nasjonal = oppdater_saker((nye_nat or [])[:NYE_PER_RUNDE], SAKER_FIL_NAT, er_morgen)
    print(f"  → {len(nasjonal)} saker totalt")

    print("Hentar RSS – lokalt...")
    lok_rss = hent_rss(RSS_LOKAL)
    print(f"  → {len(lok_rss)} artiklar")
    print("Skriv om lokale nyhende...")
    nye_lok = omskriv(lok_rss, antall=NYE_PER_RUNDE + BUFFER)
    nye_lok = fjern_duplikatar(nye_lok or [], nye_nat or [])
    lokal = oppdater_saker(nye_lok[:NYE_PER_RUNDE], SAKER_FIL_LOK, er_morgen)
    print(f"  → {len(lokal)} saker totalt")

    if er_morgen or er_middag:
        print("Hentar RSS – spel & sport...")
        spel_rss = hent_rss(RSS_SPEL, maks_per_kilde=5)
        print(f"  → {len(spel_rss)} artiklar")
        print("Skriv om spel & sport...")
        nye_spel = omskriv(spel_rss, antall=NYE_SPEL, prompt_mal=SPEL_PROMPT)
        spel = oppdater_saker(nye_spel or [], SAKER_FIL_SPEL, er_morgen, maks=MAKS_SPEL, faller_ut=4)
        print(f"  → {len(spel)} saker totalt")

        print("Hentar kinofilmar frå TMDB...")
        rå_kino = hent_kinofilmar()
        print(f"  → {len(rå_kino)} filmar")
        kino = omskriv_kino(rå_kino)
        os.makedirs("docs", exist_ok=True)
        with open(SAKER_FIL_KINO, "w", encoding="utf-8") as f:
            json.dump(kino, f, ensure_ascii=False, indent=2)
        print(f"  → {len(kino)} kinofilmar klare")
    else:
        spel = json.load(open(SAKER_FIL_SPEL, encoding="utf-8")) if os.path.exists(SAKER_FIL_SPEL) else []
        kino = json.load(open(SAKER_FIL_KINO, encoding="utf-8")) if os.path.exists(SAKER_FIL_KINO) else []
        print(f"  → Kveld: brukar {len(spel)} spelsaker og {len(kino)} kinofilmar frå middag")

    html = build_html(nasjonal, lokal, spel, kino, vaer)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ docs/index.html er oppdatert!")
