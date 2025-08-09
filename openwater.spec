# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules

APP_NAME = "OpenWaterApp"
ENTRY = "main.py"
ICON_FILE = os.path.abspath("assets/images/favicon.ico")
if not os.path.exists(ICON_FILE):
    raise SystemExit(f"Icon not found: {ICON_FILE}")


# --- datas ---
datas = []
for item in ("main.qml",):
    if os.path.exists(item):
        datas.append((item, "."))

for folder in ("pages", "components", "assets", "config", "processing"):
    if os.path.isdir(folder):
        datas.append((folder, folder))

# --- Qt & Matplotlib ---
hidden = []
hidden += collect_submodules("PyQt6")
hidden += ["qasync", "matplotlib.backends.backend_qtagg"]

qt_datas, qt_bins, qt_hidden = collect_all("PyQt6")
datas += qt_datas
hidden += qt_hidden

binaries = collect_dynamic_libs("PyQt6")

a = Analysis(
    [ENTRY],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6', 'shiboken6', 'PySide2', 'PyQt5'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe_gui = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    icon=ICON_FILE,       
    upx=True,
)

exe_cli = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=f"{APP_NAME}_console",
    console=True,
    icon=ICON_FILE,  
    upx=True,
)

coll = COLLECT(
    exe_gui,
    exe_cli,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
