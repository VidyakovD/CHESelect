# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Xray binary + geo databases
        (str(ROOT / 'bin' / 'xray.exe'),       'bin'),
        (str(ROOT / 'bin' / 'sing-box.exe'), 'bin'),
        (str(ROOT / 'bin' / 'tun2socks.exe'), 'bin'),
        (str(ROOT / 'bin' / 'wintun.dll'),    'bin'),
        (str(ROOT / 'bin' / 'geoip.dat'),     'bin'),
        (str(ROOT / 'bin' / 'geosite.dat'),   'bin'),
        # App icon
        (str(ROOT / 'assets' / 'icon.ico'), 'assets'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.Qt3D',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtMultimedia',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtSensors',
        'PySide6.QtLocation',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQml',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SelectVPN',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # no console window
    disable_windowed_traceback=False,
    icon=str(ROOT / 'assets' / 'icon.ico'),
    uac_admin=False,
    manifest=str(ROOT / 'SelectVPN.manifest'),
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SelectVPN',
)
