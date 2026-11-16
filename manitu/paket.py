#!/usr/bin/env python3
"""Upload-Paket für die Essenplan-App auf dem Webspace bauen (CGI, z. B. manitu).

    python manitu/paket.py --serverpfad /home/sites/.../web/meine-domain.de
    python manitu/paket.py --serverpfad ... --mit-daten        # erstes Hochladen
    python manitu/paket.py --serverpfad ... --passwort familie # .htpasswd anlegen

Ergebnis liegt in manitu/upload/<ordner>/ und wird 1:1 per FTP in den Webspace kopiert
(Binärmodus, Rechte siehe Ausgabe). Alle Textdateien bekommen Linux-Zeilenenden.

--mit-daten legt daten/ mit rezepte/ und vorrat.txt aus dem Repo an. Nur beim ersten Mal
verwenden: Später würde das Hochladen die in der App geänderten Rezepte überschreiben.

--passwort fragt das Passwort verdeckt ab und schreibt nur den Hash (APR1-MD5,
wie `htpasswd -m`) in .htpasswd. Das Passwort selbst wird nirgends gespeichert.
"""

import argparse
import getpass
import hashlib
import secrets
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HIER = Path(__file__).resolve().parent
ITOA64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def apr1(passwort, salt):
    """Apache-APR1-MD5-Hash, kompatibel zu `htpasswd -m` und `openssl passwd -apr1`."""
    pw, s, magic = passwort.encode(), salt.encode(), b"$apr1$"
    alt = hashlib.md5(pw + s + pw).digest()
    ctx = pw + magic + s
    for i in range(len(pw), 0, -16):
        ctx += alt[:min(16, i)]
    i = len(pw)
    while i:
        ctx += b"\0" if i & 1 else pw[:1]
        i >>= 1
    final = hashlib.md5(ctx).digest()
    for i in range(1000):
        c = pw if i & 1 else final
        if i % 3:
            c += s
        if i % 7:
            c += pw
        c += final if i & 1 else pw
        final = hashlib.md5(c).digest()

    def to64(v, n):
        out = ""
        for _ in range(n):
            out += ITOA64[v & 0x3F]
            v >>= 6
        return out

    f = final
    teile = [(f[0] << 16) | (f[6] << 8) | f[12], (f[1] << 16) | (f[7] << 8) | f[13],
             (f[2] << 16) | (f[8] << 8) | f[14], (f[3] << 16) | (f[9] << 8) | f[15],
             (f[4] << 16) | (f[10] << 8) | f[5]]
    return f"$apr1${salt}${''.join(to64(t, 4) for t in teile)}{to64(f[11], 2)}"


def text_kopieren(quelle, ziel, ersetzen=None):
    t = Path(quelle).read_text(encoding="utf-8").replace("\r\n", "\n")
    for k, v in (ersetzen or {}).items():
        t = t.replace(k, v)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(t.encode("utf-8"))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--serverpfad", required=True,
                   help="voller Pfad zum Webspace-Ordner der Domain, z. B. /home/sites/site123/web/domain.de")
    p.add_argument("--ordner", default="essen", help="Unterordner auf der Website (Standard: essen)")
    p.add_argument("--mit-daten", action="store_true", help="daten/ mit Rezepten und Vorrat mitliefern")
    p.add_argument("--passwort", metavar="BENUTZER", help=".htpasswd mit diesem Benutzernamen anlegen")
    a = p.parse_args()

    ziel = HIER / "upload" / a.ordner
    if ziel.exists():
        shutil.rmtree(ziel)
    ziel.mkdir(parents=True)

    server = f"{a.serverpfad.rstrip('/')}/{a.ordner}"
    text_kopieren(HIER / "essenplan.cgi", ziel / "essenplan.cgi")
    text_kopieren(HIER / "htaccess.vorlage", ziel / ".htaccess",
                  {"{{AUTHUSERFILE}}": f"{server}/.htpasswd"})
    for name in ("app.py", "abteilungen.py", "bring.py", "rezeptbuch.py"):
        text_kopieren(REPO / name, ziel / name)
    text_kopieren(REPO / "static" / "index.html", ziel / "static" / "index.html")

    if a.mit_daten:
        for md in sorted((REPO / "rezepte").glob("*.md")):
            text_kopieren(md, ziel / "daten" / "rezepte" / md.name)
        text_kopieren(REPO / "vorrat.txt", ziel / "daten" / "vorrat.txt")

    if a.passwort:
        pw = getpass.getpass(f"Passwort für {a.passwort}: ")
        if pw != getpass.getpass("Nochmal: "):
            sys.exit("Passwörter stimmen nicht überein – nichts geschrieben.")
        if len(pw) < 10:
            sys.exit("Bitte mindestens 10 Zeichen – nichts geschrieben.")
        salt = "".join(secrets.choice(ITOA64) for _ in range(8))
        (ziel / ".htpasswd").write_bytes(f"{a.passwort}:{apr1(pw, salt)}\n".encode())

    print(f"Paket fertig: {ziel}")
    print(f"Per FTP (Binärmodus) hochladen nach: {server}/")
    print("Rechte danach setzen:")
    print("  Ordner (auch static/, daten/, daten/rezepte/): 755")
    print("  essenplan.cgi: 755")
    print("  alle anderen Dateien: 644")
    if not (ziel / ".htpasswd").exists():
        print("Hinweis: keine .htpasswd im Paket. Beim ersten Mal mit --passwort BENUTZER bauen.")


if __name__ == "__main__":
    main()
