# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['ecur.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('cursor.png', '.'),
        ('cursor.ico', '.')
    ],
    hiddenimports=[
        'win32gui',
        'win32con',
        'winreg',
        'enhanced_cursor',
        'enhanced_cursor.config',
        'enhanced_cursor.logger',
        'enhanced_cursor.overlay',
        'enhanced_cursor.preview_widget',
        'enhanced_cursor.settings_dialog',
        'enhanced_cursor.tray_icon',
        'enhanced_cursor.win32_utils'
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ecur',
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
    icon=['cursor.ico'],
)
