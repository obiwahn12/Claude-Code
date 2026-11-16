#!/bin/bash
# Doppelklick im Finder startet die Essenplan-App und öffnet sie im Browser.
cd "$(dirname "$0")" || exit 1
(sleep 1.5 && open "http://localhost:8765") &
python3 app.py --lan
