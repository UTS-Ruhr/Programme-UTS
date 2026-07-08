# PyInstaller-Spezifikation fuer den Rechnungsscanner.
#
# Lokaler Build (Tesseract muss separat installiert sein):
#   pyinstaller rechnungsscanner.spec
#
# Build mit eingebauter Tesseract-Kopie (kein separates Tesseract-Setup auf dem
# Zielrechner noetig): vorher einen vollstaendigen Tesseract-Ordner (tesseract.exe,
# DLLs, tessdata/) nach vendor/tesseract legen - das macht automatisch die
# GitHub-Actions-Pipeline unter .github/workflows/build-windows.yml.

from pathlib import Path

vendor_tesseract = Path("vendor/tesseract")
extra_datas = []
if vendor_tesseract.exists():
    extra_datas.append((str(vendor_tesseract), "tesseract"))

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=extra_datas,
    hiddenimports=["fitz"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Rechnungsscanner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Rechnungsscanner",
)
