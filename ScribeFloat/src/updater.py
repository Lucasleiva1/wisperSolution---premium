"""GitHub Releases updater for ScribeFloat Premium."""

import hashlib
import json
import os
import re
import tempfile
import urllib.request
from pathlib import Path


GITHUB_REPOSITORY = "Lucasleiva1/wisperSolution---premium"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases/latest"
INSTALLER_ASSET_NAME = "ScribeFloat-Premium-Setup.exe"
CHECKSUM_ASSET_NAME = f"{INSTALLER_ASSET_NAME}.sha256"
USER_AGENT = "ScribeFloat-Premium-Updater"


class UpdateError(RuntimeError):
    """Raised when a release cannot be checked, downloaded, or verified."""


def _version_tuple(value):
    numbers = [int(part) for part in re.findall(r"\d+", str(value))[:3]]
    return tuple((numbers + [0, 0, 0])[:3])


def _request(url):
    return urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def _read_url(url, timeout=25):
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout) as response:
            return response.read()
    except Exception as exc:
        raise UpdateError(f"No se pudo conectar con GitHub: {exc}") from exc


def check_for_update(current_version):
    """Return release metadata when GitHub has a newer installer, else ``None``."""
    try:
        release = json.loads(_read_url(RELEASES_API_URL).decode("utf-8"))
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError(f"GitHub devolvio una respuesta invalida: {exc}") from exc

    latest_version = str(release.get("tag_name", "")).lstrip("vV")
    if not latest_version:
        raise UpdateError("La ultima GitHub Release no tiene una version valida.")
    if _version_tuple(latest_version) <= _version_tuple(current_version):
        return None

    assets = {asset.get("name"): asset for asset in release.get("assets", [])}
    installer = assets.get(INSTALLER_ASSET_NAME)
    if not installer or not installer.get("browser_download_url"):
        raise UpdateError(
            f"La version {latest_version} no contiene el asset {INSTALLER_ASSET_NAME}."
        )

    checksum = assets.get(CHECKSUM_ASSET_NAME)
    if not checksum or not checksum.get("browser_download_url"):
        raise UpdateError(
            f"La version {latest_version} no contiene el checksum {CHECKSUM_ASSET_NAME}."
        )

    return {
        "version": latest_version,
        "name": release.get("name") or f"Version {latest_version}",
        "notes": release.get("body") or "",
        "page_url": release.get("html_url") or RELEASES_PAGE_URL,
        "installer_url": installer["browser_download_url"],
        "checksum_url": checksum["browser_download_url"],
    }


def _updates_dir():
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path(tempfile.gettempdir())
    destination = root / "ScribeFloat-Premium" / "updates"
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _expected_checksum(checksum_url):
    text = _read_url(checksum_url).decode("utf-8", errors="replace").strip()
    match = re.search(r"\b[a-fA-F0-9]{64}\b", text)
    if not match:
        raise UpdateError("El archivo SHA-256 de la actualizacion no es valido.")
    return match.group(0).lower()


def download_update(update, progress_callback=None):
    """Download and SHA-256 verify a release installer. Return its local path."""
    expected_hash = _expected_checksum(update["checksum_url"])
    destination = _updates_dir() / f"ScribeFloat-Premium-{update['version']}-Setup.exe"
    partial = destination.with_suffix(".download")
    digest = hashlib.sha256()

    try:
        with urllib.request.urlopen(_request(update["installer_url"]), timeout=45) as response:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            with partial.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(min(100, int(downloaded * 100 / total)))
    except Exception as exc:
        partial.unlink(missing_ok=True)
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"No se pudo descargar la actualizacion: {exc}") from exc

    actual_hash = digest.hexdigest().lower()
    if actual_hash != expected_hash:
        partial.unlink(missing_ok=True)
        raise UpdateError("La descarga no paso la verificacion SHA-256 y fue descartada.")

    os.replace(partial, destination)
    if progress_callback:
        progress_callback(100)
    return str(destination)
