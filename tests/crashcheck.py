"""Exit-crash bisection: start SW, load add-in, optionally run Python, exit, report crash events."""
import subprocess, sys, time
import harness as h

mode = sys.argv[1]
t0 = time.strftime("%H:%M:%S")
c = h.SwPy()
if mode == "python":
    c.ok("1+1", "x")
h.exit_sw()
time.sleep(3)
ps = ("Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=(Get-Date).AddMinutes(-3)} -ErrorAction SilentlyContinue | "
      "Where-Object { $_.ProviderName -match 'Application Error' -and $_.Message -match 'sldworks' } | "
      "ForEach-Object { $_.TimeCreated.ToString('HH:mm:ss') }")
out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.split()
print(mode, "started", t0, "crashes:", [x for x in out if x >= t0])
