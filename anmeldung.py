"""Gemeinsame Anmeldung für Essenplan (/essen/) und Vorratsschrank (/vorrat/) – per Cookie statt Basic-Auth.

GLEICHE DATEI in beiden Repos (Claude-Code und inventory) – Änderungen in beide übernehmen.

- Ein Familienpasswort, gespeichert nur als PBKDF2-Hash in <Domain>/.anmeldung/passwort.json
  (gesetzt mit manitu/passwort.py im Essenplan-Repo; der Ordner ist per .htaccess gesperrt).
- Nach der Anmeldung ein signierter Cookie für die ganze Domain (beide Apps), 180 Tage gültig und
  bei Nutzung automatisch verlängert. Neues Passwort = neues Geheimnis = alle Geräte abgemeldet.
- Nach 5 Fehlversuchen von einer Adresse 15 Minuten Pause.
- ANMELDUNG_DIR nicht gesetzt (lokaler Test) = Anmeldung aus. Gesetzt, aber nicht eingerichtet = alles gesperrt.
"""

import hashlib
import hmac
import html
import json
import os
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

COOKIE = "lup_anmeldung"
GUELTIG = 180 * 86400          # 6 Monate
VERLAENGERN_NACH = 86400       # höchstens einmal am Tag neu ausstellen
FEHLVERSUCHE, SPERRE = 5, 15 * 60
ITERATIONEN = 600_000


def _ordner():
    o = os.environ.get("ANMELDUNG_DIR")
    return Path(o) if o else None


def _daten():
    try:
        return json.loads((_ordner() / "passwort.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def hash_erzeugen(passwort, salz=None):
    salz = salz or os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", passwort.encode(), salz, ITERATIONEN)
    return f"pbkdf2_sha256${ITERATIONEN}${salz.hex()}${h.hex()}"


def _passwort_ok(passwort, gespeichert):
    try:
        verfahren, n, salz, soll = gespeichert.split("$")
        ist = hashlib.pbkdf2_hmac("sha256", passwort.encode(), bytes.fromhex(salz), int(n)).hex()
    except (ValueError, AttributeError):
        return False
    return verfahren == "pbkdf2_sha256" and hmac.compare_digest(ist, soll)


def _signatur(geheimnis, nutzlast):
    return hmac.new(bytes.fromhex(geheimnis), nutzlast.encode(), hashlib.sha256).hexdigest()


def _cookie_header(wert, max_age):
    return ("Set-Cookie", f"{COOKIE}={wert}; Max-Age={max_age}; Path=/; Secure; HttpOnly; SameSite=Lax")


def _neuer_cookie(geheimnis):
    nutzlast = str(int(time.time()))
    return _cookie_header(f"{nutzlast}.{_signatur(geheimnis, nutzlast)}", GUELTIG)


def angemeldet(environ):
    """(True/False, zusätzliche Header) – bei gültigem, älterem Cookie wird er verlängert."""
    if _ordner() is None:
        return True, []
    daten = _daten()
    if not daten:
        return False, []
    jar = SimpleCookie()
    try:
        jar.load(environ.get("HTTP_COOKIE", ""))
    except Exception:  # noqa: BLE001 – kaputter Cookie-Header = nicht angemeldet
        return False, []
    wert = jar[COOKIE].value if COOKIE in jar else ""
    ausgestellt, _, sig = wert.partition(".")
    if not ausgestellt.isdigit() or not hmac.compare_digest(sig, _signatur(daten["geheimnis"], ausgestellt)):
        return False, []
    alter = time.time() - int(ausgestellt)
    if not 0 <= alter < GUELTIG:
        return False, []
    return True, [_neuer_cookie(daten["geheimnis"])] if alter > VERLAENGERN_NACH else []


# ---------- Fehlversuche ----------

def _sperrdatei():
    return _ordner() / "sperre.json"


def _versuche(adresse):
    try:
        alle = json.loads(_sperrdatei().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        alle = {}
    jetzt = time.time()
    return {a: [t for t in ts if jetzt - t < SPERRE] for a, ts in alle.items()}, jetzt


def _gesperrt(adresse):
    alle, _ = _versuche(adresse)
    return len(alle.get(adresse, [])) >= FEHLVERSUCHE


def _fehlversuch(adresse, zuruecksetzen=False):
    alle, jetzt = _versuche(adresse)
    if zuruecksetzen:
        alle.pop(adresse, None)
    else:
        alle.setdefault(adresse, []).append(jetzt)
    alle = {a: ts for a, ts in alle.items() if ts}
    try:
        tmp = _sperrdatei().with_suffix(".tmp")
        tmp.write_text(json.dumps(alle), encoding="utf-8")
        os.replace(tmp, _sperrdatei())
    except OSError:
        pass


# ---------- Seiten ----------

def _seite(app_name, meldung=""):
    meldung_html = f'<p class="fehler" role="alert">{html.escape(meldung)}</p>' if meldung else ""
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">
<title>Anmelden – {html.escape(app_name)}</title>
<meta name="theme-color" content="#f2eee8" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0c0c11" media="(prefers-color-scheme: dark)">
<style>
:root {{ color-scheme: light dark; --text:#000; --muted:#6c6c70; --accent:#8944ab; --danger:#d70015;
  --glass:rgba(255,255,255,.72); --edge:rgba(255,255,255,.75); --fill:rgba(120,120,128,.13);
  --wall:radial-gradient(60% 50% at 15% 10%,rgba(255,255,255,.95),transparent 70%),radial-gradient(55% 45% at 90% 18%,#c4d2e4,transparent 70%),
    radial-gradient(70% 55% at 80% 95%,#e0c7a8,transparent 70%),radial-gradient(50% 45% at 5% 85%,#dccdee,transparent 70%),linear-gradient(160deg,#f3efe9,#ddd5ca); }}
@media (prefers-color-scheme: dark) {{ :root {{ --text:#fff; --muted:#aeaeb2; --accent:#9a4bd6; --danger:#ff6961;
  --glass:rgba(36,36,42,.62); --edge:rgba(255,255,255,.12); --fill:rgba(118,118,128,.24);
  --wall:radial-gradient(55% 45% at 12% 8%,#2b2546,transparent 70%),radial-gradient(50% 45% at 92% 25%,#17343a,transparent 70%),
    radial-gradient(65% 55% at 75% 95%,#3a2a20,transparent 70%),linear-gradient(160deg,#111118,#08080b); }} }}
* {{ box-sizing: border-box; }}
body {{ margin:0; min-height:100dvh; display:grid; place-items:center; padding:24px; background:var(--wall); color:var(--text);
  font:17px/1.4 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",system-ui,sans-serif; }}
form {{ width:min(380px,100%); padding:28px 24px; border-radius:28px; background:var(--glass); border:1px solid var(--edge);
  -webkit-backdrop-filter:saturate(180%) blur(28px); backdrop-filter:saturate(180%) blur(28px); box-shadow:0 10px 34px rgba(0,0,0,.12); }}
h1 {{ font-size:28px; margin:0 0 18px; }}
input {{ width:100%; min-height:54px; border:0; border-radius:16px; padding:14px 16px; font:inherit; font-size:18px; color:inherit; background:var(--fill); }}
button {{ width:100%; min-height:54px; margin-top:14px; border:0; border-radius:999px; background:var(--accent); color:#fff; font:inherit; font-weight:600; }}
.fehler {{ color:var(--danger); margin:12px 2px 0; }}
:focus-visible {{ outline:3px solid var(--accent); outline-offset:2px; }}
</style></head><body>
<form method="post" action="login">
  <h1>{html.escape(app_name)}</h1>
  <input type="password" name="passwort" autocomplete="current-password" aria-label="Passwort" placeholder="Passwort" required autofocus>
  <input type="text" name="benutzer" value="familie" autocomplete="username" hidden>
  {meldung_html}
  <button type="submit">Anmelden</button>
</form></body></html>""".encode("utf-8")


def anfrage(method, path, environ, eingabe, app_name, basis):
    """Anmelde-Seiten beantworten. Liefert (status, header, body) oder None (keine Anmelde-Route).
    basis = URL-Pfad der App ohne / am Ende (z. B. „/essen“)."""
    if path == "/abmelden":
        return 303, [_cookie_header("", 0), ("Location", f"{basis}/login")], b""
    if path != "/login":
        return None
    html_typ = ("Content-Type", "text/html; charset=utf-8")
    if _ordner() is None:
        return 303, [("Location", f"{basis}/")], b""
    daten = _daten()
    if not daten:
        return 503, [html_typ], _seite(app_name, "Die Anmeldung ist noch nicht eingerichtet.")
    if method != "POST":
        ok, _ = angemeldet(environ)
        return (303, [("Location", f"{basis}/")], b"") if ok else (200, [html_typ], _seite(app_name))
    adresse = environ.get("REMOTE_ADDR", "?")
    if _gesperrt(adresse):
        return 429, [html_typ], _seite(app_name, "Zu viele Fehlversuche. Bitte in 15 Minuten noch einmal.")
    n = min(int(environ.get("CONTENT_LENGTH") or 0), 10_000)
    formular = parse_qs(eingabe.read(n).decode("utf-8", "replace"))
    if _passwort_ok(formular.get("passwort", [""])[0], daten.get("hash")):
        _fehlversuch(adresse, zuruecksetzen=True)
        return 303, [_neuer_cookie(daten["geheimnis"]), ("Location", f"{basis}/")], b""
    _fehlversuch(adresse)
    return 401, [html_typ], _seite(app_name, "Das Passwort stimmt nicht.")
