import anthropic
import json
import os
from datetime import datetime

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

NASJONAL_PROMPT = """Du er redaktør for JuniorNytt – en nyhetsside for barn mellom 8 og 12 år.

Søk etter de 6 viktigste norske nyhetssakene fra I DAG fra NRK.no, Aftenposten.no og TV2.no.

Regler:
- Ingen kjendisnyheter eller underholdningssladder
- Omformuler til enkelt, lettlest språk for 8–12-åringer
- 6–9 setninger per sak – engasjerende men saklig
- Legg til ordforklaring (1–4 ord) for vanskelige begreper
- Kildenavn: NRK, Aftenposten eller TV2

Svar KUN med JSON-array, ingen annen tekst:
[{"tittel":"...","brodtekst":"...","kilde":"...","ordforklaring":[{"ord":"...","forklaring":"..."}]}]"""

LOKAL_PROMPT = """Du er redaktør for JuniorNytt – en nyhetsside for barn mellom 8 og 12 år.

Søk etter de 6 viktigste lokale nyhetssakene fra siste 48 timer fra Vikebladet.no, Vestlandsnytt.no og smp.no (Sunnmørsposten) – aviser fra Sunnmøre/Vestlandet i Norge.

Regler:
- Omformuler til enkelt, lettlest språk for 8–12-åringer
- 6–9 setninger per sak – engasjerende men saklig
- Legg til ordforklaring (1–4 ord) for vanskelige begreper
- Kildenavn: Vikebladet, Vestlandsnytt eller Sunnmørsposten

Svar KUN med JSON-array, ingen annen tekst:
[{"tittel":"...","brodtekst":"...","kilde":"...","ordforklaring":[{"ord":"...","forklaring":"..."}]}]"""

def fetch(prompt):
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text"))
    text = text.replace("```json", "").replace("```", "").strip()
    s, e = text.find("["), text.rfind("]")
    return json.loads(text[s:e+1]) if s != -1 else []

def card(sak, idx):
    colors = ["#FEF9C3","#DBEAFE","#DCFCE7","#FCE7F3","#F3E8FF","#FFEDD5"]
    borders = ["#FDE047","#93C5FD","#86EFAC","#F9A8D4","#C4B5FD","#FCA5A1"]
    bg = colors[idx % len(colors)]
    border = borders[idx % len(borders)]
    forklaringer = ""
    if sak.get("ordforklaring"):
        items = "".join(f'<div class="ord-item"><strong>{o["ord"]}:</strong> {o["forklaring"]}</div>' for o in sak["ordforklaring"])
        forklaringer = f'<div class="ordbox"><div class="ord-title">📖 Visste du at…?</div>{items}</div>'
    return f'''
    <div class="card" style="background:{bg};border-color:{border}">
      <h3>{sak["tittel"]}</h3>
      <p>{sak["brodtekst"]}</p>
      {forklaringer}
      <span class="kilde">📰 {sak["kilde"]}</span>
    </div>'''

def build_html(nasjonal, lokal):
    dato = datetime.now().strftime("%-d. %B %Y").lower()
    ukedag = ["mandag","tirsdag","onsdag","torsdag","fredag","lørdag","søndag"][datetime.now().weekday()]
    dato_str = f"{ukedag.capitalize()} {dato}"
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
  header .dato{{font-size:.85rem;opacity:.85;margin-top:4px}}
  header .sub{{font-size:.75rem;opacity:.7;font-style:italic;margin-top:2px}}
  header .oppdatert{{font-size:.7rem;opacity:.6;margin-top:6px}}
  .tabs{{display:flex;max-width:720px;margin:24px auto 0;padding:0 16px;border-radius:16px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
  .tab{{flex:1;padding:12px;font-weight:700;font-size:.85rem;border:none;cursor:pointer;transition:.2s;display:flex;align-items:center;justify-content:center;gap:8px}}
  .tab-nat{{background:#3b82f6;color:white}}
  .tab-nat.inactive{{background:white;color:#6b7280}}
  .tab-nat.inactive:hover{{background:#eff6ff}}
  .tab-lok{{background:#10b981;color:white}}
  .tab-lok.inactive{{background:white;color:#6b7280}}
  .tab-lok.inactive:hover{{background:#f0fdf4}}
  .badge{{background:rgba(255,255,255,.3);border-radius:99px;padding:2px 8px;font-size:.7rem}}
  .inactive .badge{{background:#e5e7eb;color:#6b7280}}
  .sources{{max-width:720px;margin:6px auto 0;padding:0 20px;font-size:.72rem;color:#9ca3af}}
  main{{max-width:720px;margin:0 auto;padding:16px}}
  .panel{{display:none}}.panel.active{{display:block}}
  .card{{border-radius:16px;border:2px solid;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
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
    document.querySelectorAll('.tab').forEach(t=>{{
      t.classList.add('inactive');
    }});
    document.getElementById('tab-'+tab).classList.remove('inactive');
  }}
</script>
</head>
<body>
<header>
  <div style="font-size:2.5rem">📰</div>
  <h1>JuniorNytt</h1>
  <div class="dato">{dato_str}</div>
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
<div class="sources" id="src-line">Kilder: NRK · Aftenposten · TV2</div>

<main>
  <div class="panel active" id="panel-nasjonal">{nat_cards}</div>
  <div class="panel" id="panel-lokal">{lok_cards}</div>
</main>

<footer>JuniorNytt • Laget for nysgjerrige barn 🌟</footer>

<script>
  document.getElementById('tab-lokal').addEventListener('click',()=>{{
    document.getElementById('src-line').textContent='Kilder: Vikebladet · Vestlandsnytt · Sunnmørsposten';
  }});
  document.getElementById('tab-nasjonal').addEventListener('click',()=>{{
    document.getElementById('src-line').textContent='Kilder: NRK · Aftenposten · TV2';
  }});
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("Henter nasjonale nyheter...")
    nasjonal = fetch(NASJONAL_PROMPT)
    print(f"  → {len(nasjonal)} saker")
    print("Henter lokale nyheter...")
    lokal = fetch(LOKAL_PROMPT)
    print(f"  → {len(lokal)} saker")
    html = build_html(nasjonal, lokal)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ docs/index.html er oppdatert!")
