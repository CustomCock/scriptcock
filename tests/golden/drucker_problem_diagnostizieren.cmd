@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Drucker-Problem diagnostizieren
rem Beschreibung:      Prüft, ob der Drucker im Netz erreichbar ist, ob der Druckdienst läuft und welche Drucker eingerichtet sind.
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Enthaltene Schritte:
rem    1. Ping auf Ziel [Risiko: gruen]
rem    2. Dienst-Status prüfen [Risiko: gruen]
rem    3. Installierte Drucker auflisten [Risiko: gruen]
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
set "OKM_TIPP="
echo(==============================================
>>"%OKM_LOG%" echo(==============================================
echo( okm Script-Baukasten · Drucker-Problem diagnostizieren
>>"%OKM_LOG%" echo( okm Script-Baukasten · Drucker-Problem diagnostizieren
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

rem --------------------------------------------------------------------
rem Schritt 1/3: Ping auf Ziel (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP=Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping."
echo([1/3] Ping auf 192.168.1.50 ^(2x^) ...
>>"%OKM_LOG%" echo([1/3] Ping auf 192.168.1.50 ^(2x^) ...
(call )
(
ping -n 2 "192.168.1.50"
if errorlevel 1 (
  echo Hinweis: Das Ziel hat nicht vollständig geantwortet.
  cmd /c exit 0
)
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 2/3: Dienst-Status prüfen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
set "OKM_TIPP="
echo([2/3] Status von Dienst Spooler wird abgefragt ...
>>"%OKM_LOG%" echo([2/3] Status von Dienst Spooler wird abgefragt ...
(call )
(
sc query "Spooler"
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 3/3: Installierte Drucker auflisten (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=3"
set "OKM_TIPP="
echo([3/3] Drucker werden aufgelistet ...
>>"%OKM_LOG%" echo([3/3] Drucker werden aufgelistet ...
(call )
(
reg query "HKCU\Software\Microsoft\Windows NT\CurrentVersion\Devices"
reg query "HKCU\Software\Microsoft\Windows NT\CurrentVersion\Windows" /v Device
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
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

:okm_kein_admin
echo(      FEHLER  Dieses Script braucht Administratorrechte.
>>"%OKM_LOG%" echo(      FEHLER  Dieses Script braucht Administratorrechte.
echo(      Bitte die Eingabeaufforderung mit Rechtsklick ^> "Als Administrator ausführen" öffnen
echo(      und das Script erneut starten.
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
