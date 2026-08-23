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

# Automatically create a zip archive of the 'app' directory (from dist) for easy distribution
app_dist_dir = os.path.join(os.getcwd(), 'dist', 'app')
if os.path.exists(app_dist_dir):
    # Copy installation/uninstallation scripts into the 'app' folder so they are included in the zip
    for script in ["Install.ps1", "Uninstall.ps1"]:
        script_src = os.path.join(os.getcwd(), script)
        if os.path.exists(script_src):
            print(f"Including {script} in the distribution archive.")
            shutil.copy2(script_src, os.path.join(app_dist_dir, script))

    print(f"Creating distribution archive: app.zip from {app_dist_dir}")
    shutil.make_archive('app', 'zip', app_dist_dir)
