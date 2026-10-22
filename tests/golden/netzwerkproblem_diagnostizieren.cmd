@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Netzwerkproblem diagnostizieren
rem Beschreibung:      Prüft Schritt für Schritt Netzwerkeinstellungen, Router, Internet, Namensauflösung und ob ein bestimmter Server erreichbar ist (Ping, Traceroute, Port).
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Enthaltene Schritte:
rem    1. IP-Konfiguration anzeigen [Risiko: gruen]
rem    2. Ping auf Ziel [Risiko: gruen]
rem    3. Namensauflösung (DNS) testen [Risiko: gruen]
rem    4. Ping auf Ziel [Risiko: gruen]
rem    5. Traceroute [Risiko: gruen]
rem
rem Generiert mit dem okm Script-Baukasten
rem ======================================================================

set "OKM_TS="
for /f "delims=" %%T in ('powershell -NoProfile -NonInteractive -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "OKM_TS=%%T"
if not defined OKM_TS set "OKM_TS=%RANDOM%"
set "OKM_LOG=%TEMP%\okm-script-%OKM_TS%.log"
set "OKM_TMP=%TEMP%\okm-script-%OKM_TS%.tmp"
set "OKM_GESAMT=5"
set "OKM_OK=0"
set "OKM_SCHRITT=0"
set "OKM_RC=0"
set "OKM_TIPP="
echo(==============================================
>>"%OKM_LOG%" echo(==============================================
echo( okm Script-Baukasten · Netzwerkproblem diagnostizieren
>>"%OKM_LOG%" echo( okm Script-Baukasten · Netzwerkproblem diagnostizieren
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

rem --------------------------------------------------------------------
rem Schritt 1/5: IP-Konfiguration anzeigen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP="
echo([1/5] IP-Konfiguration wird angezeigt ...
>>"%OKM_LOG%" echo([1/5] IP-Konfiguration wird angezeigt ...
(call )
(
ipconfig /all
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 2/5: Ping auf Ziel (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
set "OKM_TIPP=Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping."
echo([2/5] Ping auf 1.1.1.1 ^(2x^) ...
>>"%OKM_LOG%" echo([2/5] Ping auf 1.1.1.1 ^(2x^) ...
(call )
(
ping -n 2 "1.1.1.1"
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
rem Schritt 3/5: Namensauflösung (DNS) testen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=3"
set "OKM_TIPP="
echo([3/5] DNS-Auflösung von www.microsoft.com wird geprüft ...
>>"%OKM_LOG%" echo([3/5] DNS-Auflösung von www.microsoft.com wird geprüft ...
(call )
(
nslookup "www.microsoft.com"
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
rem Schritt 4/5: Ping auf Ziel (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=4"
set "OKM_TIPP=Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping."
echo([4/5] Ping auf intranet.okm.local ^(4x^) ...
>>"%OKM_LOG%" echo([4/5] Ping auf intranet.okm.local ^(4x^) ...
(call )
(
ping -n 4 "intranet.okm.local"
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
rem Schritt 5/5: Traceroute (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=5"
set "OKM_TIPP="
echo([5/5] Traceroute zu intranet.okm.local ...
>>"%OKM_LOG%" echo([5/5] Traceroute zu intranet.okm.local ...
(call )
(
tracert -d -h 30 "intranet.okm.local"
cmd /c exit 0
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
