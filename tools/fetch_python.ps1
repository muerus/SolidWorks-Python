<#
.SYNOPSIS
  Download the embeddable CPython + a pip wheel into runtime\python (bundled with the add-in build).
.DESCRIPTION
  The embeddable distribution has no pip and ignores site-packages; we enable `import site`
  in its ._pth file and drop a pip wheel next to python.exe (swpy.packages runs pip from the wheel).

  Both downloads are pinned and verified by SHA-256, so a release always bundles exactly these files.
  To upgrade: change the versions and hashes below. Python's SHA-256 is computed from the official zip
  after checking it against the MD5 python.org publishes (https://www.python.org/api/v2/downloads/);
  pip's SHA-256 is the digest PyPI publishes (https://pypi.org/pypi/pip/<version>/json).
#>
$ErrorActionPreference = 'Stop'

$PythonVersion = '3.12.10'
$PythonSha256  = '4ACBED6DD1C744B0376E3B1CF57CE906F9DC9E95E68824584C8099A63025A3C3'
$PipVersion    = '26.2.1'
$PipSha256     = '71138ADF1F4CA900CDB7D289C21B7494329F2332B6D85F0E1C42108C0384ED3E'

function Get-Verified([string]$Url, [string]$OutFile, [string]$Sha256) {
    Invoke-WebRequest $Url -OutFile $OutFile -UseBasicParsing
    $actual = (Get-FileHash $OutFile -Algorithm SHA256).Hash
    if ($actual -ne $Sha256) {
        Remove-Item $OutFile -Force
        throw "SHA-256 mismatch for $Url`n  expected $Sha256`n  actual   $actual"
    }
}

$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$dest = Join-Path $root 'runtime\python'
$tag  = ($PythonVersion -split '\.')[0..1] -join ''          # 312

if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Path $dest | Out-Null

$zip = Join-Path $env:TEMP "python-$PythonVersion-embed-amd64.zip"
Get-Verified "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" $zip $PythonSha256
Expand-Archive $zip -DestinationPath $dest -Force

# enable site so pip-installed packages and .pth files work
$pth = Join-Path $dest "python$tag._pth"
(Get-Content $pth) -replace '^#\s*import site', 'import site' | Set-Content $pth -Encoding ascii

# pip wheel (runnable directly: python pip.whl/pip install ...)
$wheel = "pip-$PipVersion-py3-none-any.whl"
Get-Verified "https://files.pythonhosted.org/packages/py3/p/pip/$wheel" (Join-Path $dest $wheel) $PipSha256

"Python $PythonVersion embeddable + $wheel (SHA-256 verified) -> $dest"
