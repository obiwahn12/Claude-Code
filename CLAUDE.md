# Bring!-Einkaufslisten

Dieses Repo enthält `bring.py`, ein CLI für die inoffizielle Bring!-API (siehe README.md).
Kommunikation mit dem Nutzer auf Deutsch.

## Wochenplan → Liste „Abendessen“

Familie: 5 Personen, isst nur vegetarisch/vegan. Milch = Haferdrink, Sahne = Soja-Sahne.
„Salami“, „Wurst“, „Würstchen“ usw. meinen **immer** die vegetarische/vegane Alternative.
Mineralwasser nie aufschreiben (Sodastream; steht in `vorrat.txt`).
**Kein Knoblauch** – mag niemand. Nie in Rezepte schreiben, auch nicht in die Zubereitung
(steht zusätzlich in `vorrat.txt` unter „Nie kaufen“, damit er beim Eintragen rausfällt).
Die Gerichte stehen auf einem Freeform-Board „Essenplan“ (Screenshot vom Nutzer); zu jedem
Gericht gibt es ein Rezept in `rezepte/*.md` (`python3 bring.py rezepte` listet alle).

Schickt der Nutzer den Wochenplan (Text oder Screenshot vom Board), **in zwei Schritten**:

1. **Erst die Übersicht zeigen, nichts eintragen:**
   ```bash
   python3 bring.py woche Mo=Focaccia Di=Eierkuchen "So=Chili sin Carne"
   ```
   Dem Nutzer je Gericht die Zutaten als Markdown-Liste zeigen und fragen, was davon schon zuhause ist.
2. **Nach der Antwort eintragen**, Vorhandenes mit `--ohne` weglassen:
   ```bash
   python3 bring.py -l Abendessen rezept Mo=Focaccia Di=Eierkuchen "So=Chili sin Carne" --ohne "Oliven, Reis"
   ```
   Danach die Wochenübersicht, die das Skript druckt, als Liste ausgeben.
Teilnamen und kleine Tippfehler vom Board („Tacco-Bowls“) werden erkannt. Mengen gleicher Zutaten
werden zusammengerechnet. Steht ein Artikel schon auf der Liste, meldet das Skript die Mengen –
dem Nutzer sagen, falls dort zu wenig steht. „Reste“ ist kein Rezept.

Neue Gerichte vom Board: Rezept im passenden `rezepte/`-Abschnitt ergänzen (gleiches Format,
5 Portionen, vegetarisch/vegan), Überschrift = Name wie auf dem Board.

## Einzelnes Rezept (Text/Link) → Liste „Abendessen“

Wenn der Nutzer ein Rezept schickt (Text, Zutatenliste oder Link):

1. Zutaten aus dem Rezept herauslesen und auf einfache Einkaufsnamen bringen
   („2 rote Zwiebeln, gewürfelt“ → `Zwiebeln | 2 rote`). Menge/Hinweis kommt hinter `|`.
   Namen möglichst so wie in Bring! üblich (Singular/Plural wie im Laden, z. B. „Tomaten“, „Knoblauch“).
2. Zutaten aus `vorrat.txt` (Grundvorrat) weglassen – das Skript filtert sie zusätzlich.
3. Erst Probelauf zeigen, dann eintragen:
   ```bash
   printf '%s\n' 'Zwiebeln | 2 rote' 'Sahne | 200 ml' | python3 bring.py -l Abendessen mehrere -n
   printf '%s\n' 'Zwiebeln | 2 rote' 'Sahne | 200 ml' | python3 bring.py -l Abendessen mehrere
   ```
   Den Probelauf nur dem Nutzer zeigen, wenn etwas unklar ist; sonst direkt eintragen.
4. Dem Nutzer kurz sagen, was hinzugefügt, was als Vorrat übersprungen und was schon auf der Liste war.

Bei Zweifeln, ob etwas Grundvorrat ist (z. B. Butter, Eier), eintragen und es in der Antwort erwähnen.

## Web-App

`app.py` (Server, nur Standardbibliothek) + `static/index.html` + `rezeptbuch.py` (liest/schreibt
`rezepte/*.md` verlustfrei). Läuft beim Nutzer auf einem Windows-PC „obiwahn“ (`start.bat`). Rezeptänderungen aus
der App landen in den .md-Dateien dort – vor Änderungen hier ggf. abgleichen.

## Zugang

- Login braucht `BRING_EMAIL` und `BRING_PASSWORD` als Umgebungsvariablen. Nie in Dateien,
  Commits oder Logs schreiben. Fehlen sie, den Nutzer fragen.
- Netzwerk: `api.getbring.com` und `web.getbring.com` müssen in der Umgebung freigegeben sein
  (Umgebung „Claude-Code“).
