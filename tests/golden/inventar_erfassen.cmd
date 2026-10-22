@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Seriennummer und Inventar erfassen
rem Beschreibung:      Sammelt Seriennummer, Hardware, Betriebssystem, Lizenzstatus und installierte Programme für die Inventarisierung.
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Enthaltene Schritte:
rem    1. Seriennummer und Modell [Risiko: gruen]
rem    2. Systeminfo anzeigen [Risiko: gruen]
rem    3. Windows-Version (Feature-Update) [Risiko: gruen]
rem    4. Windows-Lizenzstatus [Risiko: gruen]
rem    5. Letzter Neustart und ausstehender Neustart [Risiko: gruen]
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
echo( okm Script-Baukasten · Seriennummer und Inventar erfassen
>>"%OKM_LOG%" echo( okm Script-Baukasten · Seriennummer und Inventar erfassen
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

rem --------------------------------------------------------------------
rem Schritt 1/5: Seriennummer und Modell (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP="
echo([1/5] Hardware-Daten werden gelesen ...
>>"%OKM_LOG%" echo([1/5] Hardware-Daten werden gelesen ...
(call )
(
reg query "HKLM\HARDWARE\DESCRIPTION\System\BIOS" /v SystemManufacturer
reg query "HKLM\HARDWARE\DESCRIPTION\System\BIOS" /v SystemProductName
reg query "HKLM\HARDWARE\DESCRIPTION\System\BIOS" /v BIOSVersion
echo Hinweis: Die Seriennummer zeigt die PowerShell-Variante dieses Bausteins.
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 2/5: Systeminfo anzeigen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
set "OKM_TIPP="
echo([2/5] Systeminformationen werden gesammelt ...
>>"%OKM_LOG%" echo([2/5] Systeminformationen werden gesammelt ...
(call )
(
echo Rechnername: %COMPUTERNAME%
ver
systeminfo | findstr /B /I /C:"Betriebssystemname" /C:"Betriebssystemversion" /C:"OS Name" /C:"OS Version" /C:"Prozessor" /C:"Processor" /C:"Gesamter physischer Speicher" /C:"Total Physical Memory" /C:"Verf" /C:"Available Physical Memory" /C:"Systemstartzeit" /C:"System Boot Time"
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 3/5: Windows-Version (Feature-Update) (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=3"
set "OKM_TIPP="
echo([3/5] Windows-Version wird gelesen ...
>>"%OKM_LOG%" echo([3/5] Windows-Version wird gelesen ...
(call )
(
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v ProductName
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v DisplayVersion
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v CurrentBuild
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v UBR
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 4/5: Windows-Lizenzstatus (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=4"
set "OKM_TIPP="
echo([4/5] Lizenzstatus wird abgefragt ...
>>"%OKM_LOG%" echo([4/5] Lizenzstatus wird abgefragt ...
(call )
(
cscript //nologo "%SystemRoot%\System32\slmgr.vbs" /dli
cscript //nologo "%SystemRoot%\System32\slmgr.vbs" /xpr
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem --------------------------------------------------------------------
rem Schritt 5/5: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=5"
set "OKM_TIPP="
echo([5/5] Startzeit und ausstehende Neustarts werden geprüft ...
>>"%OKM_LOG%" echo([5/5] Startzeit und ausstehende Neustarts werden geprüft ...
(call )
(
systeminfo | findstr /B /C:"Systemstartzeit" /C:"System Boot Time"
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired" >nul 2>&1 && echo Neustart ausstehend: JA ^(Windows Update^) || echo Neustart ausstehend laut Windows Update: nein
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
