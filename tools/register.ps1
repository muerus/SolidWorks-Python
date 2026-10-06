<#
.SYNOPSIS
  Register the SwPy add-in for the current user (no admin rights needed).
.DESCRIPTION
  Writes the COM class registrations under HKCU\Software\Classes (what regasm /codebase
  would write to HKLM) plus the SOLIDWORKS add-in keys under HKCU.
  SOLIDWORKS must run non-elevated to see per-user COM classes.
.PARAMETER Dll
  Path to SwPy.AddIn.dll. Defaults to the Debug build output.
.PARAMETER Unregister
  Remove all keys written by this script.
#>
param(
    [string]$Dll = (Join-Path $PSScriptRoot '..\src\SwPy.AddIn\bin\Debug\net48\SwPy.AddIn.dll'),
    [switch]$Unregister
)
$ErrorActionPreference = 'Stop'

$AddInClsid = '{10C1BD59-4D33-4878-BDDA-DE5D879D6213}'
$ComClasses = @(
    @{ Clsid = $AddInClsid;                              ProgId = 'SwPy.AddIn';      Class = 'SwPy.SwPyAddIn' },
    @{ Clsid = '{8278DEC1-4A35-431C-9322-D96E5845272F}'; ProgId = 'SwPy.EditorPane'; Class = 'SwPy.Ui.EditorPane' }
)
$Title = 'SwPy - Python for SOLIDWORKS'
$Desc  = 'Embedded CPython, script editor and Pythonic API'

$classes = 'HKCU:\Software\Classes'
$swKeys = @("HKCU:\Software\SolidWorks\AddIns\$AddInClsid", "HKCU:\Software\SolidWorks\AddInsStartup\$AddInClsid")

if ($Unregister) {
    $keys = $swKeys + ($ComClasses | ForEach-Object { "$classes\CLSID\$($_.Clsid)", "$classes\$($_.ProgId)" })
    foreach ($k in $keys) { if (Test-Path $k) { Remove-Item $k -Recurse -Force; "removed $k" } }
    return
}

$Dll = (Resolve-Path $Dll).Path
$asm = [Reflection.AssemblyName]::GetAssemblyName($Dll)
$codeBase = 'file:///' + ($Dll -replace '\\', '/')

function Set-Key($path, [hashtable]$values) {
    if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    foreach ($name in $values.Keys) {
        $v = $values[$name]
        if ($name -eq '(default)') { Set-Item -Path $path -Value $v }
        elseif ($v -is [int]) { New-ItemProperty -Path $path -Name $name -Value $v -PropertyType DWord -Force | Out-Null }
        else { New-ItemProperty -Path $path -Name $name -Value $v -PropertyType String -Force | Out-Null }
    }
}

# COM classes (equivalent of regasm /codebase, per user)
foreach ($c in $ComClasses) {
    $clsid = $c.Clsid
    Set-Key "$classes\$($c.ProgId)"        @{ '(default)' = $c.Class }
    Set-Key "$classes\$($c.ProgId)\CLSID"  @{ '(default)' = $clsid }
    Set-Key "$classes\CLSID\$clsid"        @{ '(default)' = $c.Class }
    Set-Key "$classes\CLSID\$clsid\ProgId" @{ '(default)' = $c.ProgId }
    Set-Key "$classes\CLSID\$clsid\Implemented Categories\{62C8FE65-4EBB-45E7-B440-6E39B2CDBF29}" @{}
    $inproc = @{ 'Class' = $c.Class; 'Assembly' = $asm.FullName; 'RuntimeVersion' = 'v4.0.30319'; 'CodeBase' = $codeBase }
    Set-Key "$classes\CLSID\$clsid\InprocServer32" ($inproc + @{ '(default)' = 'mscoree.dll'; 'ThreadingModel' = 'Both' })
    Set-Key "$classes\CLSID\$clsid\InprocServer32\$($asm.Version)" $inproc
    "Registered $($c.ProgId) $clsid"
}

# SOLIDWORKS add-in entries
Set-Key $swKeys[0] @{ '(default)' = 1; 'Title' = $Title; 'Description' = $Desc }
Set-Key $swKeys[1] @{ '(default)' = 1 }

"-> $Dll"
