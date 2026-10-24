@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Standardsoftware installieren
rem Beschreibung:      Installiert mehrere Programme auf einmal – z. B. die übliche Ausstattung eines Arbeitsplatzes. Fehlgeschlagene Pakete werden am Ende aufgelistet.
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Benötigte Rechte:  keine
rem Enthaltene Schritte:
rem    1. Mehrere Pakete installieren [Risiko: gelb]
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
set "OKM_RC=0"
rem /nopause: am Ende nicht auf eine Taste warten (Fernwartung/RMM)
if /i "%~1"=="/nopause" set "OKM_KEINE_PAUSE=1"
set "OKM_TIPP="
echo(==============================================
>>"%OKM_LOG%" echo(==============================================
echo( okm Script-Baukasten · Standardsoftware installieren
>>"%OKM_LOG%" echo( okm Script-Baukasten · Standardsoftware installieren
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

echo(Rechte: ohne erhöhte Rechte
>>"%OKM_LOG%" echo(Rechte: ohne erhöhte Rechte

rem Rückgabewerte der Schritte (Namen vergibt der Baukasten; leer = unbekannt)
set "OKM_S1_FEHLGESCHLAGEN="

rem --------------------------------------------------------------------
rem Schritt 1/1: Mehrere Pakete installieren (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP=Die Paket-IDs im Software-Katalog prüfen; die nicht installierten stehen in der Meldung oben."
echo([1/1] Pakete werden installiert: Mozilla.Firefox, 7zip.7zip, VideoLAN.VLC ...
>>"%OKM_LOG%" echo([1/1] Pakete werden installiert: Mozilla.Firefox, 7zip.7zip, VideoLAN.VLC ...
(call )
(
set /a OKM_FEHLT=0
if exist "%TEMP%\okm-pakete-fehlt.txt" del "%TEMP%\okm-pakete-fehlt.txt"
for %%p in ("Mozilla.Firefox" "7zip.7zip" "VideoLAN.VLC") do (
  echo --- %%~p
  winget install --id %%~p -e --source winget --silent --accept-package-agreements --accept-source-agreements || (set /a OKM_FEHLT+=1 & >>"%TEMP%\okm-pakete-fehlt.txt" echo %%~p)
)
set /a OKM_S1_FEHLGESCHLAGEN=OKM_FEHLT
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
if defined OKM_S1_FEHLGESCHLAGEN for /f "delims=-0123456789" %%z in ("%OKM_S1_FEHLGESCHLAGEN%") do set "OKM_S1_FEHLGESCHLAGEN="
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
