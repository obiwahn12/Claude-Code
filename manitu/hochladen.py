#!/usr/bin/env python3
"""Essenplan auf den manitu-Webspace hochladen (verschlüsselt per FTPS, nur Standardbibliothek).

    python manitu/hochladen.py          # Paket bauen, geänderte Dateien hochladen, Rechte setzen
    python manitu/hochladen.py -n       # nur anzeigen, was hochgeladen würde (ohne Verbindung)
    python manitu/hochladen.py --alle   # alle Dateien hochladen, auch unveränderte

Das FTP-Passwort wird bei jedem Start verdeckt abgefragt und nirgends gespeichert.
Auf dem Server werden nur Programmdateien ersetzt: daten/ (Rezepte, Vorrat, Woche, Bring!-Token)
und .htpasswd
bleiben unangetastet. Jede Datei wird erst unter einem Hilfsnamen hochgeladen und dann
umbenannt, damit die App nie eine halbe Datei ausliefert.
"""

import argparse
import ftplib
import getpass
import hashlib
import json
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paket  # noqa: E402

HOST = "ngcobalt403.manitu.net"
BENUTZER = "ftp200030314"
# Wo der Ordner essen/ aus FTP-Sicht liegen kann (das FTP-Konto beginnt im Webspace-Ordner)
KANDIDATEN = ["/web/luise-und-peter.de/essen", "/luise-und-peter.de/essen", "/essen"]
STAND = Path(__file__).resolve().parent / ".hochgeladen.json"  # Prüfsummen vom letzten Hochladen (nicht im Git)
RECHTE_AUSFUEHRBAR = {"essenplan.cgi"}


class FTPS(ftplib.FTP_TLS):
    """FTPS, das die TLS-Sitzung für Datenverbindungen wiederverwendet (verlangen viele Server)."""

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
        return conn, size


def pruefsumme(datei):
    return hashlib.sha256(datei.read_bytes()).hexdigest()


def dateien(ordner):
    """Alle Dateien des Pakets relativ zum Ordner (z. B. „static/index.html“), ohne .htpasswd."""
    return sorted(p.relative_to(ordner).as_posix() for p in ordner.rglob("*") if p.is_file() and p.name != ".htpasswd")


def chmod(ftp, rechte, name):
    try:
        ftp.sendcmd(f"SITE CHMOD {rechte} {name}")
        return True
    except ftplib.error_perm:
        return False


def zielordner_finden(ftp):
    for pfad in KANDIDATEN:
        try:
            ftp.cwd(pfad)
        except ftplib.error_perm:
            continue
        if "essenplan.cgi" in ftp.nlst():
            return pfad
    print("Ordner essen/ nicht gefunden. Das sieht das FTP-Konto im Hauptordner:")
    ftp.cwd("/")
    for name in ftp.nlst():
        print("  ", name)
    sys.exit("Bitte den Pfad in KANDIDATEN (manitu/hochladen.py) ergänzen.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-n", "--probe", action="store_true", help="nur anzeigen, nichts hochladen")
    p.add_argument("--alle", action="store_true", help="alle Dateien hochladen, nicht nur geänderte")
    p.add_argument("--benutzer", default=BENUTZER)
    a = p.parse_args()

    paket_ordner = paket.bauen()
    try:
        alt = {} if a.alle else json.loads(STAND.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        alt = {}
    neu = {name: pruefsumme(paket_ordner / name) for name in dateien(paket_ordner)}
    geaendert = [name for name, summe in neu.items() if alt.get(name) != summe]

    if not geaendert:
        print("Nichts geändert – alles schon online.")
        return
    print("Hochzuladen:", ", ".join(geaendert))
    if a.probe:
        return

    passwort = getpass.getpass(f"FTP-Passwort für {a.benutzer}@{HOST}: ")
    ftp = FTPS(HOST, context=ssl.create_default_context(), timeout=30)
    try:
        ftp.login(a.benutzer, passwort)
    except ftplib.error_perm:
        sys.exit("Anmeldung fehlgeschlagen – Benutzer oder Passwort falsch.")
    finally:
        del passwort
    ftp.prot_p()  # auch die Dateiübertragung verschlüsseln

    basis = zielordner_finden(ftp)
    print(f"Ziel: {basis}")
    if "daten" not in ftp.nlst():
        ftp.mkd("daten")
        chmod(ftp, "755", "daten")
        print("  daten/ angelegt")

    ohne_rechte = []
    for name in geaendert:
        ftp.cwd(basis)
        *ordner, datei = name.split("/")
        for o in ordner:
            if o not in ftp.nlst():
                ftp.mkd(o)
                chmod(ftp, "755", o)
            ftp.cwd(o)
        with open(paket_ordner / name, "rb") as f:
            ftp.storbinary(f"STOR {datei}.neu", f)
        ftp.rename(f"{datei}.neu", datei)
        if not chmod(ftp, "755" if datei in RECHTE_AUSFUEHRBAR else "644", datei):
            ohne_rechte.append(name)
        print(f"  ✓ {name}")
        alt[name] = neu[name]
        STAND.write_text(json.dumps(alt, indent=1), encoding="utf-8")  # nach jeder Datei, falls es abbricht
    ftp.quit()

    print(f"Fertig: {len(geaendert)} Datei(en) hochgeladen – https://luise-und-peter.de/essen/")
    if ohne_rechte:
        print("Achtung: Rechte konnten nicht gesetzt werden für:", ", ".join(ohne_rechte))
        print("  Bitte im FTP-Programm setzen: essenplan.cgi 755, sonst 644.")


if __name__ == "__main__":
    main()
