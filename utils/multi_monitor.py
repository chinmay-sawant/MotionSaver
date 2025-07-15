import logging
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('utils.multi_monitor')

import platform
import tkinter as tk
# For multi-monitor black-out and event hooking on Windows
WINDOWS_MULTI_MONITOR_SUPPORT = False
hWinEventHook = None
root_ref_for_hook = None # Global reference to the root window for the hook callback

# Global variables for tray mode and Ctrl+Alt+Del tracking
tray_running = False
win_s_blocker = None
tray_icon_instance = None
ctrl_alt_del_tracker = {"triggered": False, "timestamp": None}

# Define missing Windows constants
# From winuser.h: EVENT_SYSTEM_DISPLAYSETTINGSCHANGED = 0x000F
EVENT_SYSTEM_DISPLAYSETTINGSCHANGED = 0x000F

if platform.system() == "Windows":
    try:
        import win32api
        import win32con
        import win32gui
        # Remove win32ts import and any session monitoring references
        import win32event
        from ctypes import windll, CFUNCTYPE, c_int, c_uint, c_void_p, POINTER, Structure, c_size_t, byref, c_wchar_p, wintypes
        
        # Flag for multi-monitor support
        WINDOWS_MULTI_MONITOR_SUPPORT = True
        logger.info("Windows multi-monitor support enabled with pywin32")
        
        # Define the WinEventProc callback function type
        # WINEVENTPROC callback function prototype
        WinEventProcType = CFUNCTYPE(
            None,               # return type: void
            c_void_p,           # hWinEventHook
            c_uint,             # event
            c_void_p,           # hwnd
            c_int,              # idObject
            c_int,              # idChild
            c_uint,             # dwEventThread
            c_uint              # dwmsEventTime
        )
        
        # Define SetWinEventHook function prototype
        user32 = windll.user32
        user32.SetWinEventHook.argtypes = [
            c_uint,             # eventMin
            c_uint,             # eventMax
            c_void_p,           # hmodWinEventProc
            WinEventProcType,   # lpfnWinEventProc
            c_uint,             # idProcess
            c_uint,             # idThread
            c_uint              # dwFlags
        ]
        user32.SetWinEventHook.restype = c_void_p
        
        # Define UnhookWinEvent function prototype
        user32.UnhookWinEvent.argtypes = [c_void_p]  # hWinEventHook
        user32.UnhookWinEvent.restype = c_int        # BOOL
        
        # Use the properly defined functions
        SetWinEventHook = user32.SetWinEventHook
        UnhookWinEvent = user32.UnhookWinEvent
        
    except ImportError:
        logger.warning("pywin32 not installed, multi-monitor features and session monitoring will be limited.")

else:
    logger.info("Non-Windows OS detected, session monitoring not available")

secondary_screen_windows = []


# Store the callback as a global to prevent garbage collection
callback_ref = None

def update_secondary_monitor_blackouts(main_tk_window):
    """
    Identifies secondary monitors and creates/updates/destroys black Toplevel windows on them.
    This function is designed to be called initially and whenever display settings change.
    Ensures only secondary monitors are blocked, not the primary (main) display.
    """
    logger.info("update_secondary_monitor_blackouts")
    global secondary_screen_windows
    if not main_tk_window.winfo_exists() or not WINDOWS_MULTI_MONITOR_SUPPORT:
        logger.debug("Skipping monitor blackout update - main window not exists or no multi-monitor support")
        return

    main_tk_window.update_idletasks() # Ensure Tkinter's view of window state is up-to-date

    try:
        raw_monitors_info = win32api.EnumDisplayMonitors()
        logger.debug(f"Enumerated {len(raw_monitors_info)} monitors")
    except Exception as e:
        logger.error(f"Error enumerating display monitors: {e}")
        return    
    detailed_monitors_info = []
    primary_monitor_hMonitor = None # Store the hMonitor of the primary display

    for hMonitor, _, monitor_rect_coords in raw_monitors_info:
        try:
            monitor_info_dict = win32api.GetMonitorInfo(hMonitor)
            is_primary = bool(monitor_info_dict.get('Flags') == win32con.MONITORINFOF_PRIMARY)
            detailed_monitors_info.append({'hMonitor': hMonitor, 'rect': monitor_rect_coords, 'is_primary': is_primary})
            if is_primary:
                primary_monitor_hMonitor = hMonitor
        except Exception as e_info:
            logger.warning(f"Error getting info for monitor {hMonitor}: {e_info}")
            detailed_monitors_info.append({'hMonitor': hMonitor, 'rect': monitor_rect_coords, 'is_primary': False})

    # Fallback if no primary monitor was explicitly flagged
    if primary_monitor_hMonitor is None and detailed_monitors_info:
        logger.warning("No explicit primary monitor found. Attempting fallback identification.")
        # Fallback 1: Monitor containing (0,0)
        found_fallback_primary = False
        for i, mon_data in enumerate(detailed_monitors_info):
            mx1, my1, _, _ = mon_data['rect']
            if mx1 == 0 and my1 == 0:
                detailed_monitors_info[i]['is_primary'] = True
                primary_monitor_hMonitor = mon_data['hMonitor']
                # Ensure all others are marked non-primary if this fallback is used
                for j_idx, j_mon_data in enumerate(detailed_monitors_info):
                    if i != j_idx: detailed_monitors_info[j_idx]['is_primary'] = False
                logger.info(f"Fallback: Identified monitor at (0,0) as primary: {primary_monitor_hMonitor}")
                found_fallback_primary = True
                break
          # Fallback 2: Use the main Tkinter window's current monitor (less reliable if Tk window placement is uncertain)
        if not found_fallback_primary:
            logger.debug("[PhotoEngine] Fallback: Using main Tkinter window's location to identify primary.")
            main_win_center_x = main_tk_window.winfo_x() + main_tk_window.winfo_width() // 2
            main_win_center_y = main_tk_window.winfo_y() + main_tk_window.winfo_height() // 2
            for i, mon_data in enumerate(detailed_monitors_info):
                mx1, my1, mx2, my2 = mon_data['rect']
                if (mx1 <= main_win_center_x < mx2 and my1 <= main_win_center_y < my2):
                    detailed_monitors_info[i]['is_primary'] = True
                    primary_monitor_hMonitor = mon_data['hMonitor']
                    for j_idx, j_mon_data in enumerate(detailed_monitors_info):
                        if i != j_idx: detailed_monitors_info[j_idx]['is_primary'] = False
                    logger.debug(f"[PhotoEngine] Fallback: Identified monitor via Tk window center as primary: {primary_monitor_hMonitor}")
                    found_fallback_primary = True
                    break        # Fallback 3: Default to the first enumerated monitor if all else fails
        if not found_fallback_primary and detailed_monitors_info:
            logger.debug("[PhotoEngine] Ultimate Fallback: Assuming first enumerated monitor is primary.")
            detailed_monitors_info[0]['is_primary'] = True
            primary_monitor_hMonitor = detailed_monitors_info[0]['hMonitor']


    old_black_windows_to_process = list(secondary_screen_windows)
    secondary_screen_windows.clear()

    # Only block secondary monitors (not primary)
    for mon_data in detailed_monitors_info:
        if not mon_data['is_primary']:
            mx1, my1, mx2, my2 = mon_data['rect']
            width = mx2 - mx1
            height = my2 - my1

            found_and_reused_existing = False
            for i, existing_win in enumerate(old_black_windows_to_process):
                if existing_win.winfo_exists() and \
                   existing_win.winfo_x() == mx1 and existing_win.winfo_y() == my1 and \
                   existing_win.winfo_width() == width and existing_win.winfo_height() == height:
                    secondary_screen_windows.append(existing_win)
                    old_black_windows_to_process.pop(i)
                    found_and_reused_existing = True
                    logger.debug(f"Reusing existing blackout window for monitor at ({mx1},{my1})")
                    break

            if not found_and_reused_existing:
                logger.info(f"Creating new blackout window for monitor at ({mx1},{my1}) {width}x{height}")
                black_screen_window = tk.Toplevel(main_tk_window)
                black_screen_window.configure(bg='black')
                black_screen_window.overrideredirect(True)
                black_screen_window.geometry(f"{width}x{height}+{mx1}+{my1}")
                black_screen_window.attributes('-topmost', True)
                black_screen_window.wm_attributes("-disabled", True) # Make uninteractable

                # Block events (though -disabled might cover this)
                black_screen_window.bind("<Key>", lambda e: "break")
                black_screen_window.bind("<Button>", lambda e: "break")
                black_screen_window.bind("<Motion>", lambda e: "break")
                black_screen_window.protocol("WM_DELETE_WINDOW", lambda: None) # Prevent closing

                black_screen_window.lift() # Ensure it's on top
                black_screen_window.focus_set() # Attempt to give focus to solidify topmost
                secondary_screen_windows.append(black_screen_window)
    # Destroy any old blackout windows that are no longer needed
    for old_win in old_black_windows_to_process:
        if old_win.winfo_exists():
            logger.debug(f"Destroying obsolete blackout window at ({old_win.winfo_x()},{old_win.winfo_y()})")
            old_win.destroy()
