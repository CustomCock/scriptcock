cmd /c exit 9
for /f "usebackq delims=" %%s in (`powershell -NoProfile -NonInteractive -Command "$n = @(Get-CimInstance Win32_Process -Filter 'Name=''explorer.exe''' | ForEach-Object { $o = Invoke-CimMethod -InputObject $_ -MethodName GetOwner; $o.Domain + '\' + $o.User } | Sort-Object -Unique); if ($n.Count -eq 1) { (New-Object Security.Principal.NTAccount($n[0])).Translate([Security.Principal.SecurityIdentifier]).Value } else { 'FEHLER' }"`) do if "%%s"=="FEHLER" (
  echo Es ist kein oder mehr als ein Benutzer angemeldet - Bereich passt nicht.
  cmd /c exit 9
) else (
