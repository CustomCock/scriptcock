@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             .reg-Datei sicher importieren
rem Beschreibung:      Importiert eine .reg-Datei, sichert vorher alle betroffenen Schlüssel und legt eine Rückgängig-Datei an.
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Benötigte Rechte:  Administrator (Schritt 1, 2)
rem Enthaltene Schritte:
rem    1. Wiederherstellungspunkt anlegen [Risiko: gelb, Admin]
rem    2. .reg-Datei importieren [Risiko: rot, Admin]
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
rem Registry: Rückgängig-Dateien (reg export) landen hier
set "OKM_REG_SICHERUNG=%TEMP%\okm-registry-backup-%OKM_TS%-%RANDOM%"
rem Registry: was nötig ist, damit Änderungen wirken (Rang, siehe Zusammenfassung)
set "OKM_WIRKUNG=0"
set "OKM_WIRKUNG_UNBEKANNT="
echo(==============================================
>>"%OKM_LOG%" echo(==============================================
echo( okm Script-Baukasten · .reg-Datei sicher importieren
>>"%OKM_LOG%" echo( okm Script-Baukasten · .reg-Datei sicher importieren
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

rem Rechte: Administrator für Schritt 1 (Wiederherstellungspunkt anlegen), Schritt 2 (.reg-Datei importieren)
net session >nul 2>&1
if errorlevel 1 goto :okm_rechte_anfordern
echo(Rechte: als Administrator gestartet
>>"%OKM_LOG%" echo(Rechte: als Administrator gestartet

rem --------------------------------------------------------------------
rem Schritt 1/2: Wiederherstellungspunkt anlegen (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP=Computerschutz prüfen (Systemsteuerung → System → Computerschutz) und den Dienst „Volumeschattenkopie“ (VSS)."
echo([1/2] Wiederherstellungspunkt „Vor .reg-Import durch okm-Script“ wird angelegt ...
>>"%OKM_LOG%" echo([1/2] Wiederherstellungspunkt „Vor .reg-Import durch okm-Script“ wird angelegt ...
(call )
(
set OKM_BESCHREIBUNG="Vor .reg-Import durch okm-Script"
powershell -NoProfile -Command "$v = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count; Checkpoint-Computer -Description $env:OKM_BESCHREIBUNG.Trim([char]34) -RestorePointType MODIFY_SETTINGS -WarningAction SilentlyContinue; $p = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue | Sort-Object -Property SequenceNumber); if ($p.Count -gt $v) { 'Wiederherstellungspunkt angelegt.' } elseif ($p.Count -gt 0 -and $p[-1].ConvertToDateTime($p[-1].CreationTime) -gt (Get-Date).AddHours(-24)) { 'WARNUNG: Kein neuer Punkt - es gibt schon einen aus den letzten 24 Stunden.' } else { throw 'Es wurde kein Wiederherstellungspunkt angelegt.' }"
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 2/2: .reg-Datei importieren (Risiko: rot)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
set "OKM_TIPP=Ist die Datei erreichbar und eine echte .reg-Datei (Windows Registry Editor Version 5.00)?"
echo([2/2] Registry: \\fileserver\IT\Einstellungen\app.reg wird importiert ...
>>"%OKM_LOG%" echo([2/2] Registry: \\fileserver\IT\Einstellungen\app.reg wird importiert ...
rem Vorschau (vor der Bestätigung)
(call )
(
if not exist "\\fileserver\IT\Einstellungen\app.reg" (
  echo Die Datei gibt es nicht.
  cmd /c exit 1
) else (
  echo Betroffene Schlüssel:
  type "\\fileserver\IT\Einstellungen\app.reg" | findstr /b /c:"["
  type "\\fileserver\IT\Einstellungen\app.reg" | findstr /i /c:"[HKEY_CURRENT_USER" /c:"[-HKEY_CURRENT_USER" >nul
  if not errorlevel 1 (
    echo Die Datei enthält HKEY_CURRENT_USER - nach dem Admin-Neustart wäre das das Profil des Admin-Kontos.
    echo Bitte die Einstellung mit „Registry-Wert setzen“ und einem Benutzer-Bereich übernehmen.
    cmd /c exit 1
  ) else (
    type "\\fileserver\IT\Einstellungen\app.reg" | findstr /i /c:"HKEY_LOCAL_MACHINE\\SAM]" /c:"HKEY_LOCAL_MACHINE\\SAM\\" /c:"HKEY_LOCAL_MACHINE\\SECURITY]" /c:"HKEY_LOCAL_MACHINE\\SECURITY\\" /c:"HKEY_LOCAL_MACHINE\\BCD00000000]" /c:"HKEY_LOCAL_MACHINE\\BCD00000000\\" >nul
    if not errorlevel 1 (
      echo Die Datei schreibt in einen gesperrten Bereich der Registry.
      cmd /c exit 1
    ) else (
      cmd /c exit 0
    )
  )
)
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
echo(ACHTUNG: Dieser Schritt ist destruktiv: .reg-Datei importieren
set "OKM_ANTWORT="
set /p "OKM_ANTWORT=Zum Fortfahren JA eingeben (alles andere bricht ab): "
if not defined OKM_ANTWORT goto :okm_abbruch
set "OKM_ANTWORT=%OKM_ANTWORT:"=%"
if not "%OKM_ANTWORT%"=="JA" goto :okm_abbruch
(call )
(
type "\\fileserver\IT\Einstellungen\app.reg" | findstr /i /c:"[HKEY_CURRENT_USER" /c:"[-HKEY_CURRENT_USER" >nul
if not errorlevel 1 (
  echo Die Datei enthält HKEY_CURRENT_USER - nach dem Admin-Neustart wäre das das Profil des Admin-Kontos.
  echo Bitte die Einstellung mit „Registry-Wert setzen“ und einem Benutzer-Bereich übernehmen.
  cmd /c exit 1
) else (
  type "\\fileserver\IT\Einstellungen\app.reg" | findstr /i /c:"HKEY_LOCAL_MACHINE\\SAM]" /c:"HKEY_LOCAL_MACHINE\\SAM\\" /c:"HKEY_LOCAL_MACHINE\\SECURITY]" /c:"HKEY_LOCAL_MACHINE\\SECURITY\\" /c:"HKEY_LOCAL_MACHINE\\BCD00000000]" /c:"HKEY_LOCAL_MACHINE\\BCD00000000\\" >nul
  if not errorlevel 1 (
    echo Die Datei schreibt in einen gesperrten Bereich der Registry.
    cmd /c exit 1
  ) else (
    cmd /c exit 0
  )
)
if not errorlevel 1 (
  if not exist "%OKM_REG_SICHERUNG%\" mkdir "%OKM_REG_SICHERUNG%"
  type "\\fileserver\IT\Einstellungen\app.reg" | findstr /n /b /c:"[" > "%TEMP%\okm-import-%OKM_TS%.txt"
  for /f "usebackq tokens=1* delims=:" %%a in ("%TEMP%\okm-import-%OKM_TS%.txt") do for /f "tokens=* delims=[-" %%c in ("%%b") do for /f "delims=]" %%d in ("%%c") do reg export "%%d" "%OKM_REG_SICHERUNG%\%OKM_SCHRITT%-%%a.reg" /y /reg:64 >nul 2>&1
  del "%TEMP%\okm-import-%OKM_TS%.txt" >nul 2>&1
  reg import "\\fileserver\IT\Einstellungen\app.reg" /reg:64
)
if not errorlevel 1 if 0 GTR %OKM_WIRKUNG% set OKM_WIRKUNG=0
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
if exist "%OKM_REG_SICHERUNG%\" echo( Rückgängig machen: die .reg-Dateien in %OKM_REG_SICHERUNG% doppelklicken (höchste Nummer zuerst).
if "%OKM_WIRKUNG%"=="1" echo( Damit die Änderungen wirken: Explorer neu starten
if "%OKM_WIRKUNG%"=="2" echo( Damit die Änderungen wirken: Gruppenrichtlinien aktualisieren (gpupdate)
if "%OKM_WIRKUNG%"=="3" echo( Damit die Änderungen wirken: neu anmelden
if "%OKM_WIRKUNG%"=="4" echo( Damit die Änderungen wirken: Rechner neu starten
if defined OKM_WIRKUNG_UNBEKANNT echo( Ob alle Änderungen sofort wirken, ist offen - im Zweifel neu anmelden.
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
if exist "%OKM_REG_SICHERUNG%\" echo( Rückgängig machen: die .reg-Dateien in %OKM_REG_SICHERUNG% doppelklicken (höchste Nummer zuerst).
if "%OKM_WIRKUNG%"=="1" echo( Damit die Änderungen wirken: Explorer neu starten
if "%OKM_WIRKUNG%"=="2" echo( Damit die Änderungen wirken: Gruppenrichtlinien aktualisieren (gpupdate)
if "%OKM_WIRKUNG%"=="3" echo( Damit die Änderungen wirken: neu anmelden
if "%OKM_WIRKUNG%"=="4" echo( Damit die Änderungen wirken: Rechner neu starten
if defined OKM_WIRKUNG_UNBEKANNT echo( Ob alle Änderungen sofort wirken, ist offen - im Zweifel neu anmelden.
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
if exist "%OKM_REG_SICHERUNG%\" echo( Rückgängig machen: die .reg-Dateien in %OKM_REG_SICHERUNG% doppelklicken (höchste Nummer zuerst).
if "%OKM_WIRKUNG%"=="1" echo( Damit die Änderungen wirken: Explorer neu starten
if "%OKM_WIRKUNG%"=="2" echo( Damit die Änderungen wirken: Gruppenrichtlinien aktualisieren (gpupdate)
if "%OKM_WIRKUNG%"=="3" echo( Damit die Änderungen wirken: neu anmelden
if "%OKM_WIRKUNG%"=="4" echo( Damit die Änderungen wirken: Rechner neu starten
if defined OKM_WIRKUNG_UNBEKANNT echo( Ob alle Änderungen sofort wirken, ist offen - im Zweifel neu anmelden.
echo( Protokoll: "%OKM_LOG%"
>>"%OKM_LOG%" echo( Protokoll: "%OKM_LOG%"
echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 2

:okm_rechte_anfordern
echo(Dieses Script braucht Administratorrechte für: Schritt 1 ^(Wiederherstellungspunkt anlegen^), Schritt 2 ^(.reg-Datei importieren^).
>>"%OKM_LOG%" echo(Dieses Script braucht Administratorrechte für: Schritt 1 ^(Wiederherstellungspunkt anlegen^), Schritt 2 ^(.reg-Datei importieren^).
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
if exist "%OKM_REG_SICHERUNG%\" echo( Rückgängig machen: die .reg-Dateien in %OKM_REG_SICHERUNG% doppelklicken (höchste Nummer zuerst).
if "%OKM_WIRKUNG%"=="1" echo( Damit die Änderungen wirken: Explorer neu starten
if "%OKM_WIRKUNG%"=="2" echo( Damit die Änderungen wirken: Gruppenrichtlinien aktualisieren (gpupdate)
if "%OKM_WIRKUNG%"=="3" echo( Damit die Änderungen wirken: neu anmelden
if "%OKM_WIRKUNG%"=="4" echo( Damit die Änderungen wirken: Rechner neu starten
if defined OKM_WIRKUNG_UNBEKANNT echo( Ob alle Änderungen sofort wirken, ist offen - im Zweifel neu anmelden.
echo( Protokoll: "%OKM_LOG%"
>>"%OKM_LOG%" echo( Protokoll: "%OKM_LOG%"
echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
del "%OKM_TMP%" >nul 2>&1
if not defined OKM_KEINE_PAUSE pause
endlocal
exit /b 1
