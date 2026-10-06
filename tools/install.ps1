<#
.SYNOPSIS
  Install SwPy for the current user: COM registration + "SOLIDWORKS + SwPy" shortcuts.
.PARAMETER Machine
  Also register the add-in under HKLM so SOLIDWORKS auto-loads it natively (needs admin).
.PARAMETER Uninstall
  Remove registration and shortcuts.
#>
param(
    [string]$BinDir = (Join-Path $PSScriptRoot '..\src\SwPy.AddIn\bin\Debug\net48'),
    [switch]$Machine,
    [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
$Clsid = '{10C1BD59-4D33-4878-BDDA-DE5D879D6213}'
$shell = New-Object -ComObject WScript.Shell
$links = @(
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'SOLIDWORKS + SwPy.lnk'),
    (Join-Path ([Environment]::GetFolderPath('Programs')) 'SOLIDWORKS + SwPy.lnk')
)

if ($Uninstall) {
    & (Join-Path $PSScriptRoot 'register.ps1') -Unregister
    $links | Where-Object { Test-Path $_ } | ForEach-Object { Remove-Item $_; "removed $_" }
    if (Test-Path "HKLM:\SOFTWARE\SolidWorks\Addins\$Clsid") { Remove-Item "HKLM:\SOFTWARE\SolidWorks\Addins\$Clsid" -Recurse }
    return
}

$BinDir = (Resolve-Path $BinDir).Path
& (Join-Path $PSScriptRoot 'register.ps1') -Dll (Join-Path $BinDir 'SwPy.AddIn.dll')

$launcher = Join-Path $BinDir 'SwPy.Launcher.exe'
$swClsid = ([Type]::GetTypeFromProgID('SldWorks.Application')).GUID.ToString('B')
$swCmd = (Get-ItemProperty "Registry::HKEY_CLASSES_ROOT\CLSID\$swClsid\LocalServer32").'(default)'
$swExe = if ($swCmd -match '^"?(.+?\.exe)') { $Matches[1] } else { $null }
foreach ($l in $links) {
    $s = $shell.CreateShortcut($l)
    $s.TargetPath = $launcher
    $s.WorkingDirectory = $BinDir
    $s.Description = 'Start SOLIDWORKS with the SwPy Python add-in'
    if ($swExe -and (Test-Path $swExe)) { $s.IconLocation = "$swExe,0" }
    $s.Save()
    "shortcut $l"
}

if ($Machine) {
    $k = "HKLM:\SOFTWARE\SolidWorks\Addins\$Clsid"
    New-Item -Path $k -Force | Out-Null
    Set-ItemProperty $k -Name '(default)' -Value 1 -Type DWord
    Set-ItemProperty $k -Name 'Title' -Value 'SwPy - Python for SOLIDWORKS'
    Set-ItemProperty $k -Name 'Description' -Value 'Embedded CPython, script editor and Pythonic API'
    "machine registration $k (SOLIDWORKS will auto-load SwPy)"
}
