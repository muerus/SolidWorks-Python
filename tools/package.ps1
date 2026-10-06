<#
.SYNOPSIS
  Build a release zip: dist\SwPy-<version>.zip
.DESCRIPTION
  Release build of the add-in and launcher with the bundled Python runtime (verified by
  fetch_python.ps1), the install scripts, docs and licences. SOLIDWORKS interop assemblies are NOT
  included: the add-in loads them from the user's SOLIDWORKS installation.
  SOLIDWORKS must be closed if it has the Release build loaded.
#>
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$version = (Select-String -Path (Join-Path $root 'python\swpy\__init__.py') -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value

if (-not (Test-Path (Join-Path $root 'runtime\python\python.exe'))) {
    & (Join-Path $PSScriptRoot 'fetch_python.ps1')
}
foreach ($project in 'SwPy.AddIn', 'SwPy.Launcher') {
    dotnet build (Join-Path $root "src\$project") -c Release --nologo -v quiet
    if ($LASTEXITCODE -ne 0) { throw "build of $project failed" }
}

$dist  = Join-Path $root 'dist'
$name  = "SwPy-$version"
$stage = Join-Path $dist $name
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

$bin = Join-Path $stage 'bin'
Copy-Item (Join-Path $root 'src\SwPy.AddIn\bin\Release\net48') $bin -Recurse
Get-ChildItem $bin -Recurse -Include *.pdb | Remove-Item
$interop = Get-ChildItem $bin -Filter '*Interop*.dll'
if ($interop) { throw "SOLIDWORKS interop assemblies must not be shipped: $($interop.Name -join ', ')" }

New-Item -ItemType Directory -Path (Join-Path $stage 'tools') | Out-Null
Copy-Item (Join-Path $root 'tools\install.ps1'), (Join-Path $root 'tools\register.ps1') (Join-Path $stage 'tools')
foreach ($file in 'README.md', 'LICENSE', 'SECURITY.md', 'CHANGELOG.md', 'THIRD-PARTY-NOTICES.md', 'INSTALL.txt') {
    Copy-Item (Join-Path $root $file) $stage
}
New-Item -ItemType Directory -Path (Join-Path $stage 'docs') | Out-Null
Copy-Item (Join-Path $root 'docs\guide'), (Join-Path $root 'docs\images') (Join-Path $stage 'docs') -Recurse

$zip = Join-Path $dist "$name.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $stage -DestinationPath $zip
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash
"$hash  $name.zip" | Set-Content (Join-Path $dist "$name.zip.sha256") -Encoding ascii
"$zip`nSHA-256 $hash"
