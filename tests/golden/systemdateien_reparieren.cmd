@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Systemdateien reparieren (DISM + SFC)
rem Beschreibung:      Repariert beschädigte Windows-Systemdateien. Hilft bei seltsamen Fehlern, Abstürzen von Windows-Komponenten oder fehlgeschlagenen Updates.
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Enthaltene Schritte:
rem    1. Systemdateien reparieren (DISM + SFC) [Risiko: gelb, Admin]
rem
rem Generiert mit dem okm Script-Baukasten
rem ======================================================================

set "OKM_TS="
for /f "delims=" %%T in ('powershell -NoProfile -NonInteractive -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "OKM_TS=%%T"
if not defined OKM_TS set "OKM_TS=%RANDOM%"
set "OKM_LOG=%TEMP%\okm-script-%OKM_TS%.log"
set "OKM_TMP=%TEMP%\okm-script-%OKM_TS%.tmp"
set "OKM_GESAMT=1"
set "OKM_OK=0"
set "OKM_SCHRITT=0"
echo(okm Script-Baukasten: Systemdateien reparieren ^(DISM + SFC^)
>>"%OKM_LOG%" echo(okm Script-Baukasten: Systemdateien reparieren ^(DISM + SFC^)

rem Prüfung: Administratorrechte
net session >nul 2>&1
if errorlevel 1 goto :okm_kein_admin

rem --------------------------------------------------------------------
rem Schritt 1/1: Systemdateien reparieren (DISM + SFC) (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
echo([1/1] Systemdateien werden geprüft und repariert ^(dauert^) ...
>>"%OKM_LOG%" echo([1/1] Systemdateien werden geprüft und repariert ^(dauert^) ...
(call )
(
DISM /Online /Cleanup-Image /RestoreHealth
sfc /scannow
cmd /c exit 0
) >"%OKM_TMP%" 2>&1
if errorlevel 1 (set "OKM_RC=1") else if not errorlevel 0 (set "OKM_RC=1") else (set "OKM_RC=0")
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if "%OKM_RC%"=="1" goto :okm_fehler
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
