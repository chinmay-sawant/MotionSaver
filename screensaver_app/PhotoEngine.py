import logging
import tkinter as tk
import argparse
import os
import platform 
import sys
import subprocess # Added for service registration
import threading
import time

# Ensure parent directory is in sys.path for package imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('PhotoEngine')
logging.getLogger("PIL.Image").setLevel(logging.WARNING)

from screensaver_app.video_player import VideoClockScreenSaver 
from screensaver_app.PasswordConfig import verify_password_dialog_macos
from screensaver_app.screensaver_service import launch_in_user_session
# Try to import enhanced blocker first, fallback to basic blocker
try:
    from utils.enhanced_key_blocker import EnhancedKeyBlocker as KeyBlocker
    logger.info("Using enhanced key blocker")
except ImportError:
    from utils.blockit import KeyBlocker # Assuming blockit.py contains a basic KeyBlocker
    logger.info("Using basic key blocker from blockit.py")
import screensaver_app.gui as gui
import json
from PIL import Image, ImageDraw # Added for system tray icon
import pystray # Added for system tray functionality
from utils.config_utils import find_user_config_path
from screensaver_app.ServiceReg import ServiceRegistrar

# Custom UAC elevation functions to replace pyUAC
def is_admin():
    """Check if the current process is running with admin privileges."""
    logger.info("is_admin")
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Restart the current script with admin privileges without showing console window."""
    logger.info("run_as_admin")
    if platform.system() != "Windows":
        return False
    
    try:
        import ctypes
        # Get the current script path and arguments
        script = os.path.abspath(sys.argv[0])
        params = ' '.join(sys.argv[1:])
        
        # Use ShellExecuteW to run with admin privileges and hide console
        ctypes.windll.shell32.ShellExecuteW(
            None, 
            "runas", 
            sys.executable, 
            f'"{script}" {params}', 
            None, 
            0  # SW_HIDE - hide the window
        )
        return True
    except Exception as e:
        logger.error(f"Failed to elevate privileges: {e}")
        return False

def hide_console_window():
    """Hide the console window for the current process."""
    logger.info("hide_console_window")
    if platform.system() == "Windows":
        try:
            import ctypes
            # Get console window handle
            console_window = ctypes.windll.kernel32.GetConsoleWindow()
            if console_window:
                # Hide the console window
                ctypes.windll.user32.ShowWindow(console_window, 0)  # SW_HIDE
                logger.info("Console window hidden successfully")
        except Exception as e:
            logger.warning(f"Failed to hide console window: {e}")

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

# Store the callback as a global to prevent garbage collection
callback_ref = None

def WinEventProcCallback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    """Callback for Windows display change events."""
    logger.info("WinEventProcCallback")
    global root_ref_for_hook
    if event == EVENT_SYSTEM_DISPLAYSETTINGSCHANGED:  # Using our defined constant instead of win32con
        if root_ref_for_hook and root_ref_for_hook.winfo_exists():
            # Schedule the update on the main Tkinter thread
            root_ref_for_hook.after(50, lambda: update_secondary_monitor_blackouts(root_ref_for_hook)) # Small delay


def start_screensaver(video_path_override=None): 
    """Launch the full-screen screen saver directly"""
    logger.info("start_screensaver")
    global secondary_screen_windows, hWinEventHook, root_ref_for_hook, callback_ref
    secondary_screen_windows = [] 
    hWinEventHook = None
    config = load_config()
    
    key_blocker = None
    ctrl_alt_del_detector = None
    
    # Initialize key blocker if admin mode is enabled
    if config.get("run_as_admin", False):
        logger.info("Initializing enhanced key blocking...")
        key_blocker = KeyBlocker(debug_print=True)
        # Check if this is the enhanced blocker or basic blocker
        if hasattr(key_blocker, 'start_blocking'):
            # Enhanced blocker
            blocking_success = key_blocker.start_blocking()
            if blocking_success:
                logger.info("Enhanced key blocking enabled successfully.")
                status = key_blocker.get_status()
                logger.info(f"Blocking status: {status}")
            else:
                logger.warning("Enhanced key blocking failed to start.")
                # Even if C++ hooks fail, we can still use Python hooks
                logger.info("Attempting to use Python-only blocking...")
        else:
            # Basic blocker fallback
            blocking_success = key_blocker.enable_all_blocking(use_registry=True, use_hooks=True)
            if blocking_success:
                logger.info("Basic key blocking enabled successfully with Esc and Alt+Shift+Tab blocking.")
            else:
                logger.warning("Some key blocking methods failed. Check permissions.")
    
    root = tk.Tk()
    root_ref_for_hook = root # Store root for the callback
    root.attributes('-fullscreen', True)
    TRANSPARENT_KEY_FOR_LOGIN_TOPLEVEL = '#123456'
    root.attributes('-transparentcolor', TRANSPARENT_KEY_FOR_LOGIN_TOPLEVEL)
    root.configure(bg='black')

    # --- Ensure main window is visible and on top ---
    root.deiconify()  # Make sure it's not minimized
    root.lift()       # Bring to front
    root.focus_force()  # Force focus
    root.update()
    # On single monitor, force always on top and focus again
    try:
        if root.tk.call('tk', 'windowingsystem') == 'win32':
            # Check number of screens
            screen_count = root.winfo_screenmmwidth() // root.winfo_screenwidth()
            if screen_count <= 1:
                root.attributes('-topmost', True)
                root.lift()
                root.focus_force()
                root.after(100, lambda: root.focus_force())
    except Exception as e:
        logger.warning(f"Could not enforce topmost/focus for single monitor: {e}")

    app = VideoClockScreenSaver(root, video_path_override)

    def on_escape(event):
        logger.info("on_escape")
        global secondary_screen_windows, hWinEventHook, root_ref_for_hook
        if event:
            logger.info(f"Password dialog triggered by: {event.keysym if hasattr(event, 'keysym') else 'mouse click'}")
        # Pass app to password dialog for pause/screenshot/lockscreen
        success = verify_password_dialog_macos(root, video_clock_screensaver=app)
        if success: 
            app.close()
            if hWinEventHook: # Unhook before destroying windows
                try:
                    UnhookWinEvent(hWinEventHook)  # Use ctypes function
                except Exception as e_unhook:
                    logger.error(f"Error unhooking display event: {e_unhook}")
                hWinEventHook = None
            root_ref_for_hook = None

            # Disable key blocking
            if key_blocker:
                if hasattr(key_blocker, 'stop_blocking'):
                    key_blocker.stop_blocking()
                else:
                    key_blocker.disable_all_blocking()
                    
            # Stop Ctrl+Alt+Del detector
            if ctrl_alt_del_detector:
                ctrl_alt_del_detector.restart_pending = True  # Prevent restart during shutdown

            for sec_win in secondary_screen_windows:
                if sec_win.winfo_exists():
                    sec_win.destroy()
            secondary_screen_windows = []
            if root.winfo_exists():
                root.destroy()

            # --- Relaunch tray with same elevation ---
            try:
                logger.info("Attempting to restart system tray after successful screensaver login...")
                # Refactored for PyInstaller one-folder logic
                if getattr(sys, 'frozen', False):
                    # For frozen executable, use the executable directly
                    python_exe = sys.executable
                    script_args = "--min --no-elevate"
                    logger.debug(f"Detected frozen executable. python_exe={python_exe}, args={script_args}")
                else:
                    # For script mode
                    script_path = os.path.abspath(__file__)
                    python_exe = sys.executable
                    script_args = f'"{script_path}" --min --no-elevate'
                    logger.debug(f"Detected script mode. python_exe={python_exe}, args={script_args}")

                # Check if we're running as admin and preserve elevation
                if is_admin():
                    logger.info("Restarting tray with admin privileges...")
                    import ctypes
                    logger.debug(f"Using ShellExecuteW to restart tray with: {python_exe} {script_args}")
                    # Use ShellExecuteW to maintain admin privileges
                    result = ctypes.windll.shell32.ShellExecuteW(
                        None,
                        "runas",
                        python_exe,
                        script_args,
                        None,
                        0  # SW_HIDE
                    )
                    logger.debug(f"ShellExecuteW result: {result}")
                    if result <= 32:  # ShellExecuteW returns > 32 for success
                        logger.error(f"ShellExecuteW failed with result: {result}")
                else:
                    logger.info("Restarting tray without admin privileges...")
                    if getattr(sys, 'frozen', False):
                        # For frozen executable
                        cmd_args = [python_exe, "--min", "--no-elevate"]
                    else:
                        # For script mode
                        script_path = os.path.abspath(__file__)
                        cmd_args = [python_exe, script_path, "--min", "--no-elevate"]
                    
                    logger.debug(f"Using subprocess.Popen to restart tray: {cmd_args}")
                    proc = subprocess.Popen(cmd_args,
                                   creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0)
                    logger.debug(f"subprocess.Popen returned pid: {proc.pid if proc else 'unknown'}")

                logger.info("New tray process started, exiting current process.")
                # Add a small delay to ensure the new process starts before we exit
                time.sleep(1)
                os._exit(0)
            except Exception as e:
                logger.error(f"Failed to restart tray after login: {e}", exc_info=True)
        else:
            VideoClockScreenSaver.resume_video(app)

    # Initial call to black out monitors, delayed slightly for fullscreen to establish
    if WINDOWS_MULTI_MONITOR_SUPPORT:
        root.after(200, lambda: update_secondary_monitor_blackouts(root))
        
        # Set up the Windows event hook for display changes using ctypes directly
        try:
            # Convert Python callback to C callback
            callback_ref = WinEventProcType(WinEventProcCallback)
            
            hWinEventHook = SetWinEventHook(
                EVENT_SYSTEM_DISPLAYSETTINGSCHANGED, # Event Min - using our defined constant
                EVENT_SYSTEM_DISPLAYSETTINGSCHANGED, # Event Max - using our defined constant
                0, # hmodWinEventProc
                callback_ref, # Callback function
                0, # idProcess
                0, # idThread
                win32con.WINEVENT_OUTOFCONTEXT | win32con.WINEVENT_SKIPOWNPROCESS
            )            
            if not hWinEventHook:
                logger.warning("Failed to set event hook")
        except Exception as e:
            logger.error(f"Error setting up display change event hook: {e}")
            hWinEventHook = None
    
    # Bind multiple keys and mouse click to trigger password prompt
    root.bind("<Escape>", on_escape)
    root.bind("<Return>", on_escape)  # Enter key
    root.bind("<KP_Enter>", on_escape)  # Numpad Enter key
    root.bind("<space>", on_escape)  # Spacebar
    root.bind("<Button-1>", on_escape)  # Left mouse click
    
    # Make sure the root window can receive focus for key events
    root.focus_set()
    
    # Ensure hook is unhooked if window is closed by other means (though less likely for fullscreen)
    def on_closing_main_window():
        logger.info("on_closing_main_window")
        global secondary_screen_windows, hWinEventHook, root_ref_for_hook # Ensure all globals used are listed
        
        # Attempt to verify password before closing
        success = verify_password_dialog_macos(root) # 'root' is from the outer scope
        
        if success:
            if app: # 'app' is from the outer scope
                app.close()            
            if hWinEventHook:
                try:
                    UnhookWinEvent(hWinEventHook)
                except Exception as e_unhook:
                    logger.error(f"Error unhooking display event on close: {e_unhook}")
                hWinEventHook = None
              # Disable key blocking
            if key_blocker:
                if hasattr(key_blocker, 'stop_blocking'):
                    key_blocker.stop_blocking()
                else:
                    key_blocker.disable_all_blocking()
            
            root_ref_for_hook = None # Clear the global reference

            for sec_win in secondary_screen_windows:
                if sec_win.winfo_exists():
                    sec_win.destroy()
            secondary_screen_windows.clear() # Clear the list

            if root.winfo_exists():
                root.destroy()        
        else:
            # Password verification failed or was cancelled, keep screensaver active
            logger.info("Close attempt cancelled or password failed. Screensaver remains active.")
            try:
                if root and root.winfo_exists():
                    root.focus_set() # Ensure screensaver window regains focus
            except tk.TclError:
                # This might happen if the window is somehow already gone
                logger.warning("Root window was already destroyed during close attempt with failed password.")
            # Do not destroy the window or re-enable hotkeys if password fails

    root.protocol("WM_DELETE_WINDOW", on_closing_main_window)
      # Ensure key blocking is always disabled even if the app crashes
    try:
        root.mainloop()    
    finally:
        # Disable key blocking in case of crash or exception
        if key_blocker:
            if hasattr(key_blocker, 'stop_blocking'):
                key_blocker.stop_blocking()
            else:
                key_blocker.disable_all_blocking()
                
        # Stop Ctrl+Alt+Del detector
        if ctrl_alt_del_detector:
            ctrl_alt_del_detector.restart_pending = True

def load_config():
    """Load configuration from userconfig.json (using unified search logic)"""
    logger.info("load_config")
    config_path = find_user_config_path()
    default_config = {
        "run_as_admin": False,
        "video_path": None, # Ensure other relevant defaults are present
        # Add other essential default values here if necessary
    }
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                # Ensure all default keys are present in the loaded config
                for key, value in default_config.items():
                    if key not in config_data:
                        config_data[key] = value
                return config_data
        else:
            logger.info(f"[PhotoEngine] Config file not found at {config_path}. Using defaults.")
            return default_config
    except Exception as e:
        logger.error(f"Error loading config: {e}. Using defaults.")
        return default_config

def create_image(width, height, color1, color2):
    logger.info("create_image")
    # Create a simple icon for the system tray
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 2, 0, width, height // 2),
        fill=color2)
    dc.rectangle(
        (0, height // 2, width // 2, height),
        fill=color2)
    return image

def run_in_system_tray():
    logger.info("run_in_system_tray")
    logger.info("Running in system tray mode...")
    icon_image = create_image(64, 64, 'black', 'blue') # Example icon
    
    # Global variables for managing the tray mode
    global tray_running, win_s_blocker, tray_icon_instance # Add tray_icon_instance here
    tray_running = True
    win_s_blocker = None    
    
    def on_open_screensaver(icon, item):
        logger.info("on_open_screensaver")
        logger.info("Starting screensaver from tray...")
        # Run start_screensaver_with_return in a new thread to avoid blocking the tray icon
        import threading
        thread = threading.Thread(target=start_screensaver_with_return)
        thread.daemon = True        
        thread.start()
    
    def on_open_gui(icon, item):
        logger.info("on_open_gui")
        logger.info("Opening GUI from tray...")
        try:
            # Launch GUI in a separate process instead of thread
            # This ensures proper Tkinter main loop handling
            script_path = os.path.abspath(__file__)
            python_exe = sys.executable
            
            # Create the GUI process with proper flags
            if platform.system() == "Windows":
                # Use CREATE_NO_WINDOW to prevent console window
                subprocess.Popen([python_exe, script_path, "--mode", "gui"], 
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen([python_exe, script_path, "--mode", "gui"])
            
            logger.info("GUI process launched successfully")
        except Exception as e:
            logger.error(f"Failed to open GUI from tray: {e}")
            # Fallback: try to import and run GUI directly (less reliable)
            try:
                import threading
                thread = threading.Thread(target=gui.main)
                thread.daemon = True
                thread.start()
                logger.info("GUI started in fallback mode")
            except Exception as fallback_error:
                logger.error(f"Fallback GUI launch also failed: {fallback_error}")
    
    def on_exit_app(icon, item):
        logger.info("on_exit_app")
        logger.info("Exiting application from tray...")
        shutdown_system_tray() # Call the centralized shutdown
    
    def start_screensaver_with_return():
        on_stop_live_wallpaper(None, None)  
        """Start screensaver and return to tray mode after authentication."""
        logger.info("start_screensaver_with_return")
        logger.info("Win + S detected or manual start. Starting screensaver...")
        
        # Temporarily disable Win+S detection
        global win_s_blocker
        if win_s_blocker:
            # Handle both EnhancedKeyBlocker and basic KeyBlocker
            if hasattr(win_s_blocker, 'stop_blocking'):
                # EnhancedKeyBlocker
                win_s_blocker.stop_blocking()
            elif hasattr(win_s_blocker, 'disable_all_blocking'):
                # Basic KeyBlocker
                win_s_blocker.disable_all_blocking()
            elif hasattr(win_s_blocker, 'python_blocker') and win_s_blocker.python_blocker:
                # EnhancedKeyBlocker with internal python_blocker
                win_s_blocker.python_blocker.disable_all_blocking()
        
        # Start the screensaver normally
        start_screensaver()
          # After screensaver exits, restart Win+S detection
        logger.info("Screensaver closed. Returning to minimized mode...")
        start_win_s_detection()

    def start_win_s_detection():
        on_start_live_wallpaper(None, None)  # Ensure live wallpaper is started if needed
        """Start Win+S key detection and blocking using the same logic as key blocking."""
        logger.info("start_win_s_detection")
        global win_s_blocker
        
        try:
            # Try to import the same KeyBlocker that's being used in the main script
            try:
                from utils.enhanced_key_blocker import EnhancedKeyBlocker as CurrentKeyBlocker
                is_enhanced = True
            except ImportError:
                from utils.key_blocker import KeyBlocker as CurrentKeyBlocker
                is_enhanced = False
            
            win_s_blocker = CurrentKeyBlocker(debug_print=True)
            logger.info("Initializing Win+S key blocker for tray mode")
            if is_enhanced:
                logger.debug("Using EnhancedKeyBlocker for Win+S detection")
                # For EnhancedKeyBlocker, we need to work with the internal python_blocker
                if hasattr(win_s_blocker, 'python_blocker') and win_s_blocker.python_blocker is None:
                    logger.debug("Initializing internal python_blocker for EnhancedKeyBlocker")
                    from utils.key_blocker import KeyBlocker
                    win_s_blocker.python_blocker = KeyBlocker(debug_print=True)
                
                # Get the actual blocker to customize
                actual_blocker = win_s_blocker.python_blocker
            else:
                logger.debug("Using basic KeyBlocker for Win+S detection")
                # For basic KeyBlocker
                actual_blocker = win_s_blocker
            if actual_blocker:
                logger.debug("Customizing _on_block_action for Win+S detection")
                # Override the _on_block_action method to trigger screensaver AND block the key
                original_on_block_action = getattr(actual_blocker, '_on_block_action', None)
                def custom_on_block_action(combo_name):
                    logger.info("custom_on_block_action called")
                    logger.debug(f"Combo detected: {combo_name}")
                    if "win+s" in combo_name.lower():
                        logger.info(f"Win+S detected and blocked: {combo_name}")
                        # Start screensaver in a new thread
                        import threading
                        thread = threading.Thread(target=start_screensaver_with_return)
                        thread.daemon = True
                        thread.start()
                        logger.debug("Started screensaver thread from Win+S block")
                        return True  # This blocks the key combination from reaching Windows
                    else:
                        logger.debug("Non Win+S combo detected, delegating to original_on_block_action if exists")
                        # For other combinations, use original behavior if it exists
                        if original_on_block_action:
                            return original_on_block_action(combo_name)
                        return False

                actual_blocker._on_block_action = custom_on_block_action
                logger.info("Custom _on_block_action set for Win+S detection")
                # Enable full blocking mode for Win+S only // here issue 
                logger.debug("Attempting to enable Win+S blocking in tray mode")
                if hasattr(actual_blocker, 'enable_all_blocking'):
                    logger.debug("actual_blocker has enable_all_blocking method")
                    # Temporarily modify blocked_combinations to only include Win+S
                    original_combinations = actual_blocker.blocked_combinations.copy()
                    logger.debug(f"Original blocked_combinations: {original_combinations}")
                    actual_blocker.blocked_combinations = {'win+s': "Win+S (Search)"}
                    logger.debug("Set blocked_combinations to only Win+S")
                    
                    success = actual_blocker.enable_win_s_blocking(use_registry=False, use_hooks=True)
                    logger.debug(f"enable_win_s_blocking returned: {success}")

                    # Restore original combinations for reference
                    actual_blocker.blocked_combinations = original_combinations
                    logger.debug("Restored original blocked_combinations after enabling blocking")
                    if success:
                        logger.info("Win+S detection and blocking active in tray mode")
                    else:
                        logger.warning("Failed to start Win+S detection and blocking")
                elif hasattr(actual_blocker, 'start_hook_blocking'):
                    logger.debug("actual_blocker has start_hook_blocking method")
                    # Fallback to hook-only blocking
                    original_combinations = actual_blocker.blocked_combinations.copy()
                    logger.debug(f"Original blocked_combinations: {original_combinations}")
                    actual_blocker.blocked_combinations = {'win+s': "Win+S (Search)"}
                    logger.debug("Set blocked_combinations to only Win+S for hook blocking")
                    
                    success = actual_blocker.start_hook_blocking()
                    logger.debug(f"start_hook_blocking returned: {success}")
                    
                    # Restore original combinations for reference
                    actual_blocker.blocked_combinations = original_combinations
                    logger.debug("Restored original blocked_combinations after hook blocking")
                    if success:
                        logger.info("Win+S hook detection active in tray mode")
                    else:
                        logger.warning("Failed to start Win+S hook detection")                
                else:
                    logger.warning("Hook blocking not available")
            else:
                logger.error("Could not initialize key blocker for Win+S detection")
                    
        except Exception as e:
            logger.error(f"Error starting Win+S detection: {e}")
    
    # --- Live Wallpaper Tray Actions ---
    from screensaver_app.live_wallpaper.live_wallpaper_pyqt import LiveWallpaperController

    def on_start_live_wallpaper(icon, item):
        logger.info("on_start_live_wallpaper")
        config = load_config()
        video_path = config.get('video_path', None)
        if video_path:
            logger.info(f"Starting live wallpaper with video path: {video_path}")
            # Start live wallpaper in a new thread to avoid blocking the tray icon
            threading.Thread(target=LiveWallpaperController.start_live_wallpaper, args=(video_path,), daemon=True).start()
        else:
            logger.error("No video_path found in config for live wallpaper.")

    def on_stop_live_wallpaper(icon, item):
        threading.Thread(target=LiveWallpaperController.stop_live_wallpaper, daemon=True).start()

    # Create system tray menu with GUI option and live wallpaper controls
    if getattr(sys, 'frozen', False):
        menu = (
            pystray.MenuItem('Open Screensaver/Lockscreen', on_open_screensaver),
            pystray.MenuItem('Open GUI', lambda icon, item: subprocess.Popen([sys.executable, "--mode", "gui"], creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0)),
            pystray.MenuItem('Start Live Wallpaper', on_start_live_wallpaper),
            pystray.MenuItem('Stop Live Wallpaper', on_stop_live_wallpaper),
            pystray.MenuItem('Exit', on_exit_app)
        )
    else:
        menu = (
            pystray.MenuItem('Open Screensaver/Lockscreen', on_open_screensaver),
            pystray.MenuItem('Open GUI', on_open_gui),
            pystray.MenuItem('Start Live Wallpaper', on_start_live_wallpaper),
            pystray.MenuItem('Stop Live Wallpaper', on_stop_live_wallpaper),
            pystray.MenuItem('Exit', on_exit_app)
        )

    icon = pystray.Icon("PhotoEngine", icon_image, "PhotoEngine Screensaver/Lockscreen", menu)
    tray_icon_instance = icon # Store the icon instance

    # Start Win+S detection
    start_win_s_detection()
    logger.info("System tray mode active. Press Win+S to activate screensaver/lockscreen.")
    icon.run()
    logger.info("Tray icon.run() has finished.")

def shutdown_system_tray():
    """Handles the clean shutdown of the system tray icon and related resources."""
    logger.info("shutdown_system_tray")
    logger.info("shutdown_system_tray called.")
    global tray_running, win_s_blocker, tray_icon_instance
    
    if not tray_running:
        logger.info("Tray not running or already shut down.")
        return

    tray_running = False
    
    if win_s_blocker:
        logger.info("Stopping Win+S blocker...")
        if hasattr(win_s_blocker, 'stop_blocking'):
            win_s_blocker.stop_blocking()
        elif hasattr(win_s_blocker, 'disable_all_blocking'):
            win_s_blocker.disable_all_blocking()
        elif hasattr(win_s_blocker, 'python_blocker') and win_s_blocker.python_blocker:
            win_s_blocker.python_blocker.disable_all_blocking()
        win_s_blocker = None
        logger.info("Win+S blocker stopped.")

    if tray_icon_instance:
        logger.info("Stopping tray icon instance...")
        try:
            tray_icon_instance.stop()
        except Exception as e:
            logger.warning(f"Error stopping tray icon: {e}")
        tray_icon_instance = None
        logger.info("Tray icon instance stopped.")
    else:
        logger.info("No tray icon instance to stop.")
    
    # If there are any screensaver windows open, try to close them.
    # This is a bit tricky as they are managed by start_screensaver.
    # For now, focus on stopping the tray icon. A more robust solution
    # might involve PhotoEngine.start_screensaver returning its root window
    # or having a global reference to it that can be destroyed.
    # However, the screensaver should ideally close itself upon authentication.
    # If the service stops it abruptly, it might bypass password.

    logger.info("System tray shutdown process complete.")

def admin_main():
    """Main function that will check for admin rights and restart if needed"""
    logger.info("admin_main")
    parser = argparse.ArgumentParser(description='Video Clock Screen Saver')
    parser.add_argument('--mode', choices=['saver', 'gui'], default='saver', help='Run mode: saver or gui')
    parser.add_argument('--video', default=None, help='Path to video file (overrides config)')
    parser.add_argument('--min', action='store_true', help='Run in minimized system tray window')
    parser.add_argument('--register-service', action='store_true', help='Register the application as a Windows service')
    parser.add_argument('--start-service', action='store_true', help='Start the tray app in the active user session (for service use)')
    parser.add_argument('--no-elevate', action='store_true', help='Skip elevation check (internal flag)')
    args = parser.parse_args()

    # Hide console window when running in minimized mode
    if args.min:
        hide_console_window()

    if args.start_service:
        # Only works if running as a Windows service (LocalSystem)
        import ctypes
        try:
            # Correct session check
            session_id = ctypes.c_uint()
            result = ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session_id))
            if result and session_id.value == 0:
                script_path = os.path.abspath(__file__)
                python_exe = sys.executable
                command = f'"{python_exe}" "{script_path}" --min'
                try:
                    launch_in_user_session(command)
                except Exception as e:
                    logger.error(f"Failed to launch in user session: {e}")
            else:
                logger.error("--start-service must be run from a Windows service (Session 0 / LocalSystem).")
                print("--start-service must be run from a Windows service (Session 0 / LocalSystem). Use --min for normal tray mode.")
        except Exception as e:
            logger.error(f"Service context check failed: {e}")
        sys.exit(0)
        
    if args.min:
        try:
            run_in_system_tray()        
        except Exception as e:
            logger.error(f"Exception in run_in_system_tray: {e}")
            # Ensure cleanup if run_in_system_tray crashes
            shutdown_system_tray() 
        finally:
            logger.info("admin_main: run_in_system_tray finished or exited.")
        sys.exit(0) # Exit after starting tray icon (tray icon runs its own loop)
    elif args.mode == 'saver':
        start_screensaver(args.video)
    elif args.mode == 'gui':
        gui.main() # Call the main function from the gui module

if __name__ == "__main__":
    # Handle service registration commands first
    if ServiceRegistrar.handle_service_args():
        sys.exit(0)

    logger.info("Starting PhotoEngine...")
    
    # Parse arguments early to check for --no-elevate flag
    parser = argparse.ArgumentParser(description='Video Clock Screen Saver', add_help=False)
    parser.add_argument('--no-elevate', action='store_true', help='Skip elevation check (internal flag)')
    parser.add_argument('--min', action='store_true', help='Run in minimized system tray window')
    early_args, _ = parser.parse_known_args()
    
    # Request admin privileges when running on Windows
    if platform.system() == "Windows" and not early_args.no_elevate:
        current_config = load_config()
        logger.debug(f"Loaded config for admin check: run_as_admin = {current_config.get('run_as_admin')}")
        
        if current_config.get("run_as_admin", False):
            if not is_admin():
                logger.info("Admin privileges required, but not currently running as admin.")
                logger.info("Attempting to restart with admin privileges...")
                try:
                    # Add --no-elevate flag to prevent infinite loop
                    sys.argv.append('--no-elevate')
                    
                    if run_as_admin():
                        logger.info("runAsAdmin called. Exiting current non-admin instance.")
                        sys.exit(0)  # Exit the current non-admin instance immediately
                    else:
                        logger.error("Failed to restart with admin privileges")
                        logger.warning("Continuing without admin privileges. Some features may be limited.")
                        # Remove the --no-elevate flag we added since elevation failed
                        if '--no-elevate' in sys.argv:
                            sys.argv.remove('--no-elevate')
                        admin_main()
                        sys.exit(1)
                except Exception as e:
                    logger.error(f"Failed to restart with admin privileges: {e}")
                    logger.warning("Continuing without admin privileges. Some features may be limited.")
                    admin_main() 
                    sys.exit(1)
            else:
                logger.info("Already running with admin privileges.")
                # Hide console window if running in minimized mode
                if early_args.min:
                    hide_console_window()
                admin_main()
        else:
            logger.info("Admin privileges not required by configuration.")
            admin_main()
    else:
        if platform.system() != "Windows":
            logger.info("Not running on Windows. Admin check skipped.")
        elif early_args.no_elevate:
            logger.info("Elevation check skipped due to --no-elevate flag.")
        admin_main()
    logger.info("PhotoEngine finished.")