#!/usr/bin/env python3
"""Kleines Kommandozeilen-Tool für Bring!-Einkaufslisten.

Nutzt die inoffizielle Bring!-API (api.getbring.com). Keine externen
Abhängigkeiten, nur die Python-Standardbibliothek.

Zugangsdaten kommen aus Umgebungsvariablen:
    BRING_EMAIL, BRING_PASSWORD
Optional:
    BRING_LIST   Name oder UUID der Liste (Standard: deine Standardliste)

Beispiele:
    python3 bring.py listen
    python3 bring.py zeigen
    python3 bring.py add Milch "1,5 %"
    python3 bring.py erledigt Milch
    python3 bring.py entfernen Milch
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.getbring.com/rest/v2/"
ARTICLES_URL = "https://web.getbring.com/locale/articles.{locale}.json"
# Fester, öffentlich bekannter Key der Bring!-Web-App.
API_KEY = "cof4Nc6D8saplXjE3h3HXqHH8m7VU2i1Gs0g85Sp"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "bring-cli"
TOKEN_FILE = CACHE / "token.json"


class BringError(Exception):
    pass


def _request(method, url, headers, data=None, json_body=None):
    body = None
    headers = dict(headers)
    if json_body is not None:
        body = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code in (401, 403):
            raise BringError(f"Nicht berechtigt (HTTP {e.code}). E-Mail/Passwort prüfen.") from None
        raise BringError(f"HTTP {e.code} bei {method} {url}: {detail}") from None
    except urllib.error.URLError as e:
        raise BringError(f"Keine Verbindung zu {url}: {e.reason}") from None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode(errors="replace")


class Bring:
    def __init__(self, country="DE"):
        self.headers = {
            "X-BRING-API-KEY": API_KEY,
            "X-BRING-CLIENT": "webApp",
            "X-BRING-COUNTRY": country,
        }
        self.auth = None

    # ---------- Login ----------
    def login(self):
        cached = self._load_token()
        if cached and cached.get("expires_at", 0) > time.time() + 60:
            self._use(cached)
            return
        if cached and cached.get("refresh_token"):
            try:
                self._refresh(cached)
                return
            except BringError:
                pass  # dann normal neu anmelden
        email = os.environ.get("BRING_EMAIL")
        password = os.environ.get("BRING_PASSWORD")
        if not email or not password:
            raise BringError("Bitte BRING_EMAIL und BRING_PASSWORD als Umgebungsvariablen setzen.")
        res = _request("POST", BASE + "bringauth", self.headers,
                       data={"email": email, "password": password})
        self._store(res)

    def _refresh(self, cached):
        res = _request("POST", BASE + "bringauth/token", self.headers,
                       data={"grant_type": "refresh_token",
                             "refresh_token": cached["refresh_token"]})
        # Die Antwort enthält nicht immer uuid/Standardliste – aus dem Cache übernehmen.
        for key in ("uuid", "bringListUUID", "refresh_token"):
            res.setdefault(key, cached.get(key))
        self._store(res)

    def _store(self, res):
        token = {
            "uuid": res["uuid"],
            "bringListUUID": res.get("bringListUUID"),
            "access_token": res["access_token"],
            "refresh_token": res.get("refresh_token"),
            "expires_at": time.time() + int(res.get("expires_in", 3600)),
        }
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(json.dumps(token))
            TOKEN_FILE.chmod(0o600)
        except OSError:
            pass  # Cache ist nur Komfort
        self._use(token)

    def _load_token(self):
        try:
            return json.loads(TOKEN_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def _use(self, token):
        self.auth = token
        self.headers["Authorization"] = f"Bearer {token['access_token']}"
        self.headers["X-BRING-USER-UUID"] = token["uuid"]

    # ---------- Listen ----------
    def lists(self):
        res = _request("GET", BASE + f"bringusers/{self.auth['uuid']}/lists", self.headers)
        return res.get("lists", [])

    def resolve_list(self, name_or_uuid=None):
        if not name_or_uuid:
            if self.auth.get("bringListUUID"):
                return self.auth["bringListUUID"]
            lists = self.lists()
            if not lists:
                raise BringError("Keine Listen gefunden.")
            return lists[0]["listUuid"]
        for lst in self.lists():
            if name_or_uuid in (lst["listUuid"], lst["name"]) or \
               lst["name"].lower() == name_or_uuid.lower():
                return lst["listUuid"]
        raise BringError(f"Liste '{name_or_uuid}' nicht gefunden.")

    def items(self, list_uuid):
        res = _request("GET", BASE + f"bringlists/{list_uuid}", self.headers)
        return res.get("purchase", []), res.get("recently", [])

    def _put(self, list_uuid, data):
        _request("PUT", BASE + f"bringlists/{list_uuid}", self.headers, data=data)

    def add(self, list_uuid, item, spec=""):
        self._put(list_uuid, {"purchase": item, "specification": spec})

    def done(self, list_uuid, item):
        self._put(list_uuid, {"recently": item})

    def remove(self, list_uuid, item):
        self._put(list_uuid, {"remove": item})


def load_names(locale):
    """Interne Artikelschlüssel -> Anzeigenamen (z. B. 'Milch' bleibt 'Milch')."""
    cache_file = CACHE / f"articles.{locale}.json"
    try:
        if time.time() - cache_file.stat().st_mtime < 7 * 86400:
            return json.loads(cache_file.read_text())
    except (OSError, json.JSONDecodeError):
        pass
    try:
        names = _request("GET", ARTICLES_URL.format(locale=locale), {})
        CACHE.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(names))
        return names
    except (BringError, OSError):
        return {}


def main(argv=None):
    p = argparse.ArgumentParser(description="Bring!-Einkaufsliste per Kommandozeile")
    p.add_argument("-l", "--liste", default=os.environ.get("BRING_LIST"),
                   help="Name oder UUID der Liste (Standard: Standardliste)")
    p.add_argument("--locale", default="de-DE")
    p.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listen", help="alle Listen anzeigen")
    z = sub.add_parser("zeigen", help="offene Artikel anzeigen")
    z.add_argument("-a", "--alle", action="store_true", help="auch zuletzt gekaufte zeigen")
    a = sub.add_parser("add", help="Artikel hinzufügen")
    a.add_argument("artikel")
    a.add_argument("info", nargs="?", default="", help="Zusatzinfo, z. B. Menge")
    e = sub.add_parser("erledigt", help="Artikel als gekauft markieren")
    e.add_argument("artikel")
    r = sub.add_parser("entfernen", help="Artikel ganz entfernen")
    r.add_argument("artikel")
    args = p.parse_args(argv)

    bring = Bring(country=args.locale.split("-")[-1])
    try:
        bring.login()
        if args.cmd == "listen":
            lists = bring.lists()
            if args.json:
                print(json.dumps(lists, ensure_ascii=False, indent=2))
            for lst in [] if args.json else lists:
                star = " *" if lst["listUuid"] == bring.auth.get("bringListUUID") else ""
                print(f"{lst['name']}{star}  ({lst['listUuid']})")
            return 0

        list_uuid = bring.resolve_list(args.liste)
        if args.cmd == "zeigen":
            purchase, recently = bring.items(list_uuid)
            names = load_names(args.locale)
            if args.json:
                print(json.dumps({"purchase": purchase, "recently": recently},
                                 ensure_ascii=False, indent=2))
                return 0
            if not purchase:
                print("Die Liste ist leer.")
            for it in purchase:
                name = names.get(it["name"], it["name"])
                spec = f"  ({it['specification']})" if it.get("specification") else ""
                print(f"• {name}{spec}")
            if args.alle and recently:
                print("\nZuletzt gekauft:")
                for it in recently:
                    print(f"  {names.get(it['name'], it['name'])}")
        elif args.cmd == "add":
            bring.add(list_uuid, args.artikel, args.info)
            print(f"Hinzugefügt: {args.artikel}")
        elif args.cmd == "erledigt":
            bring.done(list_uuid, args.artikel)
            print(f"Erledigt: {args.artikel}")
        elif args.cmd == "entfernen":
            bring.remove(list_uuid, args.artikel)
            print(f"Entfernt: {args.artikel}")
    except BringError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
