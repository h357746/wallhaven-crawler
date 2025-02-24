# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['wallhaven_crawler.py'],
    pathex=['C:/Users/h3577/AppData/Local/Programs/Python/Python313/Lib/site-packages/PyQt6/Qt6/bin'],
    binaries=[],
    datas=[('background.png', '.'), ('icon.png', '.')],  # 添加背景图片和图标
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=True,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='wallhaven_crawler',
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
    icon=['icon.ico'],
)

