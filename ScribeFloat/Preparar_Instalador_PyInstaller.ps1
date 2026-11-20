param([switch]$CleanBuild, [switch]$SkipBuild, [switch]$SkipInstaller)

$ErrorActionPreference = "Stop"
function Get-ReleaseHash([string]$LiteralPath) {
    $stream = [System.IO.File]::OpenRead($LiteralPath)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectDir "venv\Scripts\python.exe"
$innoExe = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) { throw "Falta Python: $pythonExe" }
if (-not (Test-Path -LiteralPath $innoExe)) { throw "Falta Inno Setup: $innoExe" }
Set-Location -LiteralPath $projectDir

$appVersion = (& $pythonExe -c "import runpy; print(runpy.run_path('src/version.py')['APP_VERSION'])").Trim()
if ($LASTEXITCODE -ne 0 -or $appVersion -notmatch '^\d+\.\d+\.\d+$') { throw "Version invalida" }
$setupExe = Join-Path $projectDir "release_pyinstaller\Whisper-Solution-Setup-v$appVersion.exe"
if ((Test-Path -LiteralPath $setupExe) -and -not $SkipInstaller) { throw "Ya existe $setupExe. No se sobrescribira una version numerada." }
$workDir = Join-Path $projectDir "build_pyinstaller"
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

Write-Host "[1/5] Verificando sonidos y ventanas ANTES de compilar..." -ForegroundColor Cyan
& $pythonExe src/main.py --verify-package --verification-report "$workDir\sounds-source-v$appVersion.json"
if ($LASTEXITCODE -ne 0) { throw "Fallo la reproduccion de sonidos desde el codigo fuente" }
& $pythonExe src/main.py --verify-window-topmost
if ($LASTEXITCODE -ne 0) { throw "Fallo la prueba nativa de siempre encima" }
& $pythonExe src/main.py --verify-backend
if ($LASTEXITCODE -ne 0) { throw "Fallo la prueba del modelo o del dispositivo de entrada" }

Write-Host "[2/5] Empaquetando ejecutable independiente con PyInstaller..." -ForegroundColor Cyan
$buildArgs = @("-m", "PyInstaller", "--noconfirm", "--distpath", "$projectDir\dist_pyinstaller", "--workpath", $workDir)
if ($CleanBuild) { $buildArgs += "--clean" }
$buildArgs += Join-Path $projectDir "ScribeFloat-PyInstaller.spec"
if ($SkipBuild) {
    Write-Host "Reutilizando el ejecutable generado; se repetiran todas sus verificaciones."
} else {
    # Resolve DLLs from this Python environment and Windows, never from unrelated
    # tools inherited through PATH (for example Poppler's incompatible ICU DLL).
    $savedBuildPath = $env:PATH
    $basePythonDir = (& $pythonExe -c "import sys,pathlib; print(pathlib.Path(sys._base_executable).parent)").Trim()
    try {
        $env:PATH = (@((Split-Path -Parent $pythonExe), $basePythonDir, "$basePythonDir\DLLs", "$env:SystemRoot\System32", $env:SystemRoot) -join ';')
        & $pythonExe @buildArgs
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo con codigo $LASTEXITCODE" }
    } finally {
        $env:PATH = $savedBuildPath
    }
}

$appDir = Join-Path $projectDir "dist_pyinstaller\Whisper-Solution"
$appExe = Join-Path $appDir "Whisper-Solution.exe"
if (-not (Test-Path -LiteralPath $appExe)) { throw "No se genero $appExe" }
if ((Get-Item -LiteralPath $appExe).VersionInfo.FileVersion -ne "$appVersion.0") { throw "Version interna incorrecta" }
foreach ($sound in @("start.mp3", "stop.mp3", "icons\whisper-solution.ico", "icons\whisper-solution-icon.png")) {
    $original = Get-ReleaseHash "$projectDir\assets\$sound"
    $packed = Get-ReleaseHash "$appDir\assets\$sound"
    if ($original -ne $packed) { throw "Recurso empaquetado incorrecto: $sound" }
}

Write-Host "[3/5] Probando sonido y siempre encima EN EL EJECUTABLE..." -ForegroundColor Cyan
# Windows GUI executables must be waited for explicitly; LASTEXITCODE is not reliable here.
$reportPath = "$workDir\sounds-executable-v$appVersion.json"
$check = Start-Process -FilePath $appExe -ArgumentList @("--verify-package", "--verification-report", ('"' + $reportPath + '"')) -Wait -PassThru
if ($check.ExitCode -ne 0) { throw "Fallo el sonido del ejecutable: $($check.ExitCode)" }
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if (-not $report.ok -or $report.version -ne $appVersion) { throw "Informe de sonido invalido" }
$check = Start-Process -FilePath $appExe -ArgumentList "--verify-window-topmost" -Wait -PassThru
if ($check.ExitCode -ne 0) { throw "Fallo siempre encima en el ejecutable: $($check.ExitCode)" }
$check = Start-Process -FilePath $appExe -ArgumentList "--verify-backend" -Wait -PassThru
if ($check.ExitCode -ne 0) { throw "Fallo el modelo o el microfono en el ejecutable: $($check.ExitCode)" }
Copy-Item -LiteralPath $appExe -Destination "$appDir\Whisper-Solution-v$appVersion.exe"

Write-Host "[4/5] Creando instalador Windows v$appVersion..." -ForegroundColor Cyan
if (-not $SkipInstaller) {
    & $innoExe "/DMyAppVersion=$appVersion" (Join-Path $projectDir "Generar_Setup_PyInstaller.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup no genero el instalador" }
}
if (-not (Test-Path -LiteralPath $setupExe)) { throw "Falta el instalador" }
if ((Get-Item -LiteralPath $setupExe).VersionInfo.ProductVersion.Trim() -ne $appVersion) { throw "Version del instalador incorrecta" }

Write-Host "[5/5] Generando y verificando SHA-256 y firma de actualizaciones..." -ForegroundColor Cyan
$assetName = Split-Path -Leaf $setupExe
$hash = Get-ReleaseHash $setupExe
Set-Content -LiteralPath "$setupExe.sha256" -Value "$hash  $assetName" -Encoding ascii
& $pythonExe tools/sign_release.py $setupExe
if ($LASTEXITCODE -ne 0) { throw "No se pudo firmar $assetName" }
& $pythonExe tools/verify_release.py $setupExe
if ($LASTEXITCODE -ne 0) { throw "La firma del instalador no es valida" }

# Technical aliases required by the existing updater and older releases.
foreach ($aliasName in @("Whisper-Solution-Setup.exe", "ScribeFloat-Premium-Setup.exe")) {
    $aliasPath = Join-Path (Split-Path -Parent $setupExe) $aliasName
    if (Test-Path -LiteralPath $aliasPath) { Remove-Item -LiteralPath $aliasPath -Force }
    try {
        New-Item -ItemType HardLink -Path $aliasPath -Target $setupExe -ErrorAction Stop | Out-Null
    } catch {
        Copy-Item -LiteralPath $setupExe -Destination $aliasPath -Force
    }
    Copy-Item -LiteralPath "$setupExe.sig" -Destination "$aliasPath.sig" -Force
    Set-Content -LiteralPath "$aliasPath.sha256" -Value "$hash  $aliasName" -Encoding ascii
}
Write-Host "LISTO: $setupExe" -ForegroundColor Green
