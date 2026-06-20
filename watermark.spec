# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for the Desktop Watermark Overlay.
#
# Build with:
#     pyinstaller watermark.spec
#
# Output exe will be at: dist/DesktopWatermark.exe

block_cipher = None

a = Analysis(
    ['watermark.py'],
    pathex=[],
    binaries=[],
    datas=[],
    # win32com sometimes needs these hidden imports pulled in explicitly
    # when frozen with PyInstaller.
    hiddenimports=[
        'win32timezone',
        'win32com',
        'win32com.client',
        'win32com.gen_py',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DesktopWatermark',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # console=False -> no black console window when the exe runs
    # (equivalent to running with pythonw.exe instead of python.exe).
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Embeds the manifest so Windows shows a UAC prompt and runs the
    # exe elevated automatically. Remove this line (or change the
    # manifest's requestedExecutionLevel to "asInvoker") if you don't
    # want elevation.
    manifest='watermark.manifest',
    icon=None,  # set to a .ico path here if you want a custom tray/exe icon
)
