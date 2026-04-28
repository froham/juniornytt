const SRC = {
  nasjonal: "Kjelder: NRK · Aftenposten · VG · TV2",
  lokal:    "Kjelder: Vikebladet · Vestlandsnytt · Sunnmørsposten",
  spel:     "Kjelder: VG Sport · Aftenposten Sport · Nintendo Life · Pocket Gamer · NRK Sport"
};

function show(tab) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.getElementById("panel-" + tab).classList.add("active");
  document.querySelectorAll(".tab").forEach(t => t.classList.add("inactive"));
  document.getElementById("tab-" + tab).classList.remove("inactive");
  document.getElementById("src-line").textContent = SRC[tab] || "";
  document.getElementById("varsel-spel").style.display = tab === "spel" ? "block" : "none";
}

function toggleLenker() {
  const toggle = document.getElementById("foreldre-toggle");
  const tekst  = document.getElementById("foreldre-tekst");
  const on = toggle.classList.toggle("on");
  if (on) {
    document.body.setAttribute("class", "lenker-paa");
    tekst.textContent = "Foreldremodus - lenker er synlege";
  } else {
    document.body.removeAttribute("class");
    tekst.textContent = "Foreldremodus";
  }
}

// Admin
const ADMIN_PASSORD = "juniornytt2026"; // byt ut med eige passord
const GH_REPO      = "froham/juniornytt";
const GH_FILE      = "redaksjon.json";
const GH_WORKFLOW  = "update.yml";
let adminPaa = false;
let ghToken  = "";
let redaksjon = { skjulte: [], redigerte: {} };
let aktivKortId = null;

async function adminLogin() {
  const pw = prompt("Adminpassord:");
  if (pw !== ADMIN_PASSORD) { if (pw !== null) alert("Feil passord."); return; }
  const token = prompt("GitHub Personal Access Token (repo-tilgang):");
  if (!token) return;
  ghToken = token;
  adminPaa = true;
  document.body.classList.add("admin-paa");
  document.getElementById("admin-bar").classList.add("open");
  await lastRedaksjon();
}

function adminLoggUt() {
  adminPaa = false; ghToken = "";
  document.body.classList.remove("admin-paa");
  document.getElementById("admin-bar").classList.remove("open");
}

async function lastRedaksjon() {
  try {
    const r = await fetch(
      "https://api.github.com/repos/" + GH_REPO + "/contents/" + GH_FILE,
      { headers: { Authorization: "token " + ghToken, Accept: "application/vnd.github.v3+json" } }
    );
    if (r.ok) {
      const data = await r.json();
      redaksjon = JSON.parse(atob(data.content));
    }
  } catch(e) { console.log("Ingen redaksjon.json enda."); }
  redaksjon.skjulte.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.classList.add("skjult");
      const k = el.querySelector(".skjul-knapp");
      if (k) k.textContent = "Vis";
    }
  });
}

async function lagreRedaksjon() {
  const skjultAntall   = redaksjon.skjulte.length;
  const redigertAntall = Object.keys(redaksjon.redigerte || {}).length;
  const ok = confirm(
    "Er du sikker pa at du vil publisere?\n\n" +
    "- " + skjultAntall + " sak(er) skjult\n" +
    "- " + redigertAntall + " sak(er) redigert\n\n" +
    "Sida vert oppdatert for alle om ca 1 minutt."
  );
  if (!ok) return;

  const status = document.getElementById("publiser-status");
  const btns   = document.querySelectorAll(".admin-btn");
  btns.forEach(b => b.disabled = true);
  status.style.display = "block";
  status.textContent = "Lagrar til GitHub...";

  try {
    let sha = "";
    const r = await fetch(
      "https://api.github.com/repos/" + GH_REPO + "/contents/" + GH_FILE,
      { headers: { Authorization: "token " + ghToken } }
    );
    if (r.ok) { const d = await r.json(); sha = d.sha; }

    const innhald = btoa(unescape(encodeURIComponent(JSON.stringify(redaksjon, null, 2))));
    const body = { message: "redaksjon: oppdater", content: innhald };
    if (sha) body.sha = sha;
    await fetch(
      "https://api.github.com/repos/" + GH_REPO + "/contents/" + GH_FILE,
      { method: "PUT",
        headers: { Authorization: "token " + ghToken, "Content-Type": "application/json" },
        body: JSON.stringify(body) }
    );

    status.textContent = "Triggar ny bygg...";
    await fetch(
      "https://api.github.com/repos/" + GH_REPO + "/actions/workflows/" + GH_WORKFLOW + "/dispatches",
      { method: "POST",
        headers: { Authorization: "token " + ghToken, "Content-Type": "application/json" },
        body: JSON.stringify({ ref: "main" }) }
    );

    status.textContent = "Publisert!\nSida vert oppdatert om ca 1 min.";
    setTimeout(() => { status.style.display = "none"; btns.forEach(b => b.disabled = false); }, 4000);
  } catch(e) {
    status.textContent = "Feil: " + e.message;
    setTimeout(() => { status.style.display = "none"; btns.forEach(b => b.disabled = false); }, 5000);
  }
}

function skjulKort(id) {
  const el = document.getElementById(id);
  const erSkjult = el.classList.contains("skjult");
  if (erSkjult) {
    el.classList.remove("skjult");
    redaksjon.skjulte = redaksjon.skjulte.filter(s => s !== id);
  } else {
    el.classList.add("skjult");
    if (!redaksjon.skjulte.includes(id)) redaksjon.skjulte.push(id);
  }
  const knapp = el.querySelector(".skjul-knapp");
  if (knapp) knapp.textContent = erSkjult ? "Skjul" : "Vis";
}

function opneRediger(id) {
  aktivKortId = id;
  const el = document.getElementById(id);
  document.getElementById("modal-tittel").value    = el.querySelector("h3").textContent;
  document.getElementById("modal-brodtekst").value = el.querySelector("p").textContent;
  document.getElementById("admin-modal").classList.add("open");
}

function lukkModal() {
  document.getElementById("admin-modal").classList.remove("open");
  aktivKortId = null;
}

function lagreRedigering() {
  if (!aktivKortId) return;
  const tittel    = document.getElementById("modal-tittel").value.trim();
  const brodtekst = document.getElementById("modal-brodtekst").value.trim();
  const el = document.getElementById(aktivKortId);
  el.querySelector("h3").textContent = tittel;
  el.querySelector("p").textContent  = brodtekst;
  if (!redaksjon.redigerte) redaksjon.redigerte = {};
  redaksjon.redigerte[aktivKortId] = { tittel, brodtekst };
  lukkModal();
}

function nullstillRedaksjon() {
  if (!confirm("Nullstill ALL skjuling og redigering?")) return;
  redaksjon = { skjulte: [], redigerte: {} };
  document.querySelectorAll(".card.skjult").forEach(c => c.classList.remove("skjult"));
  document.querySelectorAll(".skjul-knapp").forEach(k => k.textContent = "Skjul");
}
