"""
Registratore idrostufa WiNet (sola lettura) — v3

- Un thread interroga /ajax/get-registers e salva in MySQL solo i registri che cambiano
  (più uno snapshot completo ogni ora).
- La pagina web mostra i valori attuali e permette di:
  * dichiarare cosa mostra il display (stato, potenza, temperature): si salva con la foto
    di tutti i registri in quel momento;
  * dare un significato ai valori non ancora noti (es. fase 3 = "Fiamma presente");
  * dare un nome ai registri;
  * annotare le azioni fatte sulla stufa.

Se nel .env c'è THERMOROSSI_TOKEN, legge anche GetStatus e GetPower dal cloud Thermorossi
(solo lettura) e li salva accanto ai registri locali, dando un nome alle fasi in automatico.

Le tabelle mancanti vengono create all'avvio.
Avvio: python app.py   (UN SOLO processo: con più worker il poller partirebbe più volte)
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pymysql
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template_string, request

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

STUFA_URL = os.getenv("STUFA_URL", "").rstrip("/")
if not STUFA_URL:
    raise SystemExit("Imposta STUFA_URL nel file .env (es. http://192.168.1.50)")
FAST_S = float(os.getenv("POLL_FAST_S", "5"))
SLOW_S = float(os.getenv("POLL_SLOW_S", "60"))
SLOW_CATS = [int(c) for c in os.getenv("SLOW_CATS", "2,3").split(",") if c.strip()]
SNAPSHOT_S = float(os.getenv("SNAPSHOT_S", "3600"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_S", "4"))
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8095"))
TZ = ZoneInfo(os.getenv("TZ_LOCALE", "Europe/Rome"))
CLOUD_TOKEN = os.getenv("THERMOROSSI_TOKEN", "").strip()
CLOUD_BASE = os.getenv("THERMOROSSI_URL", "https://wsthermorossi.cloudwinet.it/WiNetStove.svc/json").rstrip("/")
CLOUD_S = float(os.getenv("CLOUD_POLL_S", "60"))

DB = dict(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "stufa"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "stufa"),
    charset="utf8mb4",
    autocommit=True,
)

REG_FASE = 6
# Nomi iniziali (categoria 1): si modificano poi dalla pagina.
NOMI_INIZIALI = {
    18: "Temperatura acqua (°C)",
    112: "Temperatura target (°C)",
    6: "Fase",
    0: "Contatore eventi (si azzera senza corrente)",
    1: "Fuori casa",
    12: "Potenza attuale?",
    7: "Segnali a bit?",
    21: "Altra temperatura?",
    22: "Orologio stufa",
    23: "Segnale dopo modifica?",
}
REG_OROLOGIO = 22
SIGNIFICATI_INIZIALI = {(1, REG_FASE, 1): "Spenta", (1, REG_FASE, 2): "Accensione"}
# Suggerimenti per il campo "stato sul display" (si può scrivere anche altro).
STATI_SUGGERITI = [
    "Spenta", "Accensione", "Caricamento pellet", "Attesa fiamma", "Fiamma presente",
    "Lavoro", "Modulazione", "Pulizia braciere", "Pulizia finale", "Stand-by",
    "Temperatura raggiunta", "Spegnimento", "Allarme",
]

DDL = [
    """CREATE TABLE IF NOT EXISTS registri (
      id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, ts DATETIME(3) NOT NULL,
      cat TINYINT UNSIGNED NOT NULL, reg SMALLINT UNSIGNED NOT NULL, valore INT NOT NULL,
      KEY idx_ts (ts), KEY idx_cat_reg_ts (cat, reg, ts)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eventi (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, ts DATETIME(3) NOT NULL,
      testo VARCHAR(255) NOT NULL, KEY idx_ts (ts)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS errori (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, ts DATETIME(3) NOT NULL,
      messaggio VARCHAR(500) NOT NULL, KEY idx_ts (ts)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS osservazioni (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, ts DATETIME(3) NOT NULL,
      stato VARCHAR(100) NULL, potenza VARCHAR(20) NULL,
      acqua SMALLINT NULL, fumi SMALLINT NULL, target SMALLINT NULL,
      note VARCHAR(255) NULL, registri TEXT NOT NULL,
      KEY idx_ts (ts)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS nomi_registri (
      cat TINYINT UNSIGNED NOT NULL, reg SMALLINT UNSIGNED NOT NULL, nome VARCHAR(100) NOT NULL,
      PRIMARY KEY (cat, reg)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS significati (
      cat TINYINT UNSIGNED NOT NULL, reg SMALLINT UNSIGNED NOT NULL, valore INT NOT NULL,
      testo VARCHAR(100) NOT NULL, PRIMARY KEY (cat, reg, valore)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS cloud_stato (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, ts DATETIME(3) NOT NULL,
      status INT NULL, descrizione VARCHAR(100) NULL, potenza INT NULL,
      reg6 INT NULL, reg12 INT NULL, registri TEXT NOT NULL,
      KEY idx_ts (ts)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("stufa")


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def db_connect():
    return pymysql.connect(**DB)


def db_exec(sql, args=None, fetch=False):
    conn = db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall() if fetch else cur.lastrowid
    finally:
        conn.close()


def db_init():
    conn = db_connect()
    with conn.cursor() as cur:
        for ddl in DDL:
            cur.execute(ddl)
        cur.executemany("INSERT IGNORE INTO nomi_registri (cat, reg, nome) VALUES (1,%s,%s)",
                        list(NOMI_INIZIALI.items()))
        cur.executemany("INSERT IGNORE INTO significati (cat, reg, valore, testo) VALUES (%s,%s,%s,%s)",
                        [(*k, v) for k, v in SIGNIFICATI_INIZIALI.items()])
    conn.close()
    log.info("Tabelle pronte")


def leggi_dizionari():
    nomi = {str(r): n for r, n in db_exec("SELECT reg, nome FROM nomi_registri WHERE cat=1", fetch=True)}
    sig = {}
    for r, v, t in db_exec("SELECT reg, valore, testo FROM significati WHERE cat=1", fetch=True):
        sig.setdefault(str(r), {})[str(v)] = t
    return nomi, sig


def da_locale(ts):
    return ts.replace(tzinfo=timezone.utc).astimezone(TZ).strftime("%d/%m %H:%M:%S")


def intero_o_none(s):
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return None


class Poller(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="poller")
        self.sess = requests.Session()
        self.ultimi = {}
        self.attuali = {}
        self.ultimo_snapshot = {}
        self.rssi = None
        self.ultima_lettura = None
        self.ultimo_errore = None
        self._err_log = (None, 0.0)
        self.lock = threading.Lock()
        self.conn = None

    def _db(self):
        if self.conn is not None:
            try:
                self.conn.ping()
            except pymysql.MySQLError:
                self.conn = None
        if self.conn is None:
            self.conn = db_connect()
        return self.conn

    def leggi(self, cat):
        r = self.sess.post(f"{STUFA_URL}/ajax/get-registers",
                           data={"key": "020", "category": str(cat)}, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        j = r.json()
        return j, {int(a): int(b) for a, b in j.get("registers", [])}

    def salva(self, cat, regs):
        ora = time.monotonic()
        forza = ora - self.ultimo_snapshot.get(cat, 0) >= SNAPSHOT_S
        ts = utc_now()
        righe = [(ts, cat, reg, val) for reg, val in regs.items()
                 if forza or self.ultimi.get((cat, reg)) != val]
        if righe:
            with self._db().cursor() as cur:
                cur.executemany("INSERT INTO registri (ts, cat, reg, valore) VALUES (%s,%s,%s,%s)", righe)
        for _, c, reg, val in righe:
            self.ultimi[(c, reg)] = val
        if forza:
            self.ultimo_snapshot[cat] = ora
        return len(righe)

    def errore(self, msg):
        with self.lock:
            self.ultimo_errore = (utc_now(), msg)
        log.warning(msg)
        ultimo_msg, quando = self._err_log
        if msg != ultimo_msg or time.monotonic() - quando > 300:
            self._err_log = (msg, time.monotonic())
            try:
                with self._db().cursor() as cur:
                    cur.execute("INSERT INTO errori (ts, messaggio) VALUES (%s,%s)", (utc_now(), msg[:500]))
            except Exception as e:
                log.error("Impossibile salvare l'errore nel DB: %s", e)
                self.conn = None

    def run(self):
        prossima_lenta = 0.0
        log.info("Poller avviato su %s (cat 1 ogni %ss, cat %s ogni %ss)", STUFA_URL, FAST_S, SLOW_CATS, SLOW_S)
        while True:
            t0 = time.monotonic()
            cats = [1]
            if t0 >= prossima_lenta:
                cats += SLOW_CATS
                prossima_lenta = t0 + SLOW_S
            for cat in cats:
                try:
                    meta, regs = self.leggi(cat)
                    n = self.salva(cat, regs)
                    with self.lock:
                        self.attuali[cat] = regs
                        self.rssi = meta.get("rssi")
                        self.ultima_lettura = utc_now()
                    if n:
                        log.info("cat %s: %s valori salvati", cat, n)
                except requests.RequestException as e:
                    self.errore(f"Stufa non raggiungibile (cat {cat}): {e}")
                except pymysql.MySQLError as e:
                    self.conn = None
                    self.errore(f"Errore MySQL: {e}")
                except Exception as e:
                    self.errore(f"Errore cat {cat}: {e!r}")
            time.sleep(max(0.5, FAST_S - (time.monotonic() - t0)))

    def foto(self):
        with self.lock:
            return dict(self.attuali.get(1, {}))

    def stato(self):
        with self.lock:
            return {
                "ultima_lettura": self.ultima_lettura.isoformat() + "Z" if self.ultima_lettura else None,
                "rssi": self.rssi,
                "errore": ({"ts": self.ultimo_errore[0].isoformat() + "Z", "messaggio": self.ultimo_errore[1]}
                           if self.ultimo_errore else None),
                "cat1": {str(k): v for k, v in sorted(self.attuali.get(1, {}).items())},
            }


def senza_token(testo):
    return str(testo).replace(CLOUD_TOKEN, "***") if CLOUD_TOKEN else str(testo)


class CloudPoller(threading.Thread):
    """Legge GetStatus e GetPower dal cloud Thermorossi (solo lettura)."""

    def __init__(self, poller):
        super().__init__(daemon=True, name="cloud")
        self.poller = poller
        self.sess = requests.Session()
        self.ultimo = None
        self.lock = threading.Lock()

    def chiama(self, operazione):
        r = self.sess.get(f"{CLOUD_BASE}/{operazione}/{CLOUD_TOKEN}", timeout=10)
        r.raise_for_status()
        j = r.json()
        if not j.get("Success", False):
            raise RuntimeError(f"{operazione}: {j.get('ErrorDescription') or j.get('Error')}")
        return j

    def run(self):
        log.info("Lettura cloud attiva (ogni %ss)", CLOUD_S)
        while True:
            try:
                st = self.chiama("GetStatus")
                pw = self.chiama("GetPower")
                status, descr, potenza = st.get("Status"), st.get("StatusDescription"), pw.get("Result")
                foto = self.poller.foto()
                reg6, reg12 = foto.get(REG_FASE), foto.get(12)
                db_exec("INSERT INTO cloud_stato (ts, status, descrizione, potenza, reg6, reg12, registri) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (utc_now(), status, (descr or "")[:100] or None, potenza, reg6, reg12,
                         json.dumps({str(k): v for k, v in foto.items()})))
                # La fase locale prende il nome dal cloud, se i due numeri coincidono e non ha ancora un nome.
                if descr and status is not None and status == reg6:
                    db_exec("INSERT IGNORE INTO significati (cat, reg, valore, testo) VALUES (1,%s,%s,%s)",
                            (REG_FASE, reg6, descr[:100]))
                with self.lock:
                    self.ultimo = {"ts": utc_now().isoformat() + "Z", "status": status,
                                   "descrizione": descr, "potenza": potenza, "errore": None}
            except Exception as e:
                msg = senza_token(e)
                log.warning("Cloud: %s", msg)
                with self.lock:
                    self.ultimo = {"ts": utc_now().isoformat() + "Z", "errore": msg[:300]}
            time.sleep(CLOUD_S)

    def stato(self):
        with self.lock:
            return self.ultimo


poller = Poller()
cloud = CloudPoller(poller) if CLOUD_TOKEN else None
app = Flask(__name__)

AZIONI_RAPIDE = [
    "Accesa da pannello", "Spenta da pannello", "Accesa da app", "Spenta da app",
    "Potenza 1", "Potenza 2", "Potenza 3", "Potenza 4", "Potenza 5 (auto)",
    "Target +1 °C", "Target −1 °C", "Carico pellet",
]

STILE = """
:root{--carta:#eef2f3;--inchiostro:#1d2b33;--acqua:#2b6f8f;--fiamma:#c8741f;--tenue:#6b7a82;--riga:#d3dcdf;--fondo:#ffffff;--avviso:#fbf1e4}
@media (prefers-color-scheme:dark){:root{--carta:#151c20;--inchiostro:#e3eaed;--acqua:#6fb3d2;--fiamma:#e39a4c;--tenue:#93a3aa;--riga:#2b363c;--fondo:#1c252a;--avviso:#2e2418;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--carta);color:var(--inchiostro);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:880px;margin:0 auto;padding:24px 16px 48px}
nav{display:flex;gap:16px;margin-bottom:12px;font-size:15px}
nav a{color:var(--acqua)}
.quadrante{display:flex;gap:32px;align-items:flex-end;flex-wrap:wrap;padding:8px 0 20px;border-bottom:2px solid var(--inchiostro)}
.acqua{font-size:clamp(64px,14vw,120px);font-weight:700;line-height:.9;color:var(--acqua);font-variant-numeric:tabular-nums}
.acqua small{font-size:.35em;font-weight:500}
.target{font-size:20px;color:var(--tenue)}
.target b{color:var(--inchiostro);font-variant-numeric:tabular-nums}
.fase{margin-left:auto;font-size:20px;font-weight:600}
.fase.accesa{color:var(--fiamma)}
.stato{font-size:14px;color:var(--tenue);margin:8px 0 20px}
.stato.ko{color:#b3261e}
.ignota{background:var(--avviso);border-left:4px solid var(--fiamma);padding:12px 14px;margin:0 0 20px;border-radius:0 6px 6px 0}
.ignota p{margin:0 0 8px}
h2{font-size:18px;margin:28px 0 10px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th{text-align:left;font-size:14px;color:var(--tenue);font-weight:500;padding:6px 8px;border-bottom:1px solid var(--riga)}
td{padding:6px 8px;border-bottom:1px solid var(--riga);vertical-align:top}
td.n{width:56px;color:var(--tenue)}td.v{text-align:right;font-weight:600;width:90px}
tr.cambiato td.v{color:var(--fiamma)}
.rapide{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
button{font:inherit;padding:8px 12px;border:1px solid var(--acqua);background:var(--fondo);color:var(--inchiostro);border-radius:6px;cursor:pointer}
button:hover{background:var(--acqua);color:#fff}
button.primario{background:var(--acqua);color:#fff}
button.link{border:0;padding:0;background:none;color:var(--acqua);text-decoration:underline;font-size:14px}
button.link:hover{background:none;color:var(--acqua)}
button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid var(--fiamma);outline-offset:2px}
form.riga{display:flex;gap:8px;flex-wrap:wrap}
input,select{font:inherit;padding:8px 10px;border:1px solid var(--riga);border-radius:6px;background:var(--fondo);color:var(--inchiostro)}
form.riga input[type=text]{flex:1;min-width:200px}
.griglia{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:12px}
.griglia label{display:flex;flex-direction:column;font-size:14px;color:var(--tenue);gap:4px}
.griglia label.largo{grid-column:1/-1}
.aiuto{font-size:14px;color:var(--tenue);margin:-4px 0 12px}
ol.eventi{list-style:none;padding:0;margin:0}
ol.eventi li{padding:6px 0;border-bottom:1px solid var(--riga)}
time{color:var(--tenue);font-variant-numeric:tabular-nums;margin-right:12px;white-space:nowrap}
.scorri{overflow-x:auto}
.ok{background:#e3f1e6;color:#1e5e2f;padding:8px 12px;border-radius:6px;margin-bottom:16px}
@media (prefers-color-scheme:dark){.ok{background:#1d3324;color:#a9dcb5}}
"""

PAGINA = """<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Idrostufa · registratore</title><style>{{stile|safe}}</style></head><body><main>
<nav><a href="./">Stufa</a><a href="osservazioni">Osservazioni salvate</a><a href="cloud">Confronto cloud</a></nav>
{% if msg %}<p class="ok" role="status">{{msg}}</p>{% endif %}
<section class="quadrante" aria-live="polite">
  <div class="acqua"><span id="acqua">–</span><small> °C</small></div>
  <div class="target">target <b id="target">–</b> °C</div>
  <div class="fase" id="fase">–</div>
</section>
<p class="stato" id="stato">In attesa della prima lettura…</p>
<p class="stato" id="cloud" hidden></p>

<div class="ignota" id="faseIgnota" hidden>
  <p>La stufa è in <b>fase <span id="faseVal"></span></b>, che non conosciamo ancora. Cosa mostra il display?</p>
  <form class="riga" method="post" action="significato">
    <input type="hidden" name="reg" value="{{reg_fase}}">
    <input type="hidden" name="valore" id="faseValInput">
    <label for="faseTesto" hidden>Stato sul display</label>
    <input id="faseTesto" name="testo" type="text" list="stati" maxlength="100" required placeholder="Es. Fiamma presente">
    <button class="primario">Salva significato</button>
  </form>
</div>

<h2>Cosa vedi sulla stufa</h2>
<p class="aiuto">Compila solo quello che leggi sul display: si salva insieme a tutti i registri di questo momento.</p>
<form method="post" action="osservazione">
  <div class="griglia">
    <label>Stato sul display<input name="stato" type="text" list="stati" maxlength="100"></label>
    <label>Potenza<select name="potenza"><option value="">—</option>{% for p in ["1","2","3","4","5","Auto"] %}<option>{{p}}</option>{% endfor %}</select></label>
    <label>Acqua °C<input name="acqua" type="number" inputmode="numeric"></label>
    <label>Fumi °C<input name="fumi" type="number" inputmode="numeric"></label>
    <label>Target °C<input name="target" type="number" inputmode="numeric"></label>
    <label class="largo">Note<input name="note" type="text" maxlength="255" placeholder="Es. ventola fumi accesa, fiamma bassa"></label>
  </div>
  <button class="primario">Salva osservazione</button>
</form>
<datalist id="stati">{% for s in stati %}<option value="{{s}}">{% endfor %}</datalist>

<h2>Annota cosa hai fatto</h2>
<div class="rapide">
{% for a in azioni %}<form method="post" action="evento"><input type="hidden" name="testo" value="{{a}}"><button>{{a}}</button></form>{% endfor %}
</div>
<form class="riga" method="post" action="evento">
  <label for="testo" hidden>Annotazione</label>
  <input id="testo" name="testo" type="text" maxlength="255" placeholder="Es. target portato a 72 dal pannello" required>
  <button>Salva annotazione</button>
</form>

<h2>Registri categoria 1</h2>
<label class="aiuto"><input type="checkbox" id="tutti" onchange="aggiorna()"> Mostra anche i registri a zero</label>
<div class="scorri"><table>
<thead><tr><th>Reg.</th><th>Nome</th><th>Valore</th><th>Significato</th></tr></thead>
<tbody id="registri"></tbody></table></div>

<h2>Ultime annotazioni</h2>
{% if eventi %}<ol class="eventi">{% for e in eventi %}<li><time>{{e.ts}}</time>{{e.testo}}</li>{% endfor %}</ol>
{% else %}<p>Nessuna annotazione. Premi un pulsante qui sopra quando agisci sulla stufa.</p>{% endif %}
</main>
<script>
const REG_FASE = "{{reg_fase}}";
let prec = {};
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
async function invia(url, dati){
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(dati)});
  if (!r.ok) alert("Salvataggio non riuscito ("+r.status+")");
  aggiorna();
}
function rinomina(reg, attuale){
  const nome = prompt("Nome del registro "+reg, attuale || "");
  if (nome !== null) invia("nome", {reg, nome});
}
function significa(reg, valore, attuale){
  const testo = prompt("Cosa significa il valore "+valore+" nel registro "+reg+"?", attuale || "");
  if (testo !== null) invia("significato", {reg, valore, testo});
}
async function aggiorna(){
  try{
    const s = await (await fetch("api/stato")).json();
    const r = s.cat1 || {}, nomi = s.nomi || {}, sig = s.significati || {};
    document.getElementById("acqua").textContent = r["18"] ?? "–";
    document.getElementById("target").textContent = r["112"] ?? "–";
    const f = r[REG_FASE], el = document.getElementById("fase");
    const testoFase = f === undefined ? null : (sig[REG_FASE] || {})[f];
    el.textContent = f === undefined ? "–" : (testoFase || "Fase " + f);
    el.className = "fase" + (f && f !== 1 ? " accesa" : "");
    const box = document.getElementById("faseIgnota");
    if (f !== undefined && !testoFase){
      if (document.getElementById("faseValInput").value != f){
        document.getElementById("faseVal").textContent = f;
        document.getElementById("faseValInput").value = f;
      }
      box.hidden = false;
    } else box.hidden = true;
    const st = document.getElementById("stato");
    if (s.errore && (!s.ultima_lettura || s.errore.ts > s.ultima_lettura)){
      st.className = "stato ko"; st.textContent = s.errore.messaggio;
    } else if (s.ultima_lettura){
      st.className = "stato";
      st.textContent = "Ultima lettura " + new Date(s.ultima_lettura).toLocaleTimeString("it-IT") + " · segnale " + s.rssi + " dBm";
    }
    const c = s.cloud, cl = document.getElementById("cloud");
    if (c){
      cl.hidden = false;
      cl.className = "stato" + (c.errore ? " ko" : "");
      cl.textContent = c.errore ? "Cloud: " + c.errore :
        "Cloud Thermorossi: " + c.descrizione + " (stato " + c.status + ") · potenza " + c.potenza;
    }
    const tutti = document.getElementById("tutti").checked;
    const GIORNI = ["lun","mar","mer","gio","ven","sab","dom"];
    document.getElementById("registri").innerHTML = Object.entries(r).filter(([k,v]) => tutti || v !== 0 || nomi[k]).map(([k,v]) => {
      let m = (sig[k] || {})[v];
      if (!m && k === "{{reg_orologio}}") m = (GIORNI[v >> 11] || "?") + " " + String((v >> 6) & 31).padStart(2,"0") + ":" + String(v & 63).padStart(2,"0");
      return `<tr class="${prec[k] !== undefined && prec[k] !== v ? "cambiato" : ""}"><td class="n">${k}</td>`+
        `<td>${esc(nomi[k] || "")} <button class="link" onclick='rinomina(${k}, ${JSON.stringify(nomi[k]||"")})'>${nomi[k] ? "modifica" : "dai un nome"}</button></td>`+
        `<td class="v">${v}</td>`+
        `<td>${esc(m || "")} <button class="link" onclick='significa(${k}, ${v}, ${JSON.stringify(m||"")})'>${m ? "modifica" : "cosa significa?"}</button></td></tr>`;
    }).join("");
    prec = r;
  }catch(e){ document.getElementById("stato").textContent = "Pagina non aggiornata: " + e; }
}
aggiorna(); setInterval(aggiorna, 5000);
</script></body></html>"""

PAGINA_OSSERVAZIONI = """<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Idrostufa · osservazioni</title><style>{{stile|safe}}</style></head><body><main>
<nav><a href="./">Stufa</a><a href="osservazioni">Osservazioni salvate</a></nav>
<h2>Osservazioni salvate</h2>
{% if righe %}
<p class="aiuto">Ogni riga è quello che hai letto sul display, affiancato ai registri in quel momento. Cerca le colonne che si muovono insieme a ciò che hai visto.</p>
<div class="scorri"><table>
<thead><tr><th>Quando</th><th>Display</th><th>Potenza</th><th>Acqua</th><th>Fumi</th><th>Target</th>
{% for r in colonne %}<th title="{{nomi.get(r|string,'')}}">r{{r}}</th>{% endfor %}<th>Note</th></tr></thead>
<tbody>{% for o in righe %}<tr><td><time>{{o.ts}}</time></td><td>{{o.stato or ""}}</td><td>{{o.potenza or ""}}</td>
<td>{{o.acqua if o.acqua is not none else ""}}</td><td>{{o.fumi if o.fumi is not none else ""}}</td><td>{{o.target if o.target is not none else ""}}</td>
{% for r in colonne %}<td>{{o.reg.get(r|string, "")}}</td>{% endfor %}<td>{{o.note or ""}}</td></tr>{% endfor %}</tbody>
</table></div>
{% else %}<p>Nessuna osservazione salvata. Dalla pagina principale compila “Cosa vedi sulla stufa”.</p>{% endif %}
</main></body></html>"""


def risposta(msg):
    if request.is_json:
        return jsonify(ok=True, msg=msg)
    return redirect("./?msg=" + requests.utils.quote(msg))


def dati_richiesta():
    return request.get_json(silent=True) or request.form


@app.get("/")
def home():
    eventi = []
    try:
        for ts, testo in db_exec("SELECT ts, testo FROM eventi ORDER BY ts DESC LIMIT 30", fetch=True):
            eventi.append({"ts": da_locale(ts), "testo": testo})
    except pymysql.MySQLError as e:
        log.error("Lettura eventi: %s", e)
    return render_template_string(PAGINA, stile=STILE, azioni=AZIONI_RAPIDE, eventi=eventi,
                                  stati=STATI_SUGGERITI, reg_fase=REG_FASE, reg_orologio=REG_OROLOGIO,
                                  msg=request.args.get("msg"))


@app.post("/evento")
def evento():
    testo = (dati_richiesta().get("testo") or "").strip()
    if testo:
        db_exec("INSERT INTO eventi (ts, testo) VALUES (%s,%s)", (utc_now(), testo[:255]))
    return risposta("Annotazione salvata")


@app.post("/osservazione")
def osservazione():
    d = dati_richiesta()
    foto = poller.foto()
    stato = (d.get("stato") or "").strip()[:100] or None
    potenza = (d.get("potenza") or "").strip()[:20] or None
    acqua, fumi, target = (intero_o_none(d.get(k)) for k in ("acqua", "fumi", "target"))
    note = (d.get("note") or "").strip()[:255] or None
    if not any([stato, potenza, note, acqua is not None, fumi is not None, target is not None]):
        return risposta("Niente da salvare: compila almeno un campo")
    ts = utc_now()
    db_exec("INSERT INTO osservazioni (ts, stato, potenza, acqua, fumi, target, note, registri) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (ts, stato, potenza, acqua, fumi, target, note, json.dumps({str(k): v for k, v in foto.items()})))
    parti = [p for p in [stato, potenza and f"potenza {potenza}",
                         acqua is not None and f"acqua {acqua}", fumi is not None and f"fumi {fumi}",
                         target is not None and f"target {target}", note] if p]
    db_exec("INSERT INTO eventi (ts, testo) VALUES (%s,%s)", (ts, ("Display: " + ", ".join(parti))[:255]))
    # Se la fase attuale non ha ancora un significato, lo prende dallo stato dichiarato.
    if not foto:
        return risposta("Osservazione salvata, ma senza registri: la stufa in questo momento non risponde")
    msg = "Osservazione salvata"
    if stato and REG_FASE in foto:
        conn = db_connect()
        with conn.cursor() as cur:
            nuova = cur.execute("INSERT IGNORE INTO significati (cat, reg, valore, testo) VALUES (1,%s,%s,%s)",
                                (REG_FASE, foto[REG_FASE], stato))
        conn.close()
        if nuova:
            msg += f": la fase {foto[REG_FASE]} ora si chiama “{stato}”"
    return risposta(msg)


@app.post("/significato")
def significato():
    d = dati_richiesta()
    reg, valore = intero_o_none(d.get("reg")), intero_o_none(d.get("valore"))
    testo = (d.get("testo") or "").strip()[:100]
    if reg is None or valore is None:
        return risposta("Registro o valore mancante")
    if testo:
        db_exec("REPLACE INTO significati (cat, reg, valore, testo) VALUES (1,%s,%s,%s)", (reg, valore, testo))
    else:
        db_exec("DELETE FROM significati WHERE cat=1 AND reg=%s AND valore=%s", (reg, valore))
    return risposta(f"Registro {reg}, valore {valore}: significato salvato")


@app.post("/nome")
def nome():
    d = dati_richiesta()
    reg = intero_o_none(d.get("reg"))
    testo = (d.get("nome") or "").strip()[:100]
    if reg is None:
        return risposta("Registro mancante")
    if testo:
        db_exec("REPLACE INTO nomi_registri (cat, reg, nome) VALUES (1,%s,%s)", (reg, testo))
    else:
        db_exec("DELETE FROM nomi_registri WHERE cat=1 AND reg=%s", (reg,))
    return risposta(f"Registro {reg}: nome salvato")


@app.get("/osservazioni")
def osservazioni():
    righe, colonne = [], set()
    for ts, stato, pot, acqua, fumi, target, note, reg in db_exec(
            "SELECT ts, stato, potenza, acqua, fumi, target, note, registri FROM osservazioni "
            "ORDER BY ts DESC LIMIT 200", fetch=True):
        regs = json.loads(reg or "{}")
        colonne.update(int(k) for k, v in regs.items() if v)
        righe.append(dict(ts=da_locale(ts), stato=stato, potenza=pot, acqua=acqua, fumi=fumi,
                          target=target, note=note, reg=regs))
    nomi, _ = leggi_dizionari()
    return render_template_string(PAGINA_OSSERVAZIONI, stile=STILE, righe=righe,
                                  colonne=sorted(colonne), nomi=nomi)


PAGINA_CLOUD = """<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Idrostufa · confronto cloud</title><style>{{stile|safe}}</style></head><body><main>
<nav><a href="./">Stufa</a><a href="osservazioni">Osservazioni salvate</a><a href="cloud">Confronto cloud</a></nav>
<h2>Cloud Thermorossi e registri locali</h2>
{% if not attivo %}<p>La lettura del cloud è spenta: aggiungi <code>THERMOROSSI_TOKEN</code> al file .env e riavvia il servizio.</p>{% endif %}
{% if righe %}
<p class="aiuto">Sono mostrati solo i cambi di stato o potenza. “Coincide” indica che lo stato del cloud è uguale al registro 6 e la potenza al registro 12.</p>
<div class="scorri"><table>
<thead><tr><th>Quando</th><th>Cloud stato</th><th>Descrizione</th><th>Cloud potenza</th><th>Reg 6</th><th>Reg 12</th><th>Coincide</th></tr></thead>
<tbody>{% for o in righe %}<tr><td><time>{{o.ts}}</time></td><td>{{o.status}}</td><td>{{o.descrizione or ""}}</td><td>{{o.potenza}}</td>
<td>{{o.reg6}}</td><td>{{o.reg12}}</td><td>{{"sì" if o.coincide else "no"}}</td></tr>{% endfor %}</tbody>
</table></div>
{% elif attivo %}<p>Ancora nessuna lettura dal cloud: la prima arriva entro un minuto dall'avvio.</p>{% endif %}
</main></body></html>"""


@app.get("/cloud")
def pagina_cloud():
    righe, prec = [], None
    for ts, st, de, pw, r6, r12 in db_exec(
            "SELECT ts, status, descrizione, potenza, reg6, reg12 FROM cloud_stato "
            "ORDER BY ts DESC LIMIT 2000", fetch=True)[::-1]:
        chiave = (st, de, pw, r6, r12)
        if chiave != prec:
            righe.append(dict(ts=da_locale(ts), status=st, descrizione=de, potenza=pw, reg6=r6, reg12=r12,
                              coincide=(st == r6 and pw == r12)))
            prec = chiave
    return render_template_string(PAGINA_CLOUD, stile=STILE, righe=righe[::-1][:200], attivo=bool(cloud))


@app.get("/api/stato")
def api_stato():
    s = poller.stato()
    s["cloud"] = cloud.stato() if cloud else None
    try:
        s["nomi"], s["significati"] = leggi_dizionari()
    except pymysql.MySQLError as e:
        log.error("Lettura dizionari: %s", e)
    return jsonify(s)


if __name__ == "__main__":
    db_init()
    poller.start()
    if cloud:
        cloud.start()
    from waitress import serve
    log.info("Pagina web su http://%s:%s", WEB_HOST, WEB_PORT)
    serve(app, host=WEB_HOST, port=WEB_PORT, threads=4)
