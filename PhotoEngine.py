import tkinter as tk
import argparse
import os
import platform 
import sys
from screensaver_app.video_player import VideoClockScreenSaver 
from screensaver_app.PasswordConfig import verify_password_dialog_macos
import gui 
import json
import time 
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
        from ctypes import windll, CFUNCTYPE, c_int, c_uint, c_void_p, POINTER, Structure, c_size_t, byref, c_wchar_p
        
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
        
        # Define SendMessageTimeoutW function prototype for broadcasting setting changes
        user32.SendMessageTimeoutW.argtypes = [
            c_void_p,  # HWND
            c_uint,    # MSG
            c_void_p,  # WPARAM
            c_wchar_p, # LPARAM (string)
            c_uint,    # fuFlags
            c_uint,    # uTimeout
            POINTER(c_size_t) # LPDWORD_PTR lpdwResult
        ]
        user32.SendMessageTimeoutW.restype = c_void_p # LRESULT (LONG_PTR)
        
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

def disable_windows_hotkeys():
    """Disable various Windows hotkeys by modifying registry (requires admin privileges)"""
    if platform.system() == "Windows":
        disabled_count = 0
        try:
            # Disable Windows key combinations - Use HKEY_LOCAL_MACHINE for system-wide effect
            key_explorer_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer")
            
            # Disable Win+R (Run dialog)
            winreg.SetValueEx(key_explorer_lm, "NoRun", 0, winreg.REG_DWORD, 1)
            disabled_count += 1
            
            # Disable Win+X (Quick Link menu) and other Win+<key> combinations
            winreg.SetValueEx(key_explorer_lm, "NoWinKeys", 0, winreg.REG_DWORD, 1)
            disabled_count += 1
            
            # Disable Alt+Tab (Task switcher)
            winreg.SetValueEx(key_explorer_lm, "AltTabSettings", 0, winreg.REG_DWORD, 1)
            disabled_count += 1
            
            winreg.CloseKey(key_explorer_lm)
            
            # Also set in HKEY_CURRENT_USER for additional coverage
            key_explorer_cu = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer")
            
            winreg.SetValueEx(key_explorer_cu, "NoRun", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key_explorer_cu, "NoWinKeys", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key_explorer_cu, "AltTabSettings", 0, winreg.REG_DWORD, 1)
            disabled_count += 3
            
            winreg.CloseKey(key_explorer_cu)
            
            # Disable Win+Tab (Task view) through Desktop Window Manager
            dwm_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                      r"Software\Microsoft\Windows\CurrentVersion\Policies\System")
            winreg.SetValueEx(dwm_key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(dwm_key)
            disabled_count += 1
            
            # Disable Win+S (Search) - Multiple approaches for better coverage
            # Method 1: Disable search entirely
            try:
                search_key_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                             r"SOFTWARE\Policies\Microsoft\Windows\Windows Search")
                winreg.SetValueEx(search_key_lm, "DisableWebSearch", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(search_key_lm, "AllowSearchToUseLocation", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(search_key_lm)
                disabled_count += 2
            except Exception as e:
                print(f"Warning: Could not disable web search: {e}")
            
            # Method 2: Hide search box
            search_key_cu = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                         r"Software\Microsoft\Windows\CurrentVersion\Search")
            winreg.SetValueEx(search_key_cu, "SearchboxTaskbarMode", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(search_key_cu, "BingSearchEnabled", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(search_key_cu)
            disabled_count += 2
            
            # Additional Win+X blocking through System policy
            try:
                system_key_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System")
                winreg.SetValueEx(system_key_lm, "DisableLockWorkstation", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(system_key_lm)
                disabled_count += 1
            except Exception as e:
                print(f"Warning: Could not disable lock workstation: {e}")
            
            print(f"Windows hotkeys disabled ({disabled_count} registry entries modified)")

            # Lightweight registry refresh without blocking
            try:
                # Just notify the system of changes without waiting
                import subprocess
                subprocess.Popen(['gpupdate', '/force'], 
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                print("Group policy update initiated (non-blocking).")
            except Exception as e:
                print(f"Note: Could not initiate group policy update: {e}")
            
            return True
            
        except Exception as e:
            print(f"Failed to disable Windows hotkeys: {e}")
            print("This feature requires administrative privileges")
            return False
    return False

def enable_windows_hotkeys():
    """Re-enable Windows hotkeys by restoring registry values"""
    if platform.system() == "Windows":
        enabled_count = 0
        try:
            # Re-enable Windows key combinations - HKEY_LOCAL_MACHINE
            key_explorer_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer")
            
            try:
                winreg.DeleteValue(key_explorer_lm, "NoRun")
                enabled_count += 1
            except FileNotFoundError:
                pass
            
            try:
                winreg.DeleteValue(key_explorer_lm, "NoWinKeys")
                enabled_count += 1
            except FileNotFoundError:
                pass
            
            try:
                winreg.DeleteValue(key_explorer_lm, "AltTabSettings")
                enabled_count += 1
            except FileNotFoundError:
                pass
            
            winreg.CloseKey(key_explorer_lm)
            
            # Re-enable in HKEY_CURRENT_USER
            key_explorer_cu = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer")
            
            try:
                winreg.DeleteValue(key_explorer_cu, "NoRun")
                enabled_count += 1
            except FileNotFoundError:
                pass
            
            try:
                winreg.DeleteValue(key_explorer_cu, "NoWinKeys")
                enabled_count += 1
            except FileNotFoundError:
                pass
            
            try:
                winreg.DeleteValue(key_explorer_cu, "AltTabSettings")
                enabled_count += 1
            except FileNotFoundError:
                pass
            
            winreg.CloseKey(key_explorer_cu)
            
            # Re-enable Win+S (Search)
            try:
                search_key_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                             r"SOFTWARE\Policies\Microsoft\Windows\Windows Search")
                try:
                    winreg.DeleteValue(search_key_lm, "DisableWebSearch")
                    enabled_count += 1
                except FileNotFoundError:
                    pass
                
                try:
                    winreg.DeleteValue(search_key_lm, "AllowSearchToUseLocation")
                    enabled_count += 1
                except FileNotFoundError:
                    pass
                
                winreg.CloseKey(search_key_lm)
            except Exception as e:
                print(f"Warning: Could not re-enable web search: {e}")
            
            # Restore search box visibility
            search_key_cu = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                         r"Software\Microsoft\Windows\CurrentVersion\Search")
            winreg.SetValueEx(search_key_cu, "SearchboxTaskbarMode", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(search_key_cu, "BingSearchEnabled", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(search_key_cu)
            enabled_count += 2
            
            # Re-enable system functions
            try:
                system_key_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System")
                try:
                    winreg.DeleteValue(system_key_lm, "DisableLockWorkstation")
                    enabled_count += 1
                except FileNotFoundError:
                    pass
                
                winreg.CloseKey(system_key_lm)
            except Exception as e:
                print(f"Warning: Could not re-enable lock workstation: {e}")

            print(f"Windows hotkeys re-enabled ({enabled_count} registry entries restored)")

            # Lightweight registry refresh without blocking
            try:
                import subprocess
                subprocess.Popen(['gpupdate', '/force'],
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                print("Group policy restore initiated (non-blocking).")
            except Exception as e:
                print(f"Note: Could not initiate group policy update: {e}")
            
            return True
            
        except Exception as e:
            print(f"Failed to re-enable Windows hotkeys: {e}")
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
                
                # Protect secondary windows from Alt+F4 by requiring password
                def secondary_window_close_handler():
                    success = verify_password_dialog_macos(main_tk_window)
                    if success:
                        # If password is correct, trigger main window closure
                        main_tk_window.event_generate('<Escape>')
                    # If password fails, do nothing - keep window open
                
                black_screen_window.protocol("WM_DELETE_WINDOW", secondary_window_close_handler)
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
    hotkeys_disabled = False
    
    # Disable Task Manager and hotkeys at startup (requires admin privileges)
    if config.get("run_as_admin", False):
        print("Disabling system hotkeys...")
        task_manager_disabled = disable_ctrl_alt_del()
        hotkeys_disabled = disable_windows_hotkeys()
        print("Hotkey disabling completed.")
    
    root = tk.Tk()
    root_ref_for_hook = root # Store root for the callback
    root.attributes('-fullscreen', True) 
    
    TRANSPARENT_KEY_FOR_LOGIN_TOPLEVEL = '#123456' 
    root.attributes('-transparentcolor', TRANSPARENT_KEY_FOR_LOGIN_TOPLEVEL)
    root.configure(bg='black') 

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

            # Re-enable Task Manager and hotkeys if they were disabled
            if task_manager_disabled:
                enable_ctrl_alt_del()
            if hotkeys_disabled:
                enable_windows_hotkeys()

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

    # Block hotkeys at application level as additional protection
    def block_hotkey(event):
        return "break"  # Prevent the event from propagating
    
    # Bind hotkeys to password dialog - Using correct Tkinter syntax
    # Note: Tkinter has limited support for Windows key detection
    # These bindings may not work perfectly for all Windows key combinations
    try:
        root.bind("<Alt-Tab>", on_escape)
        root.bind("<Shift-Alt-Tab>", on_escape)  # Reverse Alt+Tab
    except tk.TclError:
        print("Warning: Could not bind Alt+Tab keys")
    
    # Try alternative approaches for Windows key combinations
    try:
        # These may not work on all systems due to Tkinter limitations
        root.bind("<Control-Escape>", on_escape)  # Sometimes captures Win key
        root.bind("<Alt-F4>", on_escape)  # Alt+F4
    except tk.TclError:
        print("Warning: Could not bind Windows key combinations")
    
    # Focus capture to intercept other key combinations
    def on_key_press(event):
        # Log key presses for debugging
        key_name = event.keysym
        key_code = event.keycode
        
        # Check for common escape sequences
        if key_name in ['r', 'R'] and (event.state & 0x40000):  # Win key modifier
            print("Win+R detected, showing password dialog")
            on_escape(event)
            return "break"
        elif key_name in ['x', 'X'] and (event.state & 0x40000):  # Win key modifier
            print("Win+X detected, showing password dialog") 
            on_escape(event)
            return "break"
        elif key_name in ['s', 'S'] and (event.state & 0x40000):  # Win key modifier
            print("Win+S detected, showing password dialog")
            on_escape(event)
            return "break"
        elif key_name == 'Tab' and (event.state & 0x40000):  # Win+Tab
            print("Win+Tab detected, showing password dialog")
            on_escape(event)
            return "break"
        elif key_name == 'Tab' and (event.state & 0x20000):  # Alt+Tab
            print("Alt+Tab detected, showing password dialog")
            on_escape(event)
            return "break"
        elif key_name == 'F4' and (event.state & 0x20000):  # Alt+F4
            print("Alt+F4 detected, showing password dialog")
            on_escape(event)
            return "break"
        
        return None
    
    # Bind key press event
    root.bind("<KeyPress>", on_key_press)

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
                    print(f"Error unhooking display event on close: {e_unhook}")
                hWinEventHook = None
            
            # Re-enable Task Manager and hotkeys if they were disabled
            # 'task_manager_disabled' and 'hotkeys_disabled' are from the outer scope
            if task_manager_disabled:
                enable_ctrl_alt_del()
            if hotkeys_disabled:
                enable_windows_hotkeys()
            
            root_ref_for_hook = None # Clear the global reference

            for sec_win in secondary_screen_windows:
                if sec_win.winfo_exists():
                    sec_win.destroy()
            secondary_screen_windows.clear() # Clear the list

            if root.winfo_exists():
                root.destroy()
        else:
            # Password verification failed or was cancelled, keep screensaver active
            print("Close attempt cancelled or password failed. Screensaver remains active.")
            try:
                if root and root.winfo_exists():
                    root.focus_set() # Ensure screensaver window regains focus
            except tk.TclError:
                # This might happen if the window is somehow already gone
                print("Root window was already destroyed during close attempt with failed password.")
            # Do not destroy the window or re-enable hotkeys if password fails

    root.protocol("WM_DELETE_WINDOW", on_closing_main_window)
    
    # Ensure Task Manager and hotkeys are always re-enabled even if the app crashes
    try:
        root.mainloop()
    finally:
        # Re-enable Task Manager and hotkeys in case of crash or exception
        if task_manager_disabled:
            enable_ctrl_alt_del()
        if hotkeys_disabled:
            enable_windows_hotkeys()

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
