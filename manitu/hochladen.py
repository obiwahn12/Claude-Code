#!/usr/bin/env python3
"""Essenplan auf den manitu-Webspace hochladen – per SSH mit Schlüssel, ohne Passwort.

    python manitu/hochladen.py          # Paket bauen, geänderte Dateien hochladen, Rechte setzen
    python manitu/hochladen.py -n       # nur anzeigen, was sich gegenüber dem Server geändert hat

Anmeldung: SSH-Benutzer ssh300011556 mit dem Schlüssel ~/.ssh/manitu_upload (öffentlicher Teil im
manitu-Panel hinterlegt). Der Server wird nur akzeptiert, wenn sein Schlüssel zu
~/.ssh/known_hosts_manitu passt (Fingerprint aus dem manitu-Panel geprüft).

Vergleicht Prüfsummen direkt mit dem Server und lädt nur Geändertes hoch. Die neuen Dateien
landen erst in einem Hilfsordner und werden dann einzeln an ihren Platz verschoben (atomar),
damit die App nie eine halbe Datei ausliefert. daten/ (Rezepte, Vorrat, Woche, Bring!-Token)
und .htpasswd fasst das Skript nie an.
"""

import argparse
import hashlib
import io
import shlex
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paket  # noqa: E402

HOST = "ngcobalt403.manitu.net"
BENUTZER = "ssh300011556"
ZIEL = f"{paket.SERVERPFAD}/essen"
URL = "https://luise-und-peter.de/essen/"
AUSFUEHRBAR = {"essenplan.cgi"}
SCHLUESSEL = Path.home() / ".ssh" / "manitu_upload"
KNOWN_HOSTS = Path.home() / ".ssh" / "known_hosts_manitu"
HILFSORDNER = ".upload-neu"


def ssh(befehl, eingabe=None):
    """Befehl auf dem Server ausführen; liefert die Ausgabe, bricht bei Fehlern ab."""
    r = subprocess.run(
        ["ssh", "-i", str(SCHLUESSEL), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
         "-o", f"UserKnownHostsFile={KNOWN_HOSTS}", "-o", "StrictHostKeyChecking=yes",
         "-o", "ConnectTimeout=20", f"{BENUTZER}@{HOST}", befehl],
        input=eingabe, capture_output=True)
    if r.returncode != 0:
        sys.exit("Fehler auf dem Server:\n" + r.stderr.decode(errors="replace").strip())
    return r.stdout.decode(errors="replace")


def dateien(ordner):
    """Alle Dateien des Pakets relativ zum Ordner (z. B. „static/index.html“), ohne .htpasswd."""
    return sorted(p.relative_to(ordner).as_posix() for p in ordner.rglob("*") if p.is_file() and p.name != ".htpasswd")


def server_pruefsummen(namen):
    befehl = f"cd {shlex.quote(ZIEL)} && sha256sum -- {' '.join(shlex.quote(n) for n in namen)} 2>/dev/null; true"
    summen = {}
    for zeile in ssh(befehl).splitlines():
        summe, _, name = zeile.partition("  ")
        summen[name.strip()] = summe
    return summen


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-n", "--probe", action="store_true", help="nur anzeigen, nichts hochladen")
    p.add_argument("--alle", action="store_true", help="alle Dateien neu hochladen (z. B. um Rechte zu reparieren)")
    a = p.parse_args()
    if not SCHLUESSEL.exists() or not KNOWN_HOSTS.exists():
        sys.exit(f"Schlüssel {SCHLUESSEL} oder {KNOWN_HOSTS} fehlt (siehe Kopf dieses Skripts).")

    with tempfile.TemporaryDirectory() as tmp:
        hochladen(paket.bauen(ziel=Path(tmp) / "paket"), a.probe, a.alle)


def hochladen(paket_ordner, probe, alle=False):
    namen = dateien(paket_ordner)
    lokal = {n: hashlib.sha256((paket_ordner / n).read_bytes()).hexdigest() for n in namen}
    server = {} if alle else server_pruefsummen(namen)
    geaendert = [n for n in namen if server.get(n) != lokal[n]]
    if not geaendert:
        print(f"Nichts geändert – alles schon online ({URL}).")
        return
    print("Geändert:", ", ".join(geaendert))
    if probe:
        return

    puffer = io.BytesIO()
    with tarfile.open(fileobj=puffer, mode="w") as tar:
        for n in geaendert:
            tar.add(paket_ordner / n, arcname=n)

    q = shlex.quote
    schritte = [f"cd {q(ZIEL)}", f"rm -rf {HILFSORDNER}", f"mkdir {HILFSORDNER}", f"tar -xf - -C {HILFSORDNER}"]
    for n in geaendert:
        ordner = n.rpartition("/")[0]
        if ordner:
            schritte.append(f"{{ [ -d {q(ordner)} ] || {{ mkdir -p {q(ordner)} && chmod 2770 {q(ordner)}; }}; }}")
        rechte = "770" if Path(n).name in AUSFUEHRBAR else "660"
        schritte.append(f"chmod {rechte} {HILFSORDNER}/{q(n)} && mv -f {HILFSORDNER}/{q(n)} {q(n)}")
    schritte += [f"rm -rf {HILFSORDNER}", "{ [ -d daten ] || { mkdir daten && chmod 2770 daten; }; }"]
    # Ordner, die dem FTP- oder Webserver-Konto gehören, lassen sich nicht umstellen – dann eben nicht
    ssh("set -e; " + " && ".join(schritte) + "; chmod 2770 . static 2>/dev/null || true", puffer.getvalue())

    nachher = server_pruefsummen(geaendert)
    fehlt = [n for n in geaendert if nachher.get(n) != lokal[n]]
    if fehlt:
        sys.exit("Achtung, auf dem Server weicht ab: " + ", ".join(fehlt))
    print(f"Fertig: {len(geaendert)} Datei(en) hochgeladen und geprüft – {URL}")


if __name__ == "__main__":
    main()
