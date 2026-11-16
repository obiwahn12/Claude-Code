# Bring!-Einkaufslisten

Dieses Repo enthält `bring.py`, ein CLI für die inoffizielle Bring!-API (siehe README.md).
Kommunikation mit dem Nutzer auf Deutsch.

## Rezept → Liste „Abendessen“

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

## Zugang

- Login braucht `BRING_EMAIL` und `BRING_PASSWORD` als Umgebungsvariablen. Nie in Dateien,
  Commits oder Logs schreiben. Fehlen sie, den Nutzer fragen.
- Netzwerk: `api.getbring.com` und `web.getbring.com` müssen in der Umgebung freigegeben sein
  (Umgebung „Claude-Code“).
