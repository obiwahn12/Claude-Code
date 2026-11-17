#!/usr/bin/env python3
"""Familienpasswort für Essenplan und Vorratsschrank (neu) setzen.

    python manitu/passwort.py

Fragt das neue Passwort verdeckt ab (zweimal), berechnet auf diesem PC einen PBKDF2-Hash und
legt nur Hash und ein neues Signatur-Geheimnis per SSH in <Domain>/.anmeldung/passwort.json ab
(Ordner per .htaccess gesperrt). Das Passwort selbst verlässt den PC nicht und wird nirgends
gespeichert. Mit dem neuen Geheimnis werden alle bisher angemeldeten Geräte abgemeldet.
"""

import getpass
import json
import secrets
import shlex
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER.parent))
import anmeldung  # noqa: E402
import hochladen  # noqa: E402  (SSH-Zugang wie beim Hochladen)
import paket  # noqa: E402

ORDNER = f"{paket.SERVERPFAD}/.anmeldung"


def main():
    pw = getpass.getpass("Neues Familienpasswort (wird nicht angezeigt): ")
    if pw != getpass.getpass("Nochmal zur Kontrolle: "):
        sys.exit("Die beiden Eingaben sind verschieden – nichts geändert.")
    if len(pw) < 10:
        sys.exit("Bitte mindestens 10 Zeichen – nichts geändert.")
    daten = json.dumps({"hash": anmeldung.hash_erzeugen(pw), "geheimnis": secrets.token_hex(32),
                        "gesetzt": time.strftime("%Y-%m-%d %H:%M")})
    del pw
    d = shlex.quote(ORDNER)
    hochladen.ssh(
        f"set -e; mkdir -p {d}; chmod 2770 {d} 2>/dev/null || true; "
        f"printf 'Require all denied\\n' > {d}/.htaccess; chmod 660 {d}/.htaccess; "
        f"cat > {d}/passwort.json.neu; chmod 660 {d}/passwort.json.neu; mv -f {d}/passwort.json.neu {d}/passwort.json",
        daten.encode())
    print("Neues Passwort gesetzt. Alle Geräte sind abgemeldet und melden sich mit dem neuen Passwort an.")


if __name__ == "__main__":
    main()
