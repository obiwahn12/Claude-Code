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
`rezepte/*.md` verlustfrei) + `abteilungen.py` (ordnet Zutaten den Bring!-Abteilungen zu: Bring!-Katalog,
sonst feste Liste/Stichworte, sonst „Eigene Artikel“ – neue Rezept-Zutaten dort ergänzen). Läuft im Alltag online (siehe unten); lokal nur zum Testen
(`python app.py`). Rezeptänderungen aus der Online-App landen auf dem Server – vor Änderungen hier abgleichen.

Vorratsschrank-Anbindung: `schrank.py` liest den Bestand der Schwester-App (/vorrat/, Repo
`D:\work\webdev\inventory`) nur – Pfad über `VORRATSSCHRANK_BESTAND` (setzt `manitu/essenplan.cgi`), lokal
ohne Variable aus. „Zutaten prüfen“ markiert Treffer als Status `schrank` (abgehakt = nicht kaufen, außer
`reicht` ist False bei Dosen/Gläsern). Abgleich: gleiche Sorte, Oberbegriff am Wortende mit Ausnahmen
(`ANDERES_PRODUKT`) und gleicher Bring!-Abteilung, `ZUORDNUNG` (Spaghetti → Nudeln …). Pflege/Haushalt
(gespeicherte `abteilung` im Bestand) werden ignoriert. Vorrat-Seite zeigt den Schrank nur an (`/api/schrank`).

Anmeldung: Cookie statt Basic-Auth, gemeinsam für /essen/ und /vorrat/ – `anmeldung.py` (identisch in beiden Repos,
Änderungen in beide übernehmen). Passwort-Hash + Geheimnis liegen in `<Domain>/.anmeldung/passwort.json`
(`ANMELDUNG_DIR`, setzt das CGI; lokal ohne Variable = keine Anmeldung). Neues Passwort setzt der Nutzer selbst mit
`python manitu/passwort.py` (im Essenplan-Repo; fragt verdeckt, lädt nur den Hash hoch, meldet alle Geräte ab) –
nie das Passwort entgegennehmen. Cookie 180 Tage, wird bei Nutzung verlängert; 5 Fehlversuche = 15 Min. Sperre.

Webserver (manitu, CGI): `manitu/essenplan.cgi` ruft `app.dispatch()` auf, `manitu/htaccess.vorlage`
leitet alles dorthin um (nur HTTPS). `python manitu/paket.py --serverpfad …`
baut das Upload-Paket in `manitu/upload/` (nicht im Git). Daten liegen dort in `daten/`
(`ESSENPLAN_DATA`); Rezeptänderungen aus der Online-App sind dann nur auf dem Server.
`--mit-daten` nur beim ersten Hochladen, sonst werden Online-Änderungen überschrieben.
Updates hochladen: `python manitu/hochladen.py` – per SSH als ssh300011556@ngcobalt403.manitu.net mit dem
Schlüssel `~/.ssh/manitu_upload` (Host-Key in `~/.ssh/known_hosts_manitu`), kein Passwort nötig. Vergleicht
Prüfsummen mit dem Server, lädt nur geänderte Programmdateien hoch und setzt die Rechte; `daten/` und
`.htpasswd` fasst es nie an. `-n` = Probelauf, `--alle` = alles neu. Online-Rezepte lassen sich per SSH
lesen (`daten/rezepte/`), z. B. um sie vor Rezeptänderungen im Repo abzugleichen.

## Zugang

- Login braucht `BRING_EMAIL` und `BRING_PASSWORD` als Umgebungsvariablen. Nie in Dateien,
  Commits oder Logs schreiben. Fehlen sie, den Nutzer fragen.
- Netzwerk: `api.getbring.com` und `web.getbring.com` müssen in der Umgebung freigegeben sein
  (Umgebung „Claude-Code“).
