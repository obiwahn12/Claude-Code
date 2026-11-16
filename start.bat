@echo off
rem Doppelklick startet die Essenplan-App und oeffnet sie im Browser.
cd /d "%~dp0"
start "" cmd /c "timeout /t 2 >/dev/null & start http://localhost:8765"
where py >/dev/null 2>/dev/null && (py -3 app.py --lan) || (python app.py --lan)
pause
