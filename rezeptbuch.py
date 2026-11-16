"""Rezepte in rezepte/*.md lesen und zurückschreiben.

Format je Datei:
    # Kategorie
    (Einleitungstext, bleibt erhalten)

    ## Gericht
    5 Portionen · ca. 30 min

    > Hinweis (optional, mehrzeilig)

    ### Zutaten
    - Artikel | Menge

    ### Zubereitung
    1. Schritt
"""

import os
import re
from pathlib import Path

# Auf dem Webserver per ESSENPLAN_DATA in den Datenordner umgelenkt (siehe manitu/essenplan.cgi).
REZEPTE_DIR = Path(os.environ.get("ESSENPLAN_DATA") or Path(__file__).parent) / "rezepte"


def _parse_section(name, text):
    r = {"name": name, "meta": "", "hinweis": "", "zutaten": [], "zubereitung": ""}
    section, hinweis, schritte = None, [], []
    for line in text.splitlines():
        if line.startswith("### "):
            section = line[4:].strip().casefold()
        elif section is None:
            if line.startswith(">"):
                hinweis.append(line[1:].strip())
            elif line.strip() and not r["meta"]:
                r["meta"] = line.strip()
        elif section == "zutaten" and line.startswith("- "):
            artikel, _, menge = (s.strip() for s in line[2:].partition("|"))
            r["zutaten"].append({"artikel": artikel, "menge": menge})
        elif section == "zubereitung":
            schritte.append(line)
    r["hinweis"] = "\n".join(hinweis).strip()
    r["zubereitung"] = "\n".join(schritte).strip()
    return r


def _render_section(r):
    out = [f"## {r['name'].strip()}"]
    if r.get("meta", "").strip():
        out.append(r["meta"].strip())
    if r.get("hinweis", "").strip():
        out.append("")
        out += [f"> {l}".rstrip() for l in r["hinweis"].strip().splitlines()]
    out += ["", "### Zutaten"]
    for z in r.get("zutaten", []):
        artikel = z["artikel"].strip()
        if artikel:
            menge = z.get("menge", "").strip()
            out.append(f"- {artikel} | {menge}" if menge else f"- {artikel}")
    out += ["", "### Zubereitung"]
    if r.get("zubereitung", "").strip():
        out.append(r["zubereitung"].strip())
    return "\n".join(out) + "\n"


def _split(path):
    """-> (kopf, [(name, text)])"""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^## ", text)
    kopf = parts[0]
    sections = []
    for p in parts[1:]:
        name, _, body = p.partition("\n")
        sections.append((name.strip(), body))
    return kopf, sections


def _kategorie(kopf, path):
    m = re.search(r"(?m)^# (.+)$", kopf)
    return m.group(1).strip() if m else path.stem


def load_all(directory=REZEPTE_DIR):
    """Liste aller Rezepte mit 'kategorie' und 'datei'."""
    rezepte = []
    for path in sorted(Path(directory).glob("*.md")):
        kopf, sections = _split(path)
        kat = _kategorie(kopf, path)
        for name, body in sections:
            r = _parse_section(name, body)
            r["kategorie"], r["datei"] = kat, path.name
            rezepte.append(r)
    return rezepte


def kategorien(directory=REZEPTE_DIR):
    """[{datei, kategorie}] – mehrere Dateien können dieselbe Kategorie haben."""
    return [{"datei": p.name, "kategorie": _kategorie(_split(p)[0], p)}
            for p in sorted(Path(directory).glob("*.md"))]


def _write(path, kopf, sections):
    body = "\n".join(_render_section(r) for r in sections)
    path.write_text(kopf.rstrip("\n") + "\n\n" + body, encoding="utf-8")


def _load_file(path):
    kopf, sections = _split(path)
    return kopf, [_parse_section(n, b) for n, b in sections]


def _find(name, directory):
    key = name.strip().casefold()
    for path in sorted(Path(directory).glob("*.md")):
        kopf, rezepte = _load_file(path)
        for i, r in enumerate(rezepte):
            if r["name"].casefold() == key:
                return path, kopf, rezepte, i
    return None


def save(rezept, alter_name=None, datei=None, directory=REZEPTE_DIR):
    """Rezept speichern (neu oder ändern). Umbenennen über alter_name."""
    name = rezept["name"].strip()
    if not name:
        raise ValueError("Name fehlt")
    gefunden = _find(alter_name or name, directory)
    if alter_name and alter_name.strip().casefold() != name.casefold() and _find(name, directory):
        raise ValueError(f"Es gibt schon ein Rezept '{name}'")
    if gefunden:
        path, kopf, rezepte, i = gefunden
        rezepte[i] = {**rezepte[i], **rezept, "name": name}
    else:
        path = Path(directory) / (datei or sorted(Path(directory).glob("*.md"))[0].name)
        if path.parent != Path(directory) or not path.exists():
            raise ValueError("Unbekannte Kategorie-Datei")
        kopf, rezepte = _load_file(path)
        rezepte.append({**rezept, "name": name})
    _write(path, kopf, rezepte)


def delete(name, directory=REZEPTE_DIR):
    gefunden = _find(name, directory)
    if not gefunden:
        raise ValueError(f"Rezept '{name}' nicht gefunden")
    path, kopf, rezepte, i = gefunden
    del rezepte[i]
    _write(path, kopf, rezepte)
