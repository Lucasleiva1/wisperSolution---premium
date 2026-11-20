param([string]$Version = "")

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectDir
$pythonExe = Join-Path $projectDir 'venv\Scripts\python.exe'
$sourceVersion = (& $pythonExe -c "import runpy; print(runpy.run_path('src/version.py')['APP_VERSION'])").Trim()
if (-not $Version) { $Version = $sourceVersion }
if ($Version -ne $sourceVersion) { throw 'La version solicitada no coincide con el producto' }
$repo = 'Lucasleiva1/wisperSolution---premium'
$origin = (& git remote get-url origin).Trim()
$gitRoot = (& git rev-parse --show-toplevel).Trim().Replace('/', '\')
if ($origin -ne "https://github.com/$repo.git" -or $gitRoot -ne (Split-Path -Parent $projectDir)) { throw 'Identidad de proyecto incorrecta' }
$tag = "v$Version"
$notes = "RELEASE_NOTES_$Version.md"
$installers = @("Whisper-Solution-Setup-v$Version.exe", 'Whisper-Solution-Setup.exe', 'ScribeFloat-Premium-Setup.exe')
$assets = @()
foreach ($name in $installers) {
    $installer = Join-Path $projectDir "release_pyinstaller\$name"
    foreach ($file in @($installer, "$installer.sha256", "$installer.sig")) {
        if (-not (Test-Path -LiteralPath $file)) { throw "Falta $file" }
        $assets += $file
    }
    if ((Get-Item -LiteralPath $installer).VersionInfo.ProductVersion.Trim() -ne $Version) { throw "Version incorrecta: $name" }
    & $pythonExe tools/verify_release.py $installer
    if ($LASTEXITCODE -ne 0) { throw "Firma o checksum incorrecto: $name" }
}
if (-not (Test-Path -LiteralPath $notes)) { throw "Falta $notes" }
& git diff --quiet HEAD -- src ScribeFloat-PyInstaller.spec Generar_Setup_PyInstaller.iss Preparar_Instalador_PyInstaller.ps1 Publicar_GitHub_Release.ps1 $notes
if ($LASTEXITCODE -ne 0) { throw 'Hay cambios de la version sin confirmar en Git' }
& gh auth status
if ($LASTEXITCODE -ne 0) { throw 'GitHub no esta autenticado' }
$releases = & gh release list --repo $repo --limit 100 --json tagName | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar GitHub' }
if ($releases.tagName -contains $tag) { throw "$tag ya esta publicada; no se sobrescribira" }
if (git tag --list $tag) { throw "La etiqueta $tag ya existe; revisar antes de publicar" }
& git tag -a $tag -m "Whisper Solution $Version"
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear la etiqueta' }
& git push origin HEAD:main
if ($LASTEXITCODE -ne 0) { throw 'No se pudo subir el codigo' }
& git push origin $tag
if ($LASTEXITCODE -ne 0) { throw 'No se pudo subir la etiqueta' }
& gh release create $tag @assets --repo $repo --verify-tag --title "Whisper Solution $Version" --notes-file $notes --latest
if ($LASTEXITCODE -ne 0) { throw 'No se pudo publicar la GitHub Release' }
Write-Host "GitHub Release $tag publicada correctamente."
