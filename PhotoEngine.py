import tkinter as tk
import argparse
import os
import platform 
import sys
from screensaver_app.video_player import VideoClockScreenSaver 
from screensaver_app.PasswordConfig import verify_password_dialog_macos
import gui 
import json

# Import PyUAC for UAC elevation
try:
    import pyuac
except ImportError:
    print("PyUAC not installed. Please install with: pip install pyuac")
    print("For elevation capability, also install: pip install pypiwin32")
    pyuac = None

# For multi-monitor black-out and event hooking on Windows
WINDOWS_MULTI_MONITOR_SUPPORT = False
hWinEventHook = None
root_ref_for_hook = None # Global reference to the root window for the hook callback

# Define missing Windows constants
# From winuser.h: EVENT_SYSTEM_DISPLAYSETTINGSCHANGED = 0x000F
EVENT_SYSTEM_DISPLAYSETTINGSCHANGED = 0x000F

if platform.system() == "Windows":
    try:
        import win32api
        import win32con
        import win32gui
        import winreg
        # Import additional Windows modules for event hooking
        import win32event
        from ctypes import windll, CFUNCTYPE, c_int, c_uint, c_void_p, POINTER, Structure
        
        # Flag for multi-monitor support
        WINDOWS_MULTI_MONITOR_SUPPORT = True
        
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
        print("pywin32 not installed, multi-monitor features and dynamic updates will be limited.")
else:
    pass # No specific multi-monitor black-out for other OS in this version

# Functions to disable/enable Task Manager (Ctrl+Alt+Del)
def disable_ctrl_alt_del():
    """Disable Task Manager by modifying registry (requires admin privileges)"""
    if platform.system() == "Windows":
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows\CurrentVersion\Policies\System")
            winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            print("Task Manager disabled")
            return True
        except Exception as e:
            print(f"Failed to disable Task Manager: {e}")
            print("This feature requires administrative privileges")
            return False
    return False

def enable_ctrl_alt_del():
    """Re-enable Task Manager by modifying registry"""
    if platform.system() == "Windows":
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows\CurrentVersion\Policies\System")
            winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
            print("Task Manager re-enabled")
            return True
        except Exception as e:
            print(f"Failed to re-enable Task Manager: {e}")
            return False
    return False

secondary_screen_windows = [] 

def update_secondary_monitor_blackouts(main_tk_window):
    """
    Identifies secondary monitors and creates/updates/destroys black Toplevel windows on them.
    This function is designed to be called initially and whenever display settings change.
    """
    global secondary_screen_windows
    if not main_tk_window.winfo_exists() or not WINDOWS_MULTI_MONITOR_SUPPORT:
        return

    main_tk_window.update_idletasks() 
    
    main_win_center_x = main_tk_window.winfo_x() + main_tk_window.winfo_width() // 2
    main_win_center_y = main_tk_window.winfo_y() + main_tk_window.winfo_height() // 2

    try:
        current_monitors_info = win32api.EnumDisplayMonitors()
    except Exception as e:
        print(f"Error enumerating display monitors during update: {e}")
        return

    old_black_windows_to_process = list(secondary_screen_windows)
    secondary_screen_windows.clear() 

    for hMonitor, _, monitor_rect_coords in current_monitors_info:
        # monitor_rect_coords is (left, top, right, bottom)
        mx1, my1, mx2, my2 = monitor_rect_coords
        
        # Check if the center of the main Tkinter window is within this monitor's bounds
        is_the_screensaver_monitor = (mx1 <= main_win_center_x < mx2 and
                                      my1 <= main_win_center_y < my2)
        
        if not is_the_screensaver_monitor:
            # This is a secondary monitor relative to our screensaver's current location.
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
                    break
            
            if not found_and_reused_existing:
                black_screen_window = tk.Toplevel(main_tk_window)
                black_screen_window.configure(bg='black')
                black_screen_window.overrideredirect(True)
                black_screen_window.geometry(f"{width}x{height}+{mx1}+{my1}")
                black_screen_window.attributes('-topmost', True)
                secondary_screen_windows.append(black_screen_window)
    
    for old_win in old_black_windows_to_process:
        if old_win.winfo_exists():
            old_win.destroy()

# Store the callback as a global to prevent garbage collection
callback_ref = None

def WinEventProcCallback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    """Callback for Windows display change events."""
    global root_ref_for_hook
    if event == EVENT_SYSTEM_DISPLAYSETTINGSCHANGED:  # Using our defined constant instead of win32con
        if root_ref_for_hook and root_ref_for_hook.winfo_exists():
            # Schedule the update on the main Tkinter thread
            root_ref_for_hook.after(50, lambda: update_secondary_monitor_blackouts(root_ref_for_hook)) # Small delay

def start_screensaver(video_path_override=None): 
    """Launch the full-screen screen saver directly"""
    global secondary_screen_windows, hWinEventHook, root_ref_for_hook, callback_ref
    secondary_screen_windows = [] 
    hWinEventHook = None
    
    config = load_config()
    task_manager_disabled = False
    # Disable Task Manager at startup (requires admin privileges)
    if config.get("run_as_admin", False):
        task_manager_disabled = disable_ctrl_alt_del()
    
    root = tk.Tk()
    root_ref_for_hook = root # Store root for the callback
    root.attributes('-fullscreen', True) 
    
    TRANSPARENT_KEY_FOR_LOGIN_TOPLEVEL = '#123456' 
    root.attributes('-transparentcolor', TRANSPARENT_KEY_FOR_LOGIN_TOPLEVEL)
    root.configure(bg='black') 

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
                print("Failed to set event hook")
        except Exception as e:
            print(f"Error setting up display change event hook: {e}")
            hWinEventHook = None

    app = VideoClockScreenSaver(root, video_path_override) 
    
    def on_escape(event):
        global secondary_screen_windows, hWinEventHook, root_ref_for_hook
        success = verify_password_dialog_macos(root)
        if success: 
            app.close()
            
            if hWinEventHook: # Unhook before destroying windows
                try:
                    UnhookWinEvent(hWinEventHook)  # Use ctypes function
                except Exception as e_unhook:
                    print(f"Error unhooking display event: {e_unhook}")
                hWinEventHook = None
            root_ref_for_hook = None

            # Re-enable Task Manager if it was disabled
            if task_manager_disabled:
                enable_ctrl_alt_del()

            for sec_win in secondary_screen_windows:
                if sec_win.winfo_exists():
                    sec_win.destroy()
            secondary_screen_windows = []
            if root.winfo_exists():
                root.destroy()
        else:
            try:
                if root and root.winfo_exists():
                    root.focus_set()
            except tk.TclError:
                print("Root window already destroyed.")
            print("Login cancelled or failed.")
    
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
        global hWinEventHook, root_ref_for_hook
        if hWinEventHook:
            try:
                UnhookWinEvent(hWinEventHook)  # Use ctypes function
            except Exception as e_unhook:
                print(f"Error unhooking display event on close: {e_unhook}")
            hWinEventHook = None
            
        # Re-enable Task Manager if it was disabled
        if task_manager_disabled:
            enable_ctrl_alt_del()
            
        root_ref_for_hook = None
        if root.winfo_exists():
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing_main_window)
    
    # Ensure Task Manager is always re-enabled even if the app crashes
    try:
        root.mainloop()
    finally:
        # Re-enable Task Manager in case of crash or exception
        if task_manager_disabled:
            enable_ctrl_alt_del()

def load_config():
    """Load configuration from userconfig.json"""
    # Correct path to userconfig.json, assuming it's in a 'config' subdirectory
    # relative to PhotoEngine.py's location.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config', 'userconfig.json')
    
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
            print(f"[PhotoEngine] Config file not found at {config_path}. Using defaults.")
            return default_config
    except Exception as e:
        print(f"[PhotoEngine] Error loading config: {e}. Using defaults.")
        return default_config

def check_admin_requirement():
    """Check if app should run as admin based on config"""
    config = load_config()
    return config.get("run_as_admin", False)

def main():
    parser = argparse.ArgumentParser(description='Video Clock Screen Saver')
    parser.add_argument('--video', default=None, help='Path to video file (overrides config)')
    args = parser.parse_args()
    
    start_screensaver(args.video)

def admin_main():
    """Main function that will check for admin rights and restart if needed"""
    parser = argparse.ArgumentParser(description='Video Clock Screen Saver')
    parser.add_argument('--mode', choices=['saver', 'gui'], default='saver', help='Run mode: saver or gui')
    parser.add_argument('--video', default=None, help='Path to video file (overrides config)')
    args = parser.parse_args()
    
    if args.mode == 'saver':
        start_screensaver(args.video)
    elif args.mode == 'gui':
        gui.main() # Call the main function from the gui module

if __name__ == "__main__":
    print("[PhotoEngine] Starting PhotoEngine...") # Debug
    # Request admin privileges when running on Windows
    if platform.system() == "Windows" and pyuac:
        current_config = load_config()
        print(f"[PhotoEngine] Loaded config for admin check: run_as_admin = {current_config.get('run_as_admin')}") # Debug
        
        if current_config.get("run_as_admin", False):
            if not pyuac.isUserAdmin():
                print("[PhotoEngine] Admin privileges required, but not currently running as admin.") # Debug
                print("[PhotoEngine] Attempting to restart with admin privileges...") # Debug
                try:
                    pyuac.runAsAdmin()  # This will restart the script with sys.argv
                    print("[PhotoEngine] runAsAdmin called. Exiting current non-admin instance.") # Debug
                    sys.exit(0)  # Crucial: Exit the current non-admin instance immediately
                except Exception as e:
                    print(f"[PhotoEngine] Failed to restart with admin privileges: {e}")
                    print("[PhotoEngine] Continuing without admin privileges. Some features may be limited.")
                    # Fallback to running admin_main without elevated privileges if restart fails
                    admin_main() 
                    sys.exit(1) # Exit after fallback attempt if it also has issues or to signify failure
            else:
                print("[PhotoEngine] Already running with admin privileges.") # Debug
                admin_main()
        else:
            print("[PhotoEngine] Admin privileges not required by configuration.") # Debug
            admin_main()
    else:
        if platform.system() != "Windows":
            print("[PhotoEngine] Not running on Windows. Admin check skipped.") # Debug
        elif not pyuac:
            print("[PhotoEngine] PyUAC module not available. Admin check skipped.") # Debug
        admin_main()
    print("[PhotoEngine] PhotoEngine finished.") # Debug
