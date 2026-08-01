param(
    [string]$Version = "1.1.2-pre.1"
)

$ErrorActionPreference = "Stop"

$Tag = "v$Version"
$Installer = "release_pyinstaller\Whisper-Solution-Setup.exe"
$Checksum = "$Installer.sha256"
$Signature = "$Installer.sig"
$LegacyInstaller = "release_pyinstaller\ScribeFloat-Premium-Setup.exe"
$LegacyChecksum = "$LegacyInstaller.sha256"
$LegacySignature = "$LegacyInstaller.sig"
$Notes = "RELEASE_NOTES_$Version.md"

foreach ($File in @(
    $Installer, $Checksum, $Signature,
    $LegacyInstaller, $LegacyChecksum, $LegacySignature,
    $Notes
)) {
    if (-not (Test-Path $File)) {
        throw "Falta el archivo requerido: $File"
    }
}

& gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "Primero inicia sesion con: gh auth login"
}

if (-not (git tag --list $Tag)) {
    git tag -a $Tag -m "Whisper Solution $Version PRE-FINAL"
}

git push origin main
git push origin $Tag

$ExistingRelease = gh release view $Tag 2>$null
if ($LASTEXITCODE -eq 0) {
    gh release upload $Tag $Installer $Checksum $Signature $LegacyInstaller $LegacyChecksum $LegacySignature --clobber
    gh release edit $Tag --title "Whisper Solution $Version - PRE-FINAL" --notes-file $Notes --latest
} else {
    gh release create $Tag $Installer $Checksum $Signature $LegacyInstaller $LegacyChecksum $LegacySignature --title "Whisper Solution $Version - PRE-FINAL" --notes-file $Notes --latest
}

if ($LASTEXITCODE -ne 0) {
    throw "No se pudo publicar la GitHub Release."
}

Write-Host "GitHub Release $Tag publicada correctamente."
