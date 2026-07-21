$ErrorActionPreference = "Stop"

$Tag = "v1.1.0"
$Installer = "release\ScribeFloat-Premium-Setup.exe"
$Checksum = "$Installer.sha256"
$Notes = "RELEASE_NOTES_1.1.0.md"

foreach ($File in @($Installer, $Checksum, $Notes)) {
    if (-not (Test-Path $File)) {
        throw "Falta el archivo requerido: $File"
    }
}

& gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "Primero inicia sesion con: gh auth login"
}

if (-not (git tag --list $Tag)) {
    git tag -a $Tag -m "ScribeFloat Premium 1.1.0"
}

git push origin main
git push origin $Tag

$ExistingRelease = gh release view $Tag 2>$null
if ($LASTEXITCODE -eq 0) {
    gh release upload $Tag $Installer $Checksum --clobber
    gh release edit $Tag --title "ScribeFloat Premium 1.1.0" --notes-file $Notes --latest
} else {
    gh release create $Tag $Installer $Checksum --title "ScribeFloat Premium 1.1.0" --notes-file $Notes --latest
}

if ($LASTEXITCODE -ne 0) {
    throw "No se pudo publicar la GitHub Release."
}

Write-Host "GitHub Release $Tag publicada correctamente."
