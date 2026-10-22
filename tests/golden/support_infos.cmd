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
echo(okm Script-Baukasten: Support-Infos anzeigen
>>"%OKM_LOG%" echo(okm Script-Baukasten: Support-Infos anzeigen

rem --------------------------------------------------------------------
rem Schritt 1/2: Support-Infos anzeigen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
echo([1/2] Support-Infos werden gesammelt ...
>>"%OKM_LOG%" echo([1/2] Support-Infos werden gesammelt ...
(call )
(
echo Rechnername:   %COMPUTERNAME%
echo Benutzer:      %USERDOMAIN%\%USERNAME%
ipconfig | findstr /C:"IPv4"
ver
) >"%OKM_TMP%" 2>&1
if errorlevel 1 (set "OKM_RC=1") else if not errorlevel 0 (set "OKM_RC=1") else (set "OKM_RC=0")
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if "%OKM_RC%"=="1" goto :okm_fehler
set /a OKM_OK+=1 >nul

rem --------------------------------------------------------------------
rem Schritt 2/2: Meldung/Pause für den Benutzer (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
echo([2/2] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([2/2] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Diese Angaben bitte dem Support durchgeben.") do echo(%%M
pause
if errorlevel 1 goto :okm_fehler
if not errorlevel 0 goto :okm_fehler
set /a OKM_OK+=1 >nul

echo(
echo(Fertig, %OKM_OK% von %OKM_GESAMT% Schritten erfolgreich.
>>"%OKM_LOG%" echo(Fertig, %OKM_OK% von %OKM_GESAMT% Schritten erfolgreich.
echo(Protokoll: "%OKM_LOG%"
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 0

:okm_fehler
echo(
echo(FEHLER in Schritt %OKM_SCHRITT% von %OKM_GESAMT%. Details siehe Ausgabe oben.
>>"%OKM_LOG%" echo(FEHLER in Schritt %OKM_SCHRITT% von %OKM_GESAMT%.
echo(Erfolgreich bis dahin: %OKM_OK% Schritte.
echo(Protokoll: "%OKM_LOG%"
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 1

:okm_abbruch
echo(Abgebrochen. Es wurde nichts weiter ausgeführt.
>>"%OKM_LOG%" echo(Abgebrochen durch Benutzer.
echo(Protokoll: "%OKM_LOG%"
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 2

:okm_kein_admin
echo(Dieses Script braucht Administratorrechte.
echo(Bitte die Eingabeaufforderung mit Rechtsklick ^> "Als Administrator ausführen" öffnen
echo(und das Script erneut starten.
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 1
