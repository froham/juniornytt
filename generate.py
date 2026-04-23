import anthropic
import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MAKS_SAKER    = 16
NYE_PER_RUNDE =  8
FALLER_UT     =  4

SAKER_FIL_NAT = "docs/saker_nasjonal.json"
SAKER_FIL_LOK = "docs/saker_lokal.json"

RSS_NASJONAL = [
    ("https://www.nrk.no/toppsaker.rss",   "NRK"),
    ("https://www.nrk.no/mr/rss",          "NRK Møre og Romsdal"),
    ("https://www.tv2.no/rss/",            "TV2"),
    ("https://www.aftenposten.no/rss",     "Aftenposten"),
    ("https://www.vg.no/rss/feed/",        "VG"),
]
RSS_LOKAL = [
    ("https://www.smp.no/rss/",            "Sunnmørsposten"),
    ("https://www.vikebladet.no/rss/",     "Vikebladet"),
    ("https://www.vestlandsnytt.no/rss/",  "Vestlandsnytt"),
]

# Emoji-kategorier som fallback
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

def velg_emoji(tittel, brodtekst=""):
    tekst = (tittel + " " + brodtekst).lower()
    for nokkelord, emoji in EMOJI_MAP:
        if any(ord in tekst for ord in nokkelord):
            return emoji
    return "📰"



def hent_rss(feeds, maks_per_kilde=4):
    artikler = []
    headers = {"User-Agent": "JuniorNytt/1.0"}
    ns = {"media": "http://search.yahoo.com/mrss/"}
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
                    artikler.append({
                        "kilde":   kilde,
                        "tittel":  tittel,
                        "ingress": desc[:300],
                    })
        except Exception as e:
            print(f"  Kunne ikke hente {kilde}: {e}")
    return artikler


OMSKRIV_PROMPT = """Du er redaktør for JuniorNytt – en nyhetsside for barn mellom 8 og 12 år.

Her er nyhetsartikler fra norske medier. Velg de {antall} mest interessante og viktige sakene (ingen kjendisnyheter/underholdningssladder), og omskriv dem til barnevennlig språk.

Regler:
- Enkle ord og korte setninger tilpasset 8–12-åringer
- 6–9 setninger per sak – engasjerende men saklig
- Behold det viktigste innholdet
- Legg til ordforklaring (1–4 ord) for vanskelige begreper
- Bruk kildenavnet fra artikkelen
- Legg til et felt "emoji" med én passende emoji for saken

Artikler:
{artikler}

Svar KUN med JSON-array, ingen annen tekst:
[{{"tittel":"...","brodtekst":"...","kilde":"...","emoji":"...","ordforklaring":[{{"ord":"...","forklaring":"..."}}]}}]"""


def omskriv(artikler, antall=8, retries=4, wait=60):
    # Ta med bilde-URL i teksten til Claude slik at vi kan mappe det tilbake
    tekst = "\n\n".join(
        f"[{a['kilde']}] {a['tittel']}\n{a['ingress']}" for a in artikler
    )
    prompt = OMSKRIV_PROMPT.format(antall=antall, artikler=tekst)
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
                    sak["emoji"] = velg_emoji(sak["tittel"], sak.get("brodtekst",""))
            return saker
        except anthropic.RateLimitError:
            if attempt < retries - 1:
                print(f"  Rate limit – venter {wait}s ({attempt+1}/{retries})...")
                time.sleep(wait)
            else:
                print("  Ga opp etter maks forsøk.")
                return []


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


def card(sak, idx):
    colors  = ["#FEF9C3","#DBEAFE","#DCFCE7","#FCE7F3","#F3E8FF","#FFEDD5",
               "#FEF3C7","#E0F2FE","#F0FDF4","#FDF2F8","#F5F3FF","#FFF7ED",
               "#FEFCE8","#EFF6FF","#F0FDF4","#FDF4FF"]
    borders = ["#FDE047","#93C5FD","#86EFAC","#F9A8D4","#C4B5FD","#FCA5A1",
               "#FCD34D","#7DD3FC","#6EE7B7","#F0ABFC","#A78BFA","#FB923C",
               "#FACC15","#60A5FA","#34D399","#E879F9"]
    bg, border = colors[idx % len(colors)], borders[idx % len(borders)]

    emoji = sak.get("emoji") or velg_emoji(sak.get("tittel",""), sak.get("brodtekst",""))

    forklaringer = ""
    if sak.get("ordforklaring"):
        items = "".join(
            f'<div class="ord-item"><strong>{o["ord"]}:</strong> {o["forklaring"]}</div>'
            for o in sak["ordforklaring"]
        )
        forklaringer = f'<div class="ordbox"><div class="ord-title">📖 Visste du at…?</div>{items}</div>'

    ts = sak.get("tidspunkt", "")
    ts_html = f'<span class="tidspunkt">🕐 {ts}</span>' if ts else ""

    return f'''<div class="card" style="background:{bg};border-color:{border}">
      <div class="card-meta">{ts_html}</div>
      <div class="card-emoji">{emoji}</div>
      <h3>{sak["tittel"]}</h3>
      <p>{sak["brodtekst"]}</p>
      {forklaringer}
      <span class="kilde">📰 {sak["kilde"]}</span>
    </div>'''


def build_html(nasjonal, lokal):
    ukedager = ["Mandag","Tirsdag","Onsdag","Torsdag","Fredag","Lørdag","Søndag"]
    ukedag = ukedager[datetime.now().weekday()]
    dato = datetime.now().strftime("%-d. %B %Y").lower()
    nat_cards = "".join(card(s, i) for i, s in enumerate(nasjonal))
    lok_cards = "".join(card(s, i) for i, s in enumerate(lokal))
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
  .tabs{{display:flex;max-width:720px;margin:24px auto 0;padding:0 16px;border-radius:16px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
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
  .card{{border-radius:16px;border:2px solid;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06);overflow:hidden}}
  .card-img{{width:100%;max-height:200px;object-fit:cover;border-radius:10px;margin-bottom:12px;display:block}}
  .card-meta{{display:flex;justify-content:flex-end;margin-bottom:4px}}
  .tidspunkt{{font-size:.7rem;color:#9ca3af}}
  .card-emoji{{font-size:2rem;margin-bottom:8px}}
  .card h3{{font-size:1.15rem;font-weight:800;color:#1f2937;margin-bottom:10px;line-height:1.3}}
  .card p{{font-size:.9rem;color:#374151;line-height:1.7;margin-bottom:12px}}
  .ordbox{{background:rgba(255,255,255,.7);border:1px solid #e5e7eb;border-radius:12px;padding:12px;margin-bottom:12px}}
  .ord-title{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af;margin-bottom:8px}}
  .ord-item{{font-size:.85rem;color:#374151;margin-bottom:4px}}
  .ord-item strong{{color:#1f2937}}
  .kilde{{font-size:.72rem;font-weight:600;color:#6b7280;background:white;padding:4px 12px;border-radius:99px;border:1px solid #e5e7eb}}
  footer{{text-align:center;font-size:.72rem;color:#9ca3af;padding:24px 0}}
  @media(max-width:480px){{header h1{{font-size:2rem}}}}
</style>
<script>
  function show(tab){{
    document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
    document.getElementById('panel-'+tab).classList.add('active');
    document.querySelectorAll('.tab').forEach(t=>t.classList.add('inactive'));
    document.getElementById('tab-'+tab).classList.remove('inactive');
    document.getElementById('src-line').textContent = tab==='nasjonal'
      ? 'Kilder: NRK · NRK Møre og Romsdal · Aftenposten · TV2 · VG'
      : 'Kilder: Vikebladet · Vestlandsnytt · Sunnmørsposten';
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
</header>
<div class="tabs">
  <button class="tab tab-nat" id="tab-nasjonal" onclick="show('nasjonal')">
    🇳🇴 Nasjonalt <span class="badge">{len(nasjonal)}</span>
  </button>
  <button class="tab tab-lok inactive" id="tab-lokal" onclick="show('lokal')">
    📍 Lokalt <span class="badge">{len(lokal)}</span>
  </button>
</div>
<div class="sources" id="src-line">Kilder: NRK · NRK Møre og Romsdal · Aftenposten · TV2 · VG</div>
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

    print("Henter RSS – nasjonalt...")
    nat_rss = hent_rss(RSS_NASJONAL)
    print(f"  → {len(nat_rss)} artikler")
    print("Omskriver nasjonale nyheter...")
    nye_nat = omskriv(nat_rss, antall=NYE_PER_RUNDE)
    nasjonal = oppdater_saker(nye_nat, SAKER_FIL_NAT, er_morgen)
    print(f"  → {len(nasjonal)} saker totalt")

    print("Henter RSS – lokalt...")
    lok_rss = hent_rss(RSS_LOKAL)
    print(f"  → {len(lok_rss)} artikler")
    print("Omskriver lokale nyheter...")
    nye_lok = omskriv(lok_rss, antall=NYE_PER_RUNDE)
    lokal = oppdater_saker(nye_lok, SAKER_FIL_LOK, er_morgen)
    print(f"  → {len(lokal)} saker totalt")

    html = build_html(nasjonal, lokal)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ docs/index.html er oppdatert!")
