# bring.py – Bring!-Einkaufsliste per Kommandozeile

Kleines Python-Skript (nur Standardbibliothek, Python 3.9+) für die
**inoffizielle** Bring!-API. Bring! unterstützt diese Schnittstelle nicht
offiziell; sie kann sich jederzeit ändern.

## Einrichten

```bash
export BRING_EMAIL="deine@mail.de"
export BRING_PASSWORD="dein-passwort"
# optional: export BRING_LIST="Zuhause"
```

Das Passwort nie in den Code schreiben. Nach dem ersten Login wird das Token in
`~/.cache/bring-cli/token.json` (nur für dich lesbar) gespeichert und automatisch erneuert.

## Benutzen

```bash
python3 bring.py listen              # alle Listen (* = Standardliste)
python3 bring.py zeigen              # offene Artikel
python3 bring.py zeigen --alle       # inkl. zuletzt gekauft
python3 bring.py add Milch "1,5 %"   # hinzufügen, mit Zusatzinfo
python3 bring.py erledigt Milch      # als gekauft markieren
python3 bring.py entfernen Milch     # ganz löschen
python3 bring.py -l Zuhause zeigen   # andere Liste
python3 bring.py --json zeigen       # Rohdaten als JSON
```

## Rezepte und Wochenplan

In `rezepte/` liegen Rezepte (5 Personen, vegetarisch/vegan) für alle Gerichte vom Essenplan.

```bash
python3 bring.py rezepte                                    # alle Gerichte
python3 bring.py -l Abendessen rezept Pizza "Chili sin" -n  # Probelauf
python3 bring.py -l Abendessen rezept Pizza "Chili sin"     # Zutaten eintragen
```

Zutaten aus `vorrat.txt` werden übersprungen, gleiche Zutaten zusammengerechnet und
Katalogartikel unter ihrem Bring!-Namen eingetragen (mit Bild und Ladenbereich).
