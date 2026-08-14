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

$appExe = Join-Path $projectDir "dist_pyinstaller\Whisper-Solution\Whisper-Solution.exe"
if (-not (Test-Path -LiteralPath $appExe)) {
    throw "PyInstaller no genero $appExe"
}

& $appExe --verify-package
if ($LASTEXITCODE -ne 0) { throw "La verificacion de sonidos fallo con codigo $LASTEXITCODE" }

& $innoExe (Join-Path $projectDir "Generar_Setup_PyInstaller.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup fallo con codigo $LASTEXITCODE" }

$setupExe = Join-Path $projectDir "release_pyinstaller\Whisper-Solution-Setup.exe"
if (-not (Test-Path -LiteralPath $setupExe)) {
    throw "No se genero el instalador: $setupExe"
}

$legacySetupExe = Join-Path $projectDir "release_pyinstaller\ScribeFloat-Premium-Setup.exe"
if (Test-Path -LiteralPath $legacySetupExe) {
    Remove-Item -LiteralPath $legacySetupExe -Force
}
try {
    New-Item -ItemType HardLink -Path $legacySetupExe -Target $setupExe -ErrorAction Stop | Out-Null
} catch {
    Copy-Item -LiteralPath $setupExe -Destination $legacySetupExe -Force
}

foreach ($asset in @($setupExe, $legacySetupExe)) {
    $assetName = Split-Path -Leaf $asset
    $hash = (Get-FileHash -LiteralPath $asset -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "$asset.sha256" -Value "$hash  $assetName" -Encoding ascii

    & $pythonExe (Join-Path $projectDir "tools\sign_release.py") $asset
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath "$asset.sig")) {
        throw "No se pudo firmar criptograficamente $assetName"
    }

    & $pythonExe (Join-Path $projectDir "tools\verify_release.py") $asset
    if ($LASTEXITCODE -ne 0) {
        throw "La verificacion criptografica fallo para $assetName"
    }
}

Write-Host "Instaladores y firmas listos en release_pyinstaller" -ForegroundColor Green
