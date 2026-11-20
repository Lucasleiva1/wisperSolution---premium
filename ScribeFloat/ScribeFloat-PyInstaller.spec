# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import site
import runpy
import os
import sys

from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct,
    VarFileInfo, VarStruct,
)

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)


app_version = runpy.run_path(str(Path(SPECPATH) / "src" / "version.py"))["APP_VERSION"]
version_tuple = tuple(int(part) for part in app_version.split(".")) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple, mask=0x3f,
                      flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[StringFileInfo([StringTable("040904B0", [
        StringStruct("CompanyName", "Whisper Solution"),
        StringStruct("FileDescription", "Whisper Solution Premium"),
        StringStruct("FileVersion", app_version + ".0"),
        StringStruct("ProductName", "Whisper Solution"),
        StringStruct("ProductVersion", app_version),
        StringStruct("OriginalFilename", "Whisper-Solution.exe"),
    ])]), VarFileInfo([VarStruct("Translation", [1033, 1200])])],
)
for sound_name in ("start.mp3", "stop.mp3"):
    if not (Path(SPECPATH) / "assets" / sound_name).is_file():
        raise RuntimeError(f"Falta el sonido obligatorio: {sound_name}")

datas = [
    ("assets", "assets"),
    ("models", "models"),
]
binaries = []
hiddenimports = ["keyboard._winkeyboard"]

for package in ("faster_whisper", "ctranslate2", "sounddevice", "pygame"):
    datas += collect_data_files(package, excludes=["docs/**", "tests/**", "examples/**"] if package == "pygame" else [])
    binaries += collect_dynamic_libs(package)
    if package == "pygame":
        hiddenimports += ["pygame.mixer", "pygame.sndarray"]
    else:
        hiddenimports += collect_submodules(package)

for distribution in ("faster-whisper", "ctranslate2", "sounddevice", "pygame"):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

# CTranslate2's Windows wheel supports GPU execution but CUDA/cuDNN are
# external runtime libraries. Keep them beside the executable so a clean
# installation has the same GPU runtime as the development environment.
nvidia_root = next(
    (Path(package_dir) / "nvidia" for package_dir in site.getsitepackages()
     if (Path(package_dir) / "nvidia").is_dir()),
    None,
)
if nvidia_root is None:
    raise RuntimeError("No se encontro el runtime NVIDIA dentro del entorno de build")
for relative_dir in ("cublas/bin", "cuda_runtime/bin", "cuda_nvrtc/bin", "cudnn/bin"):
    dlls = list((nvidia_root / relative_dir).glob("*.dll"))
    if not dlls:
        raise RuntimeError(f"No se encontraron DLLs NVIDIA en {nvidia_root / relative_dir}")
    binaries += [(str(dll), ".") for dll in dlls]


a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "nvidia",
        "torch",
        "tensorflow",
        "matplotlib",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
    optimize=0,
)
# A release must never pick up DLLs from unrelated applications on PATH.
allowed_binary_roots = tuple(Path(root).resolve() for root in (
    sys.prefix, sys.base_prefix, os.environ["SystemRoot"],
))
foreign_binaries = [source for _, source, _ in a.binaries
                    if not any(Path(source).resolve().is_relative_to(root)
                               for root in allowed_binary_roots)]
if foreign_binaries:
    raise RuntimeError("DLLs ajenas al entorno de build: " + ", ".join(foreign_binaries))
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Whisper-Solution",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icons/whisper-solution.ico",
    contents_directory=".",
    version=version_info,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Whisper-Solution",
)
