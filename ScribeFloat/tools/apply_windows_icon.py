"""Update a PyInstaller executable's icon without rebuilding its Python payload."""

import argparse
import shutil
from pathlib import Path

import pefile
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.config import CONF
from PyInstaller.utils.win32 import icon, winutils


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("icon", type=Path)
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve()
    archive = CArchiveReader(str(executable))
    original_main = archive.extract("main")
    original_entries = set(archive.toc)
    pe = pefile.PE(str(executable), fast_load=True)
    overlay_offset = pe.get_overlay_data_start_offset()
    pe.close()
    if overlay_offset is None:
        raise SystemExit("No se encontro el archivo PyInstaller adjunto")
    original = executable.read_bytes()
    overlay = original[overlay_offset:]
    if args.backup.exists():
        raise SystemExit(f"La copia de seguridad ya existe: {args.backup}")
    shutil.copy2(executable, args.backup)
    try:
        executable.write_bytes(original[:overlay_offset])
        CONF["workpath"] = str(executable.parent)
        icon.CopyIcons(str(executable), str(args.icon.resolve()))
        with executable.open("ab") as output:
            output.write(overlay)
        winutils.update_exe_pe_checksum(str(executable))
        updated = CArchiveReader(str(executable))
        if updated.extract("main") != original_main or set(updated.toc) != original_entries:
            raise RuntimeError("El contenido de la aplicacion cambio al aplicar el icono")
        print("ICON_UPDATED_OK: archivo de la aplicacion conservado sin cambios")
    except Exception:
        shutil.copy2(args.backup, executable)
        raise


if __name__ == "__main__":
    main()
