# PhotoEngine.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['screensaver_app/PhotoEngine.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include config folder and all its contents
        ('config', 'config'),
        # Include screensaver_app and all its contents (including icons)
        ('screensaver_app', 'screensaver_app'),
        # Include widgets and all its contents (corrected path)
        ('screensaver_app/widgets', 'screensaver_app/widgets'),
        # Include utils and all its contents
        ('utils', 'utils'),
        # requirements and batch file
        ('requirements.txt', '.'),
        ('MotionSaver.bat', '.'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'pkg_resources.py2_warn',
        'pystray._win32',
        'win32com.shell',
        'win32com.shell.shell',
        'win32com.shell.shellcon',
        'win32gui',
        'win32con',
        'win32api',
        'win32process',
        'win32security',
        'win32service',
        'win32serviceutil',
        'win32ts',
        'win32profile',
        'winsdk.windows.media.control',
        'winsdk.windows.storage.streams',
        'screeninfo',
        'keyboard',
        'pynput',
        'openmeteo_requests',
        'retry_requests',
        'pgeocode',
        'requests_cache',
        'mutagen',
        'mutagen.mp3',
        'mutagen.mp4',
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
    [],
    exclude_binaries=True,
    name='PhotoEngine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False  # Set to True if you want a console window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PhotoEngine'
)