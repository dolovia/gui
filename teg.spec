from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_dir = Path(__file__).resolve().parent
datas = collect_data_files("bs4")
hiddenimports = collect_submodules("selenium")
binaries = []

for candidate in (
    project_dir / "chromedriver.exe",
    project_dir / "chromedriver",
    project_dir / "drivers" / "chromedriver.exe",
    project_dir / "drivers" / "chromedriver",
):
    if candidate.exists():
        binaries.append((str(candidate), "." if candidate.parent == project_dir else "drivers"))


a = Analysis(
    ["gui.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="teg",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
