# -*- mode: python ; coding: utf-8 -*-


block_cipher = None

import os
import shutil

datas = []

for dirpath, dirnames, filenames in os.walk("restic_monitor"):
    for f in filenames:
        if f.endswith(".ico"):
            datas.append((os.path.join(dirpath, f), "restic_monitor"))

print(f"datas is {datas}")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='restic-monitor.exe',
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
    uac_admin=True,
    icon="restic_monitor/main.ico"
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app',
)

# Automatically create a zip archive for easy distribution.
# Layout: the zip root contains the 'app/' payload folder PLUS Install.ps1 /
# Uninstall.ps1 beside it, so Install.ps1's $PSScriptRoot\app resolves correctly.
dist_dir = os.path.join(os.getcwd(), 'dist')
app_dist_dir = os.path.join(dist_dir, 'app')
if os.path.exists(app_dist_dir):
    # Stage the install/uninstall scripts BESIDE the 'app' folder (not inside it)
    for script in ["Install.ps1", "Uninstall.ps1"]:
        script_src = os.path.join(os.getcwd(), script)
        if os.path.exists(script_src):
            print(f"Including {script} beside the app/ folder in the distribution archive.")
            shutil.copy2(script_src, os.path.join(dist_dir, script))

    print(f"Creating distribution archive: app.zip from {dist_dir}")
    shutil.make_archive('app', 'zip', dist_dir)
