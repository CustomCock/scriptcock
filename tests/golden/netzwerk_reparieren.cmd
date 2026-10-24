@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Netzwerk reparieren
rem Beschreibung:      Die üblichen Handgriffe bei Netzwerkproblemen – DNS-Cache leeren, Netzwerkadapter neu starten, IP-Adresse neu holen – und danach prüfen, ob Internet und Namensauflösung wieder gehen.
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Benötigte Rechte:  Administrator (Schritt 2)
rem Enthaltene Schritte:
rem    1. DNS-Cache leeren [Risiko: gelb]
rem    2. Netzwerkadapter neu starten [Risiko: gelb, Admin]
rem    3. IP-Adresse erneuern (DHCP) [Risiko: gelb]
rem    4. Ping auf Ziel [Risiko: gruen]
rem    5. Namensauflösung (DNS) testen [Risiko: gruen]
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
rem /nopause: am Ende nicht auf eine Taste warten (Fernwartung/RMM)
if /i "%~1"=="/nopause" set "OKM_KEINE_PAUSE=1"
set "OKM_TIPP="
echo(==============================================
>>"%OKM_LOG%" echo(==============================================
echo( okm Script-Baukasten · Netzwerk reparieren
>>"%OKM_LOG%" echo( okm Script-Baukasten · Netzwerk reparieren
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

rem Rechte: Administrator für Schritt 2 (Netzwerkadapter neu starten)
net session >nul 2>&1
if errorlevel 1 goto :okm_rechte_anfordern
echo(Rechte: als Administrator gestartet
>>"%OKM_LOG%" echo(Rechte: als Administrator gestartet

rem Rückgabewerte der Schritte (Namen vergibt der Baukasten; leer = unbekannt)
set "OKM_S4_ERREICHBAR="

rem --------------------------------------------------------------------
rem Schritt 1/5: DNS-Cache leeren (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP="
echo([1/5] DNS-Cache wird geleert ...
>>"%OKM_LOG%" echo([1/5] DNS-Cache wird geleert ...
(call )
(
ipconfig /flushdns
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 2/5: Netzwerkadapter neu starten (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
set "OKM_TIPP=Stimmt der Adaptername? Bei WLAN danach ggf. kurz warten, bis die Verbindung wieder steht."
echo([2/5] Netzwerkadapter Ethernet wird neu gestartet ...
>>"%OKM_LOG%" echo([2/5] Netzwerkadapter Ethernet wird neu gestartet ...
(call )
(
set OKM_ADAPTER="Ethernet"
powershell -NoProfile -Command "$n = ([string]$env:OKM_ADAPTER).Trim([char]34); if ($n) { $a = @(Get-NetAdapter -Name $n -ErrorAction Stop) } else { $a = @(Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' }) }; if ($a.Count -eq 0) { throw 'Kein aktiver Netzwerkadapter gefunden.' }; $a | ForEach-Object { 'Neustart: ' + $_.Name; Restart-NetAdapter -InputObject $_ -Confirm:$false }; Start-Sleep -Seconds 5; Get-NetAdapter -Name ($a | ForEach-Object { $_.Name }) | Format-Table Name, Status, LinkSpeed -AutoSize"
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 3/5: IP-Adresse erneuern (DHCP) (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=3"
set "OKM_TIPP="
echo([3/5] IP-Adresse wird erneuert ...
>>"%OKM_LOG%" echo([3/5] IP-Adresse wird erneuert ...
(call )
(
ipconfig /release
ipconfig /renew
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
echo([4/5] Ping auf 1.1.1.1 ^(4x^) ...
>>"%OKM_LOG%" echo([4/5] Ping auf 1.1.1.1 ^(4x^) ...
(call )
(
ping -n 4 "1.1.1.1"
rem "set" setzt in .cmd-Dateien den Errorlevel auf 0 – daher erst danach "cmd /c exit"
if errorlevel 1 (
  set OKM_S4_ERREICHBAR=0
  echo Hinweis: Das Ziel hat nicht vollständig geantwortet.
  cmd /c exit 0
) else (
  set OKM_S4_ERREICHBAR=1
)
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
if defined OKM_S4_ERREICHBAR if not "%OKM_S4_ERREICHBAR%"=="1" set "OKM_S4_ERREICHBAR=0"
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 5/5: Namensauflösung (DNS) testen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=5"
set "OKM_TIPP="
echo([5/5] DNS-Auflösung von www.microsoft.com wird geprüft ...
>>"%OKM_LOG%" echo([5/5] DNS-Auflösung von www.microsoft.com wird geprüft ...
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
echo(Dieses Script braucht Administratorrechte für: Schritt 2 ^(Netzwerkadapter neu starten^).
>>"%OKM_LOG%" echo(Dieses Script braucht Administratorrechte für: Schritt 2 ^(Netzwerkadapter neu starten^).
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
