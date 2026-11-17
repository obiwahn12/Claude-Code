#!/usr/bin/env python3
"""CGI-Einstieg für die Essenplan-App auf dem manitu-Webspace.

Jede Anfrage startet dieses Skript kurz (die .htaccess leitet alles hierher um).
Die eigentliche Logik steckt unverändert in app.py, rezeptbuch.py und bring.py.
Daten (rezepte/, vorrat.txt, woche.json, Bring!-Token) liegen in ./daten/.
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "daten"
os.environ["ESSENPLAN_DATA"] = str(DATA)
os.environ["XDG_CACHE_HOME"] = str(DATA / "cache")  # Bring!-Token + Artikelkatalog
# Bestand der Vorratsschrank-App im Nachbarordner /vorrat/ (wird nur gelesen)
os.environ.setdefault("VORRATSSCHRANK_BESTAND", str(HERE.parent / "vorrat" / "daten" / "bestand.json"))
# Gemeinsame Anmeldung beider Apps (Passwort-Hash + Geheimnis), siehe anmeldung.py
os.environ.setdefault("ANMELDUNG_DIR", str(HERE.parent / ".anmeldung"))
sys.path.insert(0, str(HERE))

import anmeldung  # noqa: E402
import app  # noqa: E402
import bring  # noqa: E402

try:
    import fcntl  # nur auf dem Server (Linux); verhindert gleichzeitiges Schreiben
except ImportError:  # Windows (lokaler Test)
    fcntl = None

GRUND = {200: "OK", 303: "See Other", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found",
         405: "Method Not Allowed", 429: "Too Many Requests", 500: "Internal Server Error", 503: "Service Unavailable"}


def senden(code, header, data):
    kopf = f"Status: {code} {GRUND.get(code, '')}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in header)
    kopf += (f"Content-Length: {len(data)}\r\n"
             "Cache-Control: no-store\r\n"
             "X-Content-Type-Options: nosniff\r\n\r\n")
    sys.stdout.buffer.write(kopf.encode() + data)
    sys.stdout.buffer.flush()


def antworte(code, body, ctype="application/json; charset=utf-8", extra=()):
    data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
    senden(code, [("Content-Type", ctype), *extra], data)


def lies_json():
    n = int(os.environ.get("CONTENT_LENGTH") or 0)
    if n > 1_000_000:
        raise ValueError("Anfrage zu groß")
    return json.loads(sys.stdin.buffer.read(n) or b"{}")


def main():
    method = os.environ.get("REQUEST_METHOD", "GET").upper()
    path = os.environ.get("PATH_INFO") or "/"
    if not path.startswith("/"):
        path = "/" + path

    basis = os.environ.get("SCRIPT_NAME", "").rsplit("/", 1)[0]  # z. B. „/essen“
    seite = anmeldung.anfrage(method, path, os.environ, sys.stdin.buffer, "Essenplan", basis)
    if seite:
        return senden(*seite)
    ok, extra = anmeldung.angemeldet(os.environ)
    if not ok:
        if path.startswith("/api/"):
            return antworte(401, {"fehler": "Bitte neu anmelden.", "anmelden": True})
        return senden(303, [("Location", f"{basis}/login")], b"")

    if path in ("/", "/index.html"):
        if method != "GET":
            return antworte(405, {"fehler": "Nicht erlaubt"})
        return antworte(200, (app.STATIC / "index.html").read_bytes(), "text/html; charset=utf-8", extra)
    if not path.startswith("/api/"):
        return antworte(404, {"fehler": "Nicht gefunden"})

    DATA.mkdir(exist_ok=True)
    try:
        with open(DATA / ".lock", "a") as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            result = app.dispatch(method, path, lies_json)
        if result is None:
            antworte(404, {"fehler": "Nicht gefunden"})
        else:
            antworte(200, result, extra=extra)
    except (ValueError, KeyError, bring.BringError) as e:
        antworte(400, {"fehler": str(e)})
    except Exception as e:  # noqa: BLE001 – Fehler an die Oberfläche melden
        antworte(500, {"fehler": f"Interner Fehler: {e}"})


if __name__ == "__main__":
    main()
