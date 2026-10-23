@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Windows Update reparieren
rem Beschreibung:      Setzt die Windows-Update-Komponenten zurück. In PowerShell wird zusätzlich SetupDiag zur Fehleranalyse ausgeführt.
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Benötigte Rechte:  Administrator (Schritt 1, 2)
rem Enthaltene Schritte:
rem    1. Festplattenbelegung anzeigen [Risiko: gruen, Admin]
rem    2. Windows-Update-Komponenten zurücksetzen [Risiko: rot, Admin]
rem    3. Meldung/Pause für den Benutzer [Risiko: gruen]
rem
rem Generiert mit dem okm Script-Baukasten
rem ======================================================================

set "OKM_TS="
for /f "delims=" %%T in ('powershell -NoProfile -NonInteractive -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "OKM_TS=%%T"
if not defined OKM_TS set "OKM_TS=%RANDOM%"
set "OKM_LOG=%TEMP%\okm-script-%OKM_TS%.log"
set "OKM_TMP=%TEMP%\okm-script-%OKM_TS%.tmp"
set "OKM_GESAMT=3"
set "OKM_OK=0"
set "OKM_SCHRITT=0"
set "OKM_RC=0"
rem /nopause: am Ende nicht auf eine Taste warten (Fernwartung/RMM)
if /i "%~1"=="/nopause" set "OKM_KEINE_PAUSE=1"
set "OKM_TIPP="
echo(==============================================
>>"%OKM_LOG%" echo(==============================================
echo( okm Script-Baukasten · Windows Update reparieren
>>"%OKM_LOG%" echo( okm Script-Baukasten · Windows Update reparieren
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

rem Rechte: Administrator für Schritt 1 (Festplattenbelegung anzeigen), Schritt 2 (Windows-Update-Komponenten zurücksetzen)
net session >nul 2>&1
if errorlevel 1 goto :okm_rechte_anfordern
echo(Rechte: als Administrator gestartet
>>"%OKM_LOG%" echo(Rechte: als Administrator gestartet

rem --------------------------------------------------------------------
rem Schritt 1/3: Festplattenbelegung anzeigen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP="
echo([1/3] Festplattenbelegung wird ermittelt ...
>>"%OKM_LOG%" echo([1/3] Festplattenbelegung wird ermittelt ...
(call )
(
for %%D in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do if exist %%D:\ (
  echo Laufwerk %%D:
  fsutil volume diskfree %%D: 2>nul
)
cmd /c exit 0
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 2/3: Windows-Update-Komponenten zurücksetzen (Risiko: rot)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
set "OKM_TIPP="
echo([2/3] Windows-Update-Komponenten werden zurückgesetzt ...
>>"%OKM_LOG%" echo([2/3] Windows-Update-Komponenten werden zurückgesetzt ...
echo(ACHTUNG: Dieser Schritt ist destruktiv: Windows-Update-Komponenten zurücksetzen
set "OKM_ANTWORT="
set /p "OKM_ANTWORT=Zum Fortfahren JA eingeben (alles andere bricht ab): "
if not defined OKM_ANTWORT goto :okm_abbruch
set "OKM_ANTWORT=%OKM_ANTWORT:"=%"
if not "%OKM_ANTWORT%"=="JA" goto :okm_abbruch
(call )
(
net stop wuauserv
net stop cryptSvc
net stop bits
net stop msiserver
ren "%SystemRoot%\SoftwareDistribution" "SoftwareDistribution.%OKM_TS%.old"
ren "%SystemRoot%\System32\catroot2" "catroot2.%OKM_TS%.old"
net start wuauserv
net start cryptSvc
net start bits
net start msiserver
echo Bitte den Rechner neu starten und Windows Update erneut ausführen.
if exist "%SystemRoot%\SoftwareDistribution.%OKM_TS%.old" (cmd /c exit 0) else (cmd /c exit 1)
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 3/3: Meldung/Pause für den Benutzer (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=3"
set "OKM_TIPP="
echo([3/3] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([3/3] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Bitte den Rechner jetzt neu starten und Windows Update erneut ausführen.") do echo(%%M
pause
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
echo(Dieses Script braucht Administratorrechte für: Schritt 1 ^(Festplattenbelegung anzeigen^), Schritt 2 ^(Windows-Update-Komponenten zurücksetzen^).
>>"%OKM_LOG%" echo(Dieses Script braucht Administratorrechte für: Schritt 1 ^(Festplattenbelegung anzeigen^), Schritt 2 ^(Windows-Update-Komponenten zurücksetzen^).
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
