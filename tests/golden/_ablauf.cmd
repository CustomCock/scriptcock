@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Ablauf
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Enthaltene Schritte:
rem    1. Meldung/Pause für den Benutzer [Risiko: gruen]
rem   Versuche:
rem       2. Ordner anlegen [Risiko: gelb]
rem      Versuche:
rem          3. Ping auf Ziel [Risiko: gruen]
rem      Fehler darin übergehen.
rem   Wenn das fehlschlägt:
rem       4. Meldung/Pause für den Benutzer [Risiko: gruen]
rem      Wiederhole 2-mal:
rem          5. Prozess beenden [Risiko: rot]
rem   Wiederhole 3-mal:
rem       6. Meldung/Pause für den Benutzer [Risiko: gruen]
rem      Versuche:
rem          7. Dienst-Status prüfen [Risiko: gruen]
rem      Fehler darin übergehen.
rem    8. Meldung/Pause für den Benutzer [Risiko: gruen]
rem
rem Generiert mit dem okm Script-Baukasten
rem ======================================================================

set "OKM_TS="
for /f "delims=" %%T in ('powershell -NoProfile -NonInteractive -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "OKM_TS=%%T"
if not defined OKM_TS set "OKM_TS=%RANDOM%"
set "OKM_LOG=%TEMP%\okm-script-%OKM_TS%.log"
set "OKM_TMP=%TEMP%\okm-script-%OKM_TS%.tmp"
set "OKM_GESAMT=8"
set "OKM_OK=0"
set "OKM_SCHRITT=0"
echo(okm Script-Baukasten: Ablauf
>>"%OKM_LOG%" echo(okm Script-Baukasten: Ablauf

rem --------------------------------------------------------------------
rem Schritt 1/8: Meldung/Pause für den Benutzer (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
echo([1/8] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([1/8] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Start") do echo(%%M
if errorlevel 1 goto :okm_fehler
if not errorlevel 0 goto :okm_fehler
set /a OKM_OK+=1 >nul

rem ===== Versuche (Block 1) =====
rem --------------------------------------------------------------------
rem Schritt 2/8: Ordner anlegen (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
echo([2/8] Ordner C:\temp\okm wird angelegt ...
>>"%OKM_LOG%" echo([2/8] Ordner C:\temp\okm wird angelegt ...
(call )
(
if not exist "C:\temp\okm" mkdir "C:\temp\okm"
) >"%OKM_TMP%" 2>&1
if errorlevel 1 (set "OKM_RC=1") else if not errorlevel 0 (set "OKM_RC=1") else (set "OKM_RC=0")
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if "%OKM_RC%"=="1" goto :okm_sonst_1
set /a OKM_OK+=1 >nul

rem ===== Versuche (Block 2) =====
rem --------------------------------------------------------------------
rem Schritt 3/8: Ping auf Ziel (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=3"
echo([3/8] Ping auf 10.0.0.1 ^(4x^) ...
>>"%OKM_LOG%" echo([3/8] Ping auf 10.0.0.1 ^(4x^) ...
(call )
(
ping -n 4 "10.0.0.1"
) >"%OKM_TMP%" 2>&1
if errorlevel 1 (set "OKM_RC=1") else if not errorlevel 0 (set "OKM_RC=1") else (set "OKM_RC=0")
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if "%OKM_RC%"=="1" goto :okm_sonst_2
set /a OKM_OK+=1 >nul

goto :okm_ende_2
:okm_sonst_2
echo(Schritt %OKM_SCHRITT% ist fehlgeschlagen. Der Fehler wird wie vorgesehen übergangen.
>>"%OKM_LOG%" echo(Schritt %OKM_SCHRITT% ist fehlgeschlagen. Der Fehler wird wie vorgesehen übergangen.
:okm_ende_2
rem ===== Ende Versuche (Block 2) =====

goto :okm_ende_1
:okm_sonst_1
echo(Schritt %OKM_SCHRITT% ist fehlgeschlagen. Es geht mit den Ausweichschritten weiter.
>>"%OKM_LOG%" echo(Schritt %OKM_SCHRITT% ist fehlgeschlagen. Es geht mit den Ausweichschritten weiter.
rem --------------------------------------------------------------------
rem Schritt 4/8: Meldung/Pause für den Benutzer (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=4"
echo([4/8] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([4/8] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Ausweichen") do echo(%%M
if errorlevel 1 goto :okm_fehler
if not errorlevel 0 goto :okm_fehler
set /a OKM_OK+=1 >nul

rem ===== Wiederhole 2-mal (Block 3) =====
set "OKM_DURCHLAUF_3=0"
:okm_schleife_3
set /a OKM_DURCHLAUF_3+=1 >nul
echo(--- Durchlauf %OKM_DURCHLAUF_3% von 2 ---
>>"%OKM_LOG%" echo(--- Durchlauf %OKM_DURCHLAUF_3% von 2 ---
rem --------------------------------------------------------------------
rem Schritt 5/8: Prozess beenden (Risiko: rot)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=5"
echo([5/8] Prozess notepad wird beendet ...
>>"%OKM_LOG%" echo([5/8] Prozess notepad wird beendet ...
echo(ACHTUNG: Dieser Schritt ist destruktiv: Prozess beenden
set "OKM_ANTWORT="
set /p "OKM_ANTWORT=Zum Fortfahren JA eingeben (alles andere bricht ab): "
if not defined OKM_ANTWORT goto :okm_abbruch
set "OKM_ANTWORT=%OKM_ANTWORT:"=%"
if not "%OKM_ANTWORT%"=="JA" goto :okm_abbruch
(call )
(
taskkill /F /IM "notepad".exe
if errorlevel 128 (
  echo Kein passender Prozess gefunden - nichts zu tun.
  cmd /c exit 0
)
) >"%OKM_TMP%" 2>&1
if errorlevel 1 (set "OKM_RC=1") else if not errorlevel 0 (set "OKM_RC=1") else (set "OKM_RC=0")
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if "%OKM_RC%"=="1" goto :okm_fehler
set /a OKM_OK+=1 >nul

if %OKM_DURCHLAUF_3% LSS 2 goto :okm_schleife_3

:okm_ende_1
rem ===== Ende Versuche (Block 1) =====

rem ===== Wiederhole 3-mal (Block 4) =====
set "OKM_DURCHLAUF_4=0"
:okm_schleife_4
set /a OKM_DURCHLAUF_4+=1 >nul
echo(--- Durchlauf %OKM_DURCHLAUF_4% von 3 ---
>>"%OKM_LOG%" echo(--- Durchlauf %OKM_DURCHLAUF_4% von 3 ---
rem --------------------------------------------------------------------
rem Schritt 6/8: Meldung/Pause für den Benutzer (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=6"
echo([6/8] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([6/8] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Schleife") do echo(%%M
if errorlevel 1 goto :okm_fehler
if not errorlevel 0 goto :okm_fehler
set /a OKM_OK+=1 >nul

rem ===== Versuche (Block 5) =====
rem --------------------------------------------------------------------
rem Schritt 7/8: Dienst-Status prüfen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=7"
echo([7/8] Status von Dienst Spooler wird abgefragt ...
>>"%OKM_LOG%" echo([7/8] Status von Dienst Spooler wird abgefragt ...
(call )
(
sc query "Spooler"
) >"%OKM_TMP%" 2>&1
if errorlevel 1 (set "OKM_RC=1") else if not errorlevel 0 (set "OKM_RC=1") else (set "OKM_RC=0")
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if "%OKM_RC%"=="1" goto :okm_sonst_5
set /a OKM_OK+=1 >nul

goto :okm_ende_5
:okm_sonst_5
echo(Schritt %OKM_SCHRITT% ist fehlgeschlagen. Der Fehler wird wie vorgesehen übergangen.
>>"%OKM_LOG%" echo(Schritt %OKM_SCHRITT% ist fehlgeschlagen. Der Fehler wird wie vorgesehen übergangen.
:okm_ende_5
rem ===== Ende Versuche (Block 5) =====

if %OKM_DURCHLAUF_4% LSS 3 goto :okm_schleife_4

rem --------------------------------------------------------------------
rem Schritt 8/8: Meldung/Pause für den Benutzer (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=8"
echo([8/8] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([8/8] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Ende") do echo(%%M
if errorlevel 1 goto :okm_fehler
if not errorlevel 0 goto :okm_fehler
set /a OKM_OK+=1 >nul

echo(
echo(Fertig, %OKM_OK% Schritte erfolgreich ausgeführt.
>>"%OKM_LOG%" echo(Fertig, %OKM_OK% Schritte erfolgreich ausgeführt.
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
