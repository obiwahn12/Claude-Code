#!/usr/bin/env python3
"""Essenplan-Web-App: Rezepte pflegen, Woche planen, Zutaten an Bring! schicken.

Start:
    python3 app.py            # nur auf diesem Rechner: http://localhost:8765
    python3 app.py --lan      # auch im WLAN (Handy/iPad), ohne Passwortschutz!

Nur Python-Standardbibliothek. Daten liegen als Dateien neben dem Skript:
rezepte/*.md, vorrat.txt, woche.json. Das Bring!-Passwort wird nie gespeichert,
nur das Anmelde-Token (~/.cache/bring-cli/token.json).
"""

import argparse
import json
import os
import socket
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import bring
import rezeptbuch

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
# Datenordner (vorrat.txt, woche.json, rezepte/): Standard neben dem Skript,
# auf dem Webserver per ESSENPLAN_DATA umgelenkt (siehe manitu/essenplan.cgi).
DATA = Path(os.environ.get("ESSENPLAN_DATA") or HERE)
VORRAT = DATA / "vorrat.txt"
WOCHE = DATA / "woche.json"
TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

_lock = threading.Lock()  # Dateizugriffe nacheinander
_bring = bring.Bring()
_names = None  # Bring!-Katalog, einmal laden


def katalog():
    global _names
    if _names is None:
        _names = bring.load_names("de-DE")
    return _names


def bring_bereit():
    """Mit gespeichertem Token anmelden, falls noch nicht geschehen. True, wenn angemeldet."""
    if _bring.auth is None:
        try:
            _bring.login()  # nur mit gespeichertem Token
        except bring.BringError:
            return False
    return True


def bring_status():
    if not bring_bereit():
        return {"angemeldet": False}
    try:
        listen = [l["name"] for l in _bring.lists()]
    except bring.BringError:
        _bring.auth = None
        return {"angemeldet": False}
    return {"angemeldet": True, "listen": listen}


def lade_woche():
    try:
        w = json.loads(WOCHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        w = {}
    w.setdefault("liste", "Abendessen")
    w.setdefault("tage", {t: [] for t in TAGE})
    for t in TAGE:
        w["tage"].setdefault(t, [])
    w.setdefault("extra", [])  # eigene Zutaten: [{"artikel", "menge", "tag"}], tag "" = ohne Gericht
    return w


def extra_saeubern(liste):
    """Eigene Zutaten aus der Anfrage prüfen (nur bekannte Felder, Tag Mo–So oder leer)."""
    out = []
    for e in liste or []:
        if not isinstance(e, dict):
            continue
        artikel = str(e.get("artikel", "")).strip()[:100]
        if artikel:
            tag = e.get("tag") if e.get("tag") in TAGE else ""
            out.append({"artikel": artikel, "menge": str(e.get("menge", "")).strip()[:100], "tag": tag})
    return out[:200]


def plan_pruefen(woche):
    """Zutaten der Woche zusammenfassen und mit Vorrat und Bring!-Liste abgleichen."""
    rezepte = {r["name"]: r for r in rezeptbuch.load_all()}
    vorrat = bring.load_vorrat(VORRAT)
    zeilen, gerichte = [], {}
    for tag in TAGE:
        for g in woche["tage"].get(tag, []):
            if g not in rezepte:
                continue
            for z in rezepte[g]["zutaten"]:
                zeilen.append((z["artikel"], z["menge"]))
                gerichte.setdefault(z["artikel"].casefold(), []).append(f"{tag} {g}")
    # Eigene Zutaten: zählen mit, werden aber nie als Vorrat weggefiltert
    eigene = set()
    for e in woche.get("extra", []):
        zeilen.append((e["artikel"], e["menge"]))
        key = e["artikel"].casefold()
        eigene.add(key)
        g = (woche["tage"].get(e["tag"]) or [""])[0] if e["tag"] else ""
        gerichte.setdefault(key, []).append(f"{e['tag']} {g}".strip() if g else "Eigene")
    vorhanden, liste_ok = {}, False
    if bring_bereit():
        try:
            names = katalog()
            uuid = _bring.resolve_list(woche["liste"])
            purchase, _ = _bring.items(uuid)
            for it in purchase:
                for n in (it["name"], names.get(it["name"], it["name"])):
                    vorhanden[n.casefold()] = it.get("specification", "")
            liste_ok = True
        except bring.BringError:
            pass
    artikel = []
    for name, menge in bring.merge_items(zeilen):
        key = name.casefold()
        status = ("vorrat" if key in vorrat and key not in eigene
                  else "liste" if key in vorhanden else "neu")
        artikel.append({"artikel": name, "menge": menge, "status": status, "eigene": key in eigene,
                        "dort": vorhanden.get(key, ""), "gerichte": list(dict.fromkeys(gerichte.get(key, [])))})
    return {"artikel": artikel, "liste_geprueft": liste_ok}


def an_bring(liste, artikel):
    names = katalog()
    kat = {v.casefold(): k for k, v in names.items()}
    uuid = _bring.resolve_list(liste)
    purchase, _ = _bring.items(uuid)
    da = set()
    for it in purchase:
        da |= {it["name"].casefold(), names.get(it["name"], it["name"]).casefold()}
    neu = []
    for a in artikel:
        name = a["artikel"].strip()
        if not name or name.casefold() in da:
            continue
        _bring.add(uuid, kat.get(name.casefold(), name), a.get("menge", "").strip())
        da.add(name.casefold())
        neu.append(name)
    return neu


def dispatch(method, path, lies_json):
    """API-Anfrage beantworten. lies_json() liefert den JSON-Body. None = nicht gefunden.

    Wird vom lokalen Server (Handler) und vom CGI-Einstieg (manitu/essenplan.cgi) genutzt.
    """
    if path == "/api/rezepte" and method == "GET":
        return {"rezepte": rezeptbuch.load_all(), "kategorien": rezeptbuch.kategorien()}
    if path == "/api/rezepte" and method == "POST":
        d = lies_json()
        rezeptbuch.save(d["rezept"], alter_name=d.get("alter_name"), datei=d.get("datei"))
        return {"ok": True}
    if path.startswith("/api/rezepte/") and method == "DELETE":
        rezeptbuch.delete(unquote(path[len("/api/rezepte/"):]))
        return {"ok": True}
    if path == "/api/vorrat" and method == "GET":
        return {"text": VORRAT.read_text(encoding="utf-8") if VORRAT.exists() else ""}
    if path == "/api/vorrat" and method == "PUT":
        VORRAT.write_text(lies_json()["text"].rstrip() + "\n", encoding="utf-8")
        return {"ok": True}
    if path == "/api/woche" and method == "GET":
        return lade_woche()
    if path == "/api/woche" and method == "PUT":
        w = lies_json()
        woche = {"liste": str(w.get("liste") or "Abendessen"),
                 "tage": {t: [str(g) for g in w.get("tage", {}).get(t, []) if g] for t in TAGE},
                 "extra": extra_saeubern(w.get("extra"))}
        WOCHE.write_text(json.dumps(woche, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True}
    if path == "/api/woche/pruefen" and method == "POST":
        return plan_pruefen(lade_woche())
    if path == "/api/bring" and method == "GET":
        return bring_status()
    if path == "/api/bring/login" and method == "POST":
        d = lies_json()
        _bring.login(d.get("email", "").strip(), d.get("password", ""))
        return bring_status()
    if path == "/api/bring/logout" and method == "POST":
        _bring.logout()
        return {"angemeldet": False}
    if path == "/api/bring/senden" and method == "POST":
        if not bring_bereit():
            raise bring.BringError("Nicht bei Bring! angemeldet.")
        d = lies_json()
        return {"hinzugefuegt": an_bring(d["liste"], d.get("artikel", []))}
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "Essenplan/1.0"

    def log_message(self, fmt, *args):  # ruhiger, ohne Request-Bodies
        pass

    # ---------- Hilfen ----------
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise ValueError("Anfrage zu groß")
        return json.loads(self.rfile.read(n) or b"{}")

    def _route(self, method):
        path = urlparse(self.path).path
        try:
            with _lock:
                result = dispatch(method, path, self._json)
            if result is None:
                self._send(404, {"fehler": "Nicht gefunden"})
            else:
                self._send(200, result)
        except (ValueError, bring.BringError) as e:
            self._send(400, {"fehler": str(e)})
        except Exception as e:  # noqa: BLE001 – Fehler an die Oberfläche melden
            self._send(500, {"fehler": f"Interner Fehler: {e}"})

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "?"
    finally:
        s.close()


def main():
    p = argparse.ArgumentParser(description="Essenplan-Web-App")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--lan", action="store_true",
                   help="auch im lokalen Netz erreichbar machen (kein Passwortschutz!)")
    args = p.parse_args()
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    server = ThreadingHTTPServer((host, args.port), Handler)
    print(f"Essenplan läuft: http://localhost:{args.port}")
    if args.lan:
        print(f"Im WLAN:         http://{lan_ip()}:{args.port}  (ohne Passwort – nur im Heimnetz nutzen)")
    print("Beenden mit Strg+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
