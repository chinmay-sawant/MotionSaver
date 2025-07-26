# PhotoEngine.spec
# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_all
import PyQt5  # <-- Import PyQt5 here to find its path

block_cipher = None

# --- Data Collection ---
# (The safe_collect_all helper function is a good practice, keeping it)
def safe_collect_all(module_name):
    """Safely collects data, binaries, and hidden imports for a module."""
    try:
        return collect_all(module_name)
    except Exception as e:
        print(f"Warning: Could not collect data for {module_name}: {e}")
        return [], [], []

pyqt5_datas, pyqt5_binaries, pyqt5_hiddenimports = safe_collect_all('PyQt5')
pystray_datas, pystray_binaries, pystray_hiddenimports = safe_collect_all('pystray')
vlc_datas, vlc_binaries, vlc_hiddenimports = safe_collect_all('python-vlc')
cv2_datas, cv2_binaries, cv2_hiddenimports = safe_collect_all('cv2')
mpl_datas, mpl_binaries, mpl_hiddenimports = safe_collect_all('matplotlib')


# --- THE KEY FIX: Dynamically find the absolute path to PyQt5's Qt plugins ---
# This locates the 'plugins' directory within your site-packages and provides its
# absolute path to PyInstaller.
pyqt_plugins_path = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")


a = Analysis(
    ['screensaver_app/PhotoEngine.py'],
    pathex=[os.getcwd()],
    binaries=[] + pyqt5_binaries + pystray_binaries + vlc_binaries + cv2_binaries + mpl_binaries,
    datas=[
        # Application-specific data
        ('config', 'config'),
        ('screensaver_app', 'screensaver_app'),
        ('utils', 'utils'),
        ('requirements.txt', '.'),
        ('MotionSaver.bat', '.'),

        # Library data collected automatically
        *pyqt5_datas,
        *pystray_datas,
        *vlc_datas,
        *cv2_datas,
        *mpl_datas,

        # Add the explicit path to PyQt5 plugins using our dynamically found path.
        # The source is the absolute path on your system.
        # The destination is where the app expects it in the bundled folder.
        (pyqt_plugins_path, 'PyQt5/Qt5/plugins'),
    ],
    hiddenimports=[
        # Essential Hidden Imports
        'PyQt5.sip', 'PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageTk',
        'win32com.shell', 'win32gui', 'win32con', 'win32api', 'win32process',
        'win32serviceutil', 'win32event', 'winreg',
        'winsdk.windows.media.control', 'winsdk.windows.storage.streams',
        'screeninfo', 'keyboard', 'pynput.keyboard', 'pynput.mouse',
        'openmeteo_requests', 'retry_requests', 'pgeocode', 'requests_cache', 'pandas',
        'mutagen.mp3', 'mutagen.mp4', 'requests', 'psutil', 'pygame', 'asyncio',

        # Your widget modules
        'screensaver_app.widgets.weather_widget', 'screensaver_app.widgets.clock_widget',
        'screensaver_app.widgets.stock_widget', 'screensaver_app.widgets.media_widget',
        'screensaver_app.widgets.weather_api',

        # Hidden imports from collect_all
        *pyqt5_hiddenimports, *pystray_hiddenimports, *vlc_hiddenimports,
        *cv2_hiddenimports, *mpl_hiddenimports,
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
    console=False,
    # icon='path/to/your/icon.ico' # Consider adding an icon
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