<#
.SYNOPSIS
  Download the embeddable CPython + a pip wheel into runtime\python (bundled with the add-in build).
.DESCRIPTION
  The embeddable distribution has no pip and ignores site-packages; we enable `import site`
  in its ._pth file and drop a pip wheel next to python.exe (swpy.packages runs pip from the wheel).
#>
param([string]$Version = '3.12.10')
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$dest = Join-Path $root 'runtime\python'
$tag  = ($Version -split '\.')[0..1] -join ''          # 312

if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Path $dest | Out-Null
$zip = Join-Path $env:TEMP "python-$Version-embed-amd64.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$Version/python-$Version-embed-amd64.zip" -OutFile $zip -UseBasicParsing
Expand-Archive $zip -DestinationPath $dest -Force

# enable site so pip-installed packages and .pth files work
$pth = Join-Path $dest "python$tag._pth"
(Get-Content $pth) -replace '^#\s*import site', 'import site' | Set-Content $pth -Encoding ascii

# pip wheel from PyPI (runnable directly: python pip.whl/pip install ...)
$meta = Invoke-RestMethod 'https://pypi.org/pypi/pip/json'
$wheel = $meta.urls | Where-Object { $_.packagetype -eq 'bdist_wheel' } | Select-Object -First 1
Invoke-WebRequest $wheel.url -OutFile (Join-Path $dest $wheel.filename) -UseBasicParsing

"Python $Version embeddable + $($wheel.filename) -> $dest"
