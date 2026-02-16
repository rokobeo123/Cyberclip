# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CyberClip - single-file Windows application."""

import os
import sys

block_cipher = None
ROOT = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'assets'), 'assets'),
    ],
    hiddenimports=[
        'cyberclip',
        'cyberclip.app',
        'cyberclip.storage',
        'cyberclip.storage.database',
        'cyberclip.storage.models',
        'cyberclip.storage.image_store',
        'cyberclip.core',
        'cyberclip.core.clipboard_monitor',
        'cyberclip.core.magazine',
        'cyberclip.core.ghost_typer',
        'cyberclip.core.text_cleaner',
        'cyberclip.core.photo_fixer',
        'cyberclip.core.ocr_scanner',
        'cyberclip.core.link_cleaner',
        'cyberclip.core.color_detector',
        'cyberclip.core.app_detector',
        'cyberclip.core.safety_net',
        'cyberclip.core.global_hotkeys',
        'cyberclip.gui',
        'cyberclip.gui.main_window',
        'cyberclip.gui.item_widget',
        'cyberclip.gui.tab_bar',
        'cyberclip.gui.hud_widget',
        'cyberclip.gui.choice_menu',
        'cyberclip.gui.settings_dialog',
        'cyberclip.gui.image_viewer',
        'cyberclip.gui.styles',
        'cyberclip.utils',
        'cyberclip.utils.constants',
        'cyberclip.utils.win32_helpers',
        'PIL',
        'PIL.Image',
        'sqlite3',
        'win32api',
        'win32con',
        'win32gui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter', 'unittest', 'test',
        'xml.etree', 'pydoc', 'doctest',
        'matplotlib', 'numpy', 'scipy', 'pandas',
    ],
    noarchive=False,
    optimize=1,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CyberClip',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                          # NO console window — proper GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'assets', 'icon.ico'),
    version=os.path.join(ROOT, 'version_info.py'),
    uac_admin=False,
)
