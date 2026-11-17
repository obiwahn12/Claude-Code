"""Bestand des Vorratsschranks (Schwester-App unter /vorrat/) für den Essenplan lesen und abgleichen.

Der Essenplan liest nur: VORRATSSCHRANK_BESTAND zeigt auf vorrat/daten/bestand.json (siehe
manitu/essenplan.cgi). Ist die Variable nicht gesetzt oder die Datei nicht lesbar, ist die
Funktion einfach aus.

Abgleich Rezept-Zutat <-> Schranksorte (passt):
1. gleiche Sorte (ohne Leerzeichen, ß = ss, Wortreihenfolge egal, Tippfehler bei langen Namen),
2. Oberbegriff: die Sorte endet auf die Zutat („Weizenmehl“ -> „Mehl“, „Langkorn Naturreis“ -> „Reis“),
   außer bei anderen Produkten („Röstzwiebeln“, „Milchreis“, „Puderzucker“) und nur, wenn beide in
   derselben Bring!-Abteilung landen („Passierte Tomaten“ zählt nicht als „Tomaten“),
3. feste Zuordnungen (Spaghetti, Fusilli … -> Nudeln; Mais -> Dosen-Mais).
"""

import json
import os
import re
from pathlib import Path

NICHT_ESSBAR = {"Pflege & Gesundheit", "Haushalt", "Tierbedarf", "Baumarkt & Garten"}

# Vorsilben, mit denen eine Sorte ein anderes Produkt ist als der Oberbegriff
ANDERES_PRODUKT = ("röst", "milch", "puder", "panier", "parnier", "gelier", "semmel", "kokos", "sushi",
                   "instant", "passiert", "gehackt", "getrocknet", "kräuter", "knoblauch", "chili", "wok",
                   "mie", "reis", "glas", "frucht", "trink")

# Zutat (Schlüssel) -> Schranksorten (Wortende), die dafür zählen
ZUORDNUNG = {
    "nudeln": ["spaghetti", "fusilli", "penne", "rigatoni", "farfalle", "tagliatelle", "makkaroni", "maccheroni",
               "spiralen", "linguine", "orecchiette", "conchiglie", "bandnudeln", "spirelli", "hörnchen"],
    "dosenmais": ["mais"],
    "paniermehl": ["semmelbrösel", "paniermehl", "parniermehl"],
    "pasta": ["spaghetti", "fusilli", "penne", "rigatoni", "farfalle", "nudeln"],
    "hefe": ["hefe", "trockenhefe", "backhefe"],
    "spargel": ["spargel", "spargelstangen", "spargelspitzen", "spargelköpfe"],  # im Frikassee aus dem Glas
}

# Beschreibende Zusätze ohne Einfluss auf den Abgleich („Parniermehl fein“ = „Paniermehl“)
ZUSAETZE = {"fein", "feine", "grob", "extra", "mild", "scharf", "mittelscharf", "natur", "klassisch", "classic", "light"}


def _ohne_zusaetze(s):
    woerter = re.split(r"[\s,]+", str(s).strip())
    while len(woerter) > 1 and woerter[-1].lower() in ZUSAETZE:
        woerter.pop()
    return " ".join(woerter)

# Einheiten, die man im Schrank als Packungen zählt (für den Mengenvergleich)
STUECK_EINHEITEN = r"(dosen?|gl(as|äser)?|packung(en)?|pck|pkg|päckchen|flaschen?|beutel|tüten?|würfel|becher)"


def schluessel(s):
    return re.sub(r"[^a-zäöü]", "", str(s).lower().replace("ß", "ss"))


def _staemme(s):
    out = []
    for w in re.findall(r"[a-zäöü]+", str(s).lower().replace("ß", "ss")):
        for endung in ("en", "er", "e", "n"):
            if w.endswith(endung) and len(w) - len(endung) >= 4:
                w = w[: -len(endung)]
                break
        out.append(w)
    return sorted(out)


def _abstand(a, b):
    vorher = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        jetzt = [i]
        for j, cb in enumerate(b, 1):
            jetzt.append(min(vorher[j] + 1, jetzt[j - 1] + 1, vorher[j - 1] + (ca != cb)))
        vorher = jetzt
    return vorher[-1]


def passt(zutat, sorte, abt_zutat=None, abt_sorte=None):
    """Zählt die Schranksorte für diese Rezept-Zutat?"""
    sorte = _ohne_zusaetze(sorte)
    kz, ks = schluessel(zutat), schluessel(sorte)
    if not kz or not ks:
        return False
    if kz == ks or _staemme(zutat) == _staemme(sorte):
        return True
    kurz = min(len(kz), len(ks))
    if kurz >= 10 and abs(len(kz) - len(ks)) <= 1 and _abstand(kz, ks) <= 1:
        return True
    for ende in ZUORDNUNG.get(kz, []):
        if ks.endswith(ende) and not ks[: -len(ende)].endswith(ANDERES_PRODUKT):
            return True
    if len(kz) >= 4 and ks.endswith(kz):
        vorsilbe = ks[: -len(kz)]
        if any(vorsilbe.startswith(v) or vorsilbe.endswith(v) for v in ANDERES_PRODUKT):
            return False
        return not (abt_zutat and abt_sorte and abt_zutat != abt_sorte)
    return False


def laden(abteilung=None):
    """Lebensmittel im Schrank: [{name, menge, abteilung}], [] wenn nicht verfügbar.
    abteilung(name) dient als Ersatz, falls der Bestand (noch) keine Abteilung gespeichert hat."""
    pfad = os.environ.get("VORRATSSCHRANK_BESTAND")
    if not pfad:
        return None
    try:
        daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    out = []
    for a in daten.get("artikel", []):
        if not a.get("name") or a.get("menge", 0) <= 0:
            continue
        abt = a.get("abteilung_fest") or a.get("abteilung") or (abteilung(a["name"]) if abteilung else "")
        if abt in NICHT_ESSBAR:
            continue
        out.append({"name": a["name"], "menge": a["menge"], "abteilung": abt})
    return out


def finden(zutat, abt_zutat, schrank):
    return [s for s in schrank or [] if passt(zutat, s["name"], abt_zutat, s["abteilung"])]


def reicht(menge, anzahl):
    """Mengenvergleich nur für Dosen, Gläser, Packungen …: True/False, None = nicht vergleichbar."""
    m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*" + STUECK_EINHEITEN + r"\b", str(menge or ""), re.I)
    if not m:
        return None
    return anzahl >= float(m.group(1).replace(",", "."))
