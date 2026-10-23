@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Support-Infos anzeigen
rem Beschreibung:      Zeigt Rechnername, Benutzer, IP-Adresse, Betriebssystem, Seriennummer und ggf. TeamViewer-/AnyDesk-ID – alles, was der Support am Telefon fragt.
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Benötigte Rechte:  keine
rem Enthaltene Schritte:
rem    1. Support-Infos anzeigen [Risiko: gruen]
rem    2. Meldung/Pause für den Benutzer [Risiko: gruen]
rem
rem Generiert mit dem okm Script-Baukasten
rem ======================================================================

set "OKM_TS="
for /f "delims=" %%T in ('powershell -NoProfile -NonInteractive -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "OKM_TS=%%T"
if not defined OKM_TS set "OKM_TS=%RANDOM%"
set "OKM_LOG=%TEMP%\okm-script-%OKM_TS%.log"
set "OKM_TMP=%TEMP%\okm-script-%OKM_TS%.tmp"
set "OKM_GESAMT=2"
set "OKM_OK=0"
set "OKM_SCHRITT=0"
set "OKM_RC=0"
rem /nopause: am Ende nicht auf eine Taste warten (Fernwartung/RMM)
if /i "%~1"=="/nopause" set "OKM_KEINE_PAUSE=1"
set "OKM_TIPP="
echo(==============================================
>>"%OKM_LOG%" echo(==============================================
echo( okm Script-Baukasten · Support-Infos anzeigen
>>"%OKM_LOG%" echo( okm Script-Baukasten · Support-Infos anzeigen
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

echo(Rechte: ohne erhöhte Rechte
>>"%OKM_LOG%" echo(Rechte: ohne erhöhte Rechte

rem --------------------------------------------------------------------
rem Schritt 1/2: Support-Infos anzeigen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP="
echo([1/2] Support-Infos werden gesammelt ...
>>"%OKM_LOG%" echo([1/2] Support-Infos werden gesammelt ...
(call )
(
echo Rechnername:   %COMPUTERNAME%
echo Benutzer:      %USERDOMAIN%\%USERNAME%
ipconfig | findstr /C:"IPv4"
ver
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 2/2: Meldung/Pause für den Benutzer (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
set "OKM_TIPP="
echo([2/2] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([2/2] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Diese Angaben bitte dem Support durchgeben.") do echo(%%M
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
