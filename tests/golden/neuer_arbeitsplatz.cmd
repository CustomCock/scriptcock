@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Neuer Arbeitsplatz einrichten
rem Beschreibung:      Gibt einem neuen Rechner seinen Namen, stellt die Uhrzeit richtig und installiert die Standardsoftware. Danach einmal neu starten.
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Benötigte Rechte:  Administrator (Schritt 1, 2)
rem Enthaltene Schritte:
rem    1. Rechner umbenennen [Risiko: gelb, Admin]
rem    2. Uhrzeit synchronisieren [Risiko: gelb, Admin]
rem    3. Mehrere Pakete installieren [Risiko: gelb]
rem    4. Meldung/Pause für den Benutzer [Risiko: gruen]
rem
rem Generiert mit dem okm Script-Baukasten
rem ======================================================================

set "OKM_TS="
for /f "delims=" %%T in ('powershell -NoProfile -NonInteractive -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "OKM_TS=%%T"
if not defined OKM_TS set "OKM_TS=%RANDOM%"
set "OKM_LOG=%TEMP%\okm-script-%OKM_TS%.log"
set "OKM_TMP=%TEMP%\okm-script-%OKM_TS%.tmp"
set "OKM_GESAMT=4"
set "OKM_OK=0"
set "OKM_SCHRITT=0"
set "OKM_RC=0"
rem /nopause: am Ende nicht auf eine Taste warten (Fernwartung/RMM)
if /i "%~1"=="/nopause" set "OKM_KEINE_PAUSE=1"
set "OKM_TIPP="
echo(==============================================
>>"%OKM_LOG%" echo(==============================================
echo( okm Script-Baukasten · Neuer Arbeitsplatz einrichten
>>"%OKM_LOG%" echo( okm Script-Baukasten · Neuer Arbeitsplatz einrichten
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

rem Rechte: Administrator für Schritt 1 (Rechner umbenennen), Schritt 2 (Uhrzeit synchronisieren)
net session >nul 2>&1
if errorlevel 1 goto :okm_rechte_anfordern
echo(Rechte: als Administrator gestartet
>>"%OKM_LOG%" echo(Rechte: als Administrator gestartet

rem Rückgabewerte der Schritte (Namen vergibt der Baukasten; leer = unbekannt)
set "OKM_S3_FEHLGESCHLAGEN="

rem --------------------------------------------------------------------
rem Schritt 1/4: Rechner umbenennen (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP=Ist der Rechner Mitglied einer Domäne? Dann muss die IT ihn umbenennen."
echo([1/4] Rechner wird in PC-EMPFANG-01 umbenannt ...
>>"%OKM_LOG%" echo([1/4] Rechner wird in PC-EMPFANG-01 umbenannt ...
(call )
(
set OKM_NEUER_NAME="PC-EMPFANG-01"
powershell -NoProfile -Command "Rename-Computer -NewName $env:OKM_NEUER_NAME.Trim([char]34) -Force"
if errorlevel 1 (cmd /c exit 1) else (echo Der neue Name gilt nach dem nächsten Neustart.)
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 2/4: Uhrzeit synchronisieren (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
set "OKM_TIPP=Ist der Zeitserver erreichbar (Firewall, UDP-Port 123)? In Domänen gibt der Domänencontroller die Zeit vor."
echo([2/4] Uhrzeit wird mit dem Zeitserver abgeglichen ...
>>"%OKM_LOG%" echo([2/4] Uhrzeit wird mit dem Zeitserver abgeglichen ...
(call )
(
net start w32time >nul 2>&1
w32tm /resync /force
if errorlevel 1 (cmd /c exit 1) else (w32tm /query /status)
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 3/4: Mehrere Pakete installieren (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=3"
set "OKM_TIPP=Die Paket-IDs im Software-Katalog prüfen; die nicht installierten stehen in der Meldung oben."
echo([3/4] Pakete werden installiert: Mozilla.Firefox, 7zip.7zip ...
>>"%OKM_LOG%" echo([3/4] Pakete werden installiert: Mozilla.Firefox, 7zip.7zip ...
(call )
(
set /a OKM_FEHLT=0
if exist "%TEMP%\okm-pakete-fehlt.txt" del "%TEMP%\okm-pakete-fehlt.txt"
for %%p in ("Mozilla.Firefox" "7zip.7zip") do (
  echo --- %%~p
  winget install --id %%~p -e --source winget --silent --accept-package-agreements --accept-source-agreements || (set /a OKM_FEHLT+=1 & >>"%TEMP%\okm-pakete-fehlt.txt" echo %%~p)
)
set /a OKM_S3_FEHLGESCHLAGEN=OKM_FEHLT
if exist "%TEMP%\okm-pakete-fehlt.txt" (
  echo Nicht installiert:
  type "%TEMP%\okm-pakete-fehlt.txt"
  del "%TEMP%\okm-pakete-fehlt.txt"
  cmd /c exit 1
) else (
  echo Alle Pakete installiert.
)
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
if defined OKM_S3_FEHLGESCHLAGEN for /f "delims=-0123456789" %%z in ("%OKM_S3_FEHLGESCHLAGEN%") do set "OKM_S3_FEHLGESCHLAGEN="
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 4/4: Meldung/Pause für den Benutzer (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=4"
set "OKM_TIPP="
echo([4/4] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([4/4] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Fertig. Bitte den Rechner jetzt neu starten, damit der neue Name gilt.") do echo(%%M
set "OKM_RC=%ERRORLEVEL%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
echo( Fertig: %OKM_OK% von %OKM_GESAMT% Schritten erfolgreich.
>>"%OKM_LOG%" echo( Fertig: %OKM_OK% von %OKM_GESAMT% Schritten erfolgreich.
echo( Protokoll: "%OKM_LOG%"
>>"%OKM_LOG%" echo( Protokoll: "%OKM_LOG%"
echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 0

:okm_fehler
echo(      FEHLER  Schritt %OKM_SCHRITT% endete mit Fehlercode %OKM_RC%.
>>"%OKM_LOG%" echo(      FEHLER  Schritt %OKM_SCHRITT% endete mit Fehlercode %OKM_RC%.
if defined OKM_TIPP echo(      Tipp: %OKM_TIPP%
if defined OKM_TIPP >>"%OKM_LOG%" echo(      Tipp: %OKM_TIPP%
echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
echo( Abgebrochen bei Schritt %OKM_SCHRITT% von %OKM_GESAMT%.
>>"%OKM_LOG%" echo( Abgebrochen bei Schritt %OKM_SCHRITT% von %OKM_GESAMT%.
echo( Erfolgreich bis dahin: %OKM_OK% von %OKM_GESAMT% Schritten.
>>"%OKM_LOG%" echo( Erfolgreich bis dahin: %OKM_OK% von %OKM_GESAMT% Schritten.
echo( Protokoll: "%OKM_LOG%"
>>"%OKM_LOG%" echo( Protokoll: "%OKM_LOG%"
echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 1

:okm_abbruch
echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
echo( Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt.
>>"%OKM_LOG%" echo( Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt.
echo( Protokoll: "%OKM_LOG%"
>>"%OKM_LOG%" echo( Protokoll: "%OKM_LOG%"
echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 2

:okm_rechte_anfordern
echo(Dieses Script braucht Administratorrechte für: Schritt 1 ^(Rechner umbenennen^), Schritt 2 ^(Uhrzeit synchronisieren^).
>>"%OKM_LOG%" echo(Dieses Script braucht Administratorrechte für: Schritt 1 ^(Rechner umbenennen^), Schritt 2 ^(Uhrzeit synchronisieren^).
echo(Es wird jetzt mit Administratorrechten neu gestartet ^(Windows fragt gleich nach^).
>>"%OKM_LOG%" echo(Es wird jetzt mit Administratorrechten neu gestartet ^(Windows fragt gleich nach^).
set "OKM_SELBST=%~f0"
powershell -NoProfile -Command "Start-Process -FilePath $env:OKM_SELBST -Verb RunAs"
if errorlevel 1 goto :okm_rechte_abgelehnt
echo(Läuft im neuen Fenster mit Administratorrechten weiter.
>>"%OKM_LOG%" echo(Läuft im neuen Fenster mit Administratorrechten weiter.
endlocal
exit /b 0

:okm_rechte_abgelehnt
echo(      FEHLER  Die Administratorrechte wurden abgelehnt (Benutzerkontensteuerung).
>>"%OKM_LOG%" echo(      FEHLER  Die Administratorrechte wurden abgelehnt (Benutzerkontensteuerung).
echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
echo( Abgebrochen: fehlende Administratorrechte.
>>"%OKM_LOG%" echo( Abgebrochen: fehlende Administratorrechte.
echo( Protokoll: "%OKM_LOG%"
>>"%OKM_LOG%" echo( Protokoll: "%OKM_LOG%"
echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 1
