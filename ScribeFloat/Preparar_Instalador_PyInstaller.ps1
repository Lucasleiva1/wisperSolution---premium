$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectDir "venv\Scripts\python.exe"
$innoExe = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "No se encontro Python del proyecto: $pythonExe"
}
if (-not (Test-Path -LiteralPath $innoExe)) {
    throw "No se encontro Inno Setup 6: $innoExe"
}

Set-Location -LiteralPath $projectDir
& $pythonExe -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $projectDir "dist_pyinstaller") `
    --workpath (Join-Path $projectDir "build_pyinstaller") `
    (Join-Path $projectDir "ScribeFloat-PyInstaller.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo con codigo $LASTEXITCODE" }

$appExe = Join-Path $projectDir "dist_pyinstaller\ScribeFloat-Premium\ScribeFloat-Premium.exe"
if (-not (Test-Path -LiteralPath $appExe)) {
    throw "PyInstaller no genero $appExe"
}

& $appExe --verify-package
if ($LASTEXITCODE -ne 0) { throw "La verificacion de sonidos fallo con codigo $LASTEXITCODE" }

& $innoExe (Join-Path $projectDir "Generar_Setup_PyInstaller.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup fallo con codigo $LASTEXITCODE" }

$setupExe = Join-Path $projectDir "release_pyinstaller\ScribeFloat-Premium-Setup.exe"
if (-not (Test-Path -LiteralPath $setupExe)) {
    throw "No se genero el instalador: $setupExe"
}

Write-Host "Instalador listo: $setupExe" -ForegroundColor Green
