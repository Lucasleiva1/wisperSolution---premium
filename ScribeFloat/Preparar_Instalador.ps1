$ErrorActionPreference = "Stop"

$AppVersion = "1.1.0"
$Python = ".\venv\Scripts\python.exe"
$BuildDir = "build_release"
$DistDir = Join-Path $BuildDir "main.dist"
$ExePath = Join-Path $DistDir "ScribeFloat-Premium.exe"
$InnoCompiler = "C:\Users\jaell\AppData\Local\Programs\Inno Setup 6\ISCC.exe"

Write-Host "Preparando ScribeFloat Premium $AppVersion"

if (-not (Test-Path $Python)) {
    throw "No se encontro el entorno virtual en $Python."
}

$env:NUITKA_CACHE_DIR = Join-Path (Get-Location) ".nuitka-cache"
New-Item -ItemType Directory -Force -Path $env:NUITKA_CACHE_DIR | Out-Null

Write-Host "Compilando aplicacion con Nuitka (standalone)..."
& $Python -m nuitka `
    --assume-yes-for-downloads `
    --standalone `
    --jobs=8 `
    --disable-cache=ccache `
    --enable-plugin=pyside6 `
    --nofollow-import-to=av.filter,PIL,pygments,rich,huggingface_hub.inference,huggingface_hub.commands `
    --include-package-data=faster_whisper `
    --include-data-dir=assets=assets `
    --windows-console-mode=disable `
    --company-name="ScribeFloat" `
    --product-name="ScribeFloat Premium" `
    --file-description="Captura de voz premium para Windows" `
    --file-version="$AppVersion.0" `
    --product-version="$AppVersion.0" `
    --output-filename="ScribeFloat-Premium.exe" `
    --output-dir=$BuildDir `
    src\main.py
if ($LASTEXITCODE -ne 0) {
    throw "Nuitka no pudo compilar la aplicacion."
}

if (-not (Test-Path $ExePath)) {
    throw "No se genero $ExePath."
}

Write-Host "Incluyendo las bibliotecas CUDA necesarias para faster-whisper..."
$NvidiaBins = @(
    "venv\Lib\site-packages\nvidia\cublas\bin",
    "venv\Lib\site-packages\nvidia\cudnn\bin",
    "venv\Lib\site-packages\nvidia\cuda_runtime\bin"
)
foreach ($NvidiaBin in $NvidiaBins) {
    if (-not (Test-Path $NvidiaBin)) {
        throw "Falta la dependencia CUDA empaquetable: $NvidiaBin"
    }
    Copy-Item (Join-Path $NvidiaBin "*.dll") -Destination $DistDir -Force
}

Write-Host "Verificando que el ejecutable contenga y pueda cargar ambos sonidos..."
& $ExePath --verify-package
if ($LASTEXITCODE -ne 0) {
    throw "La verificacion de start.mp3/stop.mp3 fallo (codigo $LASTEXITCODE). No se creara el instalador."
}

$RequiredSounds = @(
    (Join-Path $DistDir "assets\start.mp3"),
    (Join-Path $DistDir "assets\stop.mp3")
)
foreach ($Sound in $RequiredSounds) {
    if (-not (Test-Path $Sound)) {
        throw "Falta el sonido obligatorio $Sound."
    }
}

if (-not (Test-Path $InnoCompiler)) {
    throw "Inno Setup 6 no esta instalado en $InnoCompiler."
}

Write-Host "Creando instalador firmado por checksum..."
New-Item -ItemType Directory -Force -Path "release" | Out-Null
& $InnoCompiler "Generar_Setup.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup no pudo crear el instalador."
}

$Installer = "release\ScribeFloat-Premium-Setup.exe"
if (-not (Test-Path $Installer)) {
    throw "No se genero $Installer."
}
$Hash = (Get-FileHash $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path "$Installer.sha256" -Value "$Hash  ScribeFloat-Premium-Setup.exe" -Encoding ascii
& $Python "tools\sign_release.py" $Installer
if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$Installer.sig")) {
    throw "No se pudo firmar criptograficamente el instalador."
}
& $Python "tools\verify_release.py" $Installer
if ($LASTEXITCODE -ne 0) {
    throw "La verificacion criptografica del instalador fallo."
}

Write-Host "LISTO: $Installer"
Write-Host "SHA-256: $Hash"
Write-Host "FIRMA: $Installer.sig"
