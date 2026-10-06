<#
.SYNOPSIS
  Register the SwPy add-in for the current user (no admin rights needed).
.DESCRIPTION
  Writes the COM class registration under HKCU\Software\Classes (what regasm /codebase
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

$Clsid  = '{10C1BD59-4D33-4878-BDDA-DE5D879D6213}'
$ProgId = 'SwPy.AddIn'
$Class  = 'SwPy.SwPyAddIn'
$Title  = 'SwPy - Python for SOLIDWORKS'
$Desc   = 'Embedded CPython, script editor and Pythonic API'

$classes = 'HKCU:\Software\Classes'
$keys = @(
    "$classes\CLSID\$Clsid",
    "$classes\$ProgId",
    "HKCU:\Software\SolidWorks\AddIns\$Clsid",
    "HKCU:\Software\SolidWorks\AddInsStartup\$Clsid"
)

if ($Unregister) {
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

# COM class (equivalent of regasm /codebase, per user)
Set-Key "$classes\$ProgId"                 @{ '(default)' = $Class }
Set-Key "$classes\$ProgId\CLSID"           @{ '(default)' = $Clsid }
Set-Key "$classes\CLSID\$Clsid"            @{ '(default)' = $Class }
Set-Key "$classes\CLSID\$Clsid\ProgId"     @{ '(default)' = $ProgId }
Set-Key "$classes\CLSID\$Clsid\Implemented Categories\{62C8FE65-4EBB-45E7-B440-6E39B2CDBF29}" @{}
$inproc = @{
    '(default)'      = 'mscoree.dll'
    'ThreadingModel' = 'Both'
    'Class'          = $Class
    'Assembly'       = $asm.FullName
    'RuntimeVersion' = 'v4.0.30319'
    'CodeBase'       = $codeBase
}
Set-Key "$classes\CLSID\$Clsid\InprocServer32" $inproc
Set-Key "$classes\CLSID\$Clsid\InprocServer32\$($asm.Version)" @{
    'Class' = $Class; 'Assembly' = $asm.FullName; 'RuntimeVersion' = 'v4.0.30319'; 'CodeBase' = $codeBase
}

# SOLIDWORKS add-in entries
Set-Key "HKCU:\Software\SolidWorks\AddIns\$Clsid"        @{ '(default)' = 1; 'Title' = $Title; 'Description' = $Desc }
Set-Key "HKCU:\Software\SolidWorks\AddInsStartup\$Clsid" @{ '(default)' = 1 }

"Registered $ProgId $Clsid -> $Dll"
