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
import difflib
import json
import os
import re
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


def load_vorrat(path):
    """Grundvorrat (eine Zutat pro Zeile, '#' = Kommentar) als Menge kleingeschriebener Namen."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {l.split("#")[0].strip().casefold() for l in lines if l.split("#")[0].strip()}


REZEPTE_DIR = Path(__file__).with_name("rezepte")


def load_rezepte(directory):
    """Liest rezepte/*.md: '# Kategorie', '## Gericht', '### Zutaten' mit '- Artikel | Menge'."""
    rezepte = {}
    files = sorted(Path(directory).glob("*.md"))
    if not files:
        raise BringError(f"Keine Rezepte in {directory} gefunden.")
    for f in files:
        kategorie, name, section = f.stem, None, None
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                kategorie = line[2:].strip()
            elif line.startswith("## "):
                name = line[3:].strip()
                rezepte[name] = {"kategorie": kategorie, "zutaten": []}
                section = None
            elif line.startswith("### "):
                section = line[4:].strip().casefold()
            elif name and section == "zutaten" and line.startswith("- "):
                artikel, _, info = (s.strip() for s in line[2:].partition("|"))
                rezepte[name]["zutaten"].append((artikel, info))
    return rezepte


def find_rezept(rezepte, query):
    q = query.casefold()
    by_key = {n.casefold(): n for n in rezepte}
    if q in by_key:
        return by_key[q]
    teil = [n for k, n in by_key.items() if q in k]
    if len(teil) == 1:
        return teil[0]
    if not teil:  # Tippfehler wie 'Tacco-Bowls' -> 'Taco-Bowls'
        nah = difflib.get_close_matches(q, by_key, n=2, cutoff=0.8)
        if len(nah) == 1:
            return by_key[nah[0]]
    vorschlaege = teil or [by_key[k] for k in difflib.get_close_matches(q, by_key, n=3, cutoff=0.5)]
    hint = f" Meintest du: {', '.join(vorschlaege)}?" if vorschlaege else ""
    raise BringError(f"Gericht '{query}' nicht eindeutig gefunden.{hint}")


def parse_plan(rezepte, args):
    """['Mo=Focaccia', 'Chili'] -> [('Mo', 'Focaccia'), ('', 'Chili sin Carne')]"""
    plan = []
    for arg in args:
        tag, sep, query = arg.partition("=")
        if not sep:
            tag, query = "", arg
        plan.append((tag.strip(), find_rezept(rezepte, query.strip())))
    return plan


def wochen_uebersicht(plan, rezepte, vorrat, ohne=()):
    """Markdown: je Gericht eine Überschrift und die Zutaten als Liste."""
    out = ["", "## Wochenübersicht"]
    for tag, name in plan:
        out += ["", f"### {tag + ' – ' if tag else ''}{name}", ""]
        da = []
        for artikel, info in rezepte[name]["zutaten"]:
            if artikel.casefold() in vorrat:
                da.append(artikel)
            else:
                zuhause = " – *zuhause*" if artikel.casefold() in ohne else ""
                out.append(f"- [ ] {artikel}{f' ({info})' if info else ''}{zuhause}")
        if da:
            out.append(f"- *aus dem Vorrat:* {', '.join(da)}")
    return "\n".join(out)


_MENGE = re.compile(r"^(\d+(?:,\d+)?)\s*([A-Za-zäöüÄÖÜß.]+)?$")
_PLURAL = {"Dose": "Dosen", "Glas": "Gläser", "Kopf": "Köpfe", "Würfel": "Würfel"}


def _sum_infos(infos):
    """'250 g' + '300 g' -> '550 g'; sonst Angaben mit ' + ' verbinden."""
    if len(infos) < 2:
        return infos[0] if infos else ""
    total, unit = 0.0, None
    for info in infos:
        m = _MENGE.match(info)
        if not m:
            return " + ".join(infos)
        u = _PLURAL.get(m.group(2), m.group(2))
        if unit is not None and u != unit:
            return " + ".join(infos)
        unit = u
        total += float(m.group(1).replace(",", "."))
    num = f"{total:g}".replace(".", ",")
    if unit and total == 1:
        unit = {v: k for k, v in _PLURAL.items()}.get(unit, unit)
    return f"{num} {unit}" if unit else num


def merge_items(items):
    """Gleiche Artikel aus mehreren Rezepten zusammenfassen."""
    merged = {}
    for name, info in items:
        entry = merged.setdefault(name.casefold(), [name, []])
        if info:
            entry[1].append(info)
    return [(name, _sum_infos(infos)) for name, infos in merged.values()]


def add_items(bring, list_uuid, items, vorrat, probelauf=False, names=None):
    """Trägt Artikel ein. names: Bring!-Katalog {interner Schlüssel: Anzeigename}.

    Katalogartikel werden unter ihrem internen Schlüssel eingetragen (z. B. 'Paprika'
    -> 'Peperoni'), damit Bring! Bild und Ladenbereich zuordnet.
    """
    names = names or {}
    katalog = {v.casefold(): k for k, v in names.items()}
    purchase, _ = bring.items(list_uuid)
    vorhanden = {}
    for it in purchase:
        for n in (it["name"], names.get(it["name"], it["name"])):
            vorhanden[n.casefold()] = it.get("specification", "")
    for name, info in items:
        key = name.casefold()
        if key in vorrat:
            print(f"Übersprungen (vorrat.txt): {name}")
        elif key in vorhanden:
            dort = vorhanden[key]
            extra = f" – dort: {dort or 'ohne Menge'}, benötigt: {info}" if info and info != dort else ""
            print(f"Schon auf der Liste: {name}{extra}")
        else:
            if not probelauf:
                bring.add(list_uuid, katalog.get(key, name), info)
            vorhanden[key] = info
            print(f"{'Würde hinzufügen' if probelauf else 'Hinzugefügt'}: "
                  f"{name}{f' ({info})' if info else ''}")


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
    m = sub.add_parser("mehrere",
                       help="viele Artikel von stdin hinzufügen (eine Zeile: 'Artikel | Info')")
    m.add_argument("--vorrat", default=str(Path(__file__).with_name("vorrat.txt")),
                   help="Datei mit Grundvorrat, der übersprungen wird")
    m.add_argument("-n", "--probelauf", action="store_true",
                   help="nur anzeigen, nichts eintragen")
    rz = sub.add_parser("rezept",
                        help="Zutaten eines oder mehrerer Gerichte aus rezepte/ hinzufügen")
    rz.add_argument("gerichte", nargs="+", help="Gerichtnamen (Teilname reicht)")
    rz.add_argument("--vorrat", default=str(Path(__file__).with_name("vorrat.txt")))
    rz.add_argument("-n", "--probelauf", action="store_true",
                    help="nur anzeigen, nichts eintragen")
    rz.add_argument("--ohne", action="append", default=[], metavar="ARTIKEL",
                    help="diesmal nicht eintragen, weil zuhause (kommagetrennt, mehrfach möglich)")
    sub.add_parser("rezepte", help="alle Gerichte aus rezepte/ auflisten (ohne Login)")
    wo = sub.add_parser("woche", help="nur Wochenübersicht: Zutaten je Gericht (ohne Login)")
    wo.add_argument("gerichte", nargs="+", help="Gerichte, optional mit Tag: 'Mo=Focaccia'")
    wo.add_argument("--vorrat", default=str(Path(__file__).with_name("vorrat.txt")))
    args = p.parse_args(argv)

    if args.cmd == "woche":
        try:
            rezepte = load_rezepte(REZEPTE_DIR)
            print(wochen_uebersicht(parse_plan(rezepte, args.gerichte), rezepte,
                                    load_vorrat(args.vorrat)))
        except BringError as e:
            print(f"Fehler: {e}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "rezepte":
        try:
            rezepte = load_rezepte(REZEPTE_DIR)
        except BringError as e:
            print(f"Fehler: {e}", file=sys.stderr)
            return 1
        kategorie = None
        for name, r in rezepte.items():
            if r["kategorie"] != kategorie:
                kategorie = r["kategorie"]
                print(f"\n{kategorie}")
            print(f"  {name}")
        return 0

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
        elif args.cmd == "mehrere":
            items = []
            for line in sys.stdin:
                line = line.strip()
                if line and not line.startswith("#"):
                    name, _, info = (s.strip() for s in line.partition("|"))
                    items.append((name, info))
            add_items(bring, list_uuid, merge_items(items),
                      load_vorrat(args.vorrat), args.probelauf, load_names(args.locale))
        elif args.cmd == "rezept":
            rezepte = load_rezepte(REZEPTE_DIR)
            plan = parse_plan(rezepte, args.gerichte)
            vorrat = load_vorrat(args.vorrat)
            items = [z for _, name in plan for z in rezepte[name]["zutaten"]]
            ohne = {s.strip().casefold() for o in args.ohne for s in o.split(",") if s.strip()}
            for artikel in sorted({a for a, _ in items if a.casefold() in ohne}):
                print(f"Übersprungen (zuhause): {artikel}")
            items = [z for z in items if z[0].casefold() not in ohne]
            add_items(bring, list_uuid, merge_items(items),
                      vorrat, args.probelauf, load_names(args.locale))
            print(wochen_uebersicht(plan, rezepte, vorrat, ohne))
    except BringError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
