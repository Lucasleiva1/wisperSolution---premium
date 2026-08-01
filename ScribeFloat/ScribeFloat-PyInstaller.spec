# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import site

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)


datas = [
    ("assets", "assets"),
    ("models", "models"),
]
binaries = []
hiddenimports = ["keyboard._winkeyboard"]

for package in ("faster_whisper", "ctranslate2", "sounddevice", "pygame"):
    datas += collect_data_files(package)
    binaries += collect_dynamic_libs(package)
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
for relative_dir in ("cublas/bin", "cuda_runtime/bin", "cudnn/bin"):
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
