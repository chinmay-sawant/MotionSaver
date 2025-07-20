
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

from utils.app_utils import acquire_lock, release_lock

# Ensure only one instance runs unless in GUI mode

# Parse arguments safely
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--mode', choices=['saver', 'gui'], default='saver')
args, _ = parser.parse_known_args()

if args.mode != "gui":
    if not acquire_lock():
        logger.warning("Another instance of PhotoEngine is already running. Exiting this instance.")
        sys.exit(1)

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
from utils.config_utils import find_user_config_path, update_config
from screensaver_app.ServiceReg import ServiceRegistrar
from utils.multi_monitor import update_secondary_monitor_blackouts
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

    app = VideoClockScreenSaver(root, video_path_override, key_blocker_instance=key_blocker)

    def on_escape(event):
        logger.info("on_escape")
        global secondary_screen_windows, hWinEventHook, root_ref_for_hook
        if event:
            logger.info(f"Password dialog triggered by: {event.keysym if hasattr(event, 'keysym') else 'mouse click'}")
        # Pass app to password dialog for pause/screenshot/lockscreen
        success = verify_password_dialog_macos(root, video_clock_screensaver=app)
        if success: 
            app.close()
            release_lock()
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
            logger.info("Password verification failed, resuming video")
            try:
                VideoClockScreenSaver.resume_video(app)
                # Resume focus management and restore focus
                if hasattr(app, 'focus_management_active'):
                    app.focus_management_active = True
                if root and root.winfo_exists():
                    root.focus_force()
            except Exception as e:
                logger.error(f"Error resuming video after failed password verification: {e}")

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
    
    # Remove the old key bindings since VideoClockScreenSaver now handles them internally
    # The app now handles key events internally through _on_key_event and _on_click_event
    
    # Make sure the root window can receive focus for key events
    root.focus_set()
    root.focus_force()
    
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

def stop_application():
    """Stop the current application and clean up all resources."""
    logger.info("stop_application called")
    
    # Stop system tray if running
    shutdown_system_tray()
    
    # Additional cleanup if needed
    logger.info("Application stopped successfully")

def restart_application():
    """Restart the application by stopping current instance and launching a new one."""
    logger.info("restart_application called")
    
    try:
        # Determine the command to restart with
        if getattr(sys, 'frozen', False):
            # For frozen executable, use the executable directly
            python_exe = sys.executable
            script_args = ["--min", "--no-elevate"]
            logger.debug(f"Detected frozen executable. python_exe={python_exe}, args={script_args}")
        else:
            # For script mode
            script_path = os.path.abspath(__file__)
            python_exe = sys.executable
            script_args = [script_path, "--min", "--no-elevate"]
            logger.debug(f"Detected script mode. python_exe={python_exe}, args={script_args}")

        # Check if we're running as admin and preserve elevation
        if is_admin():
            logger.info("Restarting application with admin privileges...")
            import ctypes
            cmd_string = " ".join([f'"{arg}"' if " " in arg else arg for arg in script_args])
            logger.debug(f"Using ShellExecuteW to restart with: {python_exe} {cmd_string}")
            
            # Use ShellExecuteW to maintain admin privileges
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                python_exe,
                cmd_string,
                None,
                0  # SW_HIDE
            )
            logger.debug(f"ShellExecuteW result: {result}")
            if result <= 32:  # ShellExecuteW returns > 32 for success
                logger.error(f"ShellExecuteW failed with result: {result}")
                return False
        else:
            logger.info("Restarting application without admin privileges...")
            cmd_args = [python_exe] + script_args
            
            logger.debug(f"Using subprocess.Popen to restart: {cmd_args}")
            proc = subprocess.Popen(cmd_args,
                           creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0)
            logger.debug(f"subprocess.Popen returned pid: {proc.pid if proc else 'unknown'}")

        logger.info("New application process started, stopping current process...")
        
        # Stop current application
        stop_application()
        
        # Add a small delay to ensure the new process starts before we exit
        time.sleep(1)
        os._exit(0)
        
    except Exception as e:
        logger.error(f"Failed to restart application: {e}", exc_info=True)
        return False

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
    
    def on_restart_app(icon, item):
        logger.info("on_restart_app")
        logger.info("Restarting application from tray...")
        # Run restart in a new thread to avoid blocking the tray icon
        import threading
        thread = threading.Thread(target=restart_application)
        thread.daemon = True
        thread.start()
    
    def on_exit_app(icon, item):
        release_lock()
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
        livewallpaper_bool = config.get('enable_livewallpaper', None)
        if livewallpaper_bool:
            if video_path:
                logger.info(f"Starting live wallpaper with video path: {video_path}")
                # Start live wallpaper in a new thread to avoid blocking the tray icon
                threading.Thread(target=LiveWallpaperController.start_live_wallpaper, args=(video_path,), daemon=True).start()
        else:
            logger.warning("No video_path found in config for live wallpaper/ or is disabled.")
    
    def on_start_live_wallpaper_tray(icon, item):
        update_config('enable_livewallpaper', True)
        logger.info("on_start_live_wallpaper_tray")
        config = load_config()
        video_path = config.get('video_path', None)
        if video_path:
            logger.info(f"Starting live wallpaper with video path: {video_path}")
            # Start live wallpaper in a new thread to avoid blocking the tray icon
            threading.Thread(target=LiveWallpaperController.start_live_wallpaper, args=(video_path,), daemon=True).start()
        else:
            logger.warning("No video_path found in config for live wallpaper/ or is disabled.")

    def on_stop_live_wallpaper(icon, item):
        threading.Thread(target=LiveWallpaperController.stop_live_wallpaper, daemon=True).start()

    # Create system tray menu with GUI option and live wallpaper controls
    if getattr(sys, 'frozen', False):
        menu = (
            pystray.MenuItem('Open Screensaver/Lockscreen', on_open_screensaver),
            pystray.MenuItem('Open GUI', lambda icon, item: subprocess.Popen([sys.executable, "--mode", "gui"], creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0)),
            pystray.MenuItem('Start Live Wallpaper', on_start_live_wallpaper_tray),
            pystray.MenuItem('Stop Live Wallpaper', on_stop_live_wallpaper),
            pystray.MenuItem('Restart MotionSaver', on_restart_app),
            pystray.MenuItem('Exit', on_exit_app)
        )
    else:
        menu = (
            pystray.MenuItem('Open Screensaver/Lockscreen', on_open_screensaver),
            pystray.MenuItem('Open GUI', on_open_gui),
            pystray.MenuItem('Start Live Wallpaper', on_start_live_wallpaper_tray),
            pystray.MenuItem('Stop Live Wallpaper', on_stop_live_wallpaper),
            pystray.MenuItem('Restart MotionSaver', on_restart_app),
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

    # Additional cleanup: Create a temporary key blocker to ensure all registry changes are reverted
    logger.info("Performing additional cleanup to ensure all blocking is disabled...")
    try:
        # Try to import the same KeyBlocker that might have been used
        try:
            from utils.enhanced_key_blocker import EnhancedKeyBlocker as CleanupBlocker
            cleanup_blocker = CleanupBlocker(debug_print=True)
            if hasattr(cleanup_blocker, 'python_blocker') and cleanup_blocker.python_blocker:
                cleanup_blocker.python_blocker.disable_all_blocking()
                logger.info("Enhanced blocker cleanup completed.")
        except ImportError:
            from utils.key_blocker import KeyBlocker as CleanupBlocker
            cleanup_blocker = CleanupBlocker(debug_print=True)
            cleanup_blocker.disable_all_blocking()
            logger.info("Basic blocker cleanup completed.")
    except Exception as e:
        logger.warning(f"Error during additional cleanup: {e}")

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