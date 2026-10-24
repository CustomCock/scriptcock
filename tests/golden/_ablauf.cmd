@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem ======================================================================
rem Titel:             Ablauf
rem Erstellt von:      pytest
rem Erstellt am:       15.01.2026 09:30:00
rem Baukasten-Version: 0.1.0
rem Zielsystem:        Windows Eingabeaufforderung (CMD)
rem Benötigte Rechte:  keine
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
set "OKM_RC=0"
rem /nopause: am Ende nicht auf eine Taste warten (Fernwartung/RMM)
if /i "%~1"=="/nopause" set "OKM_KEINE_PAUSE=1"
set "OKM_TIPP="
echo(==============================================
>>"%OKM_LOG%" echo(==============================================
echo( okm Script-Baukasten · Ablauf
>>"%OKM_LOG%" echo( okm Script-Baukasten · Ablauf
echo( Erstellt: 15.01.2026 09:30 · von pytest
>>"%OKM_LOG%" echo( Erstellt: 15.01.2026 09:30 · von pytest
echo(==============================================
>>"%OKM_LOG%" echo(==============================================

echo(Rechte: ohne erhöhte Rechte
>>"%OKM_LOG%" echo(Rechte: ohne erhöhte Rechte

rem Rückgabewerte der Schritte (Namen vergibt der Baukasten; leer = unbekannt)
set "OKM_S3_ERREICHBAR="
set "OKM_S7_LAEUFT="

rem --------------------------------------------------------------------
rem Schritt 1/8: Meldung/Pause für den Benutzer (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=1"
set "OKM_TIPP="
echo([1/8] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([1/8] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Start") do echo(%%M
set "OKM_RC=%ERRORLEVEL%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem ===== Versuche (Block 1) =====
rem --------------------------------------------------------------------
rem Schritt 2/8: Ordner anlegen (Risiko: gelb)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=2"
set "OKM_TIPP="
echo([2/8] Ordner C:\temp\okm wird angelegt ...
>>"%OKM_LOG%" echo([2/8] Ordner C:\temp\okm wird angelegt ...
(call )
(
if not exist "C:\temp\okm" mkdir "C:\temp\okm"
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_sonst_1
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem ===== Versuche (Block 2) =====
rem --------------------------------------------------------------------
rem Schritt 3/8: Ping auf Ziel (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=3"
set "OKM_TIPP=Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping."
echo([3/8] Ping auf 10.0.0.1 ^(4x^) ...
>>"%OKM_LOG%" echo([3/8] Ping auf 10.0.0.1 ^(4x^) ...
(call )
(
ping -n 4 "10.0.0.1"
rem "set" setzt in .cmd-Dateien den Errorlevel auf 0 – daher erst danach "cmd /c exit"
if errorlevel 1 (
  set OKM_S3_ERREICHBAR=0
  cmd /c exit 1
) else (
  set OKM_S3_ERREICHBAR=1
)
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_sonst_2
if defined OKM_S3_ERREICHBAR if not "%OKM_S3_ERREICHBAR%"=="1" set "OKM_S3_ERREICHBAR=0"
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

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
set "OKM_TIPP="
echo([4/8] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([4/8] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Ausweichen") do echo(%%M
set "OKM_RC=%ERRORLEVEL%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

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
set "OKM_TIPP="
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
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

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
set "OKM_TIPP="
echo([6/8] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([6/8] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Schleife") do echo(%%M
set "OKM_RC=%ERRORLEVEL%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

rem ===== Versuche (Block 5) =====
rem --------------------------------------------------------------------
rem Schritt 7/8: Dienst-Status prüfen (Risiko: gruen)
rem --------------------------------------------------------------------
set "OKM_SCHRITT=7"
set "OKM_TIPP="
echo([7/8] Status von Dienst Spooler wird abgefragt ...
>>"%OKM_LOG%" echo([7/8] Status von Dienst Spooler wird abgefragt ...
(call )
(
sc query "Spooler"
if errorlevel 1 (
  echo Hinweis: Diesen Dienst gibt es nicht oder er lässt sich nicht abfragen.
  set OKM_S7_LAEUFT=0
) else (
  set OKM_S7_LAEUFT=0
  rem Der Zustand RUNNING ist auch auf deutschem Windows englisch
  sc query "Spooler" | find "RUNNING" >nul && set OKM_S7_LAEUFT=1
)
cmd /c exit 0
) >"%OKM_TMP%" 2>&1
set "OKM_RC=%ERRORLEVEL%"
type "%OKM_TMP%"
type "%OKM_TMP%" >>"%OKM_LOG%"
if not "%OKM_RC%"=="0" goto :okm_sonst_5
if defined OKM_S7_LAEUFT if not "%OKM_S7_LAEUFT%"=="1" set "OKM_S7_LAEUFT=0"
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

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
set "OKM_TIPP="
echo([8/8] Hinweis für den Benutzer ...
>>"%OKM_LOG%" echo([8/8] Hinweis für den Benutzer ...
(call )
for /f "delims=" %%M in ("Ende") do echo(%%M
set "OKM_RC=%ERRORLEVEL%"
if not "%OKM_RC%"=="0" goto :okm_fehler
set /a OKM_OK+=1 >nul
echo(      OK
>>"%OKM_LOG%" echo(      OK

echo(----------------------------------------------
>>"%OKM_LOG%" echo(----------------------------------------------
echo( Fertig: %OKM_OK% Schritte erfolgreich ausgeführt.
>>"%OKM_LOG%" echo( Fertig: %OKM_OK% Schritte erfolgreich ausgeführt.
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
echo( Abgebrochen bei Schritt %OKM_SCHRITT%.
>>"%OKM_LOG%" echo( Abgebrochen bei Schritt %OKM_SCHRITT%.
echo( Erfolgreich bis dahin: %OKM_OK% Schritte.
>>"%OKM_LOG%" echo( Erfolgreich bis dahin: %OKM_OK% Schritte.
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
